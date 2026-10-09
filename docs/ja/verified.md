# 何をどう確認したか

環境: Windows 11、**Igor Pro 8.04**（`Igor64.exe` 8.0.4.2）、Python 3.9〜3.11、matplotlib 3.6.3〜3.10.7。
**他の OS・Igor のバージョン（macOS、Igor 9/10）は未確認**です。報告を歓迎します。

記号: 🧪 Igor 8.04 の実機で確認 · 📖 公式ドキュメントでのみ確認 · ⚠ 未確認

## 🧪 Igor 8.04 の実機で確認

| 項目 | 結果 |
|---|---|
| HDF5 の次元・スケーリング・型 | numpy 軸 i = Igor 次元 i。`scaling[i]` が次元 i に効く。float32/float64/int32/NaN が保たれる |
| 固定長文字列のデータセット | `HDF5LoadData` がテキスト Wave として読む |
| `Execute/Z`、`GrepString` | 想定どおり（全文一致のアンカー、制御文字のクラス） |
| `EIG_SelfTest()` | 許可リストの見本がすべて通る（v0.1.0 で 91 件） |
| ギャラリー | 48 図が描画され、失敗 0 |
| 命令 | `Display/N=/W=`、`AppendToGraph`、`AppendImage vs {xe,ye}`、`AppendMatrixContour`、`ModifyGraph`（margin, gfSize, width, height, tick, mirror, standoff, log, mode, rgb, marker, msize, mrkThick, lSize, lStyle, opaque, grid, gridRGB, gridStyle, font, lblMargin, logLTrip）、`ModifyImage`、`ModifyContour`、`ErrorBars`、`SetAxis`（反転も）、`Label`、`Legend`、`ColorScale`、`Redimension/U/W`、`DoWindow` |
| 読み戻し | `TraceInfo`/`AxisInfo`/`ImageInfo`、`GetWindow`、`AnnotationInfo`（`RECT`）。送った値と読み戻しの照合: 一致 1633 / 差 146（大半は Igor が余白を整数に丸めたもの）/ 見つからない 6（見本図の既知の差） |
| 画像・等高線・エラーバー・線・マーカー・破線 | matplotlib と並べて確認（`tools/gallery.py`、`tools/pairs.py`） |

## 🧪 Igor 8.04 で測って決めた値

| 項目 | 値 | 測り方 |
|---|---|---|
| マーカーの外形 | Igor は `2s+1` pt、matplotlib は `markersize + 縁の線幅` → `msize = (ms·k + mew − 1)/2`。ダイヤは Igor の寸法が「辺」（k = 1） | 描画した PNG から測定 |
| 破線パターン | 絶対長（pt）で、線幅に依存しない。表は `_IGOR_DASH` | `tools/calib.py ls` |
| エラーバーのキャップ | `/X=` `/Y=` = キャップの全幅。matplotlib の `capsize` は半幅 → `X = Y = 2·capsize` | `tools/calib.py eb` |
| 軸ラベルの幾何 | 目盛りラベルの範囲とラベルの高さを、文字サイズの一次式で（目盛りの向き・対数/線形ごとに）。`mpl_to_igor.py` の `_TLB`・`_TLG` | `tools/calib.py lblpos`（168 図）+ `calib_analyze.py` |
| カラースケールの箱 | 幅 ≈ 棒 + 9.6 + 4.55×文字サイズ（対数は +1.8×）。箱の中の棒の位置 | `AnnotationInfo` の `RECT` と PNG |

## 🧪 Igor 8.04 の挙動（知っておくとよいこと）

- **`lblPos` は効かない**（記録はされるが、ラベルは動かない）。**`lblMargin(axis)`**（ウィンドウの縁から内側への距離。0 以下は効かない）を使う。既定ではラベルはウィンドウの縁に貼り付く。
- **`ColorScale /F`**: 0 = 枠なし、**1 = 下線のみ**、**2 = 箱（既定）**。
- **外側の注釈（`/E=1`）は、明示した余白を広げない**。箱がプロットに重なる。`/E=2/A=LT` と座標指定を使い、余白は自分で広げる。
- **`gridStyle=0` は実線ではない**（白背景では主目盛りが点線）。実線は `5`。
- **`logLTrip`/`logHTrip` に極端な値（1e10, 1e-10）を入れるとエラー（V_flag 84）**。`logLTrip` を軸の最小値の 2 倍にすると 10ⁿ 表記になる。
- `ModifyContour` の既定は Rainbow・自動レベル・ラベルあり。matplotlib に合わせるには `labels=0`、`manLevels=<Wave>`、色（`rgbLines` / `ctabLines`）が要る。
- 塗りの等高線: 最低レベルより下の領域も最低レベルの色で塗られる。各帯は下端のレベルの色。
- ActiveX: **両方入っていると、登録された COM サーバーが Igor 10 のことがある**。`CreateObject` は Igor 10 を起動するので、Igor 8 を自分で起動して `GetObject` で接続する。

## 📖 公式ドキュメントでのみ確認

`ModifyContour` の `autoLevels`・`moreLevels`・`cIndexLines`・`logLines`・`labelFormat`・`labelHV`・`labelRGB`・`labelBkg`・`update`、`SavePICT /E=-5 /B=`、`WinRecreation`。

## ⚠ 未確認

横向きのカラースケール、複数パネル・2 軸グラフ、`alpha`、`AppendXYZContour`、矩形でない格子、`tick=1`（交差）のラベルの配置（内向きと外向きの中間と仮定）、`contourf(colors=[...])` / `extend`、macOS、Igor 9/10。
