"""
test_mpl_to_igor.py
===================

mpl_to_igor.export_igor (v2: 線 + 2次元画像) の検証。Igor 本体は動かせないので、次を確認する。
    1. .h5 の中身が matplotlib の実データ（x, y, エラー, 画像の向き・端座標・色テーブル）と一致する
    2. .ipf が静的チェックを通る（ASCIIのみ・CRLF・引用符の対応・Wave宣言・参照するWaveがh5にある）
    3. 生成コマンドが想定どおり（対数軸・ErrorBars・AppendImage・ModifyImage・ColorScale など）
    4. 未対応の要素は黙って落とさず、警告に出る。好みのスタイル規則に合わないラベルも警告に出る

実行: python test_mpl_to_igor.py [出力ディレクトリ]
出力ディレクトリを指定すると、デモ図 (fig_demo, fig_demo2) の .h5 / .ipf / _mpl.png を残す。
"""

import os
import re
import sys
import tempfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors as mcolors

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from export_igorgraph import mpl_to_igor as _m
from export_igorgraph.mpl_to_igor import _label_literal


def export_igor(*args, **kw):
    """このテストは .ipf の中身も検査するので、既定で .ipf も出す（本体の既定は h5 のみ）。"""
    kw.setdefault("write_ipf", True)
    return _m.export_igor(*args, **kw)


try:
    import h5py
except ImportError:
    h5py = None
try:
    from minimal_hdf5_reader import MinimalHDF5Reader
except ImportError:
    MinimalHDF5Reader = None

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


def read_h5(path):
    if h5py is not None:
        with h5py.File(path, "r") as f:
            return {k: f[k][()] for k in f}
    r = MinimalHDF5Reader(path)
    return {k: v.data for k, v in r.read_all().items()}


def lint_ipf(path, h5):
    """.ipf の静的チェック。Igor でのコンパイル代わりにはならないが、機械的な誤りは検出できる。"""
    raw = open(path, "rb").read()
    text = raw.decode("ascii")  # 非ASCIIがあれば例外
    problems = []
    if b"\r\n" not in raw or re.search(rb"(?<!\r)\n", raw):
        problems.append("改行が CRLF で統一されていない")
    lines = text.split("\r\n")
    for i, ln in enumerate(lines, 1):
        stripped = re.sub(r'\\\\|\\"', "", ln)  # エスケープ済みの \\ と \" を除く
        if stripped.count('"') % 2:
            problems.append(f"{i}行目: 引用符が対応していない: {ln[:60]}")
        if len(ln) > 400:
            problems.append(f"{i}行目: 400文字を超える長い行")
    text = text.replace("\r\n", "\n")
    declared = set(re.findall(r"^\tWave (\w+)$", text, flags=re.M))
    listed = set(re.findall(r"(\w+);", " ".join(re.findall(r'names \+= "([^"]*)"', text))))
    if declared != listed:
        problems.append("Wave 宣言と names リストが一致しない")
    if not listed <= set(h5):
        problems.append(f".ipf が参照する Wave が h5 に無い: {sorted(listed - set(h5))[:5]}")
    wave_ds = {k for k in h5 if not k.startswith("igor_")}  # igor_* は埋め込みの命令・メタ情報
    if not wave_ds <= listed:
        problems.append(f"h5 にあるが .ipf が読まない Wave: {sorted(wave_ds - listed)[:5]}")
    used = set(re.findall(r"\b(\w+_[ti]\d+_\w+)\b", text))
    if not used <= listed:
        problems.append(f"宣言されていない Wave を使っている: {sorted(used - listed)[:5]}")
    for ct in re.findall(r"Redimension/U/W (\w+)", text):
        if ct not in listed:
            problems.append(f"Redimension の対象 {ct} が読み込まれない")
    for kw in ("Function Make_", "End", "HDF5OpenFile", "HDF5CloseFile", "SetDataFolder saveDF"):
        if kw not in text:
            problems.append(f"'{kw}' が無い")
    # OpenFile: ダイアログ版・パス指定版・失敗メッセージ中の文字列 = 3回。CloseFile: 失敗時と正常時 = 2回
    if text.count("HDF5OpenFile") != 3 or text.count("HDF5CloseFile") != 2:
        problems.append("HDF5OpenFile/CloseFile の数が想定と違う")
    return problems, text


# ============================ 線グラフ（v1 の確認） ==============================
def demo_figure():
    rng = np.random.default_rng(3)
    q = np.logspace(-1, 1, 25)  # nm^-1
    R = np.exp(-0.6 * q) + 1e-3
    dR_lo, dR_hi = 0.05 * R, 0.08 * R  # 非対称
    fig, ax = plt.subplots(figsize=(4, 3.2))
    ax.errorbar(q, R * (1 + 0.02 * rng.normal(size=q.size)), yerr=(dR_lo, dR_hi), fmt="o", color="k",
                ms=4, capsize=2, elinewidth=0.8, label="data")
    ax.plot(q, R, "-", color="tab:red", lw=1.5, label="fit")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel(r"$Q$ [nm$^{-1}$]")
    ax.set_ylabel("Reflectivity")
    ax.set_xlim(0.1, 10)
    ax.legend(loc="upper right", frameon=False)
    return fig, q, R, dR_lo, dR_hi


def test_demo(outdir):
    fig, q, R, lo, hi = demo_figure()
    rep = export_igor(fig, outdir, "fig_demo")
    fig.savefig(os.path.join(outdir, "fig_demo_mpl.png"), dpi=150, bbox_inches="tight")
    print(rep.summary())
    h5 = read_h5(os.path.join(outdir, "fig_demo.h5"))
    check("demo: トレース2本・画像0枚・警告なし", rep.n_traces == 2 and rep.n_images == 0 and not rep.warnings,
          str(rep.warnings))
    check("demo: 実データの x が一致", np.array_equal(h5["fig_demo_t0_x"], q))
    check("demo: 線の y が一致", np.allclose(h5["fig_demo_t1_y"], R))
    check("demo: 非対称エラー(上側=hi, 下側=lo)", np.allclose(h5["fig_demo_t0_eyp"], hi)
          and np.allclose(h5["fig_demo_t0_eyn"], lo))
    probs, text = lint_ipf(os.path.join(outdir, "fig_demo.ipf"), h5)
    check("demo: .ipf 静的チェック", not probs, "; ".join(probs))
    check("demo: 対数軸", "log(bottom)=1" in text and "log(left)=1" in text)
    check("demo: 対数軸の目盛りラベルは指数表記（logLTrip を軸の最小値の 2 倍）",
          "logLTrip(bottom)=0.2" in text and re.search(r"logLTrip\(left\)=[0-9.e+-]+", text))
    check("demo: 軸範囲は両軸とも matplotlib の実際の範囲に固定（x は手動設定の 0.1,10）",
          "SetAxis/W=fig_demo bottom 0.1,10" in text and re.search(r"SetAxis/W=fig_demo left [0-9.e+-]+,[0-9.e+-]+", text))
    check("demo: ErrorBars 非対称", re.search(
        r"ErrorBars/W=fig_demo/T=1/L=0\.8/X=4/Y=4 fig_demo_t0_y, Y wave=\(fig_demo_t0_eyp,fig_demo_t0_eyn\)", text))  # capsize=2 → 全幅 4 pt
    check("demo: 塗り円マーカー(19)と黒", "marker(fig_demo_t0_y)=19" in text and "rgb(fig_demo_t0_y)=(0,0,0)" in text)
    check("demo: 線のみトレース(mode 0, lSize 1.5)", "mode(fig_demo_t1_y)=0" in text and "lSize(fig_demo_t1_y)=1.5" in text)
    check("demo: ラベル = 斜体の変数・立体の添字と指数（斜体 Q・上付き）",
          r'Label/W=fig_demo bottom "\\f02Q\\f00 [nm\\S-1\\M]"' in text, text)
    mpl_order = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
    check("demo: 凡例の並びは matplotlib と同じ(fit→data)", mpl_order == ["fit", "data"], str(mpl_order))
    check("demo: 凡例(枠なし・記号はグラフと同じ大きさ /M=1・右上・\\s(trace))", re.search(
        r'Legend/W=fig_demo/N=legend0/F=0/M=1/A=RT "\\\\s\(fig_demo_t1_y\) fit\\r\\\\s\(fig_demo_t0_y\) data"', text))
    check("demo: preset の書式(幅 226.772, aspect 0.8, tick/mirror/standoff)",
          "width=226.772,height={Aspect,0.8}" in text and "tick=2,mirror=1,standoff=0" in text)
    plt.close(fig)


def test_symmetric_and_xy(tmp):
    fig, ax = plt.subplots()
    x = np.arange(1, 6.0)
    ax.errorbar(x, x**2, xerr=0.1, yerr=0.5 * x, fmt="s", mfc="white", mec="b", color="b", label="sq")
    ax.scatter(x, x, s=25, c="g", label="sc")
    rep = export_igor(fig, tmp, "fig_xy")
    h5 = read_h5(os.path.join(tmp, "fig_xy.h5"))
    probs, text = lint_ipf(os.path.join(tmp, "fig_xy.ipf"), h5)
    check("xy: .ipf 静的チェック", not probs, "; ".join(probs))
    check("xy: 対称エラーは1本のWave", "fig_xy_t1_ex" in h5 and "fig_xy_t1_exp" not in h5
          and np.allclose(h5["fig_xy_t1_ey"], 0.5 * x))
    check("xy: XY モードの ErrorBars", re.search(
        r"ErrorBars/W=fig_xy\S* fig_xy_t1_y, XY wave=\(fig_xy_t1_ex,fig_xy_t1_ex\), wave=\(fig_xy_t1_ey,fig_xy_t1_ey\)", text))
    check("xy: 白塗りの四角は『四角 (5)・不透明』で、警告なし", "marker(fig_xy_t1_y)=5" in text
          and "opaque(fig_xy_t1_y)=1" in text and not any("四角" in w for w in rep.warnings), rep.warnings)
    check("xy: scatter は円マーカーのみ(mode 3)", "mode(fig_xy_t0_y)=3" in text)
    plt.close(fig)


def test_warnings(tmp):
    fig, ax = plt.subplots()
    x = np.linspace(0, 1, 10)
    ax.plot(x, x, "--", color="r", alpha=0.5)
    ax.plot(x, x**2, "^-")
    ax.fill_between(x, 0, x, alpha=0.2)
    ax.text(0.5, 0.5, "note")
    ax.set_title("title")
    ax.set_yscale("symlog")
    ax.twinx()
    rep = export_igor(fig, tmp, "fig_warn")
    w = " | ".join(rep.warnings)
    for key, desc in (("alpha", "alpha"),
                      ("fill_between", "塗り"), ("texts", "テキスト"), ("タイトル", "タイトル"),
                      ("symlog", "symlog"), ("Axes が 2 個", "複数Axes")):
        check(f"警告: {desc}", key in w, w)
    check("破線・三角マーカーは Igor の線種・マーカー番号で再現するので、警告しない（第3回）",
          "線種" not in w and "マーカー '^'" not in w, w)
    plt.close(fig)


def test_misc(tmp):
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.plot([1, 2, 3], [1, 4, 9], "o-", color="k", label="_hidden")
    ax.set_xlabel(r"$Q_z$ [$\mu$m$^{-1}$]")
    ax.grid(True)
    fig.subplots_adjust(left=0.2, right=0.9, bottom=0.15, top=0.9)
    export_igor(fig, tmp, "fig_size", use_mpl_size=True)
    text = open(os.path.join(tmp, "fig_size.ipf")).read()
    check("size: use_mpl_size で margin が matplotlib 由来",
          "margin(left)=72,margin(bottom)=43.2,margin(top)=28.8,margin(right)=36" in text, text)
    check("size: 軸の大きさ = 図の大きさ x 軸位置 (pt)", "width=252,height=216" in text.replace(" ", ""), text)
    check("size: グリッド", "grid(bottom)=1" in text and "grid(left)=1" in text)
    check("size: '_' で始まるラベルは凡例に出さない・凡例なしなら Legend 行なし", "Legend" not in text)
    check("size: 添字は立体・変数は斜体・\\mu", r"\\f02Q\\f00\\Bz\\M [\u03BCm\\S-1\\M]" in text, text)
    for bad in ("Bad Name", "1abc", "x" * 17):
        try:
            export_igor(fig, tmp, bad)
            check(f"name '{bad[:8]}' を拒否", False)
        except ValueError:
            check(f"name '{bad[:8]}' を拒否", True)
    plt.close(fig)
    fig2 = plt.figure()
    try:
        export_igor(fig2, tmp, "fig_none")
        check("Axes なしを拒否", False)
    except ValueError:
        check("Axes なしを拒否", True)
    plt.close(fig2)


# ============================ ラベルの規則 ==============================
def test_label_rules(tmp):
    w = []
    own = "\\\\f02Q\\\\f00\\\\Bz\\\\M [nm\\\\S-1\\\\M]"  # Igor の注釈の書き方と同一
    check("ラベル: $Q_z$ [nm$^{-1}$] が Igor の注釈の書き方と同一の文字列になる",
          _label_literal(r"$Q_z$ [nm$^{-1}$]", w) == own, _label_literal(r"$Q_z$ [nm$^{-1}$]", w))
    check("ラベル: 添字・指数の中身は斜体にしない", "\\\\f02z" not in _label_literal(r"$Q_z$", w))
    check("ラベル: \\mathrm は立体", _label_literal(r"$\mathrm{d}x$", w) == "d\\\\f02x\\\\f00")
    check("ラベル: italic_math=False なら斜体なし", _label_literal(r"$Q$ [a.u.]", w, italic_math=False) == "Q [a.u.]")
    check("ラベル: ギリシャ文字は \\u エスケープ", _label_literal(r"$\lambda$ [nm]", w) == "\\u03BB [nm]")

    def style_warns(xlabel):
        fig, ax = plt.subplots()
        ax.plot([1, 2], [1, 2])
        ax.set_xlabel(xlabel)
        rep = export_igor(fig, tmp, "fig_style")
        plt.close(fig)
        return [x for x in rep.warnings if x.startswith("スタイル")]

    check("スタイル警告: Å を含むラベル", any("Å" in s for s in style_warns(r"$Q$ [$\mathrm{\AA}^{-1}$]")))
    check("スタイル警告: 単位が [ ] で囲まれていない", any("[ ]" in s for s in style_warns(r"$Q$ / nm$^{-1}$")))
    check("スタイル警告: 好みどおりのラベルでは出ない", not style_warns(r"$Q$ [nm$^{-1}$]"))


# ============================ 2次元画像 ==============================
def asym_array():
    i, j = np.meshgrid(np.arange(3), np.arange(5), indexing="ij")
    return (10 * i + j + 1).astype(float)  # 形 (3, 5)、値 1..25


def make_fig(setup):
    fig, ax = plt.subplots(figsize=(4, 3))
    setup(fig, ax)
    return fig, ax


def test_imshow_basic(tmp):
    A = asym_array()

    def setup(fig, ax):
        im = ax.imshow(A, cmap="viridis")
        fig.colorbar(im, ax=ax, label="Intensity [a.u.]")
        ax.set_xlabel(r"$Q_x$ [nm$^{-1}$]")
        ax.set_ylabel(r"$Q_z$ [nm$^{-1}$]")

    fig, ax = make_fig(setup)
    rep = export_igor(fig, tmp, "fig_im")
    h5 = read_h5(os.path.join(tmp, "fig_im.h5"))
    probs, text = lint_ipf(os.path.join(tmp, "fig_im.ipf"), h5)
    check("imshow: 画像1枚・トレース0本・警告なし", rep.n_images == 1 and rep.n_traces == 0 and not rep.warnings,
          str(rep.warnings))
    check("imshow: .ipf 静的チェック", not probs, "; ".join(probs))
    z = h5["fig_im_i0_z"]
    check("imshow: z は転置されて Igor の dim0 = x", z.shape == (5, 3) and np.array_equal(z, A.T))
    check("imshow: 左上のピクセル(行0,列0)=1, 右下(行2,列4)=25 が z[0,0], z[4,2]", z[0, 0] == 1 and z[4, 2] == 25)
    check("imshow: x 端座標 = -0.5..4.5 (6点)", np.allclose(h5["fig_im_i0_xe"], np.arange(6) - 0.5))
    check("imshow: y 端座標 = -0.5..2.5 (4点, 単調増加)", np.allclose(h5["fig_im_i0_ye"], np.arange(4) - 0.5))
    ct = h5["fig_im_i0_ct"]
    cm = plt.get_cmap("viridis")
    check("色テーブル: 形 (256,3)・0..65535・両端が colormap と一致",
          ct.shape == (256, 3) and ct.min() >= 0 and ct.max() <= 65535
          and np.allclose(ct[0], np.round(np.array(cm(0.0)[:3]) * 65535))
          and np.allclose(ct[-1], np.round(np.array(cm(1.0)[:3]) * 65535)))
    check("imshow: 空の Display/N= の後に AppendImage vs {端,端}",
          re.search(r"\tDisplay/N=fig_im/W=\(40,40,[0-9.]+,[0-9.]+\)\n", text) and
          "AppendImage/W=fig_im fig_im_i0_z vs {fig_im_i0_xe,fig_im_i0_ye}" in text, text)
    check("imshow: 軸は常に SetAxis（origin='upper' なので y は反転）",
          "SetAxis/W=fig_im bottom -0.5,4.5" in text and "SetAxis/W=fig_im left 2.5,-0.5" in text, text)
    check("imshow: ModifyImage ctab=色テーブルWave・範囲は norm の値", re.search(
        r"ModifyImage/W=fig_im fig_im_i0_z ctab=\{1,25,fig_im_i0_ct,0\}$", text, flags=re.M))
    check("imshow: 色テーブルWaveは Redimension/U/W", "Redimension/U/W fig_im_i0_ct" in text)
    check("imshow: aspect=equal → height={Aspect,|Δy/Δx|}=0.6, 画像の既定書式",
          "gfSize=12,width=227,height={Aspect,0.6}" in text
          and "margin(left)=51,margin(bottom)=43,margin(top)=14," in text, text)  # 下余白は preset の 43 のまま（上付きでも収まる）
    mr = float(re.search(r"margin\(right\)=([0-9.]+)", text).group(1))
    check("imshow: カラースケールの箱が入るように、右余白は preset の 57 より広がる", mr > 57, mr)
    check("imshow: 目盛りは内向き（ユーザーの好み）: tick=2,mirror=1,standoff=0",
          "tick=2,mirror=1,standoff=0" in text)
    check("カラースケール: 箱の枠 /F=2・外側 /E=2・左上基準・棒の寸法は点・ラベル。lblMargin は出さない（既定のままで重ならない）",
          re.search(r"ColorScale/C/N=cs0/F=2/E=2/A=LT/X=[0-9.]+/Y=[0-9.]+ image=fig_im_i0_z,width=15,height=[0-9.]+,frame=0,font=\"Arial\"\n", text)
          and "ColorScale/C/N=cs0 \"Intensity [a.u.]\"" in text and "lblMargin=" not in text, text)
    check("カラースケール: 線形なので log=1/logLTrip を出さない", "log=1" not in text and "logLTrip" not in text)
    check("カラースケールの直前に DoWindow/F", text.index("DoWindow/F fig_im") < text.index("ColorScale/C/N=cs0/F=2"))
    check("画像のラベル: 斜体の変数・立体の添字と指数",
          r'Label/W=fig_im bottom "\\f02Q\\f00\\Bx\\M [nm\\S-1\\M]"' in text, text)
    plt.close(fig)


def test_log_nan(tmp):
    A = 10.0 ** np.add.outer(np.arange(4), np.arange(6) / 2.0)  # 1 .. 1e6.5
    A[1, 2] = np.nan
    A = np.ma.masked_where(np.arange(24).reshape(4, 6) == 7, A)  # マスクも NaN になる

    def setup(fig, ax):
        im = ax.imshow(A, norm=mcolors.LogNorm(vmin=1, vmax=1e6))
        fig.colorbar(im, ax=ax, label="Reflectivity")

    fig, ax = make_fig(setup)
    export_igor(fig, tmp, "fig_log")
    h5 = read_h5(os.path.join(tmp, "fig_log.h5"))
    text = open(os.path.join(tmp, "fig_log.ipf")).read()
    z = h5["fig_log_i0_z"]
    check("log: NaN とマスクが NaN のまま保たれる", np.isnan(z[2, 1]) and np.isnan(z[1, 1]) and np.isnan(z).sum() == 2)
    check("log: ModifyImage に log=1・範囲は LogNorm の vmin/vmax",
          "ctab={1,1e+06,fig_log_i0_ct,0},log=1" in text, text)
    check("log: ColorScale に log=1 と logLTrip=0.1", re.search(r"ColorScale/C/N=cs0\S* image=fig_log_i0_z,log=1,", text)
          and "ColorScale/C/N=cs0 logLTrip=0.1" in text)
    plt.close(fig)
    fig2, ax2 = plt.subplots()
    ax2.imshow(np.arange(1.0, 7).reshape(2, 3), norm="log")  # 文字列指定でも LogNorm として扱う
    export_igor(fig2, tmp, "fig_log2")
    check("log: norm='log' (文字列) でも log=1", "log=1" in open(os.path.join(tmp, "fig_log2.ipf")).read())
    plt.close(fig2)


def test_origin_extent(tmp):
    A = asym_array()  # (3, 5)

    fig, ax = plt.subplots()
    ax.imshow(A, origin="lower", extent=[0, 10, 0, 6], aspect="auto")
    export_igor(fig, tmp, "fig_lo")
    h5 = read_h5(os.path.join(tmp, "fig_lo.h5"))
    text = open(os.path.join(tmp, "fig_lo.ipf")).read()
    check("origin=lower: 端座標 x=0..10, y=0..6", np.allclose(h5["fig_lo_i0_xe"], np.linspace(0, 10, 6))
          and np.allclose(h5["fig_lo_i0_ye"], np.linspace(0, 6, 4)))
    check("origin=lower: データは行0=下端のまま (z=A.T)", np.array_equal(h5["fig_lo_i0_z"], A.T))
    check("origin=lower: y 軸は反転しない", "SetAxis/W=fig_lo left 0,6" in text, text)
    check("aspect='auto' → 既定のアスペクト比 (画像の既定=1)", "height={Aspect,1}" in text, text)
    plt.close(fig)

    fig, ax = plt.subplots()
    ax.imshow(A, origin="upper", extent=[0, 10, 0, 6])  # 行0 が y=6 側 → 端座標が減少する
    export_igor(fig, tmp, "fig_up")
    h5 = read_h5(os.path.join(tmp, "fig_up.h5"))
    text = open(os.path.join(tmp, "fig_up.ipf")).read()
    ye = h5["fig_up_i0_ye"]
    check("origin=upper+extent: 端座標が単調増加になるよう反転し、データの行も反転する",
          np.all(np.diff(ye) > 0) and np.allclose(ye, np.linspace(0, 6, 4))
          and np.array_equal(h5["fig_up_i0_z"], A[::-1, :].T))
    check("origin=upper+extent: y の SetAxis は 0,6 (反転なし)", "SetAxis/W=fig_up left 0,6" in text, text)
    check("aspect=equal: |Δy/Δx| = 0.6", "height={Aspect,0.6}" in text, text)
    plt.close(fig)


def test_pcolormesh(tmp):
    xe = np.array([0, 1, 3, 6.0])
    ye = np.array([0, 2, 3.0])
    A = np.arange(1.0, 7).reshape(2, 3)
    fig, ax = plt.subplots()
    qm = ax.pcolormesh(xe, ye, A, cmap="plasma", vmin=1, vmax=6)
    fig.colorbar(qm, ax=ax, label="Counts [a.u.]")
    rep = export_igor(fig, tmp, "fig_pm")
    h5 = read_h5(os.path.join(tmp, "fig_pm.h5"))
    probs, text = lint_ipf(os.path.join(tmp, "fig_pm.ipf"), h5)
    check("pcolormesh: 不均一な端座標をそのまま渡す", np.allclose(h5["fig_pm_i0_xe"], xe) and np.allclose(h5["fig_pm_i0_ye"], ye))
    check("pcolormesh: z = A.T・警告なし・静的チェック", np.array_equal(h5["fig_pm_i0_z"], A.T) and not rep.warnings
          and not probs, str(rep.warnings) + "; ".join(probs))
    check("pcolormesh: 軸範囲は 0..6 / 0..3", "SetAxis/W=fig_pm bottom 0,6" in text and "SetAxis/W=fig_pm left 0,3" in text)
    check("pcolormesh: aspect='auto' なので既定のアスペクト比", "height={Aspect,1}" in text)
    plt.close(fig)

    # shading='nearest' (中心座標 → 端座標へ変換される)
    fig, ax = plt.subplots()
    ax.pcolormesh(np.array([0, 1, 2.0]), np.array([0, 10.0]), np.ones((2, 3)), shading="nearest")
    export_igor(fig, tmp, "fig_pn")
    h5 = read_h5(os.path.join(tmp, "fig_pn.h5"))
    check("pcolormesh(shading=nearest): 中心 [0,1,2] → 端 [-0.5,0.5,1.5,2.5]",
          np.allclose(h5["fig_pn_i0_xe"], [-0.5, 0.5, 1.5, 2.5]))
    plt.close(fig)


def test_ctab_override_and_overlay(tmp):
    A = asym_array()
    fig, ax = plt.subplots()
    ax.imshow(A, cmap="gray")
    ax.plot([0, 4], [0, 2], "-", color="w", lw=2)
    rep = export_igor(fig, tmp, "fig_ov", ctab=("Rainbow", 1))
    h5 = read_h5(os.path.join(tmp, "fig_ov.h5"))
    probs, text = lint_ipf(os.path.join(tmp, "fig_ov.ipf"), h5)
    check("ctab 指定: 色テーブルWaveを作らず Rainbow を reverse=1 で指定",
          "fig_ov_i0_ct" not in h5 and "ctab={1,25,Rainbow,1}" in text and "Redimension" not in text, text)
    check("ctab 指定: 静的チェック", not probs, "; ".join(probs))
    check("画像 + 線: Display(空) → AppendImage → AppendToGraph の順",
          text.index("\tDisplay/N=fig_ov") < text.index("AppendImage/W=fig_ov")
          < text.index("AppendToGraph/W=fig_ov fig_ov_t0_y vs fig_ov_t0_x"))
    check("画像 + 線: トレース1本・画像1枚", rep.n_traces == 1 and rep.n_images == 1)
    check("カラーバー無しなら ColorScale を出さない", "ColorScale" not in text)
    plt.close(fig)


def test_image_warnings(tmp):
    def run(setup, name):
        fig, ax = plt.subplots()
        setup(fig, ax)
        try:
            rep = export_igor(fig, tmp, name)
            return rep, None
        except ValueError as e:
            return None, str(e)
        finally:
            plt.close(fig)

    rep, err = run(lambda f, a: a.imshow(np.zeros((4, 4, 3))), "fig_rgb")
    check("警告: RGB 画像は未対応（書き出せるものが無ければエラー）", err is not None and "書き出せる" in err, str(err))

    def with_line(f, a):
        a.imshow(np.zeros((4, 4, 3)))
        a.plot([0, 1], [0, 1])
    rep, err = run(with_line, "fig_rgb2")
    check("警告: RGB 画像は警告に出て、線だけ書き出す", rep is not None and any("RGB" in w for w in rep.warnings))

    rep, err = run(lambda f, a: (a.pcolormesh(np.arange(4.0), np.arange(3.0), np.ones((3, 4)), shading="gouraud"),
                                 a.plot([0, 1], [0, 1])), "fig_gou")
    check("警告: gouraud", rep is not None and any("gouraud" in w for w in rep.warnings), str(err))

    def skewed(f, a):
        X, Y = np.meshgrid(np.arange(4.0), np.arange(3.0))
        a.pcolormesh(X + 0.3 * Y, Y, np.ones((2, 3)))
        a.plot([0, 1], [0, 1])
    rep, err = run(skewed, "fig_skew")
    check("警告: 矩形でないメッシュ", rep is not None and any("矩形でない" in w for w in rep.warnings), str(err))

    def power(f, a):
        a.imshow(asym_array(), norm=mcolors.PowerNorm(0.5))
    rep, err = run(power, "fig_pow")
    check("警告: PowerNorm は線形にして書き出す", rep is not None and any("PowerNorm" in w for w in rep.warnings), str(err))

    def horiz(f, a):
        im = a.imshow(asym_array())
        f.colorbar(im, ax=a, orientation="horizontal", label="x [a.u.]")
    rep, err = run(horiz, "fig_hor")
    check("警告: 横向きカラーバー", rep is not None and any("横向き" in w for w in rep.warnings), str(err))

    def poly(f, a):
        a.pcolor(np.arange(4.0), np.arange(3.0), np.ones((2, 3)))
        a.plot([0, 1], [0, 1])
    rep, err = run(poly, "fig_pcolor")
    check("警告: pcolor / contour は未対応", rep is not None and any("pcolor/contour" in w for w in rep.warnings), str(err))

    def two_cmaps(f, a):
        im = a.imshow(asym_array())
        f.colorbar(im, ax=a)
        a.plot([0, 1], [0, 1])
    rep, err = run(two_cmaps, "fig_cb")
    check("カラーバーの Axes は『複数 Axes』警告に数えない", rep is not None and not any("Axes が" in w for w in rep.warnings),
          str(rep.warnings if rep else err))


def demo_figure2():
    """Igor 側で matplotlib の画像と見比べるための図。向きが分かるよう非対称なパターンにしている。"""
    nx, ny = 40, 30
    qx = np.linspace(-1.0, 1.0, nx + 1)  # nm^-1 （ピクセル端）
    qz = np.linspace(0.0, 1.5, ny + 1)
    X, Z = np.meshgrid(0.5 * (qx[1:] + qx[:-1]), 0.5 * (qz[1:] + qz[:-1]))
    I = 1e4 * np.exp(-((X - 0.4) ** 2 / 0.02 + (Z - 0.5) ** 2 / 0.05)) + 1e2 * np.exp(-Z) + 5.0
    I[Z > 1.0] *= 0.1
    I[:3, :6] = 1e5  # 左下隅（Qz 最小・Qx 最小）に明るい目印
    I[-4:, -3:] = np.nan  # 右上隅に欠損
    fig, ax = plt.subplots(figsize=(4.2, 3.4))
    qm = ax.pcolormesh(qx, qz, I, norm=mcolors.LogNorm(vmin=1, vmax=1e5), cmap="turbo")
    ax.set_xlabel(r"$Q_x$ [nm$^{-1}$]")
    ax.set_ylabel(r"$Q_z$ [nm$^{-1}$]")
    fig.colorbar(qm, ax=ax, label="Intensity [a.u.]")
    return fig


def test_demo2(outdir):
    fig = demo_figure2()
    rep = export_igor(fig, outdir, "fig_demo2")
    fig.savefig(os.path.join(outdir, "fig_demo2_mpl.png"), dpi=150, bbox_inches="tight")
    print(rep.summary())
    h5 = read_h5(os.path.join(outdir, "fig_demo2.h5"))
    probs, text = lint_ipf(os.path.join(outdir, "fig_demo2.ipf"), h5)
    check("demo2: 静的チェック・警告なし", not probs and not rep.warnings, "; ".join(probs) + str(rep.warnings))
    check("demo2: 左下隅の目印が z[0,0] (Igor の dim0=Qx 最小, dim1=Qz 最小)", h5["fig_demo2_i0_z"][0, 0] == 1e5)
    check("demo2: 右上隅の欠損が z[-1,-1] = NaN", np.isnan(h5["fig_demo2_i0_z"][-1, -1]))
    plt.close(fig)


if __name__ == "__main__":
    keep = sys.argv[1] if len(sys.argv) > 1 else None
    with tempfile.TemporaryDirectory() as tmp:
        out = keep or tmp
        os.makedirs(out, exist_ok=True)
        test_demo(out)
        test_symmetric_and_xy(tmp)
        test_warnings(tmp)
        test_misc(tmp)
        test_label_rules(tmp)
        test_imshow_basic(tmp)
        test_log_nan(tmp)
        test_origin_extent(tmp)
        test_pcolormesh(tmp)
        test_ctab_override_and_overlay(tmp)
        test_image_warnings(tmp)
        test_demo2(out)
    bad = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} passed")
    sys.exit(1 if bad else 0)
