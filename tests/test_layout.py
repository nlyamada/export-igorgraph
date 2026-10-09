"""固定するもの（ウィンドウの大きさ・フォント・軸範囲）と、凡例・グリッド・マーカー・カラースケールの新しい挙動のテスト。
python test_layout.py"""
import os, re, sys, tempfile
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors as mcolors
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from export_igorgraph.mpl_to_igor import export_igor
from export_igorgraph import eig_allowlist as al
# スタイルファイルの自動探索（カレント・ホーム）が、テストの結果を左右しないようにする
os.environ.pop("EXPORT_IGORGRAPH_STYLE", None)

results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ")+name+("" if cond else f"  [{str(detail)[:300]}]"))

def cmds(fig, **kw):
    with tempfile.TemporaryDirectory() as tmp:
        rep = export_igor(fig, tmp, "t", **kw)
    plt.close(fig)
    assert all(al.is_allowed(c) for c in rep.commands), [c for c in rep.commands if not al.is_allowed(c)][:2]
    return rep.commands, rep.warnings

def line_fig(xlabel=r"$x$ [a.u.]"):
    fig, ax = plt.subplots(figsize=(4, 3)); ax.plot([0, 1, 2], [0, 1, 4], label="a"); ax.set_xlabel(xlabel); return fig, ax

def first(cs, pat):
    return next((c for c in cs if re.search(pat, c)), None)

def main():
    # --- ウィンドウの大きさ ---
    fig, ax = line_fig()
    cs, _ = cmds(fig)
    d = first(cs, r"^Display"); m = re.match(r"Display/N=t/W=\(40,40,([0-9.]+),([0-9.]+)\) t_t0_y vs t_t0_x", d)
    check("preset: ウィンドウ = 余白 + プロット領域（幅 43+226.772+14, 高さ 14+0.8*226.772+37）", m and
          abs(float(m.group(1)) - 40 - (43 + 226.772 + 14)) < 0.01 and abs(float(m.group(2)) - 40 - (14 + 0.8 * 226.772 + 37)) < 0.01, d)
    fig, ax = line_fig(); fig.subplots_adjust(left=0.2, right=0.9, bottom=0.15, top=0.9)
    cs, _ = cmds(fig, use_mpl_size=True)
    check("mpl-size: ウィンドウ = Figure の大きさ (4x3 in = 288x216 pt)", re.match(r"Display/N=t/W=\(40,40,328,256\)", first(cs, r"^Display")), first(cs, r"^Display"))
    check("mpl-size: 文字サイズは matplotlib の目盛りラベル (10)", "gfSize=10," in first(cs, "gfSize"), first(cs, "gfSize"))
    # --- フォント ---
    fig, ax = line_fig(); cs, _ = cmds(fig)
    check("フォントを明示（既定 Arial）", 'ModifyGraph/W=t font="Arial"' in cs)
    fig, ax = line_fig(); cs, _ = cmds(fig, style={"font": None})
    check("style の font=None ならフォント指定なし", not any("font=" in c for c in cs))
    fig, ax = line_fig(); cs, _ = cmds(fig, style={"font": "Times New Roman"})
    check("style で別のフォントを指定できる（許可リストにある名前）", 'font="Times New Roman"' in " ".join(cs))
    # --- 軸範囲 ---
    fig, ax = line_fig(); cs, _ = cmds(fig)
    check("axis_range='mpl'（既定）: 自動スケールの軸も SetAxis で固定", first(cs, r"SetAxis/W=t bottom") and first(cs, r"SetAxis/W=t left"))
    fig, ax = line_fig(); cs, _ = cmds(fig, axis_range="auto")
    check("axis_range='auto': 手動設定していない軸は固定しない", not first(cs, r"^SetAxis"))
    # --- 凡例 ---
    fig, ax = line_fig(); ax.legend(loc="upper left", frameon=False); cs, _ = cmds(fig)
    check("凡例: 記号はグラフと同じ大きさ (/M=1)", first(cs, r"^Legend/W=t/N=legend0/F=0/M=1/A=LT "), first(cs, "^Legend"))
    # --- グリッド ---
    fig, ax = line_fig(); ax.grid(True); cs, _ = cmds(fig)
    check("グリッド: 色（matplotlib の既定の灰色 #b0b0b0）と実線", "gridRGB(bottom)=(45232,45232,45232)" in " ".join(cs) and "gridStyle(left)=5" in " ".join(cs), cs)
    fig, ax = line_fig(); ax.grid(True, linestyle="--"); cs, w = cmds(fig)
    check("グリッド: 破線は番号が未確認なので警告して実線", any("グリッドの線種" in x for x in w) and "gridStyle(bottom)=5" in " ".join(cs))
    # --- マーカー（第2回の実機で作った対応表。第3回で寸法を実測して換算） ---
    def mk(m, **kw):
        fig, ax = plt.subplots(); ax.plot([1, 2], [1, 2], m, color="b", ms=6, **kw); cs, w = cmds(fig)
        mm = re.search(r"marker\(t_t0_y\)=(\d+),msize\(t_t0_y\)=([0-9.]+)", " ".join(cs))
        return (int(mm.group(1)), float(mm.group(2))) if mm else (None, None), " ".join(cs), w
    (no, sz), txt, w = mk("s")
    check("マーカー: 塗りつぶしの四角は 16・警告なし", no == 16 and not w, w)
    (no, sz), txt, w = mk("s", mfc="none")
    check("マーカー: 白抜きの四角は 5（透明）・警告なし", no == 5 and "opaque(t_t0_y)=0" in txt and not w, (no, w))
    (no, _), txt, w = mk("s", mfc="white")
    check("マーカー: 白で塗った四角は 5 + opaque=1", no == 5 and "opaque(t_t0_y)=1" in txt, (no, txt))
    check("マーカー: ^ は 塗り=17・白抜き=6、v は 23・22、< は 46・45、> は 49・48",
          [mk(m)[0][0] for m in "^v<>"] == [17, 23, 46, 49] and
          [mk(m, mfc="none")[0][0] for m in "^v<>"] == [6, 22, 45, 48])
    check("マーカー: D は 塗り=18・白抜き=7、d は 29・28、p は 52・51、h は 55・54",
          [mk(m)[0][0] for m in "Ddph"] == [18, 29, 52, 55] and [mk(m, mfc="none")[0][0] for m in "Ddph"] == [7, 28, 51, 54])
    check("マーカー: + は 0、x は 1、_ は 9、| は 10（線だけの記号は色に縁の色）", [mk(m)[0][0] for m in "+x_|"] == [0, 1, 9, 10])
    check("マーカー: * は 4 芒星 (60) で近似して警告", mk("*")[0][0] == 60 and any("四芒星" in x for x in mk("*")[2]))
    check("マーカー: 寸法 msize = (ms + mew - 1)/2。ms=6, mew=1 → 3（第3回の実測: 縁の線幅ぶん Igor が小さかった）",
          mk("o")[0][1] == 3.0 and mk("D")[0][1] == 3.0)
    # --- 線種（第3回: Igor の破線パターンの実測値から、matplotlib のパターンに最も近い番号を選ぶ） ---
    def ls(style, lw=1.5):
        fig, ax = plt.subplots(); ax.plot([1, 2], [1, 2], style, color="b", lw=lw); cs, w = cmds(fig)
        mm = re.search(r"lStyle\(t_t0_y\)=(\d+)", " ".join(cs)); return (int(mm.group(1)) if mm else 0), w
    check("線種: '-' は実線（lStyle を出さない）、'--' は 11、':' は 2、'-.' は 5（線幅 1.5）",
          [ls(s)[0] for s in ("-", "--", ":", "-.")] == [0, 11, 2, 5] and not ls("--")[1])
    check("線種: 線幅が変わると、破線の長さ（matplotlib は線幅に比例・Igor は絶対長）に近い番号に変わる",
          ls("--", 0.7)[0] != ls("--", 3.0)[0], (ls("--", 0.7), ls("--", 3.0)))
    # --- 軸ラベルの配置（目盛りの向き・対数軸・上付きを考慮。第3回の実機で較正） ---
    fig, ax = line_fig(r"$Q$ [nm$^{-1}$]"); cs, _ = cmds(fig)
    mb = float(re.search(r"margin\(bottom\)=([0-9.]+),", first(cs, "margin")).group(1))
    check("上付きのある x 軸ラベル: 下余白は計算で広がる（37 → 約 41.9。目盛りラベルの下端 + 隙間 + 上付き込みの高さ）",
          41.5 < mb < 42.5, mb)
    fig, ax = line_fig(r"$x$ [a.u.]"); cs, _ = cmds(fig)
    check("上付き・下付きが無ければ下余白は preset の 37 のまま", "margin(bottom)=37," in first(cs, "margin"))
    fig, ax = line_fig(r"$Q$ [nm$^{-1}$]"); cs, _ = cmds(fig, style={"sub_sup_extra": 6})
    check("style の sub_sup_extra に数値を指定すると従来どおり +6 (37 → 43)", "margin(bottom)=43," in first(cs, "margin"))
    fig, ax = line_fig(); ax.set_xscale("log"); ax.set_xlim(0.1, 10); cs, _ = cmds(fig)
    mb_log = float(re.search(r"margin\(bottom\)=([0-9.]+),", first(cs, "margin")).group(1))
    check("対数軸: 目盛りラベルが指数表記になる logLTrip を軸の最小値の 2 倍で出す", "ModifyGraph/W=t logLTrip(bottom)=0.2" in cs, cs)
    check("対数軸は線形より下余白が必要（指数・副目盛りのラベルが高い）", mb_log > 37.0, mb_log)
    fig, ax = line_fig(); ax.set_xscale("log"); ax.set_xlim(0.1, 10); cs, _ = cmds(fig, style={"log_exp": False})
    check("style の log_exp=False なら logLTrip を出さない", not any("logLTrip" in c for c in cs))
    fig, ax = line_fig(); cs, _ = cmds(fig, style={"lbl_margin_bottom": 34})
    check("style の lbl_margin_bottom で x 軸ラベルの位置を指定できる（lblMargin）", "ModifyGraph/W=t lblMargin(bottom)=34" in cs)
    # --- 主要な設定を style で指定する（tick・mirror・standoff・grid・width・height・font・gFont） ---
    def last_with(cs, pat):
        return next((c for c in cs if re.search(pat, c)), "")
    fig, ax = line_fig(); cs, w = cmds(fig, style={"width": 300, "height": 150, "gFont": "Yu Gothic"})
    check("style の別名: width / height（プロット領域の pt）・gFont", "width=300,height=150" in last_with(cs, r"gfSize") and
          'ModifyGraph/W=t gFont="Yu Gothic"' in cs and 'ModifyGraph/W=t font="Arial"' in cs and not w, (cs, w))
    fig, ax = line_fig(); cs, _ = cmds(fig)
    check("既定: gFont も font と同じにする（凡例などの既定フォントが Igor の設定に依存しないように）", 'ModifyGraph/W=t gFont="Arial"' in cs)
    fig, ax = line_fig(); cs, _ = cmds(fig, style={"font": None})
    check("font=None のとき gFont も出さない", not any("ont=" in c for c in cs))
    fig, ax = line_fig(); cs, _ = cmds(fig, style={"tick": 0, "mirror": 0, "standoff": 1})
    check("style の tick・mirror・standoff", "ModifyGraph/W=t tick=0,mirror=0,standoff=1" in cs)
    fig, ax = line_fig(); cs, _ = cmds(fig, use_mpl_size=True)
    pw_mpl = re.search(r"width=([0-9.]+)", last_with(cs, r"gfSize")).group(1)
    fig, ax = line_fig(); cs, _ = cmds(fig, use_mpl_size=True, style={"width": 200})
    check("use_mpl_size=True でも、width を指定したときだけ上書きする（指定しなければ matplotlib の大きさ）",
          "width=200," in last_with(cs, r"gfSize") and pw_mpl != "200", (pw_mpl, last_with(cs, r"gfSize")))
    # グリッド
    fig, ax = line_fig(); cs, _ = cmds(fig, style={"grid": 1})
    check("grid=1: matplotlib にグリッドが無くても、両軸にグリッド（色は matplotlib の既定、実線）",
          "ModifyGraph/W=t grid(bottom)=1" in cs and "ModifyGraph/W=t grid(left)=1" in cs
          and "ModifyGraph/W=t gridStyle(left)=5" in cs and any(c.startswith("ModifyGraph/W=t gridRGB(bottom)") for c in cs))
    fig, ax = line_fig(); cs, _ = cmds(fig, style={"grid": {"bottom": 2}})
    check("grid の辞書: 指定した軸だけ（2 = 主目盛りのみ）", "ModifyGraph/W=t grid(bottom)=2" in cs and not any("grid(left)" in c for c in cs))
    fig, ax = line_fig(); ax.grid(True); cs, _ = cmds(fig, style={"grid": 0})
    check("grid=0: matplotlib にグリッドがあっても出さない", not any("grid" in c for c in cs))
    fig, ax = line_fig(); cs, _ = cmds(fig, style={"grid": 1, "grid_rgb": "red", "grid_style": 1})
    check("grid_rgb・grid_style の指定", "ModifyGraph/W=t gridRGB(bottom)=(65535,0,0)" in cs and "ModifyGraph/W=t gridStyle(bottom)=1" in cs)
    # 別名・未知のキー・値の検査
    fig, ax = line_fig(); cs, w = cmds(fig, style={"tikc": 0})
    check("未知のキーは無視して、警告する（もしかして: tick）", any("tikc" in x and "tick" in x for x in w), w)
    fig, ax = line_fig()
    try:
        cmds(fig, style={"tick": 5}); check("tick=5 は ValueError", False)
    except ValueError as e:
        check("値の誤り（tick=5）は ValueError で理由を示す", "tick" in str(e))
    fig, ax = line_fig()
    try:
        cmds(fig, style={"font": "Papyrus"}); check("許可リストに無いフォントは ValueError", False)
    except ValueError as e:
        check("許可リストに無いフォントは ValueError で、使える名前を示す", "Arial" in str(e) and "FONT_NAMES" in str(e))
    # スタイルファイル
    import json
    with tempfile.TemporaryDirectory() as td:
        sf = os.path.join(td, "my_style.json")
        json.dump({"_comment": "メモ", "tick": 0, "grid": 1, "width": 250, "nosuchkey": 1}, open(sf, "w"))
        fig, ax = line_fig()
        with tempfile.TemporaryDirectory() as td2:
            rep = export_igor(fig, td2, "t", style_file=sf)
        plt.close(fig)
        cs2 = rep.commands
        check("スタイルファイル: 読み込む（tick・grid・width）。'_' で始まるキーは注釈として無視、未知のキーは警告",
              "tick=0," in last_with(cs2, r"tick=") and "grid(bottom)=1" in " ".join(cs2) and "width=250," in last_with(cs2, "gfSize")
              and any("nosuchkey" in x for x in rep.warnings) and not any("_comment" in x for x in rep.warnings) and rep.style_file == os.path.abspath(sf),
              (rep.warnings, rep.style_file))
        fig, ax = line_fig()
        with tempfile.TemporaryDirectory() as td2:
            rep = export_igor(fig, td2, "t", style_file=sf, style={"tick": 2})
        plt.close(fig)
        check("優先順位: 組み込みの既定 < スタイルファイル < style=（tick: ファイル 0 を style の 2 が上書き）",
              "tick=2," in last_with(rep.commands, r"tick=") and "grid(bottom)=1" in " ".join(rep.commands))
        old = os.environ.get("EXPORT_IGORGRAPH_STYLE")
        os.environ["EXPORT_IGORGRAPH_STYLE"] = sf
        try:
            fig, ax = line_fig()
            with tempfile.TemporaryDirectory() as td2:
                rep = export_igor(fig, td2, "t")
            plt.close(fig)
            check("環境変数 EXPORT_IGORGRAPH_STYLE のスタイルファイルを自動で使う", rep.style_file == os.path.abspath(sf) and "tick=0," in last_with(rep.commands, r"tick="))
            fig, ax = line_fig()
            with tempfile.TemporaryDirectory() as td2:
                rep = export_igor(fig, td2, "t", style_file=False)
            plt.close(fig)
            check("style_file=False なら、スタイルファイルを使わない", rep.style_file is None and "tick=2," in last_with(rep.commands, r"tick="))
        finally:
            if old is None:
                os.environ.pop("EXPORT_IGORGRAPH_STYLE", None)
            else:
                os.environ["EXPORT_IGORGRAPH_STYLE"] = old
    # スタイルファイルの検査（Claude が書き換えたあとの確認用）
    from export_igorgraph.mpl_to_igor import check_style_file
    with tempfile.TemporaryDirectory() as td:
        good = os.path.join(td, "good.json")
        json.dump({"_comment": "x", "tick": 0, "gFont": "Arial", "typo_key": 1}, open(good, "w"))
        st_, w_ = check_style_file(good)
        check("check_style_file: 正しいファイルは (設定, 警告) を返す。別名は正式なキーになり、未知のキーは警告", st_ == {"tick": 0, "gfont": "Arial"} and any("typo_key" in x for x in w_), (st_, w_))
        badv = os.path.join(td, "bad.json")
        json.dump({"tick": 7}, open(badv, "w"))
        try:
            check_style_file(badv); check("check_style_file: 値の誤りは例外", False)
        except ValueError:
            check("check_style_file: 値の誤りは ValueError", True)
        notdict = os.path.join(td, "list.json")
        json.dump([1, 2], open(notdict, "w"))
        try:
            check_style_file(notdict); check("check_style_file: 辞書でない JSON は例外", False)
        except ValueError:
            check("check_style_file: 辞書でない JSON は ValueError", True)
    # --- 描画のあと、サイズ指定を自動に戻す（ウィンドウの大きさを変えられるように） ---
    fig, ax = line_fig(); cs, _ = cmds(fig)
    check("最後の命令で width=0,height=0（サイズ自動）にする", cs[-1] == "ModifyGraph/W=t width=0,height=0", cs[-3:])
    check("width/height の固定は、その前に出している（描画時のプロット領域を決めるため）",
          any(re.search(r"width=[0-9.]+,height=", c) for c in cs[:-1]))
    fig, ax = line_fig(); cs, _ = cmds(fig, style={"free_size": False})
    check("style の free_size=False なら、サイズ指定を固定のままにする", not any("width=0" in c for c in cs))
    # --- 目盛りの向き ---
    fig, ax = line_fig(); cs, _ = cmds(fig)
    check("目盛りは既定で内向き（tick=2、ユーザーの好み）", "ModifyGraph/W=t tick=2,mirror=1,standoff=0" in cs)
    fig, ax = line_fig(); ax.tick_params(direction="in"); cs, _ = cmds(fig, style={"tick": "mpl"})
    check("style の tick='mpl': matplotlib の in → 2", "tick=2," in first(cs, r"tick="))
    fig, ax = line_fig(); cs, _ = cmds(fig, style={"tick": "mpl"})
    check("style の tick='mpl': matplotlib の既定（out）→ 0", "tick=0," in first(cs, r"tick="))
    fig, ax = line_fig(); cs, _ = cmds(fig, style={"tick": 0})
    mb_out = float(re.search(r"margin\(bottom\)=([0-9.]+),", first(cs, "margin")).group(1))
    check("外向きの目盛りは、内向きより下余白が必要（目盛りの長さぶん）", mb_out > 37.0, mb_out)
    # --- use_mpl_size: matplotlib の余白が足りなければ、プロット領域の大きさを変えずに窓を広げる ---
    fig, ax = line_fig(r"$Q$ [nm$^{-1}$]"); cs, w = cmds(fig, use_mpl_size=True)
    check("mpl-size: 既定の余白（下 23.8 pt）ではラベルが収まらないので、下余白を広げて警告する",
          any("下余白を" in x for x in w), w)
    fig, ax = line_fig(r"$Q$ [nm$^{-1}$]"); fig.set_layout_engine("constrained"); cs, w = cmds(fig, use_mpl_size=True)
    check("mpl-size: constrained レイアウトなら matplotlib の余白で足りるので、広げる警告は出ない",
          not any("余白を" in x for x in w), w)
    # --- カラースケールの3モード ---
    def img_fig(**kw):
        fig, ax = plt.subplots(figsize=(4, 3)); im = ax.imshow(np.arange(1., 13).reshape(3, 4), norm=mcolors.LogNorm(1, 12))
        fig.colorbar(im, ax=ax, label="I [a.u.]"); return fig
    cs, _ = cmds(img_fig(), style={"cs_mode": "preset"})
    check("カラースケール preset: 内側の配置 (/A=MC /X=56 /Y=16)", first(cs, r"^ColorScale/C/N=cs0/A=MC/X=56\.00/Y=16\.00 image=t_i0_z,log=1"), [c for c in cs if "ColorScale" in c])
    cs, _ = cmds(img_fig())
    cl = first(cs, r"^ColorScale/C/N=cs0/F=2/E=2/A=LT/X=")
    check("カラースケール outside（既定）: 箱の枠 /F=2・外側 /E=2（余白は自分で広げる）・左上基準・棒の寸法は点で指定",
          cl and re.search(r"image=t_i0_z,log=1,width=15,height=[0-9.]+,frame=0,font=\"Arial\"$", cl), cl)
    def num(pat, s): return float(re.search(pat, s).group(1))
    mg = first(cs, r"^ModifyGraph/W=t margin"); disp = first(cs, r"^Display")
    ml, mr = num(r"margin\(left\)=([0-9.]+)", mg), num(r"margin\(right\)=([0-9.]+)", mg)
    win_w = num(r"W=\(40,40,([0-9.]+),", disp) - 40
    pw = num(r"width=([0-9.]+),height", first(cs, r"gfSize"))
    bar_x = num(r"/X=([0-9.]+)/", cl) * win_w / 100 + 5.7   # 箱の左端 + 箱の左余白 = 棒の左端
    check("カラースケール outside: 棒はプロットの右 8 pt。右余白は箱が入るぶん（preset の 57 より）広がる", abs(bar_x - (ml + pw + 8)) < 0.05 and mr > 57, (bar_x, ml, pw, mr))
    check("カラースケール: 箱の右端（棒 + 箱の幅）がウィンドウの内側", bar_x - 5.7 + 15 + 9.6 + 4.55 * 12 <= win_w, (bar_x, win_w))
    cs, _ = cmds(img_fig(), style={"cs_box": False})
    check("style の cs_box=False: 枠なし /F=0", first(cs, r"^ColorScale/C/N=cs0/F=0/E=2/A=LT/X="))
    check("カラースケールのラベルは Igor の既定（lblMargin を出さない。出すと目盛りラベルと重なる）", not any("lblMargin=" in c for c in cs))
    fig = img_fig(); fig.canvas.draw(); bb = fig.axes[1].get_position(); W, H = fig.get_size_inches() * 72  # カラーバーの幅は描画時に確定する
    cs, w = cmds(fig, use_mpl_size=True)
    cs_line = first(cs, r"^ColorScale/C/N=cs0/F=2/E=2/A=LT")
    mm = re.search(r"/X=([0-9.]+)/Y=([0-9.]+) .*width=([0-9.]+),height=([0-9.]+),frame=0.8,fsize=10", cs_line or "")
    win_w = num(r"W=\(40,40,([0-9.]+),", first(cs, r"^Display")) - 40
    check("カラースケール mpl: 棒の左端・大きさ (pt) が matplotlib のカラーバーと一致（箱の左余白を引いた位置に箱を置く）", mm and
          abs(float(mm.group(1)) * win_w / 100 + 5.7 - bb.x0 * W) < 0.05 and
          abs(float(mm.group(3)) - bb.width * W) < 0.01 and abs(float(mm.group(4)) - bb.height * H) < 0.01, cs_line)
    print(f"\n{sum(results)}/{len(results)} passed"); return 0 if all(results) else 1

if __name__ == "__main__":
    sys.exit(main())
