# Supported features, limitations and known differences

"Reproduced" means: compared against matplotlib on Igor Pro 8.04 / Windows (details in [verified.md](verified.md)).
Anything that is not reproduced is listed in `ExportReport.warnings`.

## Supported

| Area | Details |
|---|---|
| Lines | Solid lines. Dashed lines map to the Igor line style whose dash pattern is closest (`--` → 11, `:` → 2, `-.` → 5 at line width 1.5). Igor dash lengths are absolute while matplotlib's scale with the line width, so the style is chosen per line width |
| Markers | `o s ^ v < > D d p h H * 8 + P x X _ \| .`; filled, open (transparent) and white-filled (opaque). `H * 8 P X` are approximations (warning) |
| Error bars | X, Y, XY; asymmetric; cap width and thickness; color |
| scatter | Single color and size (circles). Per-point colors/sizes: first value used (warning) |
| Axes | Linear/log (tick labels as 10^n), ranges (including inverted), grid (solid), tick direction (in/out/crossing/none), axis labels (mathtext subset: italic variables, sub/superscripts, Greek letters) |
| Legend | Position (`loc`), frame, symbols and text. Symbols are drawn at the graph's marker size |
| Images | `imshow` (2-D scalar data, `origin`, `extent`), `pcolormesh` (rectilinear, uniform or not), `Normalize`/`LogNorm`, NaN/masked, faithful colormap (256-entry wave) or an Igor color table |
| Color scale | Vertical. Default: framed box right of the plot; `cs_mode="mpl"` follows the matplotlib colorbar; log color scales |
| Contours | `contour` (single color or colormap lines, `clabel` labels) and `contourf` (filled), built from the **original Z matrix** as Igor contours (`AppendMatrixContour`/`ModifyContour`); can be overlaid on images |
| Layout | Window, margins, plot area, font size and font are fixed explicitly. Axis labels are placed with `lblMargin` so they do not overlap tick labels |

## Not supported (warning; substituted or skipped)

- `alpha` (ignored); several Axes (only the first is exported); title; text annotations; `fill_between` and other fills; `LineCollection` (`hlines`/`vlines`).
- RGB images; non-rectilinear meshes; `gouraud`; `pcolor`; non-linear norms other than `LogNorm` (linear); horizontal colorbars (vertical); `symlog` and other scales (linear).
- Contours: per-level color lists (`colors=[...]`) → first color; dashed negative levels → solid; colorbars of contour sets; non-rectilinear grids; matplotlib < 3.8.
- Multi-column legends (`ncol`) become one column; the errorbar glyph in a legend is a plain marker in Igor.
- Twin axes, multi-panel figures.

## Known differences (not planned)

- Minor tick labels on log axes (2, 4, 6, 8) are Igor's default.
- Tick placement, fine legend placement and font anti-aliasing differ.
- `contourf` colors are approximate (Igor fills each band with the color of its lower level; compensated by half a band). Regions below the lowest level are filled with the lowest color — for overlays on images use line contours.
- `*` (five-pointed star) is drawn as Igor's four-pointed star.

## What "matches" means

Not pixel identity. Compared are: data positions, axis ranges and log scales, colors, line widths, markers (shape and size), error bars (including caps), legend text and position, labels, image orientation and color range, window and plot-area size. `tools/audit.py` compares the commands that were sent against what Igor reports back (`igor_audit.txt`).
