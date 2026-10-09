# 使い方

## 目次
1. 作業の流れ
2. `export_igor` の引数
3. スタイル（`style=`）のキー
4. `.h5` の中身
5. Igor 側の手順
6. 数値データの渡し方の決まり（Igor で確認済み）

## 1. 作業の流れ

1. matplotlib で図を描く（Agg でよい）。
2. `import export_igorgraph`（または `from export_igorgraph import export_igor`）を、**`contour` / `contourf` を呼ぶより前に**行う。import すると、元の `(X, Y, Z)` を覚えておく小さな包みが入る（[等高線](#等高線)）。
3. `report = export_igor(fig, outdir, name)`。`name` は Igor のグラフ名・データフォルダ名・Wave 名の接頭辞（英字始まり、英数字と `_`、16 文字以内）。
4. `report.summary()` を読む。Igor で再現できないものは `report.warnings` に必ず出る（黙って落とさない）。
5. Igor で `LoadPythonFigure()` を実行して `.h5` を開く（[Igor 側](#5-igor-側の手順)）。

## 2. `export_igor` の引数

```python
export_igor(fig, outdir=".", name="fig1", *, ax=None, style=None, use_mpl_size=False, italic_math=True,
            ctab=None, write_ipf=False, text_mode="string", axis_range="mpl", contour_data=None)
```

| 引数 | 意味 |
|---|---|
| `ax` | 書き出す Axes（省略: カラーバー以外の最初の Axes） |
| `style` | 書式の上書き（下の表）。指定したものが常に優先 |
| `use_mpl_size` | `True`: ウィンドウ・余白・プロット領域・文字サイズを matplotlib の図から取る（Figure = ウィンドウ）。`False`（既定）: コンパクトな書式（プロット幅 8 cm・Arial 14 pt。画像は 12 pt）。軸ラベルが目盛りラベルと重なるときは、プロット領域の大きさを変えずに余白を広げ、警告する |
| `italic_math` | mathtext の変数（ASCII 英字）を斜体にする。添字・指数は立体 |
| `ctab` | `("Rainbow", 1)` のように Igor の色テーブル（名前・reverse）を使う。省略すると matplotlib の colormap を 256 色の Wave で再現 |
| `write_ipf` | 図ごとの `.ipf`（`Make_<name>()`）も出す。既定は `.h5` のみ |
| `text_mode` | `"string"`（固定長文字列。Igor 8.04 で読める）か `"codes"`（整数配列。代替） |
| `axis_range` | `"mpl"`（既定）: matplotlib の実際の軸範囲を `SetAxis` で固定。Igor の自動スケールは、データが枠に接して点やエラーバーが欠ける。`"auto"`: 手動設定した範囲だけ固定 |
| `contour_data` | 等高線の元データ。`(X, Y, Z)`（Z は `(ny, nx)`）、その並び（描いた順）、または `{ContourSet: (X, Y, Z)}`。省略すると、呼び出しの瞬間に保存したデータを使う |

戻り値 `ExportReport`: `.files`、`.warnings`、`.commands`（`.h5` に埋め込んだ命令）、`.n_traces`、`.n_images`、`.n_contours`、`.summary()`。

### 等高線

matplotlib の `ContourSet` は Z 行列を**保持しません**（できあがった折れ線だけ）。Igor で `ModifyContour` により編集できる**本物の等高線**にするには、元のデータが要ります。
そこで `export_igorgraph` は、import したときに公開 API の `Axes.contour` / `contourf` を包み、返ってくる `ContourSet` に `(X, Y, Z)` を保存します。
import の前に描いた等高線は、`contour_data=(X, Y, Z)` で明示的に渡してください。等高線には matplotlib 3.8 以上が必要です。

## 3. スタイル（`style=`）のキー

```python
export_igor(fig, outdir, "fig1", style={"tick": "mpl", "cs_box": False})
```

| キー | 既定 | 意味 |
|---|---|---|
| `tick` | `2` | `0` 外向き、`1` 交差、`2` 内向き、`3` なし、`"mpl"` = matplotlib の向きに合わせる。`mirror`・`standoff`（既定 1・0）も指定可 |
| `font`, `gfont` | `"Arial"`, `None` | `font`: 軸（目盛りラベル・軸ラベル）のフォント。`gfont`（Igor の `gFont`）: グラフ全体の既定フォント（凡例・注釈など）。`None` は `font` と同じ。許可リストにある名前のみ（`eig_allowlist.py` の `FONT_NAMES`: Arial, Helvetica, Times New Roman, Times, Courier New, Courier, Calibri, Verdana, Tahoma, Segoe UI, Georgia, Cambria, Meiryo, Yu Gothic, MS Gothic, MS PGothic）。`None` で指定なし |
| `margin_left/bottom/top/right`, `width_pt`, `aspect`, `gf_size` | 線: 43/37/14/14, 226.772, 0.8, 14　画像: 51/43/14/57, 227, 1, 12 | `use_mpl_size=False` のときの書式。余白は**最小値**で、軸ラベル・目盛りラベル・カラースケールの箱が入らなければ広がる |
| `grid`, `grid_rgb`, `grid_style` | `None`, `None`, `5` | グリッド。`None`: matplotlib に合わせる。`0` なし、`1` あり、`2` 主目盛りのみ。軸ごとに `{"bottom": 2, "left": 1}` も可。`grid_rgb`: matplotlib の色（既定は matplotlib のグリッドの色）。`grid_style`: Igor の `gridStyle`（5 = 実線） |
| `width`, `height` | なし | プロット領域の大きさ（pt。`width_pt`・`height_pt` の別名）。`use_mpl_size=True` のときは、指定したときだけ matplotlib の大きさを上書きする。`height` は `aspect` より優先 |
| `label_gap` | `0.3` | 目盛りラベルと軸ラベルの最小の隙間（文字サイズの倍率） |
| `lbl_margin_bottom`, `lbl_margin_left` | なし | 軸ラベルの位置（ウィンドウの縁から内側への距離 pt）。モデルより優先 |
| `sub_sup_extra` | `None` | 数値を指定すると、上付き・下付きのある x 軸ラベルのとき下余白にその量を足す（従来の動作）。`None` は計算 |
| `log_exp` | `True` | 対数軸の目盛りラベルを 10ⁿ の指数表記にする（`logLTrip`） |
| `free_size` | `True` | 最後の命令で `ModifyGraph width=0,height=0`（サイズ自動）にする。固定のままだと、Igor でウィンドウの大きさを変えられない。余白は固定のままなので、最初は同じ見た目で、あとはウィンドウの大きさに合わせてプロット領域が変わる。`False` で固定のまま |
| `cs_mode` | `"outside"` | カラースケール: `"outside"`（プロットの右。箱が入るよう余白を広げる）、`"mpl"`（matplotlib のカラーバーの位置・大きさ。`use_mpl_size=True` のとき自動）、`"preset"`（内側の注釈） |
| `cs_box` | `True` | カラースケールの枠（箱）。`False` で枠なし |
| `cs_width`, `cs_gap`, `cs_height_pct`, `cs_frame`, `cs_nticks`, `cs_log_trip` | 15, 8, 100, 0, なし, 0.1 | 棒の幅・プロットとの間隔・棒の高さ（プロットに対する %）・棒の枠線・目盛りの数・対数の指数表記のしきい値 |
| `cs_lbl_margin` | `None` | カラースケールのラベルの位置。**`None` のままにする**（Igor の既定は重ならない）。値を指定すると目盛りラベルと重なる |
| `win_left`, `win_top` | 40, 40 | ウィンドウの位置 |

### スタイルファイルと検査

既定を毎回書く代わりに、JSON ファイルに置けます: カレントフォルダの `export_igorgraph_style.json`、`~/.export_igorgraph_style.json`、環境変数 `EXPORT_IGORGRAPH_STYLE` のパス（または `export_igor(..., style_file="パス")`。`style_file=False` でファイルを使わない）。優先順位: 組み込みの既定 < スタイルファイル < `style=`。`_` で始まるキーは注釈として無視されます。`export_igorgraph_style.example.json` を参照。書き換えたら、`python -m export_igorgraph style-check ファイル.json`（または `export_igorgraph.check_style_file(パス)`）で検査できます。

別名（`width`・`height`・`gFont`・`gfSize`）を受け付けます。**未知のキーは警告して無視**し（「もしかして」つき）、**値が不正なら `ValueError`** にします（例: `tick=5`、許可リストにないフォント）。

## 4. `.h5` の中身

| 名前 | 中身 |
|---|---|
| `name_t{k}_x`, `_y` | トレース k の座標 |
| `name_t{k}_ex` / `_ey` | 対称な誤差。非対称なら `_exp/_exn/_eyp/_eyn`（正側/負側） |
| `name_i{k}_z`, `_xe`, `_ye`, `_ct` | 画像 k。z は形 `(nx, ny)`（Igor の dim0 = x）、`_xe/_ye` はピクセルの**端**の座標（n+1 点）、`_ct` は色テーブル（256×3、float64、0〜65535。Igor 側で `Redimension/U/W`） |
| `name_c{k}_z`, `_x`, `_y`, `_lv`, `_ct` | 等高線 k: 元の Z 行列、行・列の座標、レベル、色テーブル（colormap のとき） |
| `igor_cmds` | 描画命令（固定長文字列。許可リストに合う命令だけ） |
| `igor_waves`, `igor_meta` | 読み込む Wave の一覧、`format=1; name=…; generator=…; text=string\|codes` |

書き出しに `h5py` は不要です（`minimal_hdf5_writer.py` は numpy だけで動き、Igor が書いたファイルの構造に合わせてあります）。

## 5. Igor 側の手順

1. 初回だけ、ローダーを入れる。`python -m export_igorgraph loader <フォルダ>` で `ExportIgorGraphLoader.ipf` を書き出す（またはリポジトリの `igor/ExportIgorGraphLoader.ipf`）。`Documents\WaveMetrics\Igor Pro 8 User Files\Igor Procedures\` に置くと、起動時に自動で読み込まれる。
2. コマンドラインで `LoadPythonFigure()` → `.h5` を選ぶ。パス指定: `LoadPythonFigure_exec(h5Path="C:\\work\\fig1.h5")`（Igor の文字列では `\` を二重にする）。
3. 拒否された・失敗した命令は History に出る。`EIG_SelfTest()` で許可リストの自己検査（「ALL PASS」が出る）。

## 6. 数値データの渡し方の決まり（Igor で確認済み）

- numpy の軸 `i` = Igor の次元 `i`（転置不要）。`IGORWaveScaling` の `scaling[i] = (delta, offset)` が次元 `i` に効く。読み込みは `HDF5LoadData /IGOR=-1`。
- 画像・等高線は、Igor の dim0 = x（列）、dim1 = y（行）。matplotlib の `A[行, 列]` は**転置**して渡す。座標が減少していれば反転して増加にそろえる。
- `origin="upper"` の画像は y 軸が反転しているので、2 次元の図では**常に `SetAxis`** を出す（`left 2.5,-0.5` など）。
- float32 → WaveType 2、float64 → 4、int32 → 32。NaN は保たれる。
