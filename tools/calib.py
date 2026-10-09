"""
calib.py
========

Igor の見た目を較正するための実験図（k 系列）を、許可リストを通る命令で直接組み立てて h5 に書く。
matplotlib は使わない。結果の PNG は calib_analyze.py で測る。

    python calib.py trip  <出力ディレクトリ>     # 対数軸の指数表記（logLTrip / logHTrip）の効き方
    python calib.py lblpos <出力ディレクトリ>    # lblPos・文字サイズ・目盛りの向き・対数・上付きの組み合わせ
"""

from __future__ import annotations

import itertools
import os
import sys

import numpy as np

from export_igorgraph.mpl_to_igor import write_figure_h5
from export_igorgraph.eig_allowlist import is_allowed


def _fig(name, outdir, xlog, ylog, xr, yr, mg_extra, gf=12, tick=2, label_x='x [a.u.]', label_y='y [a.u.]',
         width=200, height=150, margins=(50, 70, 14, 14), after=()):
    """1本の線だけの図。margins=(left, bottom, top, right)。"""
    xn, yn = f"{name}_t0_x", f"{name}_t0_y"
    if xlog:
        x = np.logspace(np.log10(xr[0]), np.log10(xr[1]), 20)
    else:
        x = np.linspace(xr[0], xr[1], 20)
    if ylog:
        y = np.logspace(np.log10(yr[0]), np.log10(yr[1]), 20)
    else:
        y = np.linspace(yr[0], yr[1], 20)
    ml, mb, mt, mr = margins
    W, H = ml + width + mr, mt + height + mb
    C = [f"DoWindow/K {name}",
         f"Display/N={name}/W=(40,40,{40 + W},{40 + H}) {yn} vs {xn}",
         f"ModifyGraph/W={name} margin(left)={ml},margin(bottom)={mb},margin(top)={mt},margin(right)={mr}",
         f"ModifyGraph/W={name} gfSize={gf},width={width},height={height}",
         f'ModifyGraph/W={name} font="Arial"',
         f"ModifyGraph/W={name} tick={tick},mirror=1,standoff=0"]
    if xlog:
        C.append(f"ModifyGraph/W={name} log(bottom)=1")
    if ylog:
        C.append(f"ModifyGraph/W={name} log(left)=1")
    C += [f"SetAxis/W={name} bottom {xr[0]:g},{xr[1]:g}", f"SetAxis/W={name} left {yr[0]:g},{yr[1]:g}"]
    C += mg_extra
    C += [f'Label/W={name} bottom "{label_x}"', f'Label/W={name} left "{label_y}"']
    C.append(f"ModifyGraph/W={name} mode({yn})=0,rgb({yn})=(0,0,0),lSize({yn})=1")
    C += list(after)
    C.append(f"DoWindow/F {name}")
    for cmd in C:
        assert is_allowed(cmd), cmd
    write_figure_h5(outdir, name, {xn: x, yn: y}, C, [xn, yn], "string")
    return C


def build_trip(outdir):
    """対数軸の指数表記: logLTrip / logHTrip の値を変えて、目盛りラベルがどう変わるか見る。"""
    os.makedirs(outdir, exist_ok=True)
    variants = {
        "t01_none": [],
        "t02_l1e10": ["logLTrip(bottom)=1e10", "logLTrip(left)=1e10"],
        "t03_l0p5": ["logLTrip(bottom)=0.5", "logLTrip(left)=0.5"],
        "t04_h1": ["logHTrip(bottom)=1", "logHTrip(left)=1"],
        "t05_h1em10": ["logHTrip(bottom)=1e-10", "logHTrip(left)=1e-10"],
        "t06_l1e10h1em10": ["logLTrip(bottom)=1e10", "logLTrip(left)=1e10", "logHTrip(bottom)=1e-10",
                            "logHTrip(left)=1e-10"],
    }
    out = []
    for k, v in variants.items():
        extra = [f"ModifyGraph/W={k} " + ",".join(v)] if v else []
        out.append(_fig(k, outdir, True, True, (0.1, 10), (1e-2, 1), extra))
    # 範囲が違うとき（1〜1e5、1e-6〜1e-1）にも効くか
    for k, xr, yr in (("t07_wide", (1, 1e5), (1e-6, 1e-1)), ("t08_narrow", (1, 100), (1e-2, 1))):
        v = ["logLTrip(bottom)=1e10", "logLTrip(left)=1e10"]
        extra = [f"ModifyGraph/W={k} " + ",".join(v)]
        out.append(_fig(k, outdir, True, True, xr, yr, extra))
        out.append(_fig(k + "_d", outdir, True, True, xr, yr, []))
    return out


def build_lbl(outdir):
    """軸ラベルの位置を決めるキーワード（lblPos・lblMargin）の効き方を切り分ける。"""
    os.makedirs(outdir, exist_ok=True)
    out = []
    for name, before, after in (
        ("l01_none", [], []),
        ("l02_pos28", ["lblPos(bottom)=28"], []),
        ("l03_pos28_after", [], ["lblPos(bottom)=28"]),
        ("l04_mar40", ["lblMargin(bottom)=40"], []),
        ("l05_mar_m40", ["lblMargin(bottom)=-40"], []),
        ("l06_pos28_mar0", ["lblPos(bottom)=28", "lblMargin(bottom)=0"], []),
        ("l07_posl30", ["lblPos(left)=30"], []),
        ("l08_marl30", ["lblMargin(left)=30"], []),
    ):
        extra = [f"ModifyGraph/W={name} " + ",".join(before)] if before else []
        aft = [f"ModifyGraph/W={name} " + ",".join(after)] if after else []
        out.append(_fig(name, outdir, False, False, (0, 5), (0, 1), extra, margins=(60, 80, 14, 14), after=aft))
    return out


def build_ls(outdir):
    """線種 0〜17 の破線パターンの実寸を測るための図。線幅 1 と 3 の2枚（線は y = 番号 の水平線）。"""
    os.makedirs(outdir, exist_ok=True)
    out = []
    for lw in (1, 3):
        name = f"ls_w{lw}"
        n = 18
        datasets, wnames, C = {}, [], [f"DoWindow/K {name}"]
        H = 20 * n
        for i in range(n):
            xn, yn = f"{name}_t{i}_x", f"{name}_t{i}_y"
            datasets[xn] = np.array([0.0, 1.0])
            datasets[yn] = np.array([float(i), float(i)])
            wnames += [xn, yn]
            C.append(f"Display/N={name}/W=(40,40,{40 + 360},{40 + H + 30}) {yn} vs {xn}" if i == 0
                     else f"AppendToGraph/W={name} {yn} vs {xn}")
        C += [f"ModifyGraph/W={name} margin(left)=20,margin(bottom)=14,margin(top)=14,margin(right)=20",
              f"ModifyGraph/W={name} gfSize=10,width=320,height={H}",
              f"SetAxis/W={name} bottom 0,1", f"SetAxis/W={name} left -0.5,{n - 0.5}",
              f"ModifyGraph/W={name} noLabel=2,tick=3,mirror=0,standoff=0" if False else
              f"ModifyGraph/W={name} tick=3,mirror=0,standoff=0"]
        for i in range(n):
            yn = f"{name}_t{i}_y"
            C.append(f"ModifyGraph/W={name} mode({yn})=0,lStyle({yn})={i},lSize({yn})={lw},rgb({yn})=(0,0,0)")
        C.append(f"DoWindow/F {name}")
        for cmd in C:
            assert is_allowed(cmd), cmd
        write_figure_h5(outdir, name, datasets, C, wnames, "string")
        out.append(C)
    return out


def build_eb(outdir):
    """エラーバーのキャップ幅: ErrorBars の /X=/Y= を 1〜8 に変えた8本（各1点、y=5±3）。キャップの実寸を測る。"""
    os.makedirs(outdir, exist_ok=True)
    name = "eb01"
    datasets, wn, C = {}, [], [f"DoWindow/K {name}"]
    n = 8
    for i in range(n):
        xn, yn, en = f"{name}_t{i}_x", f"{name}_t{i}_y", f"{name}_t{i}_ey"
        datasets[xn], datasets[yn], datasets[en] = np.array([i + 1.0]), np.array([5.0]), np.array([3.0])
        wn += [xn, yn, en]
        C.append(f"Display/N={name}/W=(40,40,400,300) {yn} vs {xn}" if i == 0 else f"AppendToGraph/W={name} {yn} vs {xn}")
    C += [f"ModifyGraph/W={name} margin(left)=30,margin(bottom)=30,margin(top)=14,margin(right)=14",
          f"ModifyGraph/W={name} gfSize=10,width=300,height=200", f'ModifyGraph/W={name} font="Arial"',
          f"SetAxis/W={name} bottom 0,{n + 1}", "SetAxis/W=%s left 0,10" % name]
    for i in range(n):
        yn, en = f"{name}_t{i}_y", f"{name}_t{i}_ey"
        C.append(f"ModifyGraph/W={name} mode({yn})=3,marker({yn})=19,msize({yn})=1,rgb({yn})=(0,0,0)")
        C.append(f"ErrorBars/W={name}/T=1/L=1/X={i + 1}/Y={i + 1} {yn}, Y wave=({en},{en})")
    C.append(f"DoWindow/F {name}")
    for cmd in C:
        assert is_allowed(cmd), cmd
    write_figure_h5(outdir, name, datasets, C, wn, "string")
    return [C]


def build_ct(outdir):
    """等高線（AppendMatrixContour / ModifyContour）が Igor 8.04 で期待どおりに描けるかの試作。
    画像の上に、フィット結果のような等高線を重ねる図（要望の使い方）と、色テーブル・塗り・ラベルの変種。"""
    os.makedirs(outdir, exist_ok=True)
    nx, ny = 60, 50
    x = np.linspace(-3, 3, nx)
    y = np.linspace(-2, 2, ny)
    X, Y = np.meshgrid(x, y)
    Z = np.exp(-(X**2 + Y**2) / 2) + 0.5 * np.exp(-((X - 1.5)**2 + (Y + 0.5)**2) / 0.5)   # (ny, nx)
    rng = np.random.default_rng(1)
    data = Z + 0.05 * rng.normal(size=Z.shape)
    xe = np.linspace(x[0] - (x[1] - x[0]) / 2, x[-1] + (x[1] - x[0]) / 2, nx + 1)
    ye = np.linspace(y[0] - (y[1] - y[0]) / 2, y[-1] + (y[1] - y[0]) / 2, ny + 1)
    import matplotlib
    cm = np.round(np.asarray(matplotlib.colormaps["viridis"](np.linspace(0, 1, 256)))[:, :3] * 65535).astype("<f8")
    levels = np.linspace(0.15, 1.05, 7)
    variants = {
        "ct01_lines_k": dict(mod=["rgbLines=(0,0,0)", "labels=0"], lsize=1.5),
        "ct02_lines_cmap": dict(mod=["ctabLines={0.15,1.05,@CT@,0}", "labels=0"], lsize=1.5),
        "ct03_lines_label": dict(mod=["rgbLines=(65535,0,0)", "labels=3", "labelFSize=9"], lsize=1.0),
        "ct04_filled": dict(mod=["fill=1", "cTabFill={0.15,1.05,@CT@,0}", "labels=0"], lsize=0),
        "ct05_default": dict(mod=[], lsize=None),
    }
    out = []
    for name, v in variants.items():
        zn, xn, yn, ln, cn = f"{name}_c0_z", f"{name}_c0_x", f"{name}_c0_y", f"{name}_c0_lv", f"{name}_c0_ct"
        izn, ixe, iye = f"{name}_i0_z", f"{name}_i0_xe", f"{name}_i0_ye"
        ds = {zn: np.ascontiguousarray(Z.T), xn: x, yn: y, ln: levels, cn: cm, izn: np.ascontiguousarray(data.T),
              ixe: xe, iye: ye}
        W, H = 340, 260
        C = [f"Redimension/U/W {cn}", f"DoWindow/K {name}", f"Display/N={name}/W=(40,40,{40 + W},{40 + H})",
             f"AppendImage/W={name} {izn} vs {{{ixe},{iye}}}",
             f"ModifyImage/W={name} {izn} ctab={{-0.2,1.2,Grays,0}}",
             f"AppendMatrixContour/W={name} {zn} vs {{{xn},{yn}}}"]
        mods = [m.replace("@CT@", cn) for m in v["mod"]]
        if mods:
            C.append(f"ModifyContour/W={name} {zn}, manLevels={ln}," + ",".join(mods) if v["mod"] else "")
        if v["lsize"] is not None:
            C.append(f"ModifyGraph/W={name} lSize={v['lsize']}")
        C += [f"ModifyGraph/W={name} margin(left)=40,margin(bottom)=36,margin(top)=14,margin(right)=14",
              f"ModifyGraph/W={name} gfSize=10,width=270,height=200", f'ModifyGraph/W={name} font="Arial"',
              f"ModifyGraph/W={name} tick=2,mirror=1,standoff=0",
              f"SetAxis/W={name} bottom -3,3", f"SetAxis/W={name} left -2,2",
              f'Label/W={name} bottom "x"', f'Label/W={name} left "y"', f"DoWindow/F {name}"]
        C = [cmd for cmd in C if cmd]
        for cmd in C:
            assert is_allowed(cmd), cmd
        write_figure_h5(outdir, name, ds, C, list(ds), "string")
        out.append(C)
    return out


def build_lblpos(outdir):
    """x 軸ラベルの位置: 文字サイズ × 目盛りの向き × 軸の種類 × ラベル（普通・上付き）× lblPos。"""
    os.makedirs(outdir, exist_ok=True)
    out = []
    for gf, tick, lg, sup, lp in itertools.product((10, 12, 14), (0, 2), (False, True), (False, True),
                                                   (0, 12, 16, 20, 24, 28, 32)):
        name = f"k{gf}t{tick}{'l' if lg else 'n'}{'s' if sup else 'p'}_{lp}"
        lab = "Q [nm\\\\S-1\\\\M]" if sup else "Q [nm]"
        extra = []
        if lg:
            extra += ["logLTrip(bottom)=0.5", "logLTrip(left)=0.05"]  # 軸の最小値より大きくして、指数表記にする
        if lp:
            extra.append(f"lblPos(bottom)={lp}")
        extra = [f"ModifyGraph/W={name} " + ",".join(extra)] if extra else []
        xr = (0.1, 10) if lg else (0, 5)
        out.append(_fig(name, outdir, lg, lg, xr, (1e-2, 1) if lg else (0, 1), extra, gf=gf, tick=tick,
                        label_x=lab, margins=(50, 80, 14, 14)))
    return out


if __name__ == "__main__":
    what, out = sys.argv[1], sys.argv[2]
    n = len({"trip": build_trip, "lblpos": build_lblpos, "lbl": build_lbl, "ls": build_ls, "eb": build_eb, "ct": build_ct}[what](out))
    print(f"{n} figures -> {out}")
