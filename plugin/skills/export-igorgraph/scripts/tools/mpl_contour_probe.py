"""
mpl_contour_probe.py
====================

matplotlib のバージョンごとに、等高線の元データ (X, Y, Z) を取り出す仕組みが使えるかを調べる検査。
他のファイルに依存しない（check_mpl_versions.py が、バージョンごとの仮想環境で実行して JSON を受け取る）。

調べること
  1. 内部関数 QuadContourSet._contour_args があるか、引数の形、呼ばれているか（内部の仕様。バージョンで変わりうる）
  2. 公開 API（Axes.contour / contourf）を包んで、引数から (X, Y, Z) を取る方法が、全部の呼び方で元の Z と一致するか
  3. export_igor が使う ContourSet の属性（levels, filled, cmap, norm, colors, 線幅 …）が取れるか
"""
import inspect
import json
import sys

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import contour as mc
from matplotlib.axes import Axes
from matplotlib.collections import Collection


def args_to_xyz(args):
    """Axes.contour([X, Y,] Z, [levels]) の位置引数から (X, Y, Z) を取る（公開された呼び出し形のみ）。"""
    n = len(args)
    if n in (1, 2):
        Z = np.ma.asarray(args[0])
        X, Y = np.arange(Z.shape[1]), np.arange(Z.shape[0])
    elif n in (3, 4):
        X, Y, Z = np.asarray(args[0]), np.asarray(args[1]), np.ma.asarray(args[2])
    else:
        return None
    return X, Y, Z


def main():
    out = {"matplotlib": matplotlib.__version__, "python": sys.version.split()[0], "numpy": np.__version__}
    # --- 1. 内部関数 ---
    f = getattr(mc.QuadContourSet, "_contour_args", None)
    out["private__contour_args"] = None if f is None else str(inspect.signature(f))
    try:
        src = inspect.getsource(mc.QuadContourSet._process_args)
        out["private__process_args_calls__contour_args"] = "_contour_args" in src
    except Exception as e:  # noqa
        out["private__process_args_calls__contour_args"] = f"?{type(e).__name__}"
    out["ContourSet_is_Collection"] = issubclass(mc.ContourSet, Collection)

    x1 = np.linspace(-3, 3, 7)
    y1 = np.linspace(-2, 2, 5)
    X, Y = np.meshgrid(x1, y1)
    Z = np.exp(-(X**2 + Y**2) / 2)
    Zm = np.ma.masked_where(Z < 0.2, Z)

    # --- 2a. 内部関数を包む方法 ---
    priv = {}
    if f is not None:
        orig = mc.QuadContourSet._contour_args

        def wrapped(self, args, kwargs):
            r = orig(self, args, kwargs)
            self._eig_priv = tuple(np.ma.array(v, copy=True) for v in r[:3])
            return r

        mc.QuadContourSet._contour_args = wrapped
    cases = {
        "contour(X,Y,Z)": lambda ax: ax.contour(X, Y, Z, levels=4),
        "contourf(x1,y1,Z)": lambda ax: ax.contourf(x1, y1, Z, levels=4),
        "contour(Z)": lambda ax: ax.contour(Z, levels=4),
        "contour(Z,levels)": lambda ax: ax.contour(Z, [0.2, 0.5, 0.8]),
        "contour(X,Y,Z,levels)": lambda ax: ax.contour(X, Y, Z, [0.2, 0.5, 0.8]),
        "contour(masked Z)": lambda ax: ax.contour(X, Y, Zm, levels=4),
        "plt.contour(X,Y,Z)": lambda ax: plt.contour(X, Y, Z, levels=4),
    }
    for k, fn in cases.items():
        fig, ax = plt.subplots()
        plt.sca(ax)
        try:
            cs = fn(ax)
            got = getattr(cs, "_eig_priv", None)
            priv[k] = "no-capture" if got is None else bool(np.array_equal(np.ma.filled(got[2], np.nan), np.ma.filled(Zm if "masked" in k else Z, np.nan), equal_nan=True))
        except Exception as e:  # noqa
            priv[k] = f"error:{type(e).__name__}:{e}"
        plt.close(fig)
    if f is not None:
        mc.QuadContourSet._contour_args = orig
    out["private_hook"] = priv

    # --- 2b. 公開 API を包む方法 ---
    pub = {}
    o_contour, o_contourf = Axes.contour, Axes.contourf

    def mk(o):
        def w(self, *args, **kwargs):
            cs = o(self, *args, **kwargs)
            xyz = args_to_xyz(args)
            if xyz is not None:
                cs._eig_pub = tuple(np.ma.array(v, copy=True) for v in xyz)
            return cs
        return w

    Axes.contour, Axes.contourf = mk(o_contour), mk(o_contourf)
    for k, fn in cases.items():
        fig, ax = plt.subplots()
        plt.sca(ax)
        try:
            cs = fn(ax)
            got = getattr(cs, "_eig_pub", None)
            want = Zm if "masked" in k else Z
            if got is None:
                pub[k] = "no-capture"
            else:
                ok = np.array_equal(np.ma.filled(got[2], np.nan), np.ma.filled(want, np.nan), equal_nan=True)
                pub[k] = bool(ok)
        except Exception as e:  # noqa
            pub[k] = f"error:{type(e).__name__}:{e}"
        plt.close(fig)
    Axes.contour, Axes.contourf = o_contour, o_contourf
    out["public_hook"] = pub

    # --- 3. export_igor が使う属性 ---
    attrs = {}
    fig, ax = plt.subplots()
    cs = ax.contour(X, Y, Z, levels=4, cmap="viridis")
    csf = ax.contourf(X, Y, Z, levels=4, cmap="viridis")
    cs1 = ax.contour(X, Y, Z, levels=4, colors="k")
    for nm, c in (("lines_cmap", cs), ("filled_cmap", csf), ("lines_colors", cs1)):
        d = {}
        for a in ("levels", "filled", "norm", "colors", "labelTexts", "colorbar"):
            d[a] = hasattr(c, a)
        for m in ("get_cmap", "get_edgecolor", "get_facecolor", "get_linewidth", "get_linestyle", "get_alpha"):
            try:
                getattr(c, m)()
                d[m] = True
            except Exception as e:  # noqa
                d[m] = f"error:{type(e).__name__}"
        d["in_ax.collections"] = any(c is x for x in ax.collections)
        d["colors_is_None_when_cmap"] = (c.colors is None) if hasattr(c, "colors") else "n/a"
        attrs[nm] = d
    out["attrs"] = attrs
    print("EIG_PROBE_JSON " + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()

