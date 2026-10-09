"""
test_loader.py
==============

生成した ExportIgorGraphLoader.ipf が、Python 側の許可リスト（eig_allowlist.py）と同じ意味を持つことを確認する。
Igor は動かせないので、.ipf のテキストから正規表現と自己検査の見本を読み戻して、元の定義と照合する。

    1. 生成した .ipf の先頭にある「パターンの指紋」が、現在の eig_allowlist.py と一致する（古くなっていない）
    2. .ipf の EIG_Patterns() から読み戻した正規表現が、eig_allowlist.PATTERNS と一字一句同じ
    3. .ipf の EIG_SelfTest() から読み戻した見本が、元の見本と同じ文字列になる
    4. 読み戻した正規表現で、ローダーと同じ手順（長さ・制御文字・全文一致）の判定をして、
       正常な見本は全部通り、悪意のある見本は全部拒否される
    5. Execute は1か所だけ（EIG_RunCommand）で、その直前に必ず許可リストの検査がある
    6. .ipf が規約チェッカーを通る
    7. 実際に export_igor が出した命令（ギャラリー全図）が、全部許可リストを通る

実行: python test_loader.py
"""

import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from export_igorgraph import eig_allowlist as al
from export_igorgraph import make_loader

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


def unescape_igor_literal(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt in '\\"':
                out.append(nxt)
                i += 2
                continue
            if nxt == "u" and i + 5 < len(s) + 0 and re.fullmatch(r"[0-9A-Fa-f]{4}", s[i + 2 : i + 6]):
                out.append(chr(int(s[i + 2 : i + 6], 16)))
                i += 6
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


def split_top_level_plus(expr: str):
    """Igor の式 `"abc" + num2char(10) + "def"` を、引用符の外の ' + ' で分割する。"""
    parts, cur, in_s, i = [], "", False, 0
    while i < len(expr):
        ch = expr[i]
        if in_s:
            cur += ch
            if ch == "\\" and i + 1 < len(expr):
                cur += expr[i + 1]
                i += 2
                continue
            if ch == '"':
                in_s = False
        else:
            if ch == '"':
                in_s = True
                cur += ch
            elif expr.startswith(" + ", i):
                parts.append(cur)
                cur = ""
                i += 3
                continue
            else:
                cur += ch
        i += 1
    parts.append(cur)
    return parts


def eval_igor_expr(expr: str) -> str:
    out = ""
    for p in split_top_level_plus(expr.strip()):
        p = p.strip()
        m = re.fullmatch(r'num2char\((\d+)\)', p)
        if m:
            out += chr(int(m.group(1)))
        elif p.startswith('"') and p.endswith('"'):
            out += unescape_igor_literal(p[1:-1])
        else:
            raise ValueError(f"解釈できない式: {p[:60]}")
    return out


def parse_patterns(text: str):
    body = text.split("Function/WAVE EIG_Patterns()")[1].split("\nEnd")[0]
    pats, cur = {}, ""
    for line in body.split("\n"):
        line = line.strip()
        m = re.match(r'^s (=|\+=) "(.*)"$', line)
        if m:
            cur = m.group(2) if m.group(1) == "=" else cur + m.group(2)
            continue
        m = re.match(r"^pats\[(\d+)\] = s$", line)
        if m:
            pats[int(m.group(1))] = unescape_igor_literal(cur)
    return [pats[k] for k in sorted(pats)]


def parse_vectors(text: str, name: str):
    out = {}
    for m in re.finditer(rf"^\t{name}\[(\d+)\] = (.*)$", text, re.M):
        out[int(m.group(1))] = eval_igor_expr(m.group(2))
    return [out[k] for k in sorted(out)]


def simulate_loader_check(cmd: str, patterns) -> bool:
    """ローダーの EIG_IsAllowed と同じ手順を、読み戻した正規表現で行う。"""
    if len(cmd) == 0 or len(cmd) > al.MAX_COMMAND_BYTES:
        return False
    if re.search(r"[^ -~]", cmd):
        return False
    return any(re.search(p, cmd) for p in patterns)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        path = make_loader.main(tmp)
        check("ローダーが指定したディレクトリの中に書き出される",
              os.path.dirname(os.path.abspath(path)) == os.path.abspath(tmp), path)
        text = open(path, encoding="ascii", newline="").read()
        lf = text.replace("\r\n", "\n")

        fp = make_loader.patterns_fingerprint()
        check("指紋が現在の eig_allowlist.py と一致", f"pattern fingerprint {fp}" in lf)

        parsed = parse_patterns(lf)
        check("EIG_Patterns() の数が PATTERNS と同じ", len(parsed) == len(al.PATTERNS), f"{len(parsed)} vs {len(al.PATTERNS)}")
        same = [i for i, (a, (_, b)) in enumerate(zip(parsed, al.PATTERNS)) if a != b]
        check("読み戻した正規表現が元の定義と一字一句同じ", not same, f"違う番号: {same}")

        good = parse_vectors(lf, "good")
        bad = parse_vectors(lf, "bad")
        exp_bad = [s for s in al.BAD_SAMPLES if len(s) <= make_loader.SELFTEST_LONG_LIMIT]
        check("自己検査の正常な見本が元と同じ文字列", good == al.GOOD_SAMPLES)
        check("自己検査の悪意のある見本が元と同じ文字列（制御文字・非ASCIIを含む）", bad == exp_bad)

        ng = [s for s in good if not simulate_loader_check(s, parsed)]
        ok_bad = [s for s in bad if simulate_loader_check(s, parsed)]
        check("読み戻した正規表現で、正常な見本がすべて通る", not ng, str(ng[:2]))
        check("読み戻した正規表現で、悪意のある見本がすべて拒否される", not ok_bad, str(ok_bad[:2]))
        long_cmd = 'Label/W=fig1 bottom "' + "a" * 3000 + '"'
        check("3000バイトの命令は拒否される", not simulate_loader_check(long_cmd, parsed))

        code_lines = [l for l in lf.split("\n") if not l.strip().startswith("//")]
        exe = [i for i, l in enumerate(code_lines) if re.search(r"\bExecute\b", re.sub(r'"(?:[^"\\]|\\.)*"', '""', l.split("//")[0]))]
        check("Execute を使う行は1つだけ", len(exe) == 1, str(exe))
        if len(exe) == 1:
            i = exe[0]
            ctx = "\n".join(code_lines[max(0, i - 8) : i])
            check("Execute の直前に EIG_IsAllowed の検査がある", "EIG_IsAllowed(cmd)" in ctx and "return -999" in ctx)
        main_part = lf.split("Function LoadPythonFigure_exec")[1].split("Function EIG_RunCommand")[0]
        check("LoadPythonFigure は、読み込み・実行の前に全命令を検査する",
              main_part.index("EIG_IsAllowed(c)") < main_part.index("HDF5LoadData/O/Z/Q/IGOR=-1")
              < main_part.index("EIG_RunCommand(c)"))
        check("拒否があれば、読み込みも実行もせず戻る",
              re.search(r"if \(nBad > 0\)[\s\S]*?return -1[\s\S]*?endif", main_part) is not None)

        chk = os.path.join(os.path.dirname(os.path.abspath(__file__)), "check_igor_style.py")
        cmd = [sys.executable, chk] if os.path.exists(chk) else [sys.executable, "-m", "export_igorgraph.check_igor_style"]
        r = subprocess.run(cmd + [path, "--strict"], capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "PYTHONIOENCODING": "utf-8"})
        check("ローダーが規約チェッカーを通る (--strict)", r.returncode == 0, r.stdout.strip().splitlines()[-1])
        check("ローダーは ASCII のみ・CRLF のみ", not re.search(rb"[\x80-\xff]", text.encode("latin-1", "replace"))
              and "\n" not in text.replace("\r\n", ""))

    # 実際の export_igor の出力が、全部許可リストを通る（ギャラリー全図）
    try:
        import gallery
        import matplotlib
        matplotlib.use("Agg")
        bad_cmds = []
        total = 0
        with tempfile.TemporaryDirectory() as tmp:
            for name, rep in gallery.build_all(tmp, png=False):
                for cmd in rep.commands:
                    total += 1
                    if not al.is_allowed(cmd):
                        bad_cmds.append((name, cmd[:100]))
        check(f"ギャラリー全図の命令 {total} 個がすべて許可リストを通る", not bad_cmds, str(bad_cmds[:2]))
    except ImportError:
        print("SKIP ギャラリーの命令の検査（gallery.py なし）")

    bad = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
