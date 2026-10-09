#!/usr/bin/env python3
"""
contact_sheet.py
================

gallery フォルダの mpl/<name>.png（matplotlib）と <name>_igor.png（Igor）を左右に並べたシートを作る。
    python contact_sheet.py <gallery フォルダ> [出力ディレクトリ]      # sheet_01.png, sheet_02.png, ...
Igor 側の PNG が無い図は、「no Igor PNG」と表示する（matplotlib の既定フォントは日本語を描けないため英語）。1ページに4図（左: matplotlib / 右: Igor）。
"""
from __future__ import annotations

import glob
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt

PER_PAGE = 4


def make_sheets(folder: str, outdir: str | None = None) -> list:
    outdir = outdir or folder
    os.makedirs(outdir, exist_ok=True)
    names = sorted({os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(folder, "mpl", "*.png"))}
                   | {os.path.basename(p)[: -len("_igor.png")] for p in glob.glob(os.path.join(folder, "*_igor.png"))})
    pages = []
    for p0 in range(0, len(names), PER_PAGE):
        chunk = names[p0 : p0 + PER_PAGE]
        fig, axes = plt.subplots(len(chunk), 2, figsize=(9, 3.2 * len(chunk)), squeeze=False)
        for r, name in enumerate(chunk):
            for c, (label, path) in enumerate((("matplotlib", os.path.join(folder, "mpl", f"{name}.png")),
                                               ("Igor", os.path.join(folder, f"{name}_igor.png")))):
                ax = axes[r][c]
                ax.axis("off")
                if os.path.exists(path):
                    ax.imshow(mpimg.imread(path))
                else:
                    ax.text(0.5, 0.5, "no Igor PNG" if label == "Igor" else "no matplotlib image (chart)", ha="center", va="center")
                ax.set_title(f"{name}  [{label}]", fontsize=9)
        fig.tight_layout()
        out = os.path.join(outdir, f"sheet_{len(pages) + 1:02d}.png")
        fig.savefig(out, dpi=110)
        plt.close(fig)
        pages.append(out)
    return pages


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    for p in make_sheets(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None):
        print(p)
