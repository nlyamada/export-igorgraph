"""
charts.py
=========

Igor のマーカー番号（0〜62）と線種の番号（0〜17）を、実際に描いて確かめるための見本図。
公式ドキュメントでは、番号と形の対応表は画像（ColorsMarkersLinesPatterns の実験から生成した表）で、
文字としては取れない。そこで、凡例に「記号 + 番号」を並べた図を Igor に描かせて、その PNG から対応を読み取る。

matplotlib は使わず、許可リストを通る命令を直接組み立てて、export_igor と同じ形式の h5 に書く
（読み込みは、他の図と同じ LoadPythonFigure）。
    c01_mk_a … c04_mk_d   マーカー 0〜15, 16〜31, 32〜47, 48〜62
    c05_lstyle            線種 0〜17
"""

from __future__ import annotations

import numpy as np

from export_igorgraph.mpl_to_igor import write_figure_h5

MARKERS_PER_CHART = 16
N_MARKERS = 63
N_LINESTYLES = 18


def _legend_text(items) -> str:
    return "\\r".join(f"\\\\s({tn}) {label}" for tn, label in items)


def _build(name, kind, ids, outdir, text_mode="string"):
    """kind: 'marker' か 'lstyle'。ids: 描く番号のリスト。"""
    datasets, wave_names, items = {}, [], []
    for i, k in enumerate(ids):
        xn, yn = f"{name}_t{i}_x", f"{name}_t{i}_y"
        # 軸の範囲の外（x=100）に置いて、記号は凡例でだけ見る
        datasets[xn] = np.array([100.0, 101.0])
        datasets[yn] = np.array([0.0, 0.0])
        wave_names += [xn, yn]
        items.append((yn, str(k)))
    n = len(ids)
    C = [f"DoWindow/K {name}"]
    for i in range(n):
        yn, xn = f"{name}_t{i}_y", f"{name}_t{i}_x"
        C.append(f"Display/N={name}/W=(40,40,300,{int(60 + 16 * n)}) {yn} vs {xn}" if i == 0
                 else f"AppendToGraph/W={name} {yn} vs {xn}")
    h = 16 * n
    C += [f"ModifyGraph/W={name} margin(left)=20,margin(bottom)=20,margin(top)=14,margin(right)=14",
          f"ModifyGraph/W={name} gfSize=12,width=220,height={h}",
          f'ModifyGraph/W={name} font="Arial"',
          f"SetAxis/W={name} bottom 0,1", f"SetAxis/W={name} left 0,1"]
    for i, k in enumerate(ids):
        yn = f"{name}_t{i}_y"
        if kind == "marker":
            C.append(f"ModifyGraph/W={name} mode({yn})=3,marker({yn})={k},msize({yn})=6,mrkThick({yn})=1,rgb({yn})=(0,0,0)")
        else:
            C.append(f"ModifyGraph/W={name} mode({yn})=0,lStyle({yn})={k},lSize({yn})=1.5,rgb({yn})=(0,0,0)")
    hh = "/H=80" if kind == "lstyle" else ""
    C.append(f'Legend/W={name}/N=legend0/F=2/M=1{hh}/A=LT/X=2/Y=2 "{_legend_text(items)}"')
    C.append(f"DoWindow/F {name}")
    h5 = write_figure_h5(outdir, name, datasets, C, wave_names, text_mode)
    return C


def build_charts(outdir: str):
    """(名前, 命令のリスト) を順に返す。"""
    out = []
    for j, (suffix, start) in enumerate((("a", 0), ("b", 16), ("c", 32), ("d", 48))):
        ids = list(range(start, min(start + MARKERS_PER_CHART, N_MARKERS)))
        name = f"c{j + 1:02d}_mk_{suffix}"
        out.append((name, _build(name, "marker", ids, outdir)))
    out.append(("c05_lstyle", _build("c05_lstyle", "lstyle", list(range(N_LINESTYLES)), outdir)))
    return out
