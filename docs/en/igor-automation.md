# Driving Igor automatically (Windows)

`tools/run_igor_round.py` starts Igor Pro 8, draws a folder of figures through the loader, and collects the history, a read-back of every graph (`igor_audit.txt`) and a PNG of every graph. It uses Igor's ActiveX automation server (`Execute2`).

> It places two `.ipf` files in your `Igor Procedures` folder and starts/quits Igor. It only opens `.h5` files that it generated itself. If Igor is already running it stops, so it never disturbs your work.

## Use

(Inside the Claude skill the tools are in `scripts/tools/`; run them with `PYTHONPATH=<skill>/scripts` unless the package is pip-installed.)

```
pip install pywin32 pillow
python -X utf8 tools/run_igor_round.py <workdir>                        # the whole gallery
python -X utf8 tools/run_igor_round.py <workdir> --only <h5 folder>     # only .h5 files you generated
```

1. Builds `eig_kit/` (loader + gallery), or with `--only` just rebuilds the loader from the allow-list.
2. Copies `ExportIgorGraphLoader.ipf` and `EIG_Gallery.ipf` to `Documents\WaveMetrics\Igor Pro 8 User Files\Igor Procedures\` (loaded at Igor's startup).
3. Starts `Igor64.exe` (Igor 8) and attaches with `GetObject` — **not `CreateObject`** — then checks that `IgorVersion` is 8.
4. `Execute2` runs `EIG_RunGalleryAt("<folder>")`. Output: `igor_history.txt`, `EIG_done.txt`, `igor_audit.txt`, `<name>_igor.png`.
5. Runs `audit.py` (→ `audit_report.md`) and `contact_sheet.py`.
6. Quits the Igor it started (`--keep-igor` leaves it running).

## Things that bit us

- **The registered COM server can be Igor 10.** With both installed, `IgorPro.Application` in the registry points to Igor 10, so `CreateObject` starts Igor 10. Start Igor 8 yourself by its path and attach with `GetObject(Class="IgorPro.Application")`.
- `Execute2` returns the error code, error message and history. Paths are Igor string literals; colon-separated (`"C:folder:sub"`) avoids backslash doubling.
- A **compile error blocks on a dialog**. If a run times out, take a screenshot.
- On a Japanese Windows, run Python with `-X utf8`.
- PNGs: `SavePICT/O/Z/P=…/E=-5/B=144/WIN=<name>`. Pixels per point depend on the display scaling; divide by the window width from `GetWindow wsize`.
- `AnnotationInfo` returns `RECT:l,t,r,b` (points): the real size of a legend or color scale — useful for calibrating layouts.

## Without automation

Put the two `.ipf` files from `igor/` into Igor, run `EIG_SelfTest()` (expect "ALL PASS"), run `RunGallery()` and choose the gallery folder, then send the history output and the folder (with `igor_audit.txt` and `*_igor.png`).
