# Developing

## Setup

```
git clone https://github.com/nlyamada/export-igorgraph
cd export-igorgraph
python -m venv .venv && .venv\Scripts\activate        # or: source .venv/bin/activate
pip install -e ".[test]"
python -X utf8 tests/run_all.py
```

On Windows with a Japanese locale, use `python -X utf8` (otherwise printing `Å` etc. fails under cp932).

## Layout

```
src/export_igorgraph/    the library (mpl_to_igor.py: Figure → .h5; eig_allowlist.py: the allow-list; make_loader.py;
                         minimal_hdf5_writer.py; check_igor_style.py)
igor/                    ExportIgorGraphLoader.ipf (generated — do not edit) and EIG_Gallery.ipf (verification tool)
tests/                   test scripts (run_all.py runs them all)
tools/                   gallery, calibration, Igor automation, matplotlib version check
plugin/                  Claude Code plugin (a skill that drives export_igor)
docs/                    documentation
```

## Round trips with Igor (changes that affect what Igor sees)

1. Fix mechanical errors with the Python tests.
2. Build the kit: `python tools/make_kit.py <out>` (or let `tools/run_igor_round.py` do it).
3. Run it in Igor: automatically on Windows (`tools/run_igor_round.py`, see [igor-automation.md](igor-automation.md)) or by hand (`EIG_SelfTest()`, then `RunGallery()`).
4. Analyze with `tools/audit.py` (sent vs read-back) and **by looking at the images** (`tools/contact_sheet.py`, `tools/pairs.py`).
5. Fix and repeat. Decide a stopping rule first (e.g. three round trips).
6. Record new facts in [verified.md](verified.md).

## Tests

```
python -X utf8 tests/run_all.py                 # everything below
python -X utf8 tests/test_mpl_to_igor.py <dir>  # conversion (the argument is an output directory)
python -X utf8 tests/test_layout.py             # window, fonts, label placement, markers, dashes, grid, color scale
python -X utf8 tests/test_contour.py            # contours: capture of the original Z, commands
python -X utf8 tests/test_loader.py             # the loader means the same as the allow-list; all gallery commands pass
python -X utf8 tests/test_audit.py              # the comparison tool
python -X utf8 tests/test_check_igor_style.py   # the Igor code style checker
python -X utf8 tests/test_minimal_hdf5_writer.py [igor_written.h5]
python -X utf8 tools/check_mpl_versions.py <workdir> 3.8.4 3.9.4 3.10.7 --python <python.exe>   # several matplotlib versions in throw-away venvs
```

## Adding features

### A new Igor command
1. Check the syntax in the official docs (`https://docs.wavemetrics.com/llms.txt` is the index; append `.md` to a page URL). If you cannot confirm it, say so and test it in Igor with a small calibration figure (`tools/calib.py`).
2. Add a **strict** pattern to `eig_allowlist.py` and add samples to `GOOD_SAMPLES` and `BAD_SAMPLES`.
3. Regenerate the loader: `python -m export_igorgraph loader igor/`.
4. Make `test_loader.py` pass.

### A new matplotlib element
1. Read it in `_collect` and emit commands in `export_igor` (`mpl_to_igor.py`).
2. Add tests; add a figure to `tools/gallery.py`.
3. Compare in Igor.

### Calibrating sizes and positions
`tools/calib.py <kind> <out>` builds figures that vary one parameter (`lblpos`, `trip`, `ls`, `eb`, `ct`, …); `tools/run_igor_round.py --only <dir>` draws them; measure the PNGs (`calib_analyze.py` or a small script: pixels per point = PNG width / window width in pt). Put the numbers in the calibration constants of `mpl_to_igor.py` and in [verified.md](verified.md).

## Dependencies

- Required: `numpy`, `matplotlib` (≥ 3.8 for contours). Optional: `h5py` (tests), `pillow` (comparison sheets), `pywin32` (Igor automation).
- matplotlib 3.6.3 – 3.10.7 pass the conversion and layout tests. **Switch on features (`hasattr`), not on version numbers** (e.g. `Axis.get_tick_params` exists since 3.7).
- Avoid private (`_`-prefixed) matplotlib API. The contour data is captured by wrapping the public `Axes.contour` / `contourf`.
