# 開発

## セットアップ

```
git clone https://github.com/nlyamada/export-igorgraph
cd export-igorgraph
python -m venv .venv && .venv\Scripts\activate        # または source .venv/bin/activate
pip install -e ".[test]"
python -X utf8 tests/run_all.py
```

日本語の Windows では `python -X utf8` を使います（`Å` などの出力が cp932 で失敗するため）。

## 構成

```
src/export_igorgraph/    ライブラリ（mpl_to_igor.py: Figure → .h5、eig_allowlist.py: 許可リスト、make_loader.py、
                         minimal_hdf5_writer.py、check_igor_style.py）
igor/                    ExportIgorGraphLoader.ipf（生成物。手で編集しない）と EIG_Gallery.ipf（確認用）
tests/                   テスト（run_all.py が全部流す）
tools/                   ギャラリー、較正、Igor の自動実行、matplotlib のバージョン検査
plugin/                  Claude Code プラグイン（export_igor を使うスキル）
docs/                    ドキュメント
```

## Igor との往復（Igor の見た目に関わる変更）

1. Python のテストで機械的な誤りを潰す。
2. 一式を作る: `python tools/make_kit.py <出力先>`（`tools/run_igor_round.py` が自動で行う）。
3. Igor で実行する。Windows なら自動（`tools/run_igor_round.py`。[igor-automation.md](igor-automation.md)）、手動なら `EIG_SelfTest()` のあと `RunGallery()`。
4. `tools/audit.py`（送った値と読み戻しの照合）と、**画像の目視**（`tools/contact_sheet.py`、`tools/pairs.py`）で解析する。
5. 直して繰り返す。止まる条件を先に決める（例: 3 往復）。
6. 新しい事実を [verified.md](verified.md) に記録する。

## テスト

```
python -X utf8 tests/run_all.py                 # 以下を全部
python -X utf8 tests/test_mpl_to_igor.py <dir>  # 変換本体（引数は出力ディレクトリ）
python -X utf8 tests/test_layout.py             # ウィンドウ・フォント・ラベルの配置・マーカー・破線・グリッド・カラースケール
python -X utf8 tests/test_contour.py            # 等高線: 元の Z の取得と命令
python -X utf8 tests/test_loader.py             # ローダーが許可リストと同じ意味か。ギャラリー全命令が通るか
python -X utf8 tests/test_audit.py              # 照合ツール
python -X utf8 tests/test_check_igor_style.py   # Igor コードの規約チェッカー
python -X utf8 tests/test_minimal_hdf5_writer.py [Igor が書いた .h5]
python -X utf8 tools/check_mpl_versions.py <作業フォルダ> 3.8.4 3.9.4 3.10.7 --python <python.exe>   # 使い捨ての venv で複数の matplotlib を検査
```

## 機能を足す

### Igor の新しい命令
1. 公式ドキュメントで構文を確認する（`https://docs.wavemetrics.com/llms.txt` が索引。ページの URL の末尾に `.md`）。確認できなければ「未確認」と書き、小さな較正図（`tools/calib.py`）で Igor に試す。
2. `eig_allowlist.py` に**厳密な**パターンを足し、`GOOD_SAMPLES` と `BAD_SAMPLES` に見本を足す。
3. ローダーを再生成する: `python -m export_igorgraph loader igor/`。
4. `test_loader.py` を通す。

### matplotlib の新しい要素
1. `mpl_to_igor.py` の `_collect`（読み取り）と `export_igor`（命令の生成）に足す。
2. テストを足す。`tools/gallery.py` に図を足す。
3. Igor で見比べる。

### 寸法・位置の較正
`tools/calib.py <種類> <出力>` が、1 つの値を振った図を作る（`lblpos`・`trip`・`ls`・`eb`・`ct` など）。`tools/run_igor_round.py --only <dir>` で描き、PNG を測る（`calib_analyze.py`、または小さなスクリプト。画素/pt = PNG の幅 ÷ ウィンドウ幅 pt）。数値を `mpl_to_igor.py` の較正定数と [verified.md](verified.md) に反映する。

## 依存ライブラリ

- 必須: `numpy`、`matplotlib`（等高線は 3.8 以上）。任意: `h5py`（テスト）、`pillow`（比較シート）、`pywin32`（Igor の自動実行）。
- matplotlib 3.6.3〜3.10.7 で、変換本体とレイアウトのテストが通る。**バージョン番号ではなく機能の有無（`hasattr`）で切り替える**（例: `Axis.get_tick_params` は 3.7 以降）。
- matplotlib の非公開 API（`_` で始まるもの）は避ける。等高線の元データは、公開 API の `Axes.contour` / `contourf` を包んで取る。
