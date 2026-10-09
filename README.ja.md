# export-igorgraph

**matplotlib の図を、Igor Pro のグラフにする。見た目はそのまま、Igor で編集もできる。**

`export_igor(fig, outdir, name)` が、実データと Igor の描画命令を 1 つの HDF5（`name.h5`）に書きます。
Igor では `LoadPythonFigure()` で読むだけ。図ごとの procedure ファイルは要りません。

[English README](README.md)

![matplotlib（左）と Igor Pro 8（右）](docs/images/overview_lines.png)

## なぜ作ったか

解析や下書きは Python、仕上げ（と共同研究者の慣れ）は Igor、ということは多いはずです。手で描き直すと、手間もばらつきも出ます。
このツールは、matplotlib の図（データ・軸・対数軸・マーカー・破線・キャップつきエラーバー・凡例・ラベル・画像・カラースケール・**等高線**）を、
Igor で**そのまま編集できるネイティブなグラフ**として再現します。

- **Igor のネイティブな部品**: トレース、画像、`ColorScale`、元の Z 行列から作る Igor の等高線（`AppendMatrixContour` / `ModifyContour`）。
- **「だいたい」ではなく、測って合わせた**: 寸法、破線のパターン、マーカーの外形、キャップ、ラベルの位置は、Igor 上で測って較正しています。
- **黙って落とさない**: Igor で再現できないものは `report.warnings` に必ず出ます。
- **開いても安全**: ローダーは、厳密な許可リストに合う命令だけを実行し、1 つでも外れたらファイル全体を拒否します。
- Igor に追加の XOP は不要。Python を Igor から呼ぶ必要もありません（`.h5` を作るときだけ Python）。

## 最初に: Igor にローダーを入れる（1 回だけ）

Igor でグラフを読むには、固定のローダー `ExportIgorGraphLoader.ipf` を Igor に入れます（このリポジトリの `igor/` にあります。`python -m export_igorgraph loader <フォルダ>` でも書き出せます）。

1. `ExportIgorGraphLoader.ipf` を、次のフォルダにコピーします（Windows）。
   `Documents\WaveMetrics\Igor Pro 8 User Files\Igor Procedures\`
   - **ここに置くと、Igor の起動時に自動で読み込まれます**（動作確認はこの方法です）。
   - 自動で読み込ませたくないときは、`...\Igor Pro 8 User Files\User Procedures\` に置き、使うときに Igor で読み込みます（`File > Open File > Procedure…`、またはプロシージャウィンドウに `#include "ExportIgorGraphLoader"`）。この方法は、このプロジェクトでは未確認です。
2. Igor を再起動します（すでに起動中なら、Igor Procedures に置いたあと再起動が必要です）。
3. **Macros メニューに `LoadPythonFigure` が出る**ことを確認します。出ない場合は、プロシージャウィンドウのコンパイルエラーを確認してください。
4. 図を読むときは、メニューの `Macros > LoadPythonFigure`、またはコマンドラインで `LoadPythonFigure()` を実行し、`.h5` を選びます。

（`LoadPythonFigure` は、関数 `LoadPythonFigure_exec()` を呼ぶだけのマクロです。パスを指定したいときは `LoadPythonFigure_exec(h5Path="C:\\folder\\fig1.h5")` のように関数を直接呼べます。）

## クイックスタート

```
pip install git+https://github.com/nlyamada/export-igorgraph      # clone したなら pip install .
```

```python
import export_igorgraph                                 # contour() より前に import（下の「等高線」）
from export_igorgraph import export_igor
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(4, 3))
ax.errorbar(q, R, yerr=dR, fmt="o", color="k", ms=4, capsize=2, label="data")
ax.plot(q, R_fit, "-", color="tab:red", lw=1.5, label="fit")
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel(r"$Q$ [nm$^{-1}$]"); ax.set_ylabel("Reflectivity")
ax.legend(loc="upper right", frameon=False)

report = export_igor(fig, "out", "fig1")                # → out/fig1.h5
print(report.summary())                                 # Igor で再現できないものの警告
```

Igor で `LoadPythonFigure()` を実行し、`fig1.h5` を選びます。

### 書式: 自分の既定

主な設定は `style=` で指定します — `tick`・`mirror`・`standoff`・`grid`・`width`・`height`・`font`・`gFont`:

```python
export_igor(fig, "out", "fig1", style={"tick": 0, "grid": 1, "width": 300, "height": 200})
```

いつも使う設定は、JSON ファイル（カレントの `export_igorgraph_style.json`、または `~/.export_igorgraph_style.json`。`export_igorgraph_style.example.json` を参照）に置けます。未知のキーは警告、不正な値はエラーになります。全キー: [docs/ja/usage.md](docs/ja/usage.md)。

### 画像に等高線を重ねる（2 次元データへのフィット結果など）

```python
ax.imshow(data, extent=(x0, x1, y0, y1), origin="lower", cmap="gray", aspect="auto")
ax.contour(X, Y, fit, levels=levels, colors="tab:red", linewidths=1.2)
export_igor(fig, "out", "fig_fit")      # Igor の等高線になる。レベル・色は、あとから ModifyContour で変えられる
```

matplotlib の等高線は Z 行列を保持しません。`import export_igorgraph` すると、公開 API の `Axes.contour` / `contourf` を包んで、呼び出しの瞬間に `(X, Y, Z)` を保存します。
import の前に描いた等高線は `export_igor(..., contour_data=(X, Y, Z))` で渡してください。matplotlib 3.8 以上が必要です。

![画像・等高線・マーカー](docs/images/overview_images.png)

## しくみ

```
matplotlib の Figure ──export_igor()──▶ name.h5（Wave + 命令） ──Igor: LoadPythonFigure()──▶ Igor のグラフ
                                          │
                                          └─ ローダーが、全命令を許可リストで検査してから実行
```

## 現状

- **Igor Pro 8.04・Windows** で確認しています。他の Igor のバージョン・macOS は未確認です（報告歓迎）。
- Python 3.9 以上。matplotlib 3.6〜3.10 でテストが通ります（等高線は 3.8 以上）。
- 対応範囲・未対応・既知の差: [docs/ja/supported.md](docs/ja/supported.md)。確認と較正の記録: [docs/ja/verified.md](docs/ja/verified.md)。
- 既定のレイアウトは、コンパクトな 1 カラム用（プロット幅 8 cm・Arial・内向きの目盛り）。`use_mpl_size=True` で matplotlib の図の大きさに合わせ、`style=` で何でも上書きできます。

## 安全性

`.h5` には Igor が実行する命令が入るので、ローダーは、厳密な許可リストに全文一致した命令だけを実行し、1 つでも拒否されたら何も読み込みません。
設計と限界は [docs/ja/safety.md](docs/ja/safety.md)、問題の報告は [SECURITY.md](SECURITY.md)。

## Claude で使う

`plugin/` は Claude Code のプラグインです（同じスキルを Claude.ai 用にも作れます）。「これを Igor で描いて」と頼むと、Claude が matplotlib のコードを書いて `export_igor` を実行し、Windows の Claude Code なら Igor を動かして結果を見比べられます。

```
/plugin marketplace add nlyamada/export-igorgraph
/plugin install export-igorgraph@export-igorgraph
```

## ドキュメント

[使い方](docs/ja/usage.md) · [対応範囲](docs/ja/supported.md) · [安全性](docs/ja/safety.md) · [確認の記録](docs/ja/verified.md) · [Igor の自動実行](docs/ja/igor-automation.md) · [開発](docs/ja/developing.md)

## ライセンス

MIT（[LICENSE](LICENSE)）。

*Igor Pro は WaveMetrics, Inc. の製品・商標です。このプロジェクトは同社とは無関係で、同社の承認を受けたものでもありません。*
