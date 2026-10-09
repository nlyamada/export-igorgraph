#!/usr/bin/env python3
"""run_igor_round.py: ギャラリーを作り、Igor Pro 8 で自動実行し、結果を照合する（Windows・ActiveX）。

    python -X utf8 run_igor_round.py <作業フォルダ> [--igor <Igor64.exe>] [--keep-igor]

手順:
  1. make_kit で <作業フォルダ>/eig_kit/（igor/・gallery/）を作る（自分で生成した h5 だけを使う）
  2. igor/ の2つの .ipf を Igor 8 の Igor Procedures フォルダに置く（起動時に自動で読み込まれる）
  3. Igor 8 を起動し、ActiveX（GetObject。新しいインスタンスは作らない）で接続する
     注意: 登録された COM サーバーが別の版（Igor 10 など）のことがあるので、CreateObject は使わない
  4. Execute2 で EIG_RunGalleryAt("<gallery>") を実行。History を igor_history.txt に保存
  5. audit.py・contact_sheet.py を実行
  6. 自分で起動した Igor を終了する（--keep-igor で残す）
"""
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
IGOR8 = r"C:\Program Files\WaveMetrics\Igor Pro 8 Folder\IgorBinaries_x64\Igor64.exe"
IGOR_PROCS = os.path.join(os.path.expanduser("~"), "Documents", "WaveMetrics", "Igor Pro 8 User Files",
                          "Igor Procedures")
IPF_FILES = ("ExportIgorGraphLoader.ipf", "EIG_Gallery.ipf")
SAFE_PATH = re.compile(r"^[A-Za-z]:[\\A-Za-z0-9_. \-]*$")


def igor_path_literal(folder):
    """Windows のフルパスを Igor の文字列リテラル（コロン区切り）にする。使える文字は限定する。"""
    folder = os.path.abspath(folder)
    if not SAFE_PATH.match(folder):
        raise ValueError(f"使えない文字を含むパス: {folder!r}")
    drive, rest = folder[:2], folder[2:].strip("\\")
    return '"' + drive + rest.replace("\\", ":") + '"'


def igor_running():
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                         errors="replace").stdout
    return [line for line in out.splitlines() if line.lower().startswith(('"igor64.exe"', '"igor.exe"'))]


def connect(timeout):
    import pythoncom
    import win32com.client
    t0 = time.time()
    while True:
        try:
            obj = win32com.client.GetObject(Class="IgorPro.Application")
            return win32com.client.gencache.EnsureDispatch(obj)
        except pythoncom.com_error:
            if time.time() - t0 > timeout:
                raise
            time.sleep(2)


def execute2(app, cmd):
    """Execute2(flags, codePage, cmds) -> (errorCode, errorMsg, history, results)"""
    r = app.Execute2(0, 0, cmd)
    # pywin32 は [out] 引数をタプルで返す
    return tuple(r[-4:]) if isinstance(r, tuple) else (0, "", str(r), "")


def install_procs(igor_dir):
    os.makedirs(IGOR_PROCS, exist_ok=True)
    for f in IPF_FILES:
        shutil.copy(os.path.join(igor_dir, f), os.path.join(IGOR_PROCS, f))
        print(f"配置: {os.path.join(IGOR_PROCS, f)}")


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv:
        print(__doc__)
        return 2
    work = os.path.abspath(argv[0])
    igor = argv[argv.index("--igor") + 1] if "--igor" in argv else IGOR8
    keep = "--keep-igor" in argv

    if igor_running():
        print("Igor が既に起動しています。ユーザーの作業を壊さないよう、ここで止めます:", igor_running())
        return 3

    os.makedirs(work, exist_ok=True)
    if "--only" in argv:  # 既にある h5 のフォルダ（自分で生成したもの）だけを回す。ローダーは最新の許可リストで作り直す
        gal = os.path.abspath(argv[argv.index("--only") + 1])
        igor_dir = os.path.join(work, "igor")
        from export_igorgraph import make_loader
        os.makedirs(igor_dir, exist_ok=True)
        make_loader.main(igor_dir)
        t = open(os.path.join(HERE, "EIG_Gallery.ipf"), "rb").read().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        open(os.path.join(igor_dir, "EIG_Gallery.ipf"), "wb").write(t)
        install_procs(igor_dir)
    else:
        import make_kit
        make_kit.main([work])
        kit = os.path.join(work, "eig_kit")
        gal = os.path.join(kit, "gallery")
        install_procs(os.path.join(kit, "igor"))
    lit = igor_path_literal(gal)

    print(f"Igor を起動: {igor}")
    proc = subprocess.Popen([igor])
    app = None
    try:
        app = connect(timeout=180)
        err, msg, hist, res = execute2(app, 'fprintf 0, "%g", IgorVersion()')
        print(f"接続: IgorVersion={res!r} err={err}")
        if not str(res).startswith("8."):
            print("Igor 8 ではないので止めます。")
            return 4
        t0 = time.time()
        err, msg, hist, res = execute2(app, f"EIG_RunGalleryAt({lit})")
        print(f"EIG_RunGalleryAt: err={err} msg={msg!r} ({time.time() - t0:.0f} s)")
        with open(os.path.join(gal, "igor_history.txt"), "w", encoding="utf-8") as f:
            f.write(str(hist).replace("\r", "\n"))
        done = os.path.join(gal, "EIG_done.txt")
        print("完了の印:", open(done).read().strip() if os.path.exists(done) else "無し")
    finally:
        if app is not None and not keep:
            try:
                app.Quit()
            except Exception as e:  # Quit の途中で接続が切れることがある
                print("Quit:", e)
        if not keep:
            try:
                proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                print("Igor が終了しません。確認してください。")

    py = [sys.executable, "-X", "utf8"]
    if os.path.exists(os.path.join(gal, "igor_audit.txt")) and os.path.exists(os.path.join(gal, "expected.json")):
        subprocess.run(py + [os.path.join(HERE, "audit.py"), gal])
        subprocess.run(py + [os.path.join(HERE, "contact_sheet.py"), gal, os.path.join(work, "sheets")])
    return 0


if __name__ == "__main__":
    sys.exit(main())
