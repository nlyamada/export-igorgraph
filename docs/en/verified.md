# What has been verified, and how

Environment: Windows 11, **Igor Pro 8.04** (`Igor64.exe` 8.0.4.2), Python 3.9–3.11, matplotlib 3.6.3 – 3.10.7.
**Other platforms and Igor versions (macOS, Igor 9/10) are untested** — reports are welcome.

Legend: 🧪 verified on Igor 8.04 · 📖 checked against the official documentation only · ⚠ unverified

## 🧪 Verified on Igor 8.04

| Item | Result |
|---|---|
| HDF5 dimensions, scaling, types | numpy axis i = Igor dimension i; `scaling[i]` applies to dimension i; float32/float64/int32/NaN preserved |
| Fixed-length string datasets | `HDF5LoadData` reads them as text waves |
| `Execute/Z`, `GrepString` | behave as relied upon (full-match anchors, control-character class) |
| `EIG_SelfTest()` | all allow-list samples pass (91 at v0.1.0) |
| Gallery | 48 figures drawn, 0 failures |
| Commands | `Display/N=/W=`, `AppendToGraph`, `AppendImage vs {xe,ye}`, `AppendMatrixContour`, `ModifyGraph` (margin, gfSize, width, height, tick, mirror, standoff, log, mode, rgb, marker, msize, mrkThick, lSize, lStyle, opaque, grid, gridRGB, gridStyle, font, lblMargin, logLTrip), `ModifyImage`, `ModifyContour`, `ErrorBars`, `SetAxis` (including reversed), `Label`, `Legend`, `ColorScale`, `Redimension/U/W`, `DoWindow` |
| Read-back | `TraceInfo`/`AxisInfo`/`ImageInfo`, `GetWindow`, `AnnotationInfo` (`RECT`). Comparison of sent vs read-back values: 1633 OK, 146 differences (mostly Igor rounding margins to integers), 6 missing (known differences in test charts) |
| Images, contours, error bars, lines, markers, dashes | compared side by side with matplotlib (`tools/gallery.py`, `tools/pairs.py`) |

## 🧪 Calibrations measured on Igor 8.04

| Item | Value | How |
|---|---|---|
| Marker outline | Igor `2s+1` pt vs matplotlib `markersize + edge width` → `msize = (ms·k + mew − 1)/2`; diamonds: Igor's size is the *side* (k = 1) | measured from rendered PNGs |
| Dash patterns | absolute lengths (pt), independent of line width; table `_IGOR_DASH` | `tools/calib.py ls` |
| Error-bar caps | `/X=` `/Y=` = full cap width; matplotlib `capsize` is the half-width → `X = Y = 2·capsize` | `tools/calib.py eb` |
| Axis-label geometry | tick-label extent and label height as linear functions of font size, per tick direction and log/linear (`_TLB`, `_TLG` in `mpl_to_igor.py`) | `tools/calib.py lblpos` (168 figures) + `calib_analyze.py` |
| Color-scale box | width ≈ bar + 9.6 + 4.55·font size (+1.8·fs for log); bar offsets inside the box | `AnnotationInfo` `RECT` + PNG |

## 🧪 Igor 8.04 behaviors worth knowing

- **`lblPos` has no effect** (it is recorded but the label does not move). Use **`lblMargin(axis)`** (distance from the window edge inward; 0 or negative does nothing). By default labels sit against the window edge.
- **`ColorScale /F`**: 0 = no frame, **1 = underline only**, **2 = box (default)**.
- **External annotations (`/E=1`) do not widen explicitly set margins** — the box overlaps the plot. Use `/E=2/A=LT` with explicit coordinates and widen the margin yourself.
- **`gridStyle=0` is not solid** (white background → major dotted). Solid is `5`.
- **`logLTrip`/`logHTrip` with extreme values (1e10, 1e-10) fail (V_flag 84).** Setting `logLTrip` to twice the axis minimum gives 10^n labels.
- `ModifyContour` defaults: Rainbow, automatic levels, labels on. To match matplotlib: `labels=0`, `manLevels=<wave>`, and a color (`rgbLines` / `ctabLines`).
- Filled contours: the area below the lowest level is filled with the lowest color; each band uses the color of its lower level.
- ActiveX: **the registered COM server may be Igor 10** when both are installed. `CreateObject` starts Igor 10; start Igor 8 yourself and attach with `GetObject`.

## 📖 Official documentation only

`ModifyContour` keywords `autoLevels`, `moreLevels`, `cIndexLines`, `logLines`, `labelFormat`, `labelHV`, `labelRGB`, `labelBkg`, `update`; `SavePICT /E=-5 /B=`; `WinRecreation`.

## ⚠ Unverified

Horizontal color scales, multi-panel / twin-axis graphs, `alpha`, `AppendXYZContour`, non-rectilinear grids, `tick=1` (crossing) label placement (assumed halfway between inside and outside), `contourf(colors=[...])`/`extend`, macOS, Igor 9/10.
