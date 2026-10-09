# Igor を自動で動かす（Windows）

`tools/run_igor_round.py` は、Igor Pro 8 を起動し、フォルダ内の図をローダーで描き、History・全グラフの読み戻し（`igor_audit.txt`）・全グラフの PNG を集めます。Igor の ActiveX オートメーション・サーバー（`Execute2`）を使います。

> `Igor Procedures` フォルダに 2 つの `.ipf` を置き、Igor を起動・終了します。開くのは、このツールが自分で生成した `.h5` だけです。Igor が既に起動していたら止まるので、作業を壊しません。

## 使い方

（Claude のスキルの中では、ツールは `scripts/tools/` にあります。パッケージを pip でインストールしていなければ、`PYTHONPATH=<スキル>/scripts` を付けて実行します。）

```
pip install pywin32 pillow
python -X utf8 tools/run_igor_round.py <作業フォルダ>                         # ギャラリー全体
python -X utf8 tools/run_igor_round.py <作業フォルダ> --only <h5 のフォルダ>    # 自分で生成した .h5 だけ
```

1. `eig_kit/`（ローダー + ギャラリー）を作る。`--only` なら、ローダーだけを許可リストから作り直す。
2. `ExportIgorGraphLoader.ipf` と `EIG_Gallery.ipf` を、`Documents\WaveMetrics\Igor Pro 8 User Files\Igor Procedures\` に置く（Igor の起動時に読み込まれる）。
3. `Igor64.exe`（Igor 8）を起動し、`GetObject`（**`CreateObject` ではない**）で接続して、`IgorVersion` が 8 であることを確認する。
4. `Execute2` で `EIG_RunGalleryAt("<フォルダ>")` を実行。出力: `igor_history.txt`、`EIG_done.txt`、`igor_audit.txt`、`<name>_igor.png`。
5. `audit.py`（→ `audit_report.md`）と `contact_sheet.py` を実行する。
6. 自分で起動した Igor を終了する（`--keep-igor` で残す）。

## 踏んだ落とし穴

- **登録された COM サーバーが Igor 10 のことがある**。両方入っていると、レジストリの `IgorPro.Application` は Igor 10 を指し、`CreateObject` は Igor 10 を起動する。Igor 8 をパスで自分で起動し、`GetObject(Class="IgorPro.Application")` で接続する。
- `Execute2` は、エラーコード・エラーメッセージ・History を返す。パスは Igor の文字列リテラル。コロン区切り（`"C:folder:sub"`）なら、バックスラッシュを二重にしなくてよい。
- **コンパイルエラーはダイアログで止まる**。タイムアウトしたら、スクリーンショットで確認する。
- 日本語の Windows では、Python に `-X utf8` を付ける。
- PNG は `SavePICT/O/Z/P=…/E=-5/B=144/WIN=<name>`。画素/pt は画面の倍率に依存するので、`GetWindow wsize` のウィンドウ幅で割って求める。
- `AnnotationInfo` は `RECT:l,t,r,b`（pt）を返す。凡例やカラースケールの実寸で、レイアウトの較正に使える。

## 自動実行しないとき

`igor/` の 2 つの `.ipf` を Igor に入れ、`EIG_SelfTest()`（「ALL PASS」が出る）→ `RunGallery()` でギャラリーのフォルダを選ぶ。History の出力と、フォルダ（`igor_audit.txt` と `*_igor.png` 入り）を送ってもらう。
