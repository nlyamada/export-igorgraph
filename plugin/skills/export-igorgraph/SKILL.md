---
name: export-igorgraph
description: Exports matplotlib figures (lines, error bars, images, contours) as Igor Pro 8 graphs. Use when asked to draw a Python result in Igor Pro or as an Igor graph, e.g. "Igor で描画したい".
---

# export-igorgraph

```
matplotlib Figure ──export_igor()──▶ name.h5 (data + drawing commands) ──Igor: LoadPythonFigure()──▶ Igor graph
```

The `.h5` contains waves and Igor commands. In Igor, a fixed loader (`ExportIgorGraphLoader.ipf`) is installed once; it checks **every command against a strict allow-list before running anything** (see `references/safety.md`). No per-figure `.ipf` is needed.

## Ground rules

- Target: **Igor Pro 8.x on Windows** (verified on 8.04). Other versions/OSes are unverified — say so.
- Analysis in Python; Igor draws. Claude's sandbox cannot run Igor: generated files are guaranteed only by tests and by what has been verified on a real Igor (`references/verified.md`). In **Claude Code on the user's own Windows machine**, ask permission and then drive Igor to compare (`references/igor-automation.md`).
- Be calm and honest: mark anything not verified as "unverified".

## Steps

1. Draw the figure with matplotlib (Agg). Always give legends an explicit `loc` (`'best'` has no Igor equivalent and produces a warning).
2. Make the package importable — `pip install export-igorgraph` (or from the repository), **or** without installing: `import sys; sys.path.insert(0, "<this skill>/scripts")` (the package is bundled in `scripts/export_igorgraph/`). Then `import export_igorgraph` (or `from export_igorgraph import export_igor`) **before any `contour`/`contourf` call**: matplotlib does not keep the Z matrix of a contour set, so importing installs a wrapper that remembers `(X, Y, Z)` at call time. (Otherwise pass `contour_data=(X, Y, Z)`.) Contours need matplotlib ≥ 3.8.
3. `report = export_igor(fig, outdir, name)` → `name.h5`. `print(report.summary())` and **tell the user every warning** (nothing Igor cannot reproduce is dropped silently).
4. Save a matplotlib PNG of the figure too, as the reference for comparison.
5. Hand over `name.h5` and the PNG with the Igor steps: install the loader once (the skill ships `igor/ExportIgorGraphLoader.ipf`; or `python -m export_igorgraph loader <folder>`; put it in `Documents\WaveMetrics\Igor Pro 8 User Files\Igor Procedures\`), then in Igor run `LoadPythonFigure()` and choose the file. If Igor reports an error, ask for the message.

```python
import export_igorgraph                      # before contour()
from export_igorgraph import export_igor
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(4, 3))
ax.imshow(data, extent=(x0, x1, y0, y1), origin="lower", cmap="gray", aspect="auto")
ax.contour(X, Y, fit, levels=levels, colors="tab:red", linewidths=1.2)   # becomes an Igor contour (editable with ModifyContour)
ax.set_xlabel(r"$Q_x$ [nm$^{-1}$]"); ax.set_ylabel(r"$Q_z$ [nm$^{-1}$]")
report = export_igor(fig, "out", "fig_fit")
print(report.summary())
fig.savefig("out/fig_fit_mpl.png", dpi=150, bbox_inches="tight")
```

## Rules

0. **Formatting goes through `style=`** (main settings: `tick`, `mirror`, `standoff`, `grid`, `width`, `height`, `font`, `gFont`; e.g. `style={"tick": 0, "grid": 1, "width": 300, "height": 200}`). For settings the user always wants, put them in `export_igorgraph_style.json` (current folder or home) instead of passing them every time (`references/usage.md`, "Style files and checks"). Unknown keys warn; invalid values raise `ValueError`. If the user asks to make a setting permanent, update that JSON file (read it, change only the requested keys, validate with `python -m export_igorgraph style-check FILE`, show the result); if you cannot write it in this environment, show the full JSON and ask the user to save it.
1. **What the user specifies always wins** over presets. Defaults: inside ticks, 10^n labels on log axes, a framed color scale, a compact 8 cm layout (`use_mpl_size=True` takes sizes from the matplotlib figure; `style=` overrides anything — `references/usage.md`).
2. **Label style** (only if the user wants it; the tool warns, never rewrites): variables in italics and subscripts/superscripts upright (`$Q_z$ [nm$^{-1}$]` converts automatically); units in `[ ]`. If the user has house rules (e.g. no Å, nm⁻¹ only), convert data *before* plotting and follow them.
3. **Never present unverified behavior as verified.** Check `references/verified.md` and `references/supported.md`.
4. **Do not loosen the allow-list.** To support a new command form: strict pattern + good and malicious samples + regenerate the loader + tests (`references/developing.md`).
5. **Generated `.ipf` files and the loader are ASCII-only with CRLF**; non-ASCII characters go in strings as `\uXXXX`.
6. **Confirm Igor syntax in the official documentation** (https://docs.wavemetrics.com/llms.txt is the index; append `.md` to a page URL) instead of recalling it.

## References

`references/usage.md` (API, style keys, file contents, Igor steps) · `supported.md` (supported / not supported / known differences) · `safety.md` · `verified.md` (what was verified and measured on Igor 8.04) · `igor-automation.md` · `developing.md`.
