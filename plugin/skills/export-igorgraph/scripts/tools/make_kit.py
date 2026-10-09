#!/usr/bin/env python3
"""make_kit.py: Igor で試す一式 (eig_kit/) を作って zip にする。  python make_kit.py <出力ディレクトリ>"""
import os
import shutil
import sys
import zipfile

import gallery
from export_igorgraph import make_loader
import make_probe

HERE = os.path.dirname(os.path.abspath(__file__))
PY_FILES = ["mpl_to_igor.py", "minimal_hdf5_writer.py", "eig_allowlist.py", "make_loader.py", "make_probe.py",
            "gallery.py", "charts.py", "audit.py", "contact_sheet.py", "check_igor_style.py", "make_kit.py",
            "run_igor_round.py", "calib.py", "calib_analyze.py",
            "test_loader.py", "test_audit.py", "test_mpl_to_igor.py", "test_layout.py",
            "test_minimal_hdf5_writer.py", "test_check_igor_style.py"]

README = """\
EIG kit (第2回): Igor での確認用の一式
=====================================

今回の目的
  1. フォントとウィンドウの大きさを固定した状態で、matplotlib と Igor の見た目を比べる。
     （g 系列は、matplotlib の大きさ・文字サイズ・Figure = ウィンドウで描く。ウィンドウの大きさは数値で読み戻す）
  2. 前回見つかった差の修正（軸範囲の固定、カラースケールの配置、上付き・下付きラベル、グリッド、凡例の記号）の確認。
  3. Igor のマーカー番号（0〜62）と線種の番号（0〜17）を、実際に描いて確かめる（c 系列）。

フォルダ
  igor/      Igor に読み込む2つのファイル
  gallery/   42 個の .h5 と、基準になる matplotlib の画像（mpl/）、期待値（expected.json）
  python/    ソースとテスト（確認には不要。中身を見たいとき用）

図の系列
  g01〜g25   全機能。matplotlib の大きさ・文字サイズで描く（図は constrained レイアウト）
  p01〜p04   preset の書式の見本
  v01〜v04   軸ラベルの配置（内向きの目盛り・対数軸の指数表記・上付き）
  v05〜v09   カラースケールの配置（preset／箱つき外側／mpl／枠なし／高さ 90%）
  v10〜v11   目盛りの向き（tick="mpl" で内向き／外向き）
  c01〜c05   マーカー番号・線種番号の見本（matplotlib の画像は無い）

手順
  0. igor/ の2つの .ipf を Igor で開く（File > Open File > Procedure... で選ぶか、プロシージャウィンドウに貼る）。
     前回のファイルが開いたままなら、閉じるか、Igor を再起動してから開く。
        ExportIgorGraphLoader.ipf   固定のローダー（許可リストが拡張されているので、新しいものに入れ替える）
        EIG_Gallery.ipf             ギャラリーの実行と読み戻し
     コンパイルエラーが出たら、そのメッセージを教えてください。
  1. コマンドラインで   EIG_SelfTest()   を実行。「ALL PASS」が出れば OK。
  2. コマンドラインで   RunGallery()   を実行 → gallery/ フォルダを選ぶ（zip を新しく展開したフォルダで）。
        42 枚のグラフが順に作られ、gallery/ に igor_audit.txt と <名前>_igor.png ができる。
        図によっては失敗するかもしれない（例: 線種やマーカーの番号が範囲外）。失敗した図は History に出て、次へ進む。
  3. 送っていただくもの:
        - 手順 1・2 の History の出力（テキスト）
        - gallery/ フォルダを zip にしたもの（igor_audit.txt と *_igor.png が入っている）

使い方（確認が済んだあと）: ExportIgorGraphLoader.ipf を1回入れておけば、あとは
        LoadPythonFigure()    → ファイル選択ダイアログで、export_igor が書いた .h5 を選ぶだけ。

注意
  - h5 の中の命令は、許可リストに一致したものだけが実行される（それ以外は実行されず、History に出る）。
  - ExportIgorGraphLoader.ipf は、python/make_loader.py が生成したもの。手で編集しない。
"""


def main(argv=None):
    out = (argv or sys.argv[1:] or ["."])[0]
    kit = os.path.join(out, "eig_kit")
    shutil.rmtree(kit, ignore_errors=True)
    for d in ("igor", "gallery", "python"):
        os.makedirs(os.path.join(kit, d))
    make_loader.main(os.path.join(kit, "igor"))
    shutil.copy(os.path.join(HERE, "EIG_Gallery.ipf"), os.path.join(kit, "igor", "EIG_Gallery.ipf"))
    # CRLF にそろえる（Windows の Igor 向け）
    p = os.path.join(kit, "igor", "EIG_Gallery.ipf")
    t = open(p, "rb").read().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    open(p, "wb").write(t)
    gallery.main([os.path.join(kit, "gallery")])
    for f in PY_FILES:  # 公開版のツリーでは、ライブラリはパッケージ側にあるので、無いものは飛ばす
        if os.path.exists(os.path.join(HERE, f)):
            shutil.copy(os.path.join(HERE, f), os.path.join(kit, "python", f))
    if os.path.isdir(os.path.join(HERE, "fixtures")):
        shutil.copytree(os.path.join(HERE, "fixtures"), os.path.join(kit, "python", "fixtures"))
    with open(os.path.join(kit, "README_RUN.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(README)
    zpath = os.path.join(out, "eig_kit.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _, fs in os.walk(kit):
            for fn in sorted(fs):
                full = os.path.join(dp, fn)
                z.write(full, os.path.relpath(full, out))
    print(f"-> {zpath}")
    return zpath


if __name__ == "__main__":
    main()
