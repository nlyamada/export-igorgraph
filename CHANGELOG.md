# Changelog

All notable changes are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0]

First public version.

### Added
- `export_igor(fig, outdir, name)`: matplotlib `Figure` → HDF5 (`name.h5`) with the data and Igor drawing commands; `LoadPythonFigure()` in Igor builds the graph.
- Lines (solid and dashed), 20 marker shapes, error bars (X/Y/XY, asymmetric, caps), scatter, log axes (10^n labels), grid, tick direction, axis labels with sub/superscripts and Greek letters, legends.
- Images (`imshow`, `pcolormesh`), colormaps, `LogNorm`, framed color scale.
- Contours (`contour`, `contourf`) as editable Igor contours built from the original Z matrix (captured at call time, or passed with `contour_data`).
- Loader with an allow-list: every command is checked before anything is executed.
- Layout measured on Igor 8.04: marker sizes, dash patterns, error-bar caps, axis-label placement (`lblMargin`), color-scale box.
- Tools: gallery and read-back audit, Igor automation over ActiveX (Windows), matplotlib version check.
- Claude Code plugin with a skill.

- Main formatting settings via `style=` (`tick`, `mirror`, `standoff`, `grid`, `width`, `height`, `font`, `gFont`), with aliases, "did you mean" warnings for unknown keys, value checks, and an optional JSON style file.
- The graph size is released at the very end (`width=0,height=0`) so the window can be resized in Igor (`free_size`).

### Known limitations
See `docs/en/supported.md`. Verified on Igor Pro 8.04 / Windows only.
