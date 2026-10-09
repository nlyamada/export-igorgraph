"""
gallery.py
==========

再現度チェック用のギャラリー。機能を網羅した図（g 系列）と、書式の見本（p）、較正用（v）、マーカー・線種の見本（c）を作り、それぞれ
    gallery/<name>.h5          export_igor の出力（実データ + 埋め込みの描画命令）
    gallery/mpl/<name>.png     matplotlib で描いた基準画像
    gallery/expected.json      各図の期待値（実行される命令、警告）
を出す。Igor 側は EIG_Gallery.ipf の RunGallery() が、全 .h5 を LoadPythonFigure で描き、
グラフの読み戻し（igor_audit.txt）と PNG（<name>_igor.png）を保存する。

    python gallery.py [出力ディレクトリ]      # 既定: ./gallery
"""

from __future__ import annotations

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors as mcolors

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export_igorgraph.mpl_to_igor import export_igor

FIGSIZE = (4.0, 3.0)


def _rng(seed=0):
    return np.random.default_rng(seed)


def _fig():
    # constrained: 軸ラベル・目盛りラベルが収まるように、matplotlib が余白を決める（既定の余白だと、ラベルが図の外にはみ出す）
    return plt.subplots(figsize=FIGSIZE, layout="constrained")


def g25_tick_in():
    """目盛りが内向きの matplotlib の図（style の tick="mpl" で Igor の向きも内向きになる）。"""
    fig, ax = _fig()
    x = np.linspace(0, 6, 40)
    ax.plot(x, np.sin(x), "-", color="k", lw=1.5)
    ax.tick_params(direction="in", top=True, right=True)
    ax.set_xlabel(r"$Q_z$ [nm$^{-1}$]")
    ax.set_ylabel(r"$\Delta\rho$ [$\mu$m$^{-2}$]")
    return fig, {}


def g01_line():
    fig, ax = _fig()
    x = np.linspace(0, 10, 50)
    ax.plot(x, np.sin(x), "-", color="tab:blue", lw=1.5, label="sin")
    ax.plot(x, np.cos(x), "-", color="tab:red", lw=2.5, label="cos")
    ax.set_xlabel(r"$x$ [a.u.]")
    ax.set_ylabel(r"$y$ [a.u.]")
    ax.legend(loc="upper left")
    return fig, {}


def g02_markers():
    fig, ax = _fig()
    x = np.arange(1, 8.0)
    ax.plot(x, x, "o", color="tab:blue", mfc="none", ms=6, label="open")
    ax.plot(x, x + 2, "o", color="tab:green", ms=6, label="filled")
    ax.plot(x, x + 4, "o", color="tab:red", mfc="white", ms=9, label="white face")
    ax.set_xlabel(r"$x$ [a.u.]")
    ax.set_ylabel(r"$y$ [a.u.]")
    ax.legend(loc="upper left", frameon=False)
    return fig, {}


def g03_err_ysym():
    fig, ax = _fig()
    x = np.arange(1, 9.0)
    ax.errorbar(x, x**1.5, yerr=1.5, fmt="o", color="k", ms=4, capsize=3, elinewidth=1.0, label="data")
    ax.set_xlabel(r"$x$ [a.u.]")
    ax.set_ylabel(r"$y$ [a.u.]")
    ax.legend(loc="upper left", frameon=False)
    return fig, {}


def g04_err_yasym():
    fig, ax = _fig()
    x = np.arange(1, 9.0)
    y = x**1.5
    ax.errorbar(x, y, yerr=(0.3 * y, 0.1 * y), fmt="s", color="tab:blue", ecolor="tab:red", ms=5, capsize=2,
                elinewidth=1.5, label="asym")
    ax.set_xlabel(r"$x$ [a.u.]")
    ax.set_ylabel(r"$y$ [a.u.]")
    ax.legend(loc="upper left", frameon=False)
    return fig, {}


def g05_err_xy():
    fig, ax = _fig()
    x = np.arange(1, 8.0)
    ax.errorbar(x, 2 * x, xerr=0.3 * np.ones_like(x), yerr=1.0 + 0.2 * x, fmt="o", color="tab:purple", ms=5,
                capsize=2, label="xy")
    ax.set_xlabel(r"$x$ [a.u.]")
    ax.set_ylabel(r"$y$ [a.u.]")
    ax.legend(loc="lower right", frameon=False)
    return fig, {}


def g06_loglog():
    fig, ax = _fig()
    rng = _rng(3)
    q = np.logspace(-1, 1, 25)
    R = np.exp(-0.6 * q) + 1e-3
    ax.errorbar(q, R * (1 + 0.02 * rng.normal(size=q.size)), yerr=(0.05 * R, 0.08 * R), fmt="o", color="k", ms=4,
                capsize=2, elinewidth=0.8, label="data")
    ax.plot(q, R, "-", color="tab:red", lw=1.5, label="fit")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"$Q$ [nm$^{-1}$]")
    ax.set_ylabel("Reflectivity")
    ax.set_xlim(0.1, 10)
    ax.legend(loc="upper right", frameon=False)
    return fig, {}


def g07_semilogx():
    fig, ax = _fig()
    x = np.logspace(-2, 2, 40)
    ax.semilogx(x, 1 / (1 + x**2), "-", color="tab:orange", lw=2)
    ax.set_xlim(1e-2, 1e2)
    ax.set_ylim(0, 1.1)
    ax.set_xlabel(r"$\omega$ [rad s$^{-1}$]")
    ax.set_ylabel(r"$|H|$ [a.u.]")
    return fig, {}


def g08_semilogy():
    fig, ax = _fig()
    t = np.linspace(0, 5, 40)
    ax.semilogy(t, np.exp(-t), "-", color="tab:green", lw=2)
    ax.semilogy(t, 0.1 * np.exp(-0.3 * t), "-", color="tab:purple", lw=1)
    ax.set_xlabel(r"$t$ [s]")
    ax.set_ylabel(r"$I$ [a.u.]")
    return fig, {}


def g09_inverted():
    fig, ax = _fig()
    x = np.linspace(0, 5, 30)
    ax.plot(x, x**2, "-", color="k", lw=1.5)
    ax.set_xlim(5, 0)
    ax.set_ylim(0, 30)
    ax.set_xlabel(r"$x$ [a.u.]")
    ax.set_ylabel(r"$y$ [a.u.]")
    return fig, {}


def g10_legend_lb():
    fig, ax = _fig()
    x = np.linspace(0, 6, 40)
    for k, col in enumerate(("tab:blue", "tab:orange", "tab:green")):
        ax.plot(x, np.sin(x + k), "-", color=col, lw=1.5, label=f"s{k}")
    ax.set_xlabel(r"$x$ [a.u.]")
    ax.set_ylabel(r"$y$ [a.u.]")
    ax.legend(loc="lower left", frameon=True)
    return fig, {}


def g11_legend_rc():
    fig, ax = _fig()
    x = np.linspace(0, 6, 40)
    ax.plot(x, x, "-", color="tab:red", lw=1.5, label="linear")
    ax.plot(x, x**2 / 6, "--", color="tab:blue", lw=1.5, label="quad")
    ax.set_xlabel(r"$x$ [a.u.]")
    ax.set_ylabel(r"$y$ [a.u.]")
    ax.legend(loc="center right", frameon=False)
    return fig, {}


def g12_labels_math():
    fig, ax = _fig()
    x = np.linspace(0.1, 5, 40)
    ax.plot(x, 1 / x, "-", color="k", lw=1.5, label=r"$I$($Q_z$)")
    ax.set_xlabel(r"$Q_z$ [nm$^{-1}$]")
    ax.set_ylabel(r"$\Delta\rho$ [$\mu$m$^{-2}$]")
    ax.legend(loc="upper right", frameon=False)
    return fig, {}


def g13_scatter():
    fig, ax = _fig()
    rng = _rng(1)
    ax.scatter(rng.normal(size=40), rng.normal(size=40), s=25, color="tab:blue", label="a")
    ax.scatter(rng.normal(1, 0.5, size=30), rng.normal(1, 0.5, size=30), s=36, facecolors="none",
               edgecolors="tab:red", label="b")
    ax.set_xlabel(r"$x$ [a.u.]")
    ax.set_ylabel(r"$y$ [a.u.]")
    ax.legend(loc="upper left", frameon=False)
    return fig, {}


def g14_grid():
    fig, ax = _fig()
    x = np.linspace(0, 6, 40)
    ax.plot(x, np.sin(x), "-", color="k", lw=1.5)
    ax.grid(True)
    ax.set_xlabel(r"$x$ [a.u.]")
    ax.set_ylabel(r"$y$ [a.u.]")
    return fig, {}


def g15_many():
    fig, ax = _fig()
    x = np.linspace(0, 10, 60)
    cm = plt.get_cmap("tab10")
    for k in range(10):
        ax.plot(x, np.sin(x + 0.5 * k) + 0.3 * k, "-", color=cm(k), lw=1.2)
    ax.set_xlabel(r"$x$ [a.u.]")
    ax.set_ylabel(r"$y$ [a.u.]")
    return fig, {}


def g16_big():
    fig, ax = _fig()
    rng = _rng(7)
    x = np.linspace(0, 100, 50000)
    ax.plot(x, np.exp(-x / 30) * (1 + 0.1 * rng.normal(size=x.size)), "-", color="k", lw=0.5)
    ax.set_yscale("log")
    ax.set_xlabel(r"$t$ [s]")
    ax.set_ylabel(r"$I$ [a.u.]")
    return fig, {}


def _asym_array():
    i, j = np.meshgrid(np.arange(6), np.arange(10), indexing="ij")
    A = (10 * i + j + 1).astype(float)
    A[0, 0] = 200.0  # 左上の目印
    A[-1, -1] = 1.0  # 右下
    return A


def g17_img_upper():
    fig, ax = _fig()
    im = ax.imshow(_asym_array(), cmap="viridis")
    fig.colorbar(im, ax=ax, label="Intensity [a.u.]")
    ax.set_xlabel(r"$Q_x$ [nm$^{-1}$]")
    ax.set_ylabel(r"$Q_z$ [nm$^{-1}$]")
    return fig, {}


def g18_img_lower():
    fig, ax = _fig()
    ax.imshow(_asym_array(), origin="lower", extent=[0, 10, 0, 6], aspect="auto", cmap="gray")
    ax.set_xlabel(r"$Q_x$ [nm$^{-1}$]")
    ax.set_ylabel(r"$Q_z$ [nm$^{-1}$]")
    return fig, {}


def g19_img_logmask():
    fig, ax = _fig()
    nx, ny = 40, 30
    qx = np.linspace(-1.0, 1.0, nx + 1)
    qz = np.linspace(0.0, 1.5, ny + 1)
    X, Z = np.meshgrid(0.5 * (qx[1:] + qx[:-1]), 0.5 * (qz[1:] + qz[:-1]))
    I = 1e4 * np.exp(-((X - 0.4) ** 2 / 0.02 + (Z - 0.5) ** 2 / 0.05)) + 1e2 * np.exp(-Z) + 5.0
    I[Z > 1.0] *= 0.1
    I[:3, :6] = 1e5
    I[-4:, -3:] = np.nan
    qm = ax.pcolormesh(qx, qz, I, norm=mcolors.LogNorm(vmin=1, vmax=1e5), cmap="turbo")
    ax.set_xlabel(r"$Q_x$ [nm$^{-1}$]")
    ax.set_ylabel(r"$Q_z$ [nm$^{-1}$]")
    fig.colorbar(qm, ax=ax, label="Intensity [a.u.]")
    return fig, {}


def g20_mesh_nonuni():
    fig, ax = _fig()
    xe = np.array([0, 1, 3, 6, 10.0])
    ye = np.array([0, 2, 3, 7.0])
    A = np.arange(1.0, 13).reshape(3, 4)
    qm = ax.pcolormesh(xe, ye, A, cmap="plasma", vmin=1, vmax=12)
    fig.colorbar(qm, ax=ax, label="Counts [a.u.]")
    ax.set_xlabel(r"$x$ [mm]")
    ax.set_ylabel(r"$y$ [mm]")
    return fig, {}


def g21_img_overlay():
    fig, ax = _fig()
    ax.imshow(_asym_array(), cmap="gray")
    ax.plot([0, 9], [0, 5], "-", color="w", lw=2, label="path")
    ax.set_xlabel(r"$x$ [pixel]")
    ax.set_ylabel(r"$y$ [pixel]")
    return fig, {"ctab": ("Rainbow", 1)}


def g22_linestyles():
    fig, ax = _fig()
    x = np.linspace(0, 6, 40)
    for st, col in (("-", "k"), ("--", "tab:red"), (":", "tab:blue"), ("-.", "tab:green")):
        ax.plot(x, np.sin(x + 0.4 * len(st)) + 1.2 * ["-", "--", ":", "-."].index(st), st, color=col, lw=1.5, label=f"'{st}'")
    ax.set_xlabel(r"$x$ [a.u.]")
    ax.set_ylabel(r"$y$ [a.u.]")
    ax.legend(loc="upper right", frameon=False)
    return fig, {}


def g23_img_extup():
    fig, ax = _fig()
    im = ax.imshow(_asym_array(), origin="upper", extent=[0, 10, 0, 6], cmap="magma")
    fig.colorbar(im, ax=ax, label="Intensity [a.u.]")
    ax.set_xlabel(r"$Q_x$ [nm$^{-1}$]")
    ax.set_ylabel(r"$Q_z$ [nm$^{-1}$]")
    return fig, {}


def g24_marker_var():
    fig, ax = _fig()
    x = np.arange(1, 7.0)
    for k, (mk, col) in enumerate((("o", "k"), ("s", "tab:blue"), ("^", "tab:red"), ("v", "tab:green"),
                                    ("D", "tab:purple"), ("x", "tab:orange"), ("+", "tab:brown"), ("*", "tab:pink"))):
        ax.plot(x, x + 1.4 * k, mk, color=col, ms=6, label=f"'{mk}'")
    ax.set_xlabel(r"$x$ [a.u.]")
    ax.set_ylabel(r"$y$ [a.u.]")
    ax.legend(loc="upper left", frameon=False, ncol=2)
    return fig, {}


def _blob(x=None, y=None):
    x = np.linspace(-3, 3, 60) if x is None else x
    y = np.linspace(-2, 2, 50) if y is None else y
    X, Y = np.meshgrid(x, y)
    Z = np.exp(-(X**2 + Y**2) / 2) + 0.5 * np.exp(-((X - 1.5)**2 + (Y + 0.5)**2) / 0.5)
    return x, y, X, Y, Z


def g26_contour_fit():
    """2次元データ（画像）の上に、フィット結果を等高線で重ねる（元の Z は contour の呼び出しの瞬間に保存される）。"""
    fig, ax = _fig()
    x, y, X, Y, Z = _blob()
    data = Z + 0.06 * _rng(1).normal(size=Z.shape)
    ax.imshow(data, extent=(-3, 3, -2, 2), origin="lower", cmap="gray", aspect="auto", vmin=-0.2, vmax=1.3)
    ax.contour(X, Y, Z, levels=np.linspace(0.15, 1.05, 7), colors="tab:red", linewidths=1.2)
    ax.set_xlabel(r"$Q_x$ [nm$^{-1}$]")
    ax.set_ylabel(r"$Q_z$ [nm$^{-1}$]")
    return fig, {}


def g27_contour_cmap():
    """色テーブルの線と、等高線のラベル（clabel）。1次元の座標で渡す形。"""
    fig, ax = _fig()
    x, y, X, Y, Z = _blob()
    cs = ax.contour(x, y, Z, levels=np.linspace(0.15, 1.05, 7), cmap="viridis")
    ax.clabel(cs, fontsize=8)
    ax.set_xlabel(r"$x$ [a.u.]")
    ax.set_ylabel(r"$y$ [a.u.]")
    return fig, {}


def g28_contourf():
    fig, ax = _fig()
    x, y, X, Y, Z = _blob()
    ax.contourf(X, Y, Z, levels=np.linspace(0.0, 1.05, 8), cmap="viridis")
    ax.set_xlabel(r"$x$ [a.u.]")
    ax.set_ylabel(r"$y$ [a.u.]")
    return fig, {}


G_BUILDERS = [
    g01_line, g02_markers, g03_err_ysym, g04_err_yasym, g05_err_xy, g06_loglog, g07_semilogx, g08_semilogy,
    g09_inverted, g10_legend_lb, g11_legend_rc, g12_labels_math, g13_scatter, g14_grid, g15_many, g16_big,
    g17_img_upper, g18_img_lower, g19_img_logmask, g20_mesh_nonuni, g21_img_overlay, g22_linestyles,
    g23_img_extup, g24_marker_var, g25_tick_in, g26_contour_fit, g27_contour_cmap, g28_contourf,
]

# 系列: (名前, 図を作る関数, export_igor に渡す引数)
#   g…  全機能。matplotlib の大きさ・文字サイズ・Figure = ウィンドウで書き出す（use_mpl_size=True）
#   p…  preset の書式の見本
#   v…  較正用の図: x 軸ラベルの位置（v01〜v04）、カラースケールの配置（v05〜v09）の比較
#   c…  Igor のマーカー番号・線種番号の見本（charts.py）
SERIES = [(f.__name__, f, {"use_mpl_size": True}) for f in G_BUILDERS]
SERIES += [
    ("p01_line", g01_line, {}),
    ("p02_loglog", g06_loglog, {}),
    ("p03_img", g17_img_upper, {}),
    ("p04_labels", g12_labels_math, {}),
    # 軸ラベルの配置（目盛りの向き=内向き・対数軸・上付きの組み合わせ。preset の書式で、重ならないことを見る）
    ("v01_lin_plain", g01_line, {}),
    ("v02_lin_sup", g12_labels_math, {}),
    ("v03_log_sup", g06_loglog, {}),
    ("v04_log_semilogx", g07_semilogx, {}),
    # カラースケール（既定の文字・lblMargin なし）の配置
    ("v05_cs_preset", g17_img_upper, {"style": {"cs_mode": "preset"}}),
    ("v06_cs_outside", g17_img_upper, {"style": {"cs_mode": "outside"}}),
    ("v07_cs_mpl", g17_img_upper, {"use_mpl_size": True}),
    ("v08_cs_nobox", g17_img_upper, {"style": {"cs_mode": "outside", "cs_box": False}}),
    ("v09_cs_h90", g17_img_upper, {"style": {"cs_mode": "outside", "cs_height_pct": 90}}),
    # 主要な設定の指定（style=）: グリッド・フォント（gFont）・プロット領域のサイズ・目盛り・mirror・standoff
    ("v12_grid", g01_line, {"style": {"grid": {"bottom": 2, "left": 1}, "grid_rgb": "tab:blue"}}),
    ("v13_font_times", g01_line, {"style": {"font": "Times New Roman"}}),
    ("v14_size_tick", g01_line, {"style": {"width": 300, "height": 150, "tick": 0, "mirror": 0, "standoff": 1}}),
    # 目盛りの向きを matplotlib に合わせる（tick="mpl"）
    ("v10_tick_mpl", g25_tick_in, {"use_mpl_size": True, "style": {"tick": "mpl"}}),
    ("v11_tick_out", g01_line, {"use_mpl_size": True, "style": {"tick": 0}}),
]

# 基準画像の文字は、Arial と文字幅が同じ Liberation Sans にする（Igor 側は Arial）
# Windows では Liberation Sans が無いことが多いので、そのときは Arial そのものを使う
def _rc_font():
    from matplotlib import font_manager
    names = {f.name for f in font_manager.fontManager.ttflist}
    if "Liberation Sans" in names or "Arial" not in names:
        return "Liberation Sans", "Liberation Mono"
    return "Arial", "Courier New"


_SANS, _MONO = _rc_font()
RC = {"font.family": _SANS, "mathtext.fontset": "custom", "mathtext.rm": _SANS,
      "mathtext.it": f"{_SANS}:italic", "mathtext.bf": f"{_SANS}:bold",
      "mathtext.cal": _SANS, "mathtext.sf": _SANS, "mathtext.tt": _MONO}


def build_all(outdir: str, png: bool = True, charts: bool = True):
    """全図を書き出す。(名前, 報告) を順に返す。報告には .commands, .warnings, .n_traces, .n_images がある。"""
    os.makedirs(outdir, exist_ok=True)
    if png:
        os.makedirs(os.path.join(outdir, "mpl"), exist_ok=True)
    for name, fn, kw in SERIES:
        with plt.rc_context(RC):
            fig, kw0 = fn()
            rep = export_igor(fig, outdir, name, **{**kw0, **kw})
            if png:
                fig.savefig(os.path.join(outdir, "mpl", f"{name}.png"), dpi=100, bbox_inches="tight")
            plt.close(fig)
        yield name, rep
    if charts:
        import charts as _charts
        from types import SimpleNamespace
        for name, cmds in _charts.build_charts(outdir):
            yield name, SimpleNamespace(commands=cmds, warnings=[], n_traces=len(cmds), n_images=0)


def main(argv=None):
    if isinstance(argv, (str, os.PathLike)):
        argv = [os.fspath(argv)]
    out = (argv or sys.argv[1:] or ["gallery"])[0]
    expected = {}
    for name, rep in build_all(out):
        expected[name] = {"commands": rep.commands, "warnings": rep.warnings,
                          "n_traces": rep.n_traces, "n_images": rep.n_images}
        print(f"{name:20s} traces={rep.n_traces} images={rep.n_images} commands={len(rep.commands)} "
              f"warnings={len(rep.warnings)}")
    with open(os.path.join(out, "expected.json"), "w", encoding="utf-8") as f:
        json.dump(expected, f, ensure_ascii=False, indent=1)
    print(f"-> {out}/ ({len(expected)} figures)")


if __name__ == "__main__":
    main()
