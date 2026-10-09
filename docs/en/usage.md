# Usage

## Contents
1. Workflow
2. `export_igor` arguments
3. Style keys (`style=`)
4. What is inside the `.h5`
5. Igor side
6. Data conventions (verified in Igor)

## 1. Workflow

1. Draw the figure with matplotlib (Agg is fine).
2. `import export_igorgraph` (or `from export_igorgraph import export_igor`) **before** calling `contour` / `contourf` — importing installs a small wrapper that remembers the original `(X, Y, Z)` (see [Contours](#contours)).
3. `report = export_igor(fig, outdir, name)`. `name` becomes the Igor graph name, data folder name and wave-name prefix (starts with a letter; letters, digits and `_`; at most 16 characters).
4. Read `report.summary()`. Every element that Igor cannot reproduce is listed in `report.warnings` — nothing is dropped silently.
5. Open the `.h5` in Igor with `LoadPythonFigure()` (see [Igor side](#5-igor-side)).

## 2. `export_igor` arguments

```python
export_igor(fig, outdir=".", name="fig1", *, ax=None, style=None, use_mpl_size=False, italic_math=True,
            ctab=None, write_ipf=False, text_mode="string", axis_range="mpl", contour_data=None)
```

| Argument | Meaning |
|---|---|
| `ax` | Axes to export (default: the first Axes that is not a colorbar) |
| `style` | Overrides of the style dictionaries (below). What you specify always wins |
| `use_mpl_size` | `True`: window, margins, plot area and font size are taken from the matplotlib figure (figure = window). `False` (default): a compact layout (8 cm wide plot area, Arial 14 pt; 12 pt for images). If axis labels would collide with tick labels, the margins are widened (the plot area keeps its size) and a warning is issued |
| `italic_math` | Italicize mathtext variables (ASCII letters); subscripts and superscripts stay upright |
| `ctab` | e.g. `("Rainbow", 1)`: use an Igor color table (name, reverse) instead of reproducing the matplotlib colormap as a 256-entry wave |
| `write_ipf` | Also write a per-figure `.ipf` (`Make_<name>()`). Default: only the `.h5` |
| `text_mode` | `"string"` (fixed-length strings; works in Igor 8.04) or `"codes"` (integer arrays; fallback) |
| `axis_range` | `"mpl"` (default): fix the axis ranges to what matplotlib shows (`SetAxis`). Igor's autoscale puts data on the frame and clips markers/error bars. `"auto"`: fix only manually set ranges |
| `contour_data` | Original data for contour sets: `(X, Y, Z)` (Z is `(ny, nx)`), a list of such tuples (in drawing order), or `{ContourSet: (X, Y, Z)}`. If omitted, the data captured at call time is used |

The return value `ExportReport` has `.files`, `.warnings`, `.commands` (the commands embedded in the `.h5`), `.n_traces`, `.n_images`, `.n_contours` and `.summary()`.

### Contours

matplotlib's `ContourSet` does **not** keep the Z matrix (only the resulting polylines). To export a *real* Igor contour — editable with `ModifyContour` — the original data is needed. `export_igorgraph` therefore wraps the public `Axes.contour` / `Axes.contourf` when it is imported and stores `(X, Y, Z)` on the returned `ContourSet`. If a contour was drawn before the import, pass `contour_data=(X, Y, Z)` explicitly. matplotlib ≥ 3.8 is required for contours.

## 3. Style keys (`style=`)

```python
export_igor(fig, outdir, "fig1", style={"tick": "mpl", "cs_box": False})
```

| Key | Default | Meaning |
|---|---|---|
| `tick` | `2` | `0` outside, `1` crossing, `2` inside, `3` none, `"mpl"` follow matplotlib's tick direction. `mirror` and `standoff` (defaults 1 and 0) can be given too |
| `font`, `gfont` | `"Arial"`, `None` | `font`: the axes' font (tick labels, axis labels). `gfont` (Igor's `gFont`): the default font of the whole graph (legend, annotations); `None` follows `font`. Only names on the allow-list (`FONT_NAMES` in `eig_allowlist.py`: Arial, Helvetica, Times New Roman, Times, Courier New, Courier, Calibri, Verdana, Tahoma, Segoe UI, Georgia, Cambria, Meiryo, Yu Gothic, MS Gothic, MS PGothic); `None` for no command |
| `margin_left/bottom/top/right`, `width_pt`, `aspect`, `gf_size` | lines: 43/37/14/14, 226.772, 0.8, 14; images: 51/43/14/57, 227, 1, 12 | Layout for `use_mpl_size=False`. Margins are *minimums*: they grow if axis labels, tick labels or the color scale box need more room |
| `grid`, `grid_rgb`, `grid_style` | `None`, `None`, `5` | Grid. `None`: follow matplotlib. `0` none, `1` on, `2` major ticks only; or per axis `{"bottom": 2, "left": 1}`. `grid_rgb`: any matplotlib color (default: matplotlib's grid color). `grid_style`: Igor `gridStyle` (5 = solid) |
| `width`, `height` | none | Plot-area size in points (aliases of `width_pt`, `height_pt`). With `use_mpl_size=True` they override matplotlib's size only when you give them. `height` wins over `aspect` |
| `label_gap` | `0.3` | Minimum gap between tick labels and the axis label (fraction of the font size) |
| `lbl_margin_bottom`, `lbl_margin_left` | none | Position of the axis label (points from the window edge inward). Overrides the model |
| `sub_sup_extra` | `None` | A number adds that many points to the bottom margin when the x label has sub/superscripts (legacy behavior). `None`: computed |
| `log_exp` | `True` | Log-axis tick labels as 10^n (via `logLTrip`) |
| `free_size` | `True` | As the very last command, `ModifyGraph width=0,height=0` (auto size). Without it, a fixed `width`/`height` prevents resizing the window in Igor. The margins stay fixed, so the plot area looks the same at first and then follows the window size. `False` keeps the fixed size |
| `cs_mode` | `"outside"` | Color scale: `"outside"` (right of the plot; margin widened to fit), `"mpl"` (position and size of the matplotlib colorbar; automatic with `use_mpl_size=True`), `"preset"` (an inside annotation) |
| `cs_box` | `True` | Frame (box) around the color scale; `False` for none |
| `cs_width`, `cs_gap`, `cs_height_pct`, `cs_frame`, `cs_nticks`, `cs_log_trip` | 15, 8, 100, 0, none, 0.1 | Bar width, gap to the plot, bar height (% of plot), bar border, number of ticks, log-label threshold |
| `cs_lbl_margin` | `None` | Position of the color-scale label. **Leave `None`** (Igor's default never overlaps); a value makes it overlap the tick labels |
| `win_left`, `win_top` | 40, 40 | Window position |

### Style files and checks

Defaults can live in a JSON file instead of every call: `export_igorgraph_style.json` in the current folder, `~/.export_igorgraph_style.json`, or the path in the environment variable `EXPORT_IGORGRAPH_STYLE` (or `export_igor(..., style_file="path")`; `style_file=False` ignores files). Priority: built-in defaults < style file < `style=`. Keys starting with `_` are comments. See `export_igorgraph_style.example.json`. After editing a file, validate it with `python -m export_igorgraph style-check FILE.json` (or `export_igorgraph.check_style_file(path)`).

Aliases are accepted (`width`, `height`, `gFont`, `gfSize`). **Unknown keys are ignored with a warning** (with "did you mean"), and **invalid values raise `ValueError`** (e.g. `tick=5`, a font that is not on the allow-list).

## 4. What is inside the `.h5`

| Name | Content |
|---|---|
| `name_t{k}_x`, `_y` | Trace k coordinates |
| `name_t{k}_ex` / `_ey` | Symmetric errors; asymmetric: `_exp/_exn/_eyp/_eyn` (plus/minus) |
| `name_i{k}_z`, `_xe`, `_ye`, `_ct` | Image k. `z` has shape `(nx, ny)` (Igor dim0 = x); `_xe/_ye` are pixel **edges** (n+1 points); `_ct` is a color table (256×3, float64, 0–65535; `Redimension/U/W` in Igor) |
| `name_c{k}_z`, `_x`, `_y`, `_lv`, `_ct` | Contour k: the original Z matrix, row/column coordinates, levels, color table (for colormaps) |
| `igor_cmds` | Drawing commands (fixed-length string; only commands matching the allow-list) |
| `igor_waves`, `igor_meta` | Waves to load; `format=1; name=…; generator=…; text=string\|codes` |

`h5py` is not required to *write* files (`minimal_hdf5_writer.py` uses numpy only; its output mirrors the layout of files written by Igor).

## 5. Igor side

1. Once: install the loader. `python -m export_igorgraph loader <folder>` writes `ExportIgorGraphLoader.ipf` (or copy `igor/ExportIgorGraphLoader.ipf` from the repository). Put it in `Documents\WaveMetrics\Igor Pro 8 User Files\Igor Procedures\` to have it loaded at startup.
2. In Igor's command line: `LoadPythonFigure()`, then choose the `.h5`. With a path: `LoadPythonFigure_exec(h5Path="C:\\work\\fig1.h5")` (backslashes are doubled in Igor strings).
3. Rejected or failed commands are printed to the history. `EIG_SelfTest()` runs the allow-list self test (it should end with "ALL PASS").

## 6. Data conventions (verified in Igor)

- numpy axis `i` = Igor dimension `i` (no transpose). `scaling[i] = (delta, offset)` of `IGORWaveScaling` applies to dimension `i`; load with `HDF5LoadData /IGOR=-1`.
- Images and contours: Igor dim0 = x (columns), dim1 = y (rows), so matplotlib's `A[row, col]` is **transposed**. Decreasing coordinates are flipped so they increase.
- `origin="upper"` images have a reversed y axis, so `SetAxis` is always emitted for 2-D figures (e.g. `left 2.5,-0.5`).
- float32 → WaveType 2, float64 → 4, int32 → 32; NaN is preserved.
