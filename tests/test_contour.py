"""等高線（元の Z を使う方式）のテスト。python test_contour.py"""
import os
import re
import sys
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from export_igorgraph import mpl_to_igor as m
from export_igorgraph import eig_allowlist as al

results = []


def check(name, cond, detail=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  [{str(detail)[:300]}]"))


x = np.linspace(-3, 3, 60)
y = np.linspace(-2, 2, 50)
X, Y = np.meshgrid(x, y)
Z = np.exp(-(X**2 + Y**2) / 2) + 0.5 * np.exp(-((X - 1.5)**2 + (Y + 0.5)**2) / 0.5)


def export(build, **kw):
    fig, ax = plt.subplots(figsize=(4, 3), layout="constrained")
    build(ax)
    with tempfile.TemporaryDirectory() as d:
        rep = m.export_igor(fig, d, "t", use_mpl_size=True, **kw)
        import h5py
        with h5py.File(os.path.join(d, "t.h5"), "r") as f:
            data = {k: np.array(f[k]) for k in f if not k.startswith("igor_")}
    plt.close(fig)
    assert all(al.is_allowed(c) for c in rep.commands), [c for c in rep.commands if not al.is_allowed(c)][:2]
    return rep, data


def main():
    # --- 元データの取得 ---
    for label, call in (
        ("X, Y, Z（meshgrid）", lambda ax: ax.contour(X, Y, Z, levels=5)),
        ("1次元の x, y, Z", lambda ax: ax.contour(x, y, Z, levels=5)),
        ("Z だけ（座標は 0..n-1）", lambda ax: ax.contour(Z, levels=5)),
        ("levels 付き", lambda ax: ax.contour(X, Y, Z, [0.2, 0.5, 0.8])),
        ("contourf", lambda ax: ax.contourf(X, Y, Z, levels=5)),
    ):
        rep, d = export(call)
        zz = d["t_c0_z"]
        check(f"等高線の元データ: {label}: Z がそのまま Wave に入る（形 (nx, ny) = {Z.T.shape}）",
              rep.n_contours == 1 and zz.shape == Z.T.shape and np.array_equal(zz, Z.T), (rep.warnings, zz.shape))
    rep, d = export(lambda ax: ax.contour(Z, levels=5))
    check("Z だけのとき、座標は 0..n-1", np.array_equal(d["t_c0_x"], np.arange(Z.shape[1])) and np.array_equal(d["t_c0_y"], np.arange(Z.shape[0])))
    rep, d = export(lambda ax: ax.contour(X, Y, Z, [0.2, 0.5, 0.8]))
    check("レベルは Wave（manLevels）で渡す", np.allclose(d["t_c0_lv"], [0.2, 0.5, 0.8]))

    # --- 命令 ---
    rep, d = export(lambda ax: ax.contour(X, Y, Z, levels=[0.2, 0.6], colors="r", linewidths=2))
    cs = rep.commands
    check("命令: AppendMatrixContour → ModifyContour（レベル Wave・線の色・ラベルなし）→ lSize",
          "AppendMatrixContour/W=t t_c0_z vs {t_c0_x,t_c0_y}" in cs
          and "ModifyContour/W=t t_c0_z, manLevels=t_c0_lv,rgbLines=(65535,0,0),labels=0" in cs
          and "ModifyGraph/W=t lSize=2" in cs, cs)
    rep, d = export(lambda ax: ax.contour(X, Y, Z, levels=5, cmap="viridis"))
    mc = next(c for c in rep.commands if c.startswith("ModifyContour"))
    check("色テーブル: ctabLines={vmin,vmax,<色テーブル Wave>,0} と、256x3 の色テーブル Wave",
          re.search(r"ctabLines=\{[0-9.e+-]+,[0-9.e+-]+,t_c0_ct,0\}", mc) and d["t_c0_ct"].shape == (256, 3)
          and "Redimension/U/W t_c0_ct" in rep.commands, mc)
    rep, d = export(lambda ax: ax.contourf(X, Y, Z, levels=5, cmap="viridis"))
    mc = next(c for c in rep.commands if c.startswith("ModifyContour"))
    check("塗り: fill=1・cTabFill、線は消す (lSize=0)", "fill=1" in mc and "cTabFill=" in mc and "ModifyGraph/W=t lSize=0" in rep.commands, mc)
    rep, d = export(lambda ax: ax.clabel(ax.contour(X, Y, Z, levels=5, colors="k")))
    mc = next(c for c in rep.commands if c.startswith("ModifyContour"))
    check("clabel: labels=3 と文字サイズ。ラベルの文字は『未対応のテキスト』の警告にしない",
          "labels=3,labelFSize=" in mc and not any("texts" in w for w in rep.warnings), (mc, rep.warnings))
    rep, d = export(lambda ax: (ax.imshow(Z, extent=(-3, 3, -2, 2), origin="lower"), ax.contour(X, Y, Z, levels=4, colors="w")))
    cs = rep.commands
    check("画像の上に等高線: AppendImage の後に AppendMatrixContour（等高線が上に描かれる）",
          rep.n_images == 1 and rep.n_contours == 1
          and next(i for i, c in enumerate(cs) if c.startswith("AppendImage")) < next(i for i, c in enumerate(cs) if c.startswith("AppendMatrixContour")), cs)
    check("軸は SetAxis で固定（等高線だけの図でも）", any(c.startswith("SetAxis/W=t bottom") for c in rep.commands))

    # --- contour_data の明示 ---
    def other(ax):
        ax.contour(X, Y, np.hypot(X, Y), levels=4, colors="b")
    rep, d = export(other, contour_data=(x, y, Z))
    check("contour_data=(X, Y, Z) を渡すと、そちらを使う", np.array_equal(d["t_c0_z"], Z.T))
    rep, d = export(other, contour_data={})  # 空の辞書: 保存されたデータを使う
    check("contour_data が空なら、保存された元データを使う", np.array_equal(d["t_c0_z"], np.hypot(X, Y).T))

    # --- 保存されない場合 ---
    m.uninstall_contour_capture()
    try:
        fig, ax = plt.subplots(layout="constrained")
        ax.contour(X, Y, Z, levels=4)
        ax.plot([0, 1], [0, 1])
        with tempfile.TemporaryDirectory() as d_:
            rep = m.export_igor(fig, d_, "t", use_mpl_size=True)
        plt.close(fig)
        check("元データが無い等高線は、理由を示す警告を出してスキップ（ほかの図は出力）",
              rep.n_contours == 0 and rep.n_traces == 1 and any("contour_data" in w for w in rep.warnings), rep.warnings)
    finally:
        m.install_contour_capture()

    # --- 格子・向き ---
    zd = Z[::-1, ::-1]
    rep, d = export(lambda ax: ax.contour(x[::-1], y[::-1], zd, levels=4))
    check("座標が減少していても、単調増加に並べ替え、Z も並べ替える", np.all(np.diff(d["t_c0_x"]) > 0) and np.all(np.diff(d["t_c0_y"]) > 0)
          and np.array_equal(d["t_c0_z"], Z.T))
    xs = np.linspace(0, 1, 5)
    ys = np.linspace(0, 1, 4)
    Xn, Yn = np.meshgrid(xs, ys)
    Xn = Xn + 0.1 * Yn   # 傾いた（矩形でない）格子
    fig, ax = plt.subplots()
    ax.contour(Xn, Yn, np.arange(20.0).reshape(4, 5), levels=3)
    with tempfile.TemporaryDirectory() as d_:
        try:
            m.export_igor(fig, d_, "t")
            check("矩形でない格子は、書き出せる図が無いのでエラー", False)
        except ValueError as e:
            check("矩形でない格子は、書き出せる図が無いのでエラー（警告に理由）", "ありません" in str(e))
    plt.close(fig)
    check("等高線の Wave 名は 31 文字以内", all(len(n) <= 31 for n in d))

    # --- 登録 ---
    fig, ax = plt.subplots()
    cs = ax.contour(X, Y, Z, levels=3)
    check("包んだ関数: ContourSet に _eig_xyz と、Axes への登録", hasattr(cs, "_eig_xyz") and cs in ax._eig_contours)
    cs.remove()
    check("cs.remove() した等高線は、書き出さない", m._contour_sets(ax) == [])
    plt.close(fig)
    print(f"\n{sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
