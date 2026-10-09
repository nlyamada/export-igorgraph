"""
check_mpl_versions.py
=====================

matplotlib の複数のバージョンを、使い捨ての仮想環境（venv）に入れて、mpl_contour_probe.py を流し、結果を表にする。
依存ライブラリのバージョン差で壊れないかを、手元で確かめる普通のやり方（CI では、同じことを matrix で自動化する）。

    python check_mpl_versions.py <作業フォルダ> [<matplotlib のバージョン> ...] [--python <python.exe>]

 - 作業フォルダには、バージョンごとの venv（venv_<ver>）を作る。pip でインターネットから matplotlib を取得する。
 - 仮想環境は互いに独立で、元の環境には影響しない。消したいときはフォルダごと削除すればよい。
 - 既定のバージョン: 3.6.3, 3.7.5, 3.8.4, 3.9.4, 3.10.7（それぞれ Python 3.11 の wheel がある版）
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_VERSIONS = ["3.6.3", "3.7.5", "3.8.4", "3.9.4", "3.10.7"]


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    py = sys.executable
    if "--python" in argv:
        i = argv.index("--python")
        py = argv[i + 1]
        del argv[i:i + 2]
    if not argv:
        print(__doc__)
        return 2
    work = os.path.abspath(argv[0])
    versions = argv[1:] or DEFAULT_VERSIONS
    os.makedirs(work, exist_ok=True)
    results = {}
    for v in versions:
        env_dir = os.path.join(work, f"venv_{v}")
        if not os.path.exists(env_dir):
            r = run([py, "-m", "venv", env_dir])
            if r.returncode:
                results[v] = {"error": "venv: " + r.stderr[-300:]}
                continue
        vpy = os.path.join(env_dir, "Scripts", "python.exe")
        if run([vpy, "-c", f"import matplotlib; assert matplotlib.__version__ == '{v}'"]).returncode:
            # numpy 2 に未対応の古い matplotlib は numpy<2 を指定する（pip が自動では選ばない）
            pin = ["numpy<2"] if tuple(int(x) for x in v.split(".")[:2]) < (3, 9) else []
            print(f"[{v}] pip install ...", flush=True)
            r = run([vpy, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--only-binary", ":all:",
                     f"matplotlib=={v}"] + pin)
            if r.returncode:
                results[v] = {"error": "pip: " + (r.stderr or r.stdout)[-400:]}
                continue
        # -I: 利用者のサイトや PYTHONPATH を見ない。スクリプトは別のフォルダ（このリポジトリの src）にある
        r = run([vpy, "-I", os.path.join(HERE, "mpl_contour_probe.py")], cwd=work)
        line = next((ln for ln in r.stdout.splitlines() if ln.startswith("EIG_PROBE_JSON ")), None)
        results[v] = json.loads(line[len("EIG_PROBE_JSON "):]) if line else {"error": "probe: " + (r.stderr or r.stdout)[-400:]}
    with open(os.path.join(work, "mpl_versions.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    # --- 表 ---
    def yn(x):
        return {True: "OK", False: "NG"}.get(x, str(x))

    print("\nversion | python numpy | _contour_args | ContourSet=Collection | 内部フック(全部一致) | 公開フック(全部一致)")
    for v, r in results.items():
        if "error" in r:
            print(f"{v:8s}| ERROR {r['error'][:200]}")
            continue
        ph = r["private_hook"]
        bh = r["public_hook"]
        print(f"{v:8s}| {r['python']} {r['numpy']} | {r['private__contour_args']} | {yn(r['ContourSet_is_Collection'])} | "
              f"{yn(all(x is True for x in ph.values()))} | {yn(all(x is True for x in bh.values()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
