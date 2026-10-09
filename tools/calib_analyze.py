"""
calib_analyze.py
================

calib.py lblpos の PNG（Igor）から、x 軸の下にある「目盛りラベル」と「軸ラベル」の位置を画素で測る。

    python calib_analyze.py <フォルダ>      # 結果を calib_lblpos.csv に書き、要約を表示する

測るもの（単位 pt。軸線 = プロット領域の下端から下向きの距離）:
    tl_top / tl_bot   目盛りラベルの帯の上端・下端
    lb_top / lb_bot   軸ラベルの帯の上端・下端
    gap               tl_bot から lb_top までの隙間（負なら重なり）
"""

import csv
import glob
import os
import re
import sys

import numpy as np
from PIL import Image

WIN_W = 50 + 200 + 14      # calib.py の margins=(50, 80, 14, 14), width=200
PLOT_W = 200.0
LEFT = 50.0


def bands(mask_rows):
    out, start = [], None
    for i, v in enumerate(mask_rows):
        if v and start is None:
            start = i
        if not v and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(mask_rows) - 1))
    return out


def measure(path):
    im = np.array(Image.open(path).convert("L"))
    dark = im < 128
    H, W = dark.shape
    sc = W / WIN_W                                   # px / pt
    x0, x1 = int(round(LEFT * sc)), int(round((LEFT + PLOT_W) * sc))
    # 軸線: プロット領域の幅の 9 割以上が暗い、いちばん下の行
    rows = np.where(dark[:, x0:x1].sum(axis=1) > 0.9 * (x1 - x0))[0]
    if rows.size == 0:
        return None
    y_ax = rows.max()
    # 軸線の下で、プロット領域の左右 ±10 pt の範囲にある暗い画素を行ごとに見る（Y 軸ラベルは含めない）
    cl, cr = int((LEFT - 10) * sc), int((LEFT + PLOT_W + 10) * sc)
    below = dark[y_ax + 2:, cl:cr].any(axis=1)
    bs = bands(below)
    # 1 画素ぶんの隙間で分かれている帯はつなぐ（文字の i の点など）
    merged = []
    for b in bs:
        if merged and b[0] - merged[-1][1] <= 2:
            merged[-1] = (merged[-1][0], b[1])
        else:
            merged.append(b)
    pt = lambda r: (r + 2 + 0.5) / sc                # 軸線の直下からの距離 (pt)
    # 左軸: 左端の軸線（高さの 9 割以上が暗い、いちばん左の列）から左向きの帯
    y0 = int(round(14 * sc))
    y1 = int(round((14 + 150) * sc))
    cols = np.where(dark[y0:y1, :].sum(axis=0) > 0.9 * (y1 - y0))[0]
    x_ax = cols.min()
    left = dark[y0:y1, : x_ax - 2].any(axis=0)       # 軸線の左側（外向き目盛りも含む）
    lb_ = bands(left[::-1])                           # 軸線に近い側から数える
    lb_ = [(a, b) for a, b in lb_]
    mergedl = []
    for b in lb_:
        if mergedl and b[0] - mergedl[-1][1] <= 2:
            mergedl[-1] = (mergedl[-1][0], b[1])
        else:
            mergedl.append(b)
    ptl = lambda c: (c + 2 + 0.5) / sc                # 軸線から左向きの距離 (pt)
    return dict(scale=sc, bands=[(pt(a), pt(b + 1)) for a, b in merged],
                lbands=[(ptl(a), ptl(b + 1)) for a, b in mergedl])


def main():
    folder = sys.argv[1]
    rows = []
    for p in sorted(glob.glob(os.path.join(folder, "k*_igor.png"))):
        name = os.path.basename(p)[: -len("_igor.png")]
        m = re.match(r"k(\d+)t(\d)([ln])([ps])_(\d+)$", name)
        if not m:
            continue
        gf, tick, lg, sup, lp = int(m[1]), int(m[2]), m[3], m[4], int(m[5])
        r = measure(p)
        if r is None or len(r["bands"]) < 2:
            rows.append([name, gf, tick, lg, sup, lp, "", "", "", "", ""])
            continue
        b = r["bands"]
        tl, lb = b[-2], b[-1]
        if tick == 0 and len(b) >= 3:  # 外向きの目盛りは、目盛りラベルの上に別の帯として出ることがある
            tl = b[-2]
        lbs = r["lbands"]
        ly = lbs[-1] if lbs else (0, 0)               # いちばん外側 = y 軸ラベル
        lt = lbs[-2] if len(lbs) >= 2 else (0, 0)     # その内側 = 目盛りラベル（外向き目盛りだけの帯が混ざることがある）
        rows.append([name, gf, tick, lg, sup, lp, round(tl[0], 1), round(tl[1], 1), round(lb[0], 1),
                     round(lb[1], 1), round(lb[0] - tl[1], 1), round(lt[0], 1), round(lt[1], 1), round(ly[0], 1),
                     round(ly[1], 1), len(lbs)])
    with open(os.path.join(folder, "calib_lblpos.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "gf", "tick", "axis", "label", "lblPos", "tl_top", "tl_bot", "lb_top", "lb_bot", "gap",
                    "ltl_in", "ltl_out", "lyl_in", "lyl_out", "nbands_left"])
        w.writerows(rows)
    print(f"{len(rows)} 行 -> calib_lblpos.csv")


if __name__ == "__main__":
    main()
