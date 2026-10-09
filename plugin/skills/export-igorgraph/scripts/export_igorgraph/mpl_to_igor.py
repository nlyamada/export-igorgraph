"""
mpl_to_igor.py
==============

描画済みの matplotlib Figure から、Igor Pro 8 のグラフを作るためのデータ (.h5) を書き出す。
.h5 には、実データ（Wave）と、Igor の描画命令（文字列。許可リストに合う命令だけ）が入る。

    from export_igorgraph.mpl_to_igor import export_igor
    report = export_igor(fig, "outdir", "fig1")      # outdir/fig1.h5
    print(report.summary())

Igor 側では、固定のローダー ExportIgorGraphLoader.ipf を 1 回入れておけば、
    LoadPythonFigure()         // ファイル選択ダイアログで fig1.h5 を選ぶだけ（図ごとの .ipf は不要）
でグラフが作られる。ローダーは、全命令を許可リスト（eig_allowlist.py）で検査してから実行する。
（図ごとの .ipf が欲しいときは write_ipf=True。）

方針
    - スクリプトの文面ではなく、実行後の Figure オブジェクト（解決済みの値）から読み取る。
    - 対応していない要素は黙って落とさず、ExportReport.warnings に必ず記録する。
    - 既定の書式は STYLE_DEFAULT（線）と STYLE_IMAGE（画像）。いずれも作者が普段使うコンパクトな書式
      （幅 8 cm・Arial・内向きの目盛り）。matplotlib 側の色・線幅・マーカー・軸範囲・対数軸・ラベル・
      カラースケール範囲は常にそちらを優先する。use_mpl_size=True なら、図の大きさ・余白も matplotlib に合わせる。

対応範囲
    線:   実線・破線（Igor の線種に近いものを選ぶ）、マーカー（o s ^ v < > D d p h * + x _ | .）、
          エラーバー（X/Y・非対称可・キャップ）、scatter（単色）
    画像: imshow（2次元スカラー）、pcolormesh（矩形格子）、colormap（色テーブル Wave）、Normalize / LogNorm、
          NaN・マスク、縦向きのカラーバー（枠つきのカラースケール）
    等高線: contour / contourf を、元の Z 行列から Igor の等高線（AppendMatrixContour）にする。
          元の Z は、このモジュールを import した後に描いた図なら自動で保存される（contour_data= でも渡せる）
    軸:   線形/対数（10^n の指数表記）、軸範囲、軸ラベル（簡易 mathtext 変換）、目盛りの向き、凡例、グリッド
未対応（警告を出す）
    alpha、可変サイズ・可変色の scatter、複数 Axes、RGB画像、非矩形メッシュ、gouraud、
    LogNorm 以外の非線形 Norm、横向きカラーバー、等高線のカラーバー、fill_between 等の塗り、
    テキスト注釈、タイトル、symlog 等の軸。

ラベルのスタイル規則（警告のみ。書き換えない）
    - mathtext の変数（ASCII英字）は斜体（\\f02 … \\f00）、添字・指数は立体。
      例: $Q_z$ [nm$^{-1}$] → \\f02Q\\f00\\Bz\\M [nm\\S-1\\M]
    - Å の使用、単位が [ ] で囲まれていないラベルは、スタイル警告を出す。

検証状況（Igor 8.04, Windows の実機）は references/verified-in-igor.md と HANDOFF.md §5〜6。
"""

from __future__ import annotations

import datetime
import os
import re

import matplotlib
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from matplotlib import colors as mcolors
import functools

from matplotlib.axes import Axes
from matplotlib.collections import Collection, LineCollection, PathCollection, QuadMesh
from matplotlib.contour import ContourSet
from matplotlib.container import ErrorbarContainer
from matplotlib.image import AxesImage, BboxImage, NonUniformImage, PcolorImage
from matplotlib.scale import LogScale

from export_igorgraph.eig_allowlist import MAX_COMMAND_BYTES, is_allowed
from export_igorgraph.minimal_hdf5_writer import text_to_codes, write_h5

# 線グラフの既定書式（プロット領域の幅 8 cm・縦横比 0.8・Arial 14 pt。作者が普段使うコンパクトな書式）
STYLE_DEFAULT = dict(
    margin_left=43, margin_bottom=37, margin_top=14, margin_right=14,
    gf_size=14, width_pt=226.772, aspect=0.8, height_pt=None,   # height_pt を指定すると aspect より優先（プロット領域の高さ pt）
    tick=2, mirror=1, standoff=0,             # tick: 0=外向き 1=交差 2=内向き 3=なし。"mpl" なら matplotlib の向きに合わせる
    font="Arial", win_left=40, win_top=40,   # フォントとウィンドウの位置・大きさを固定する（見た目が環境に依存しないように）
    gfont=None,                               # グラフ全体の既定フォント（ModifyGraph gFont。凡例などにも効く）。None なら font と同じ
    grid=None, grid_rgb=None, grid_style=5,   # grid: None=matplotlib に合わせる、0/1/2（2=主目盛りのみ）、{"bottom": 1, "left": 0}
    # 軸ラベルの配置（第2回の実機で較正。HANDOFF §6.3）。None なら、目盛りの向き・対数軸・上付きから計算する。
    sub_sup_extra=None,                       # 数値を指定すると、上付き・下付きのある x 軸ラベルのとき下余白にその量を足す（従来の動作）
    label_gap=0.3,                            # 目盛りラベルと軸ラベルの最小の隙間 (文字サイズの倍率)
    lbl_margin_bottom=None, lbl_margin_left=None,   # 軸ラベルの位置 (pt)。ウィンドウの縁から内側への距離。指定が最優先
    log_exp=True,                             # 対数軸の目盛りラベルを 10^n の指数表記にする
    free_size=True,                           # 描画のあと、最後に width=0,height=0（サイズ自動）にして、ウィンドウの大きさを変えられるようにする
)
# 画像の既定書式（Arial 12 pt・縦横比 1）。目盛りは内向き（作者の好み）
STYLE_IMAGE = dict(
    margin_left=51, margin_bottom=43, margin_top=14, margin_right=57,
    gf_size=12, width_pt=227, aspect=1, height_pt=None,
    tick=2, mirror=1, standoff=0,
    font="Arial", gfont=None, grid=None, grid_rgb=None, grid_style=5,
    win_left=40, win_top=40, sub_sup_extra=None, label_gap=0.3,
    lbl_margin_bottom=None, lbl_margin_left=None, log_exp=True, free_size=True,
    # カラースケール。cs_mode: "preset"（内側の注釈: /A=MC /X=56 /Y=16）、
    #   "outside"（グラフの右外側に、外側の注釈として。余白を自動で押し広げる）、
    #   "mpl"（matplotlib のカラーバーの位置と大きさに合わせる。use_mpl_size=True 向け）
    # cs_box: 注釈の枠（/F=1）をつける（ユーザーの好み）。cs_lbl_margin: None なら Igor の自動（重ならない）
    cs_mode="outside", cs_x=56.0, cs_y=16.0, cs_lbl_margin=None, cs_log_trip=0.1,
    cs_width=15, cs_frame=0, cs_nticks=None, cs_box=True,
)

# --- スタイルの指定（style=）---------------------------------------------------------
# 別名: Igor のキーワードに近い名前でも指定できる。 例: style={"width": 300, "height": 200, "gFont": "Arial"}
_STYLE_ALIASES = {"width": "width_pt", "height": "height_pt", "gFont": "gfont", "gfSize": "gf_size", "gfsize": "gf_size"}
_KNOWN_STYLE_KEYS = (set(STYLE_DEFAULT) | set(STYLE_IMAGE)
                     | {"cs_height_pct", "cs_gap", "cs_lbl_margin_mpl"})
STYLE_FILE_NAME = "export_igorgraph_style.json"


def _normalize_style(style, warn, where):
    """別名を正式なキーにし、未知のキー（綴りの誤りなど）は警告して捨てる。'_' で始まるキーは注釈として無視する。"""
    import difflib
    out = {}
    for k, v in (style or {}).items():
        if str(k).startswith("_"):
            continue
        k2 = _STYLE_ALIASES.get(k, k)
        if k2 not in _KNOWN_STYLE_KEYS:
            near = difflib.get_close_matches(k, sorted(_KNOWN_STYLE_KEYS | set(_STYLE_ALIASES)), n=3, cutoff=0.6)
            warn.append(f"{where}: 未知のキー '{k}' は無視しました" + (f"（もしかして: {', '.join(near)}）" if near else ""))
            continue
        out[k2] = v
    return out


def _check_style_values(st):
    """値の誤りは、黙って無視せず、ValueError で知らせる。"""
    from export_igorgraph.eig_allowlist import FONT_NAMES

    def bad(k, msg):
        raise ValueError(f"style['{k}'] = {st[k]!r}: {msg}")

    if st.get("tick") not in (None, 0, 1, 2, 3, "mpl"):
        bad("tick", "0（外向き）・1（交差）・2（内向き）・3（なし）か 'mpl'")
    if st.get("mirror") not in (None, 0, 1, 2, 3):
        bad("mirror", "0〜3")
    if st.get("standoff") not in (None, 0, 1):
        bad("standoff", "0 か 1")
    g = st.get("grid")
    if isinstance(g, dict):
        for ax_, v in g.items():
            if ax_ not in ("bottom", "left") or v not in (None, 0, 1, 2):
                bad("grid", "{'bottom': 0|1|2, 'left': 0|1|2} の形")
    elif g not in (None, 0, 1, 2):
        bad("grid", "None（matplotlib に合わせる）・0（なし）・1（あり）・2（主目盛りのみ）、または軸ごとの辞書")
    for k in ("width_pt", "height_pt", "gf_size"):
        v = st.get(k)
        if v is not None and not (isinstance(v, (int, float)) and v > 0):
            bad(k, "正の数（pt）")
    for k in ("font", "gfont"):
        v = st.get(k)
        if v is not None and v not in FONT_NAMES:
            bad(k, f"使えるフォント名は {', '.join(FONT_NAMES)}（足すには eig_allowlist.py の FONT_NAMES に足して、ローダーを作り直す）")


def find_style_file():
    """スタイルファイルの探し方: 環境変数 EXPORT_IGORGRAPH_STYLE、カレントの export_igorgraph_style.json、
    ホームの .export_igorgraph_style.json の順。無ければ None。"""
    cands = [os.environ.get("EXPORT_IGORGRAPH_STYLE"), os.path.join(os.getcwd(), STYLE_FILE_NAME),
             os.path.join(os.path.expanduser("~"), "." + STYLE_FILE_NAME)]
    return next((p for p in cands if p and os.path.isfile(p)), None)


def _load_style_file(path, warn):
    import json
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"スタイルファイル {path} は、キーと値の辞書（JSON オブジェクト）にしてください")
    return _normalize_style(data, warn, f"スタイルファイル {os.path.basename(path)}")


def check_style_file(path):
    """スタイルファイルを読み、キーと値を検査する（export_igor と同じ検査）。戻り値 (読み込んだ設定, 警告のリスト)。
    JSON の誤り・値の誤りは例外（ValueError など）。ファイルを書き換えたあとの確認に使う。"""
    warn = []
    st = _load_style_file(path, warn)
    _check_style_values({**STYLE_DEFAULT, **STYLE_IMAGE, **st})
    return st, warn


_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,15}$")
_IGOR_MARKER_CIRCLE_OPEN = 8     # 公式ドキュメントの例（marker=8 は透明の円として使われている）
_IGOR_MARKER_CIRCLE_FILLED = 19  # 公式ドキュメント: marker=19 は塗りつぶしの円

# matplotlib のマーカー → Igor のマーカー番号。第2回の実機（Igor 8.04, Windows）で、c01〜c04 の PNG を目視して作成。
#   (白抜き・透明, 塗りつぶし, 寸法の係数, 近似の説明)
# 寸法の係数: Igor の msize は「記号の外形 = 2*s+1 pt」なので、s = (外形 - 1) / 2。外形 = mpl の markersize × 係数 + 縁の線幅。
# 線だけの記号（+ x _ |）は、塗りの区別が無いので、どちらも同じ番号。
_MARKER_MAP = {
    "o": (8, 19, 1.0, None),
    "s": (5, 16, 1.0, None),
    "^": (6, 17, 1.0, None),
    "v": (22, 23, 1.0, None),
    "<": (45, 46, 1.0, None),
    ">": (48, 49, 1.0, None),
    "D": (7, 18, 1.0, None),    # Igor の外形 2s+1 は菱形の「辺」（対角線ではない。第3回の実測: 係数 1.414 だと 1.3 倍大きかった）
    "d": (28, 29, 1.0, None),
    "p": (51, 52, 1.0, None),
    "h": (54, 55, 1.0, None),
    "H": (54, 55, 1.0, "六角形の向きが違います"),
    "*": (59, 60, 1.0, "五芒星の代わりに四芒星です"),
    "8": (8, 19, 1.0, "八角形の代わりに円です"),
    "+": (0, 0, 1.0, None),
    "P": (0, 0, 1.0, "太い + の代わりに + です"),
    "x": (1, 1, 1.0, None),
    "X": (1, 1, 1.0, "太い x の代わりに x です"),
    "_": (9, 9, 1.0, None),
    "|": (10, 10, 1.0, None),
    ".": (19, 19, 0.5, None),
}
_LINE_MARKERS = ("+", "P", "x", "X", "_", "|")  # 線だけで描く記号。色は塗りではなく線の色（縁の色）を使う

# Igor の破線パターン（lStyle の番号 → [(線の長さ, 隙間), …]。単位 pt）。第2回の実機で ls_w1 / ls_w3 の PNG から測定。
# 線幅を 1 と 3 に変えても同じ長さだった（= 絶対長。matplotlib は線幅に比例する）。
_IGOR_DASH = {
    1: [(0.6, 1.2)],
    2: [(1.5, 2.1)],
    3: [(3.6, 4.2)],
    4: [(2.7, 2.1), (0.6, 2.1)],
    5: [(5.7, 4.2), (1.5, 4.2)],
    6: [(6.6, 2.1), (1.5, 2.1), (1.5, 2.1)],
    7: [(5.7, 6.3)],
    8: [(9.6, 10.2)],
    9: [(9.6, 6.3), (2.7, 6.3)],
    10: [(9.6, 6.3), (2.7, 6.3), (2.7, 6.3)],
    11: [(4.5, 2.1)],
    12: [(32.7, 2.1), (4.5, 2.1)],
    13: [(25.5, 2.1), (4.5, 2.1), (4.5, 2.1)],
    14: [(18.6, 2.1), (4.5, 2.1), (4.5, 2.1), (4.5, 2.1)],
}
_MPL_DASH_RC = {"--": "lines.dashed_pattern", "dashed": "lines.dashed_pattern",
                "-.": "lines.dashdot_pattern", "dashdot": "lines.dashdot_pattern",
                ":": "lines.dotted_pattern", "dotted": "lines.dotted_pattern"}
_LEGEND_ANCHOR = {0: "RT", 1: "RT", 2: "LT", 3: "LB", 4: "RB", 5: "RC",
                  6: "LC", 7: "RC", 8: "MB", 9: "MT", 10: "MC"}
_MAX_IMAGES = 9

# --- mathtext の簡易変換 -------------------------------------------------------
_MATH_SYMBOLS = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε",
    "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ", "kappa": "κ", "lambda": "λ",
    "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ",
    "phi": "φ", "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
    "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
    "AA": "Å", "cdot": "·", "times": "×", "pm": "±", "mp": "∓", "degree": "°",
    "sim": "∼", "approx": "≈", "infty": "∞", "leq": "≤", "geq": "≥", "neq": "≠",
    "rightarrow": "→", "leftarrow": "←", "partial": "∂", "nabla": "∇", "hbar": "ℏ",
    "ell": "ℓ", "angstrom": "Å", "perp": "⊥", "parallel": "∥", "propto": "∝",
}
_MATH_UPRIGHT_CMDS = {"mathrm", "rm", "text", "textrm", "mathsf", "mathtt", "mathbf", "mathcal", "textbf", "bf"}
_MATH_ITALIC_CMDS = {"mathit", "it", "textit"}
_MATH_SPACE_CMDS = {",", ";", ":", " ", "quad", "qquad"}


def _read_arg(s: str, i: int):
    """s[i:] の先頭の引数（{...} か 1トークン）を返す。戻り値: (内容, 次の位置)"""
    if i >= len(s):
        return "", i
    if s[i] == "{":
        depth, j = 1, i + 1
        while j < len(s) and depth:
            depth += (s[j] == "{") - (s[j] == "}")
            j += 1
        return s[i + 1 : j - 1], j
    if s[i] == "\\":
        m = re.match(r"\\([A-Za-z]+|.)", s[i:])
        return m.group(0), i + len(m.group(0))
    return s[i], i + 1


def _parse_math(s: str, warn: list, italic: bool = True) -> list:
    """トークン: ('t', 文字列) 通常 / ('i', 英字) 斜体にする文字 / ('e', Igorエスケープ)"""
    toks: list = []
    i = 0
    while i < len(s):
        c = s[i]
        if c in "^_":
            arg, i = _read_arg(s, i + 1)
            code = "\\S" if c == "^" else "\\B"
            toks += [("e", code)] + _parse_math(arg, warn, italic=False) + [("e", "\\M")]
        elif c == "\\":
            m = re.match(r"\\([A-Za-z]+|.)", s[i:])
            cmd = m.group(1)
            i += len(m.group(0))
            if cmd in _MATH_UPRIGHT_CMDS or cmd in _MATH_ITALIC_CMDS:
                arg, i = _read_arg(s, i)
                toks += _parse_math(arg, warn, italic=cmd in _MATH_ITALIC_CMDS)
            elif cmd in _MATH_SPACE_CMDS:
                toks.append(("t", " "))
            elif cmd in ("!", "left", "right"):
                pass
            elif cmd in _MATH_SYMBOLS:
                toks.append(("t", _MATH_SYMBOLS[cmd]))
            elif len(cmd) == 1 and not cmd.isalpha():
                toks.append(("t", cmd))  # \% \{ \} \_ \^ \$ \# \&
            else:
                warn.append(f"mathtext の \\{cmd} は未対応のため、そのまま文字として出力しました")
                toks.append(("t", "\\" + cmd))
        elif c in "{}":
            i += 1
        else:
            toks.append(("i" if (italic and c.isascii() and c.isalpha()) else "t", c))
            i += 1
    return toks


def _text_to_tokens(text: str, warn: list, italic_math: bool = True) -> list:
    """matplotlib のラベル文字列をトークン列に変換する。$...$ の内側だけ mathtext として扱う。"""
    toks: list = []
    parts = re.split(r"(?<!\\)\$", text)
    for k, seg in enumerate(parts):
        if k % 2 == 1 and k < len(parts) - 1:  # 奇数番目で、閉じの $ があるものが数式
            toks += _parse_math(seg, warn, italic=italic_math)
        else:
            prefix = "$" if (k % 2 == 1 and k == len(parts) - 1) else ""  # 閉じていない $ は文字として残す
            toks.append(("t", prefix + seg.replace("\\$", "$")))
    return toks


def _escape_text(v: str) -> str:
    out = []
    for ch in v:
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\r")
        elif o < 32:
            out.append(" ")
        elif o > 126:
            if o > 0xFFFF:
                o -= 0x10000
                out.append("\\u%04X\\u%04X" % (0xD800 + (o >> 10), 0xDC00 + (o & 0x3FF)))
            else:
                out.append("\\u%04X" % o)
        else:
            out.append(ch)
    return "".join(out)


def _tokens_to_literal(toks: list) -> str:
    """トークン列を Igor の文字列リテラルの中身（引用符の内側）に変換する。
    - 注釈レベルのエスケープ \\S などは、リテラルでは \\\\S と二重にする。
    - 非ASCII文字は \\uXXXX（UTF-16）にして、ファイルの文字コードに依存しないようにする。
    - 斜体の連続した英字は \\f02 … \\f00 で囲む。
    """
    out = []
    i = 0
    while i < len(toks):
        kind, v = toks[i]
        if kind == "e":
            out.append("\\\\" + v[1:])
        elif kind == "i":
            j = i
            run = ""
            while j < len(toks) and toks[j][0] == "i":
                run += toks[j][1]
                j += 1
            out.append("\\\\f02" + _escape_text(run) + "\\\\f00")
            i = j
            continue
        else:
            out.append(_escape_text(v))
        i += 1
    return "".join(out)


def _label_literal(text: str, warn: list, italic_math: bool = True) -> str:
    return _tokens_to_literal(_text_to_tokens(text, warn, italic_math))


def _style_check_label(text: str, where: str, warn: list) -> None:
    """好みの規則（Åを使わない・単位は [ ] で囲む）に合わないラベルを警告する。書き換えはしない。"""
    if re.search(r"Å|\\AA|\\angstrom|\\mathring|\\Ang\b", text):
        warn.append(f"スタイル: {where}のラベル '{text}' に Å があります。nm 系の単位で書く規則です"
                    "（Å のデータは nm⁻¹ に換算してから描く）")
    if re.search(r"\s/\s*\S", text) and "[" not in text:
        warn.append(f"スタイル: {where}のラベル '{text}' の単位が [ ] で囲まれていません"
                    "（例: Q [nm$^{-1}$]。比のラベルなら無視してよい）")


# --- 内部データ構造 ----------------------------------------------------------
@dataclass
class _Err:
    lo: np.ndarray
    hi: np.ndarray


@dataclass
class _Trace:
    x: np.ndarray
    y: np.ndarray
    rgb: tuple
    mode: int  # Igor: 0=線, 3=マーカー, 4=線+マーカー
    marker: Optional[int] = None
    msize: float = 2.5
    opaque: Optional[int] = None
    mrk_thick: float = 1.0
    lsize: Optional[float] = None
    lstyle: Optional[int] = None   # Igor の線種番号（None または 0 は実線）
    label: Optional[str] = None
    xerr: Optional[_Err] = None
    yerr: Optional[_Err] = None
    err_rgb: Optional[tuple] = None
    err_lthick: float = 1.0
    err_capthick: float = 1.0
    err_capsize: float = 3.0


@dataclass
class _Image:
    z: np.ndarray            # 形 (nx, ny)。Igor の dim0 = x, dim1 = y
    xe: np.ndarray           # ピクセル端の x 座標 (nx+1)、単調増加
    ye: np.ndarray           # ピクセル端の y 座標 (ny+1)、単調増加
    cmap_rgb: Optional[np.ndarray]  # (256, 3) の 0..65535。None なら Igor 標準テーブルを使う
    vmin: float
    vmax: float
    log: bool
    cbar_label: Optional[str] = None
    has_cbar: bool = False
    cb_box: Optional[tuple] = None   # (x0, y0, 幅, 高さ): matplotlib のカラーバー軸の位置（Figure に対する割合）
    cb_fsize: Optional[float] = None  # カラーバーの目盛りラベルの文字サイズ (pt)


@dataclass
class _Contour:
    z: np.ndarray            # 形 (nx, ny)。Igor の dim0 = x, dim1 = y
    x: np.ndarray            # 行の x 座標 (nx)、単調増加
    y: np.ndarray            # 列の y 座標 (ny)、単調増加
    levels: np.ndarray       # 等高線のレベル（昇順）
    color: tuple             # ("rgb", (r,g,b)) か ("cmap", 色テーブル(256,3), vmin, vmax)
    lsize: float = 1.0
    filled: bool = False     # contourf（塗り）
    labels: Optional[float] = None   # clabel があれば、その文字サイズ (pt)


@dataclass
class ExportReport:
    files: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    n_traces: int = 0
    n_images: int = 0
    n_contours: int = 0
    commands: list = field(default_factory=list)  # h5 に埋め込んだ（= ローダーが実行する）命令
    style_file: Optional[str] = None              # 使ったスタイルファイル（あれば）

    def summary(self) -> str:
        lines = [f"{self.n_traces} トレース、{self.n_images} 画像{'、' + str(self.n_contours) + ' 等高線' if self.n_contours else ''}を書き出しました:"]
        if self.style_file:
            lines.append(f"スタイルファイル: {self.style_file}")
        lines += [f"  {f}" for f in self.files]
        if self.warnings:
            lines.append(f"警告 {len(self.warnings)} 件（Igor では再現されない要素・スタイル規則）:")
            lines += [f"  - {w}" for w in self.warnings]
        else:
            lines.append("警告なし")
        return "\n".join(lines)


# --- Figure の読み取り（線） ----------------------------------------------------
def _f64(a) -> np.ndarray:
    return np.ma.filled(np.ma.asarray(a).astype(float), np.nan).astype("<f8")


def _rgb(c) -> tuple:
    r, g, b = mcolors.to_rgb(c)
    return (r, g, b)


def _igor_rgb(rgb) -> str:
    return "(%d,%d,%d)" % tuple(int(round(v * 65535)) for v in rgb)


def _fmt(v: float) -> str:
    return f"{v:.6g}"


def _marker_size(ms_points: float, mew: float = 1.0) -> float:
    """matplotlib の markersize（pt）と縁の線幅 → Igor の msize。公式: 外形 = 2*s+1 pt。
    matplotlib の外形は markersize + 縁の線幅（縁は輪郭の内外に半分ずつ）。第3回の実機の実測で、
    縁の線幅ぶん（約 0.8 pt）Igor の方が小さかったので、それを足して合わせる。"""
    return max((ms_points + mew - 1.0) / 2.0, 0.5)


def _is_none_marker(m) -> bool:
    return m is None or (isinstance(m, str) and m.strip() in ("", "None", "none", " "))


def _mpl_dash_pattern(line):
    """matplotlib の線の破線パターン [on, off, …]（pt、線幅を掛けたもの）。実線・不明なら None。"""
    import matplotlib as mpl
    ls = line.get_linestyle()
    scale = line.get_linewidth() if mpl.rcParams["lines.scale_dashes"] else 1.0
    if isinstance(ls, str):
        rc = _MPL_DASH_RC.get(ls)
        pat = mpl.rcParams[rc] if rc else None
    elif isinstance(ls, (tuple, list)) and len(ls) == 2 and ls[1] is not None:
        pat = list(ls[1])
    else:
        pat = None
    if not pat or len(pat) < 2:
        return None
    return [float(p) * scale for p in pat]


def _best_igor_dash(pattern):
    """matplotlib の破線パターンに最も近い Igor の線種番号と、近さの指標（周期の比）を返す。
    同じ数の線分を持つパターンから、周期（線+隙間）と線の割合が近いものを選ぶ。"""
    ons, offs = pattern[0::2], pattern[1::2][: len(pattern[0::2])]
    if len(offs) < len(ons):
        offs = offs + [offs[-1] if offs else 1.0]
    period, duty = sum(ons) + sum(offs), sum(ons) / (sum(ons) + sum(offs))
    best, best_score, best_ratio = None, 1e9, 1.0
    for no, segs in _IGOR_DASH.items():
        if len(segs) != len(ons):
            continue
        p = sum(a + b for a, b in segs)
        d = sum(a for a, _ in segs) / p
        score = abs(np.log(p / period)) + 2.0 * abs(d - duty)
        if score < best_score:
            best, best_score, best_ratio = no, score, p / period
    if best is None:  # 線分の数が合うものが無ければ、全体から選ぶ
        for no, segs in _IGOR_DASH.items():
            p = sum(a + b for a, b in segs)
            d = sum(a for a, _ in segs) / p
            score = abs(np.log(p / period)) + 2.0 * abs(d - duty) + 0.5
            if score < best_score:
                best, best_score, best_ratio = no, score, p / period
    return best, best_ratio


def _line_style_info(line, warn: list, what: str):
    """(線があるか, Igor の線種番号)。実線は番号 0。"""
    ls = line.get_linestyle()
    has_line = (ls not in ("None", "none", " ", "")) and line.get_linewidth() > 0
    if not has_line or ls in ("-", "solid"):
        return has_line, 0
    pat = _mpl_dash_pattern(line)
    if pat is None:
        warn.append(f"{what}: 線種 '{ls}' を読み取れないため、実線にしました")
        return has_line, 0
    no, ratio = _best_igor_dash(pat)
    if not (0.6 <= ratio <= 1.7):
        warn.append(f"{what}: 線種 '{ls}' は Igor の線種 {no} で近似しました（破線の周期が {ratio:.1f} 倍）")
    return has_line, no


def _circle_style(m, face, edge, ms, mew, warn: list, what: str):
    """マーカー記号と塗りから (marker番号, opaque, rgb, size) を決める（名前は円だけだった頃のまま）。
    対応表は _MARKER_MAP。塗り = 塗りつぶしの番号、白抜き・透明 = 白抜きの番号（白で塗るなら opaque=1）。
    線だけの記号（+ x _ |）は色に縁の色を使う。表に無い記号は、円に置き換えて警告する。"""
    white = face is not None and mcolors.to_rgb(face) == (1.0, 1.0, 1.0) and mcolors.to_rgb(edge) != (1.0, 1.0, 1.0)
    ent = _MARKER_MAP.get(m)
    if ent is None:
        warn.append(f"{what}: マーカー '{m}' は Igor に対応する記号が無いため、円にしました")
        ent = _MARKER_MAP["o"]
    open_no, filled_no, factor, note = ent
    if note:
        warn.append(f"{what}: マーカー '{m}': {note}")
    size = ms * factor
    if m in _LINE_MARKERS:
        return open_no, None, edge, size
    if m == ".":
        return filled_no, None, (face if face is not None else edge), size
    if face is None:  # 白抜き・透明
        return open_no, 0, edge, size
    if white:
        return open_no, 1, edge, size  # 白で塗った記号 = 不透明マーカー
    return filled_no, None, face, size


def _resolve_face(line):
    mfc = line.get_markerfacecolor()
    if isinstance(mfc, str) and mfc in ("auto", "default"):
        mfc = line.get_color()
    if isinstance(mfc, str) and mfc == "none":
        return None
    rgba = mcolors.to_rgba(mfc)
    return None if rgba[3] == 0 else rgba[:3]


def _trace_from_line(line, warn, what, label=None) -> Optional[_Trace]:
    try:
        x, y = _f64(line.get_xdata(orig=False)), _f64(line.get_ydata(orig=False))
    except (TypeError, ValueError):
        warn.append(f"{what}: データを数値に変換できないためスキップしました（日付軸など）")
        return None
    if line.get_alpha() not in (None, 1, 1.0):
        warn.append(f"{what}: alpha は未対応のため無視しました")
    has_line, lstyle = _line_style_info(line, warn, what)
    m = line.get_marker()
    has_marker = not _is_none_marker(m)
    if not has_line and not has_marker:
        warn.append(f"{what}: 線もマーカーも無いためスキップしました")
        return None
    line_rgb = _rgb(line.get_color())
    t = _Trace(x=x, y=y, rgb=line_rgb, mode=0, label=label)
    if has_line:
        t.lsize = float(line.get_linewidth())
        t.lstyle = lstyle or None
    if has_marker:
        face = _resolve_face(line)
        edge = line.get_markeredgecolor()
        edge = line.get_color() if (isinstance(edge, str) and edge in ("auto", "default")) else edge
        mk, opq, mrgb, size = _circle_style(m, face, _rgb(edge), line.get_markersize(),
                                            line.get_markeredgewidth(), warn, what)
        t.mrk_thick = float(line.get_markeredgewidth())
        t.marker, t.opaque, t.msize = mk, opq, _marker_size(size, t.mrk_thick)
        t.mode = 4 if has_line else 3
        if has_line and tuple(np.round(mrgb, 4)) != tuple(np.round(line_rgb, 4)):
            warn.append(f"{what}: 線とマーカーの色が異なるが、Igor のトレースは1色のため線の色にしました")
        if not has_line:
            t.rgb = tuple(mrgb)
    return t


def _trace_from_scatter(coll, warn, what) -> Optional[_Trace]:
    off = np.ma.filled(np.ma.asarray(coll.get_offsets()).astype(float), np.nan)
    if off.ndim != 2 or off.shape[1] != 2 or len(off) == 0:
        warn.append(f"{what}: scatter の座標を読み取れないためスキップしました")
        return None
    sizes = np.asarray(coll.get_sizes(), float)
    s = float(sizes[0]) if sizes.size else 36.0
    if sizes.size > 1 and not np.allclose(sizes, sizes[0]):
        warn.append(f"{what}: 点ごとに異なるサイズは未対応のため、最初の値を全点に使いました")
    fc = np.asarray(coll.get_facecolor())
    ec = np.asarray(coll.get_edgecolor())
    if len(fc) > 1 and not np.allclose(fc, fc[0]):
        warn.append(f"{what}: 点ごとに異なる色は未対応のため、最初の色を全点に使いました")
    face = None if (len(fc) == 0 or fc[0][3] == 0) else tuple(fc[0][:3])
    edge = tuple(ec[0][:3]) if len(ec) else (face or (0, 0, 0))
    mk, opq, mrgb, size = _circle_style("o", face, edge, float(np.sqrt(s)), 1.0, warn, what)
    return _Trace(x=off[:, 0].astype("<f8"), y=off[:, 1].astype("<f8"), rgb=tuple(mrgb), mode=3,
                  marker=mk, msize=_marker_size(size), opaque=opq, label=coll.get_label())


def _errors_from_container(cont, t: _Trace, warn, what):
    data_line, caplines, barcols = cont.lines
    n = len(t.x)
    for col in barcols:
        segs = [np.asarray(s, float) for s in col.get_segments()]
        if len(segs) != n:
            warn.append(f"{what}: エラーバーの本数 {len(segs)} が点数 {n} と一致しないため省略しました")
            continue
        seg = np.array([s if s.shape == (2, 2) else np.full((2, 2), np.nan) for s in segs])
        vertical = np.nanmax(np.abs(seg[:, 0, 0] - seg[:, 1, 0])) < 1e-12 * max(1.0, np.nanmax(np.abs(seg[:, :, 0])))
        if vertical:
            t.yerr = _Err(lo=(t.y - seg[:, 0, 1]).astype("<f8"), hi=(seg[:, 1, 1] - t.y).astype("<f8"))
        else:
            t.xerr = _Err(lo=(t.x - seg[:, 0, 0]).astype("<f8"), hi=(seg[:, 1, 0] - t.x).astype("<f8"))
    if barcols:
        lw = barcols[0].get_linewidths()
        t.err_lthick = float(lw[0]) if len(lw) else 1.0
        col = barcols[0].get_colors()
        if len(col):
            ec = tuple(col[0][:3])
            if tuple(np.round(ec, 4)) != tuple(np.round(t.rgb, 4)):
                t.err_rgb = ec
    if caplines:
        # matplotlib の capsize はキャップの半幅で、キャップ記号の markersize = 2*capsize（全幅）。
        # Igor の ErrorBars /X= /Y= は全幅（第3回の実機で 1〜8 を測定: キャップの実寸 ≈ 指定値）。
        t.err_capsize = float(caplines[0].get_markersize())
        t.err_capthick = float(caplines[0].get_markeredgewidth())
    else:
        t.err_capsize = 0.0


# --- Figure の読み取り（画像） ----------------------------------------------------
def _is_log_norm(norm) -> bool:
    return isinstance(norm, mcolors.LogNorm) or isinstance(getattr(norm, "_scale", None), LogScale)


def _cmap_table(cmap) -> np.ndarray:
    rgb = np.asarray(cmap(np.linspace(0.0, 1.0, 256)))[:, :3]
    return np.round(rgb * 65535.0).astype("<f8")


def _monotonic(edges: np.ndarray, z: np.ndarray, axis: int):
    """端の座標が減少している場合、座標とデータを反転して単調増加にする。"""
    if edges[0] > edges[-1]:
        return edges[::-1].copy(), np.flip(z, axis=axis)
    return edges, z


def _image_common(mappable, arr, xe, ye, what, warn, ctab) -> Optional[_Image]:
    """画像の共通部分: 配列（ny, nx）・端座標・norm・colormap・カラーバーから _Image を作る。"""
    arr = np.ma.asarray(arr)
    z = np.ma.filled(arr.astype(float) if arr.dtype.kind not in "f" else arr, np.nan)
    if arr.dtype == np.float32:
        z = z.astype("<f4")
    else:
        z = z.astype("<f8")
    z = z.T  # Igor: dim0 = x（列）, dim1 = y（行）
    xe = np.asarray(xe, float)
    ye = np.asarray(ye, float)
    xe, z = _monotonic(xe, z, 0)
    ye, z = _monotonic(ye, z, 1)

    norm = mappable.norm
    norm.autoscale_None(arr)
    log = _is_log_norm(norm)
    if not log and type(norm).__name__ != "Normalize":
        warn.append(f"{what}: {type(norm).__name__} は未対応のため、線形のカラースケールにしました")
    vmin, vmax = float(norm.vmin), float(norm.vmax)
    if mappable.get_alpha() not in (None, 1, 1.0):
        warn.append(f"{what}: alpha は未対応のため無視しました")
    cmap_rgb = None if ctab is not None else _cmap_table(mappable.get_cmap())

    img = _Image(z=np.ascontiguousarray(z), xe=xe, ye=ye, cmap_rgb=cmap_rgb, vmin=vmin, vmax=vmax, log=log)
    cb = getattr(mappable, "colorbar", None)
    if cb is not None:
        img.has_cbar = True
        bb = cb.ax.get_position()
        img.cb_box = (bb.x0, bb.y0, bb.width, bb.height)
        tl = [t for t in cb.ax.get_yticklabels() + cb.ax.get_xticklabels() if t.get_text()]
        img.cb_fsize = float(tl[0].get_fontsize()) if tl else None
        if cb.orientation != "vertical":
            warn.append(f"{what}: 横向きのカラーバーは未対応のため、縦向きのカラースケールにしました")
            img.cbar_label = cb.ax.get_xlabel() or None
        else:
            img.cbar_label = cb.ax.get_ylabel() or None
    return img


def _image_from_axesimage(im, what, warn, ctab) -> Optional[_Image]:
    arr = im.get_array()
    if arr is None:
        return None
    if np.ma.asarray(arr).ndim != 2:
        warn.append(f"{what}: RGB/RGBA 画像（3次元配列）は未対応のためスキップしました")
        return None
    ny, nx = np.ma.asarray(arr).shape
    left, right, bottom, top = im.get_extent()
    xe = left + (right - left) * np.arange(nx + 1) / nx
    if im.origin == "upper":  # 行0が上端（top）
        ye = top + (bottom - top) * np.arange(ny + 1) / ny
    else:
        ye = bottom + (top - bottom) * np.arange(ny + 1) / ny
    return _image_common(im, arr, xe, ye, what, warn, ctab)


def _image_from_quadmesh(qm, what, warn, ctab) -> Optional[_Image]:
    if getattr(qm, "_shading", "flat") == "gouraud":
        warn.append(f"{what}: shading='gouraud' は未対応のためスキップしました")
        return None
    coords = np.asarray(qm.get_coordinates(), float)
    if coords.ndim != 3 or coords.shape[2] != 2:
        warn.append(f"{what}: メッシュ座標を読み取れないためスキップしました")
        return None
    ny, nx = coords.shape[0] - 1, coords.shape[1] - 1
    arr = np.ma.asarray(qm.get_array())
    if arr.size != nx * ny:
        warn.append(f"{what}: 配列の大きさ {arr.shape} がメッシュ ({ny}, {nx}) と一致しないためスキップしました")
        return None
    xs, ys = coords[:, :, 0], coords[:, :, 1]
    if not (np.allclose(xs, xs[0:1, :]) and np.allclose(ys, ys[:, 0:1])):
        warn.append(f"{what}: 矩形でないメッシュは未対応のためスキップしました")
        return None
    return _image_common(qm, arr.reshape(ny, nx), xs[0, :], ys[:, 0], what, warn, ctab)


# --- 等高線の元データ (X, Y, Z) の取得 --------------------------------------------
# matplotlib の ContourSet は、contour() を呼んだ瞬間に Z から折れ線を作り、Z は捨てる（3.9.4 で確認。
# _contour_generator にも z は無い）。そこで、公開 API の Axes.contour / contourf を包んで、呼び出しの瞬間に
# (X, Y, Z) を ContourSet に保存する。このモジュールを import した後に描いた図が対象（import 時に自動で入る）。
# 内部関数 _contour_args を包む方法でも同じ結果になるが、非公開なので使わない（check_mpl_versions.py で 3.6〜3.10 を確認）。
def _args_to_xyz(args):
    """Axes.contour([X, Y,] Z, [levels]) の位置引数から (X, Y, Z) を取る。取れなければ None。"""
    n = len(args)
    try:
        if n in (1, 2):
            Z = np.ma.array(args[0], copy=True)
            if Z.ndim != 2:
                return None
            return np.arange(Z.shape[1], dtype=float), np.arange(Z.shape[0], dtype=float), Z
        if n in (3, 4):
            return (np.array(args[0], dtype=float), np.array(args[1], dtype=float), np.ma.array(args[2], copy=True))
    except (TypeError, ValueError):
        return None
    return None


def _wrap_contour(orig):
    @functools.wraps(orig)
    def wrapper(self, *args, **kwargs):
        cs = orig(self, *args, **kwargs)
        try:
            xyz = None if "data" in kwargs else _args_to_xyz(args)
            if xyz is not None:
                cs._eig_xyz = xyz
                self.__dict__.setdefault("_eig_contours", []).append(cs)
        except Exception:  # 取得に失敗しても、matplotlib の動作は妨げない
            pass
        return cs
    wrapper._eig_wrapped = True
    return wrapper


def install_contour_capture() -> None:
    """Axes.contour / contourf を包んで、元データ (X, Y, Z) を保存する。import 時に呼ばれる。何度呼んでも1回だけ。"""
    for nm in ("contour", "contourf"):
        f = getattr(Axes, nm)
        if not getattr(f, "_eig_wrapped", False):
            setattr(Axes, nm, _wrap_contour(f))


def uninstall_contour_capture() -> None:
    for nm in ("contour", "contourf"):
        f = getattr(Axes, nm)
        if getattr(f, "_eig_wrapped", False):
            setattr(Axes, nm, f.__wrapped__)


install_contour_capture()


def _contour_grid(data, what, warn):
    """(X, Y, Z) を Igor の行列・座標にする。Z: (ny, nx)。X, Y: 1次元 (nx, ny)、または meshgrid の2次元（矩形格子のみ）。
    戻り値 (x, y, z[nx, ny]) か None。"""
    try:
        X, Y, Z = data
    except (TypeError, ValueError):
        warn.append(f"{what}: contour_data は (X, Y, Z) の形で渡してください")
        return None
    z = np.ma.filled(np.ma.asarray(Z).astype(float), np.nan)
    if z.ndim != 2:
        warn.append(f"{what}: Z は2次元配列にしてください（形 {z.shape}）")
        return None
    ny, nx = z.shape
    X, Y = np.asarray(X, float), np.asarray(Y, float)
    if X.ndim == 2:
        if X.shape != z.shape or not np.allclose(X, X[0:1, :]):
            warn.append(f"{what}: 矩形でない格子の X は未対応です（Igor の AppendMatrixContour は行と列の座標を取ります）")
            return None
        X = X[0]
    if Y.ndim == 2:
        if Y.shape != z.shape or not np.allclose(Y, Y[:, 0:1]):
            warn.append(f"{what}: 矩形でない格子の Y は未対応です")
            return None
        Y = Y[:, 0]
    if X.shape != (nx,) or Y.shape != (ny,):
        warn.append(f"{what}: X {X.shape} と Y {Y.shape} が Z {z.shape} = (ny, nx) と合いません")
        return None
    zz = np.ascontiguousarray(z.T)  # Igor: dim0 = x（列）, dim1 = y（行）
    x, zz = _monotonic(X.copy(), zz, 0)
    y, zz = _monotonic(Y.copy(), zz, 1)
    return x.astype("<f8"), y.astype("<f8"), np.ascontiguousarray(zz, dtype="<f8")


def _contour_from_set(cs, data, what, warn) -> Optional[_Contour]:
    if not isinstance(cs, Collection):
        warn.append(f"{what}: matplotlib 3.8 未満の等高線は未対応のためスキップしました")
        return None
    grid = _contour_grid(data, what, warn)
    if grid is None:
        return None
    x, y, z = grid
    levels = np.sort(np.asarray(cs.levels, float))
    if levels.size < (2 if cs.filled else 1):
        warn.append(f"{what}: レベルがありません")
        return None
    lw = np.asarray(cs.get_linewidth(), float)
    lsize = float(lw[0]) if lw.size and lw[0] > 0 else 1.0
    uses_cmap = getattr(cs, "colors", None) is None
    if cs.filled:
        if uses_cmap:
            color = ("cmap", _cmap_table(cs.get_cmap()), float(cs.norm.vmin), float(cs.norm.vmax))
        else:
            color = ("rgb", tuple(float(v) for v in np.asarray(cs.get_facecolor())[0][:3]))
            warn.append(f"{what}: contourf の colors= の色リストは未対応のため、最初の色で塗りました")
    else:
        ec = np.asarray(cs.get_edgecolor())
        if uses_cmap:
            color = ("cmap", _cmap_table(cs.get_cmap()), float(cs.norm.vmin), float(cs.norm.vmax))
        else:
            color = ("rgb", tuple(float(v) for v in ec[0][:3]))
            if len(ec) > 1 and not np.allclose(ec, ec[0]):
                warn.append(f"{what}: レベルごとに異なる色のリスト（colors=[…]）は未対応のため、最初の色にしました")
        if any(isinstance(s, tuple) and len(s) == 2 and s[1] is not None for s in cs.get_linestyle()):
            warn.append(f"{what}: 負のレベルの破線は未対応のため、実線にしました")
    lt = getattr(cs, "labelTexts", None)
    if getattr(cs, "colorbar", None) is not None:
        warn.append(f"{what}: 等高線のカラーバーは未対応のためスキップしました")
    if cs.get_alpha() not in (None, 1, 1.0):
        warn.append(f"{what}: alpha は未対応のため無視しました")
    return _Contour(z=z, x=x, y=y, levels=levels, color=color, lsize=lsize, filled=bool(cs.filled),
                    labels=float(lt[0].get_fontsize()) if lt else None)


def _contour_sets(ax):
    """Axes にある ContourSet（描かれた順）。import 後に描いたものは、包んだ関数が登録している。"""
    sets = []
    for cs in list(ax.__dict__.get("_eig_contours", [])) + [c for c in ax.collections if isinstance(c, ContourSet)]:
        if not any(cs is s for s in sets):
            sets.append(cs)
    present = []
    for cs in sets:  # cs.remove() 済みのものは除く
        if isinstance(cs, Collection):
            if any(cs is c for c in ax.collections):
                present.append(cs)
        else:
            present.append(cs)
    return present


def _collect(ax, warn: list, ctab, contour_data=None):
    traces: list = []
    images: list = []
    contours: list = []
    # contour_data: (X, Y, Z) 1組、またはその並び（等高線を描いた順）、または {ContourSet: (X, Y, Z)}
    cd_map: dict = {}
    cd_list: list = []
    if isinstance(contour_data, dict):
        cd_map = dict(contour_data)
    elif contour_data is not None:
        looks_single = len(contour_data) == 3 and np.ndim(contour_data[2]) == 2 and not isinstance(contour_data[0], (tuple, list))
        cd_list = [contour_data] if looks_single else list(contour_data)
    for j, cs in enumerate(_contour_sets(ax)):
        what = f"{'contourf' if getattr(cs, 'filled', False) else 'contour'}[{j}]"
        data = cd_map.get(cs, cd_list[j] if j < len(cd_list) else getattr(cs, "_eig_xyz", None))
        if data is None:
            warn.append(f"{what}: 元のデータ (X, Y, Z) がありません。mpl_to_igor を import した後に描くか、"
                        "contour_data=(X, Y, Z) を渡してください。スキップしました")
            continue
        ct_ = _contour_from_set(cs, data, what, warn)
        if ct_ is not None:
            contours.append(ct_)
    cont_by_line, skip_ids = {}, set()
    for cont in ax.containers:
        if isinstance(cont, ErrorbarContainer):
            data_line, caplines, barcols = cont.lines
            for cl in caplines:
                skip_ids.add(id(cl))
            for bc in barcols:
                skip_ids.add(id(bc))
            if data_line is None:
                warn.append(f"errorbar '{cont.get_label()}': fmt='none' (データ点なし) は未対応のためスキップしました")
            else:
                cont_by_line[id(data_line)] = cont
    for k, im in enumerate(ax.images):
        what = f"imshow[{k}]"
        if isinstance(im, (NonUniformImage, PcolorImage, BboxImage)) or not isinstance(im, AxesImage):
            warn.append(f"{what}: {type(im).__name__} は未対応のためスキップしました")
            continue
        img = _image_from_axesimage(im, what, warn, ctab)
        if img is not None:
            images.append(img)
    # 描画順: matplotlib は collections(scatter) → lines の順に重なる
    for k, coll in enumerate(ax.collections):
        if id(coll) in skip_ids or isinstance(coll, ContourSet):  # 等高線は上で処理済み
            continue
        if isinstance(coll, QuadMesh):
            img = _image_from_quadmesh(coll, f"pcolormesh[{k}]", warn, ctab)
            if img is not None:
                images.append(img)
        elif isinstance(coll, PathCollection):
            t = _trace_from_scatter(coll, warn, f"scatter[{k}]")
            if t:
                traces.append(t)
        elif isinstance(coll, LineCollection):
            warn.append(f"LineCollection[{k}] (hlines/vlines 等) は未対応のためスキップしました")
        else:
            warn.append(f"{type(coll).__name__}[{k}] (pcolor/contour/fill_between 等) は未対応のためスキップしました")
    for k, line in enumerate(ax.lines):
        if id(line) in skip_ids or not line.get_visible():
            continue
        cont = cont_by_line.get(id(line))
        what = f"errorbar '{cont.get_label()}'" if cont else f"line[{k}] '{line.get_label()}'"
        t = _trace_from_line(line, warn, what, label=cont.get_label() if cont else line.get_label())
        if t is None:
            continue
        if cont is not None:
            _errors_from_container(cont, t, warn, what)
        traces.append(t)
    for t in traces:
        if t.label is not None and (t.label.startswith("_") or t.label == ""):
            t.label = None
    label_ids = {id(t) for cs in _contour_sets(ax) for t in (getattr(cs, "labelTexts", None) or [])}  # clabel の文字は等高線のラベルで再現する
    for kind, items in (("patches (bar/Rectangle 等)", ax.patches),
                        ("texts (注釈)", [t for t in ax.texts if id(t) not in label_ids])):
        if len(items):
            warn.append(f"{kind} が {len(items)} 個あるが未対応のためスキップしました")
    if ax.get_title():
        warn.append("タイトルは未対応のためスキップしました（Igor のグラフにはタイトル欄がありません）")
    return traces, images, contours


def _mpl_font_size(ax) -> int:
    """軸の目盛りラベルの文字サイズ (pt)。Igor の gfSize に使う。"""
    tl = [t for t in ax.get_xticklabels() + ax.get_yticklabels() if t.get_text()]
    size = tl[0].get_fontsize() if tl else ax.xaxis.label.get_size()
    return max(int(round(float(size))), 1)


def _has_sub_sup(text: str) -> bool:
    return any(k == "e" and v in ("\\S", "\\B") for k, v in _text_to_tokens(text, [], True))


# --- 軸ラベルの配置モデル ------------------------------------------------------
# 第2回の実機（Igor 8.04, Windows, Arial）で、calib.py / calib_analyze.py により測った値（単位 pt）。gf = gfSize。
#  * 軸ラベルは、既定ではウィンドウの縁に貼り付く。位置は lblMargin（縁から内側への距離。公式の説明と実測が一致:
#    40 を指定すると 39.9 pt 動いた）で決める。lblPos は 8.04 では効かなかった（記録されるだけ）。
#  * 下軸: 軸線から目盛りラベルの下端までの距離 = a*gf + b（目盛りの向きと対数軸で変わる）。
_TLB = {(False, False): (1.20, 1.40), (False, True): (1.80, 2.90),     # キー: (外向きの目盛りか, 対数軸か)
        (True, False): (1.875, 1.55), (True, True): (2.18, 2.40)}
#  * 左軸: 軸線から目盛りラベルの外縁までの距離 = (文字の幅) + a*gf + b。文字の幅は matplotlib の目盛りラベルから測る。
_TLG = {(False, False): (0.475, -2.25), (False, True): (0.23, -2.2),
        (True, False): (1.15, -2.1), (True, True): (0.6, -2.5)}
_LBL_H = (0.92, 0.1)        # 軸ラベルの文字の高さ = a*gf + b（インクの範囲）
_LBL_SUP = 0.43             # 上付き・下付きがあると、さらに 0.43*gf だけ高くなる
_EDGE_B, _EDGE_L = 0.5, 2.2  # ラベルのインクの外縁とウィンドウの縁の隙間（lblMargin=0 のとき）


def _tick_out_weight(tick) -> float:
    """目盛りが外向きの度合い: 0 外向き → 1、交差 → 0.5（外向きと内向きの中間と仮定。未確認）、内向き・なし → 0。"""
    return {0: 1.0, 1: 0.5}.get(tick, 0.0)


def _tl_bottom(gf, tick, is_log) -> float:
    w = _tick_out_weight(tick)
    (ai, bi), (ao, bo) = _TLB[(False, is_log)], _TLB[(True, is_log)]
    return (1 - w) * (ai * gf + bi) + w * (ao * gf + bo)


def _tl_left(gf, tick, is_log, width_pt) -> float:
    w = _tick_out_weight(tick)
    (ai, bi), (ao, bo) = _TLG[(False, is_log)], _TLG[(True, is_log)]
    g = (1 - w) * (ai * gf + bi) + w * (ao * gf + bo)
    return width_pt + max(g, 0.0)


def _label_size(gf, sup) -> float:
    return _LBL_H[0] * gf + _LBL_H[1] + (_LBL_SUP * gf if sup else 0.0)


def _tick_mode(st, ax):
    """ModifyGraph tick= の値。st["tick"] が "mpl" なら matplotlib の目盛りの向きに合わせる。"""
    t = st.get("tick")
    if t == "mpl":
        axis = ax.xaxis
        try:
            if hasattr(axis, "get_tick_params"):   # matplotlib 3.7 以降の公開 API
                d = axis.get_tick_params(which="major").get("direction", "out")
            else:                                   # 3.6 以前: 内部の辞書（バージョン番号ではなく、機能の有無で切り替える）
                d = getattr(axis, "_major_tick_kw", {}).get("tickdir", "out")
        except Exception:
            d = "out"
        return {"in": 2, "inout": 1, "out": 0}.get(d, 0)
    return t


def _tick_label_width(axis_obj, fs_ratio) -> float:
    """matplotlib の目盛りラベルの最大の幅 (pt)。描画後に呼ぶ。fs_ratio = Igor の文字サイズ / matplotlib の文字サイズ。"""
    try:
        r = axis_obj.figure.canvas.get_renderer()
        dpi = axis_obj.figure.dpi
        labs = axis_obj.get_majorticklabels()
        locs = list(axis_obj.get_majorticklocs())
        lo, hi = sorted(axis_obj.get_view_interval())
        eps = 1e-9 * max(abs(hi - lo), 1e-300)
        if len(locs) != len(labs):
            locs = [lo] * len(labs)  # 対応が取れなければ、全部を見る
        ws = [t.get_window_extent(r).width * 72.0 / dpi for loc, t in zip(locs, labs)
              if t.get_text() and lo - eps <= loc <= hi + eps]
    except Exception:
        return 0.0
    return (max(ws) if ws else 0.0) * fs_ratio


def _mpl_label_gaps(ax):
    """matplotlib の軸ラベルの位置: 軸線からラベルの近い縁までの距離 (pt)。(x 軸ラベル, y 軸ラベル)。ラベルが無ければ None。"""
    fig = ax.figure
    r = fig.canvas.get_renderer()
    k = 72.0 / fig.dpi
    bb = ax.get_window_extent(r)
    out = []
    for lab, side in ((ax.xaxis.label, "b"), (ax.yaxis.label, "l")):
        if not lab.get_text():
            out.append(None)
            continue
        lb = lab.get_window_extent(r)
        out.append(max((bb.y0 - lb.y1) * k, 0.0) if side == "b" else max((bb.x0 - lb.x1) * k, 0.0))
    return tuple(out)


def _colorbar_axes(fig) -> list:
    out = []
    for a in fig.axes:
        for m in list(a.images) + list(a.collections):
            cb = getattr(m, "colorbar", None)
            if cb is not None and cb.ax not in out:
                out.append(cb.ax)
    return out


# --- Igor コードの生成 ---------------------------------------------------------
def _wave_name(prefix: str, k: int, suffix: str) -> str:
    return f"{prefix}_t{k}_{suffix}"


def _img_wave(prefix: str, k: int, suffix: str) -> str:
    return f"{prefix}_i{k}_{suffix}"


def _cont_wave(prefix: str, k: int, suffix: str) -> str:
    return f"{prefix}_c{k}_{suffix}"


def _chunks(items, n):
    for i in range(0, len(items), n):
        yield items[i : i + n]


def write_figure_h5(outdir: str, name: str, datasets: dict, commands: list, wave_names: list,
                    text_mode: str = "string") -> str:
    """実データ（datasets）と描画命令（commands）を、1つの h5 に書く。許可リストの自己検査つき。
    export_igor と、見本図（charts.py）など matplotlib を通さない利用の共通部分。"""
    rejected = [x for x in commands if not is_allowed(x)]
    if rejected:  # 安全性の自己検査: 全命令が、ローダーの許可リストを通ること
        raise ValueError(
            f"生成した命令 {len(rejected)} 個がローダーの許可リスト（eig_allowlist.py）を通りません。"
            f"長すぎる（{MAX_COMMAND_BYTES} バイト超）か、許可されていない形です。最初の1個: {rejected[0][:160]}")
    datasets = dict(datasets)
    meta = ["format=1", f"name={name}", "generator=mpl_to_igor", f"text={text_mode}"]
    if text_mode == "string":
        datasets["igor_cmds"], datasets["igor_waves"], datasets["igor_meta"] = list(commands), list(wave_names), meta
    elif text_mode == "codes":  # 固定長文字列を Igor が読めない場合の代替（文字コードの整数配列）
        datasets["igor_cmds_codes"] = text_to_codes(commands)
        datasets["igor_waves_codes"] = text_to_codes(wave_names)
        datasets["igor_meta_codes"] = text_to_codes(meta)
    else:
        raise ValueError("text_mode は 'string' か 'codes'")
    os.makedirs(outdir, exist_ok=True)
    h5path = os.path.join(outdir, f"{name}.h5")
    write_h5(h5path, datasets)
    return h5path


def export_igor(fig, outdir: str = ".", name: str = "fig1", *, ax=None, style: Optional[dict] = None,
                use_mpl_size: bool = False, italic_math: bool = True,
                ctab: Optional[tuple] = None, write_ipf: bool = False,
                text_mode: str = "string", axis_range: str = "mpl", contour_data=None,
                style_file=None) -> ExportReport:
    """
    fig: 描画済みの matplotlib Figure。ax を省略すると、カラーバー以外の最初の Axes。
    name: グラフ名・データフォルダ名・Wave名の接頭辞（英字始まり・英数字と_・16文字以内）。
    style: STYLE_DEFAULT / STYLE_IMAGE を上書きする辞書。
    use_mpl_size: True なら、matplotlib の軸の大きさ・余白を Igor の width/height/margin にする。
    italic_math: True なら mathtext の変数（ASCII英字）を斜体にする。
    ctab: ("Rainbow", 1) のように Igor 標準の色テーブル名と reverse を渡すと、
          matplotlib の colormap の代わりにそれを使う。None なら colormap を色テーブルWaveで再現する。
    write_ipf: True なら、図ごとの .ipf（Make_<name>()）も出す。既定は h5 だけ。
               h5 には描画命令が埋め込まれ、固定のローダー ExportIgorGraphLoader.ipf の LoadPythonFigure() で読める。
    text_mode: 命令の埋め込み方。"string"（固定長文字列, 既定）か "codes"（文字コードの整数配列。
               Igor 8 が固定長文字列を読めない場合の代替）。
    axis_range: "mpl"（既定）は、matplotlib の実際の軸範囲を SetAxis で固定する（Igor の自動スケールだと、
               データが枠に接して、点や誤差バーが欠ける）。"auto" は、手動で設定した範囲だけ固定する。
    contour_data: 等高線の元データ (X, Y, Z)（Z は (ny, nx)。matplotlib の contour に渡したのと同じ）。
               省略すると、このモジュールを import した後に描いた contour/contourf が、呼び出しの瞬間に保存した
               データを使う。複数あるときは (X, Y, Z) の並び（描いた順）か {ContourSet: (X, Y, Z)}。
    style: 書式の上書き。主な設定: tick・mirror・standoff・grid・width（= width_pt）・height（= height_pt）・
               font・gFont（= gfont）。別名と未知のキー（警告）、値の検査あり。優先順位: 組み込みの既定 < スタイルファイル < style=。
    style_file: スタイルファイル（JSON）。None なら、環境変数 EXPORT_IGORGRAPH_STYLE、カレントの
               export_igorgraph_style.json、ホームの .export_igorgraph_style.json の順に探す。False なら使わない。
    ウィンドウの位置・大きさ、フォント名（style["font"], 既定 Arial）は常に明示して固定する。
    """
    if not _NAME_RE.match(name):
        raise ValueError(f"name '{name}' は英字で始まる英数字と_のみ、16文字以内にしてください")
    rep = ExportReport()
    warn = rep.warnings

    fig.canvas.draw()  # 色・凡例・軸範囲・norm を解決済みの値にする
    if not fig.axes:
        raise ValueError("Figure に Axes がありません")
    cbaxes = _colorbar_axes(fig)
    mains = [a for a in fig.axes if a not in cbaxes] or list(fig.axes)
    if ax is None:
        ax = mains[0]
        if len(mains) > 1:
            warn.append(f"Axes が {len(mains)} 個あるが v2 は1つのみ対応のため、最初の Axes だけを書き出しました")
    traces, images, contours = _collect(ax, warn, ctab, contour_data)
    if not traces and not images and not contours:
        raise ValueError("書き出せるトレース・画像・等高線がありません（警告を確認してください）")
    if len(traces) > 99:
        raise ValueError("トレース数が99を超えています")
    if len(images) > _MAX_IMAGES:
        raise ValueError(f"画像が {_MAX_IMAGES} 枚を超えています")
    if len(contours) > _MAX_IMAGES:
        raise ValueError(f"等高線が {_MAX_IMAGES} 組を超えています")
    rep.n_traces, rep.n_images, rep.n_contours = len(traces), len(images), len(contours)
    has_images = bool(images)
    has_2d = has_images or bool(contours)   # 画像か等高線があれば、2次元データ用の書式（STYLE_IMAGE）・軸の固定を使う
    file_style = {}
    if style_file is not False:
        sf = style_file or find_style_file()
        if sf:
            file_style = _load_style_file(sf, warn)
            rep.style_file = os.path.abspath(sf)
    arg_style = _normalize_style(style, warn, "style")
    user_keys = set(file_style) | set(arg_style)   # 利用者が指定したキー（既定値と区別する）
    st = {**(STYLE_IMAGE if has_2d else STYLE_DEFAULT), **file_style, **arg_style}
    _check_style_values(st)

    # --- データセット（実データ） ---
    datasets, names, ct_waves = {}, [], []
    for k, t in enumerate(traces):
        xn, yn = _wave_name(name, k, "x"), _wave_name(name, k, "y")
        datasets[xn], datasets[yn] = t.x, t.y
        names += [xn, yn]
        for ax_key, err in (("x", t.xerr), ("y", t.yerr)):
            if err is None:
                continue
            if np.allclose(err.lo, err.hi, equal_nan=True):
                en = _wave_name(name, k, "e" + ax_key)
                datasets[en] = err.hi
                names.append(en)
            else:
                for suf, arr in (("p", err.hi), ("n", err.lo)):
                    en = _wave_name(name, k, "e" + ax_key + suf)
                    datasets[en] = arr
                    names.append(en)
    for k, im in enumerate(images):
        for suf, arr in (("z", im.z), ("xe", im.xe), ("ye", im.ye)):
            n = _img_wave(name, k, suf)
            datasets[n] = arr
            names.append(n)
        if im.cmap_rgb is not None:
            n = _img_wave(name, k, "ct")
            datasets[n] = im.cmap_rgb
            names.append(n)
            ct_waves.append(n)
    for k, ct_ in enumerate(contours):  # 等高線: 元の Z 行列・座標・レベル（Igor で ModifyContour により編集できる）
        for suf, arr in (("z", ct_.z), ("x", ct_.x), ("y", ct_.y), ("lv", ct_.levels)):
            n = _cont_wave(name, k, suf)
            datasets[n] = arr
            names.append(n)
        if ct_.color[0] == "cmap":
            n = _cont_wave(name, k, "ct")
            datasets[n] = ct_.color[1]
            names.append(n)
            ct_waves.append(n)

    # --- 命令列（Igor のコマンドライン形式。.ipf にも、h5 への埋め込みにも同じものを使う） ---
    def wnames(k, ax_key, err):
        if np.allclose(err.lo, err.hi, equal_nan=True):
            n = _wave_name(name, k, "e" + ax_key)
            return n, n
        return _wave_name(name, k, "e" + ax_key + "p"), _wave_name(name, k, "e" + ax_key + "n")

    C: list = []
    c = C.append
    for n in ct_waves:
        c(f"Redimension/U/W {n}")  # 色テーブルWaveは 16 ビット符号なし (0..65535) にする
    c(f"DoWindow/K {name}")
    g = f"/W={name}"

    # --- レイアウト: ウィンドウの大きさ・余白・プロット領域・文字を、すべて明示して固定する ---
    aspect_ratio = st["aspect"]
    if has_2d:
        xlo, xhi = ax.get_xlim()
        ylo, yhi = ax.get_ylim()
        asp = ax.get_aspect()
        if asp != "auto":
            try:
                aspect_ratio = abs((yhi - ylo) / (xhi - xlo)) * float(1.0 if asp == "equal" else asp)
            except (TypeError, ValueError, ZeroDivisionError):
                warn.append(f"軸の aspect '{asp}' を読み取れないため、既定のアスペクト比を使いました")
    if use_mpl_size:  # 図の大きさ・軸の位置・文字サイズを matplotlib から取る。ウィンドウ = Figure の大きさ
        pos = ax.get_position()
        W, H = fig.get_size_inches() * 72.0
        lay = dict(ml=pos.x0 * W, mb=pos.y0 * H, mt=(1 - pos.y1) * H, mr=(1 - pos.x1) * W,
                   pw=pos.width * W, ph=pos.height * H)
        gf = _mpl_font_size(ax)
        if "gf_size" in user_keys:
            gf = int(round(st["gf_size"]))
        # 利用者が width / height（プロット領域の大きさ pt）を指定したときだけ、matplotlib の大きさを上書きする
        if "width_pt" in user_keys and st.get("width_pt"):
            lay["pw"] = float(st["width_pt"])
        if "height_pt" in user_keys and st.get("height_pt"):
            lay["ph"] = float(st["height_pt"])
        height_val = _fmt(lay["ph"])
    else:  # preset の書式（STYLE_*）。ウィンドウ = 余白 + プロット領域
        ph_ = float(st["height_pt"]) if st.get("height_pt") else st["width_pt"] * aspect_ratio
        lay = dict(ml=st["margin_left"], mb=st["margin_bottom"], mt=st["margin_top"], mr=st["margin_right"],
                   pw=st["width_pt"], ph=ph_)
        gf = st["gf_size"]
        height_val = _fmt(ph_) if st.get("height_pt") else f"{{Aspect,{_fmt(aspect_ratio)}}}"
    # 軸ラベルの配置: 目盛りの向き・対数軸・上付きを考慮して、目盛りラベルと重ならないようにする（モデルは _TLB 以下）。
    # 軸ラベルは lblMargin（ウィンドウの縁から内側への距離）で置く。足りない余白は、プロット領域の大きさを変えずに広げる。
    tick_val = _tick_mode(st, ax)
    xlog, ylog = ax.get_xscale() == "log", ax.get_yscale() == "log"
    xlab, ylab = ax.get_xlabel(), ax.get_ylabel()
    xsup, ysup = bool(xlab) and _has_sub_sup(xlab), bool(ylab) and _has_sub_sup(ylab)
    gap = st.get("label_gap", 0.3) * gf
    req_top = _tl_bottom(gf, tick_val, xlog) + gap       # 軸線 → x 軸ラベルの上端 の最小
    req_in = _tl_left(gf, tick_val, ylog, _tick_label_width(ax.yaxis, gf / max(_mpl_font_size(ax), 1))) + gap
    hb, hl = _label_size(gf, xsup), _label_size(gf, ysup)
    lbl_m = {"bottom": None, "left": None}
    if use_mpl_size:  # matplotlib のラベルの位置を再現する。ただし、目盛りラベルと重なる位置にはしない
        gx, gy = _mpl_label_gaps(ax)
        top_b, in_l = max(req_top, gx or 0.0), max(req_in, gy or 0.0)
        if xlab:
            need = top_b + hb + _EDGE_B
            if need > lay["mb"] + 0.05:
                warn.append(f"下余白を {need - lay['mb']:.1f} pt 広げました（x 軸ラベルが目盛りラベルと重ならないように。"
                            "プロット領域の大きさは変わりません）")
                lay["mb"] = need
            lbl_m["bottom"] = lay["mb"] - _EDGE_B - hb - top_b
        if ylab:
            need = in_l + hl + _EDGE_L
            if need > lay["ml"] + 0.05:
                warn.append(f"左余白を {need - lay['ml']:.1f} pt 広げました（y 軸ラベルが目盛りラベルと重ならないように）")
                lay["ml"] = need
            lbl_m["left"] = lay["ml"] - _EDGE_L - hl - in_l
    else:  # preset: STYLE_* の余白を最小として、足りなければ広げる。ラベルは既定（ウィンドウの縁）のまま
        if xlab:
            extra = st.get("sub_sup_extra")
            if extra is not None:  # 数値を明示したときは従来どおり、上付き・下付きのとき下余白にその量を足す
                lay["mb"] += extra if xsup else 0.0
                hb = _label_size(gf, False)
            lay["mb"] = max(lay["mb"], req_top + hb + _EDGE_B)
        if ylab:
            lay["ml"] = max(lay["ml"], req_in + hl + _EDGE_L)
    for side, key in (("bottom", "lbl_margin_bottom"), ("left", "lbl_margin_left")):
        if st.get(key) is not None:  # ユーザーの指定が最優先
            lbl_m[side] = st[key]
    # カラースケール（枠つきの注釈）: 外側(/E=1)の注釈は、余白を明示すると余白を広げてくれず、プロットに重なる（第3回の実機で確認）。
    # そこで、棒の位置・大きさを点で決め、箱（棒 + 目盛りラベル + ラベル + 枠の余白）が入るように右余白を足す。
    # 箱の幅 = 棒の幅 + 4.55 * 文字サイズ（+ 枠の余白 7.2）。第3回の実機で AnnotationInfo の RECT から見積もった（同一条件で ±2pt）。
    cs_plan = None
    cb_i = next((k for k, im_ in enumerate(images) if im_.has_cbar), None)
    if cb_i is not None:
        im_ = images[cb_i]
        mode = "mpl" if (use_mpl_size and st.get("cs_mode", "outside") == "outside" and im_.cb_box) else st.get("cs_mode", "outside")
        if mode == "mpl" and not im_.cb_box:
            mode = "outside"
        if mode in ("outside", "mpl"):
            box = bool(st.get("cs_box", True))
            fs = (int(round(im_.cb_fsize)) if (mode == "mpl" and im_.cb_fsize) else gf)
            # 箱の左上から棒までの余白 (pt)。第3回の実機で、箱の RECT と棒の位置から実測:
            #   箱あり（/F=2） 左 5.2〜6.2・上 0.93*fs・下 0.4*fs+8.4（目盛りラベルのはみ出しぶんを含む）、枠なし 左 1.6・上下 7〜7.5
            pad_l, pad_t, pad_b = (5.7, 0.93 * fs, 0.4 * fs + 8.4) if box else (1.6, 0.65 * fs, 0.6 * fs)
            if mode == "mpl":
                x0_, y0_, w_, h_ = im_.cb_box
                Wp_, Hp_ = fig.get_size_inches() * 72.0
                bar_x, bar_top, bar_w, bar_h = x0_ * Wp_, (1 - y0_ - h_) * Hp_, w_ * Wp_, h_ * Hp_
            else:
                bar_h = lay["ph"] * st.get("cs_height_pct", 100) / 100.0
                bar_x = lay["ml"] + lay["pw"] + st.get("cs_gap", 8.0)
                bar_top = lay["mt"] + (lay["ph"] - bar_h) / 2.0
                bar_w = float(st["cs_width"])
            box_w = bar_w + (9.6 if box else 0.0) + 4.55 * fs   # 第3回の実測: fs=12 で 79.2（棒 15）、枠なしで 69.6
            if im_.log:
                box_w += 1.8 * fs  # 対数の目盛りラベル（10^n）は広い。g19（fs=10）の実測で、線形の見積もりより 17 pt 広かった
            grown = []
            short = bar_x - pad_l + box_w + 2.0 - (lay["ml"] + lay["pw"] + lay["mr"])
            if short > 0.05:
                lay["mr"] += short
                grown.append(f"右 {short:.1f}")
            up = pad_t - bar_top + 1.5           # 箱の上端がウィンドウの上に出る量
            if up > 0.05:
                lay["mt"] += up
                bar_top += up
                grown.append(f"上 {up:.1f}")
            down = bar_top + bar_h + pad_b + 1.5 - (lay["mt"] + lay["ph"] + lay["mb"])
            if down > 0.05:
                lay["mb"] += down
                grown.append(f"下 {down:.1f}")
            if grown and mode == "mpl":
                warn.append("余白を広げました（pt: " + "、".join(grown) + "。カラースケールの箱がウィンドウに収まるように。"
                            "プロット領域の大きさは変わりません）")
            cs_plan = dict(mode=mode, x=bar_x, top=bar_top, w=bar_w, h=bar_h, pad_l=pad_l, pad_t=pad_t, fs=fs)
    win_w = lay["ml"] + lay["pw"] + lay["mr"]
    win_h = lay["mt"] + lay["ph"] + lay["mb"]
    wl, wt = st.get("win_left", 40), st.get("win_top", 40)
    rect = f"/W=({_fmt(wl)},{_fmt(wt)},{_fmt(wl + win_w)},{_fmt(wt + win_h)})"
    if has_2d:
        c(f"Display/N={name}{rect}")
        for k in range(len(images)):
            c(f"AppendImage{g} {_img_wave(name, k, 'z')} vs {{{_img_wave(name, k, 'xe')},{_img_wave(name, k, 'ye')}}}")
        for k in range(len(traces)):
            c(f"AppendToGraph{g} {_wave_name(name, k, 'y')} vs {_wave_name(name, k, 'x')}")
        for k, ct_ in enumerate(contours):
            zn = _cont_wave(name, k, "z")
            c(f"AppendMatrixContour{g} {zn} vs {{{_cont_wave(name, k, 'x')},{_cont_wave(name, k, 'y')}}}")
            items = [f"manLevels={_cont_wave(name, k, 'lv')}"]
            if ct_.color[0] == "cmap":
                _, _, vmin_, vmax_ = ct_.color
                if ct_.filled and ct_.levels.size > 1:
                    # Igor は各帯を「下端のレベル」の色で塗るが、matplotlib は帯の中央の値の色。半帯ぶんずらして合わせる
                    half = float(np.median(np.diff(ct_.levels))) / 2.0
                    vmin_, vmax_ = vmin_ - half, vmax_ - half
                tbl = f"{{{_fmt(vmin_)},{_fmt(vmax_)},{_cont_wave(name, k, 'ct')},0}}"
                items.append(f"cTabFill={tbl}" if ct_.filled else f"ctabLines={tbl}")
            else:
                rgb_ = _igor_rgb(ct_.color[1])
                items.append(f"rgbFill={rgb_}" if ct_.filled else f"rgbLines={rgb_}")
            if ct_.filled:
                items.append("fill=1")
            if ct_.labels is not None:
                items += ["labels=3", f"labelFSize={_fmt(ct_.labels)}"]
            else:
                items.append("labels=0")
            c(f"ModifyContour{g} {zn}, " + ",".join(items))
            # 線の太さは全トレースに掛ける（等高線のレベルごとのトレース名は図ごとに変わる）。塗りでは線を消す。
            # 自分のトレースの lSize は、あとの ModifyGraph で個別に指定されるので上書きされない。
            c(f"ModifyGraph{g} lSize={_fmt(0 if ct_.filled else ct_.lsize)}")
    else:
        for k in range(len(traces)):
            yn, xn = _wave_name(name, k, "y"), _wave_name(name, k, "x")
            if k == 0:
                c(f"Display/N={name}{rect} {yn} vs {xn}")
            else:
                c(f"AppendToGraph/W={name} {yn} vs {xn}")
    c(f"ModifyGraph{g} margin(left)={_fmt(lay['ml'])},margin(bottom)={_fmt(lay['mb'])},"
      f"margin(top)={_fmt(lay['mt'])},margin(right)={_fmt(lay['mr'])}")
    c(f"ModifyGraph{g} gfSize={gf},width={_fmt(lay['pw'])},height={height_val}")
    if st.get("font") and st["font"] != "default":
        c(f'ModifyGraph{g} font="{st["font"]}"')                 # 軸（目盛りラベル・軸ラベル）のフォント
    gfont_ = st.get("gfont") or st.get("font")
    if gfont_ and gfont_ != "default":
        c(f'ModifyGraph{g} gFont="{gfont_}"')                    # グラフ全体の既定フォント（凡例・注釈など）
    opts = [f"{k}={v}" for k, v in (("tick", tick_val), ("mirror", st.get("mirror")), ("standoff", st.get("standoff")))
            if v is not None]
    if opts:
        c(f"ModifyGraph{g} " + ",".join(opts))
    for side in ("bottom", "left"):
        if lbl_m[side] is not None and lbl_m[side] > 0.4:  # lblMargin は 0 以下では効かない（実測）
            c(f"ModifyGraph{g} lblMargin({side})={_fmt(lbl_m[side])}")
    # 軸（既定: matplotlib の実際の範囲に固定する。axis_range="auto" なら、手動で設定した範囲だけ）
    for axis_name, mpl_axis, scale, getlim, autos in (
        ("bottom", "x", ax.get_xscale(), ax.get_xlim, ax.get_autoscalex_on),
        ("left", "y", ax.get_yscale(), ax.get_ylim, ax.get_autoscaley_on),
    ):
        if scale == "log":
            c(f"ModifyGraph{g} log({axis_name})=1")
        elif scale != "linear":
            warn.append(f"{mpl_axis} 軸のスケール '{scale}' は未対応のため線形にしました")
        if has_2d or axis_range == "mpl" or not autos():
            lo, hi = getlim()  # 反転した軸（imshow の origin='upper' など）は lo > hi のまま渡す
            c(f"SetAxis{g} {axis_name} {_fmt(lo)},{_fmt(hi)}")
        if scale == "log" and st.get("log_exp", True):
            # 目盛りラベルを 10^n の指数表記にする。logLTrip（これ未満の軸の端なら指数表記）を軸の最小値より大きくする
            # （第2回の実機で、0.5 などで指数表記になることを確認。1e10 のような極端な値は Igor がエラーにする）
            lo, hi = getlim()
            m = min(abs(lo), abs(hi))
            if m > 0 and np.isfinite(m):
                c(f"ModifyGraph{g} logLTrip({axis_name})={_fmt(2 * m)}")
    # グリッド: style の grid が None なら matplotlib に合わせる。0（なし）・1（あり）・2（主目盛りのみ）、または軸ごとの辞書で指定
    gsel = st.get("grid")
    for axis_name, ax_obj in (("bottom", ax.xaxis), ("left", ax.yaxis)):
        gl = ax_obj.get_gridlines()
        mpl_on = bool(gl) and gl[0].get_visible()
        want = gsel.get(axis_name) if isinstance(gsel, dict) else gsel
        val = (1 if mpl_on else 0) if want is None else int(want)
        if val:
            col = st.get("grid_rgb")
            if col is None:
                col = gl[0].get_color() if (mpl_on and gl) else matplotlib.rcParams["grid.color"]
            c(f"ModifyGraph{g} grid({axis_name})={val}")
            c(f"ModifyGraph{g} gridRGB({axis_name})={_igor_rgb(_rgb(col))}")
            # 5 = All solid。0 は「背景が白ならモード 1（主目盛りは点線）」で、実線にならない（公式・第2回の実機で確認）
            c(f"ModifyGraph{g} gridStyle({axis_name})={st.get('grid_style', 5)}")
            gls = gl[0].get_linestyle() if (mpl_on and gl) else "-"
            if want is None and gls not in ("-", "solid") and st.get("grid_style", 5) == 5:
                warn.append(f"グリッドの線種 '{gls}' は Igor の番号が未確認のため、実線にしました")
    # 画像
    for k, im in enumerate(images):
        zn = _img_wave(name, k, "z")
        ct = f"{ctab[0]}" if ctab is not None else _img_wave(name, k, "ct")
        rev = int(ctab[1]) if ctab is not None else 0
        extra = ",log=1" if im.log else ""
        c(f"ModifyImage{g} {zn} ctab={{{_fmt(im.vmin)},{_fmt(im.vmax)},{ct},{rev}}}{extra}")
    # トレース
    for k, t in enumerate(traces):
        yn = _wave_name(name, k, "y")
        parts = [f"mode({yn})={t.mode}", f"rgb({yn})={_igor_rgb(t.rgb)}"]
        if t.marker is not None:
            parts += [f"marker({yn})={t.marker}", f"msize({yn})={_fmt(t.msize)}",
                      f"mrkThick({yn})={_fmt(t.mrk_thick)}"]
            if t.opaque is not None:
                parts.append(f"opaque({yn})={t.opaque}")
        if t.lsize is not None:
            parts.append(f"lSize({yn})={_fmt(t.lsize)}")
        if t.lstyle:
            parts.append(f"lStyle({yn})={t.lstyle}")
        c(f"ModifyGraph{g} " + ",".join(parts))
        if t.xerr is not None or t.yerr is not None:
            flags = f"/T={_fmt(t.err_capthick)}/L={_fmt(t.err_lthick)}"
            if t.err_capsize > 0:
                flags += f"/X={_fmt(t.err_capsize)}/Y={_fmt(t.err_capsize)}"
            else:
                flags = f"/T=0/L={_fmt(t.err_lthick)}"
            if t.err_rgb is not None:
                flags += f"/RGB={_igor_rgb(t.err_rgb)}"
            specs, mode = [], ""
            if t.xerr is not None:
                mode += "X"
                specs.append("wave=(%s,%s)" % wnames(k, "x", t.xerr))
            if t.yerr is not None:
                mode += "Y"
                specs.append("wave=(%s,%s)" % wnames(k, "y", t.yerr))
            c(f"ErrorBars{g}{flags} {yn}, {mode} " + ", ".join(specs))
    # ラベル
    for axis_name, text, where in (("bottom", ax.get_xlabel(), "x軸"), ("left", ax.get_ylabel(), "y軸")):
        if text:
            _style_check_label(text, where, warn)
            c(f"Label{g} {axis_name} \"{_label_literal(text, warn, italic_math)}\"")
    # 凡例
    leg = ax.get_legend()
    if leg is not None:
        entries = []
        by_label = {t.label: k for k, t in enumerate(traces) if t.label}
        for tx in leg.get_texts():
            lab = tx.get_text()
            k = by_label.get(lab)
            lit = _label_literal(lab, warn, italic_math)
            if k is None:
                warn.append(f"凡例の項目 '{lab}' に対応するトレースが無いため、記号なしの文字だけにしました")
                entries.append(lit)
            else:
                entries.append(f"\\\\s({_wave_name(name, k, 'y')}) {lit}")
        loc = getattr(leg, "_loc", 0)
        if loc == 0:
            warn.append("凡例位置が 'best' のため右上にしました（Igor には自動配置がありません）")
        frame = "" if leg.get_frame_on() else "/F=0"
        c(f"Legend{g}/N=legend0{frame}/M=1/A={_LEGEND_ANCHOR.get(loc, 'RT')} \"" + "\\r".join(entries) + "\"")
    # カラースケール（最初のカラーバー付き画像）
    cb_idx = next((k for k, im in enumerate(images) if im.has_cbar), None)
    if cb_idx is not None:
        im = images[cb_idx]
        zn = _img_wave(name, cb_idx, "z")
        mode = cs_plan["mode"] if cs_plan else st.get("cs_mode", "outside")
        kw = [f"image={zn}"] + (["log=1"] if im.log else [])
        frame_flag = "/F=2" if st.get("cs_box", True) else "/F=0"   # 注釈の枠。公式: 0=枠なし 1=下線のみ 2=箱（既定）。ユーザーの好みは箱
        if mode == "preset":
            flags = f"/A=MC/X={st['cs_x']:.2f}/Y={st['cs_y']:.2f}"
        else:
            # "outside": グラフの右外側（プロットの右、cs_gap pt）に、棒の高さ = プロットの高さ。
            # "mpl": matplotlib のカラーバーの位置と大きさに合わせる。
            # どちらも、ウィンドウの左上からの割合で箱の左上を指定する（箱は棒より枠の余白ぶん大きい）。
            p = cs_plan
            flags = (f"{frame_flag}/E=2/A=LT/X={_fmt((p['x'] - p['pad_l']) / win_w * 100)}"
                     f"/Y={_fmt((p['top'] - p['pad_t']) / win_h * 100)}")
            kw += [f"width={_fmt(p['w'])}", f"height={_fmt(p['h'])}",
                   f"frame={_fmt(0.8 if mode == 'mpl' else st.get('cs_frame', 0))}"]
        if st.get("cs_nticks") is not None:
            kw.append(f"nticks={st['cs_nticks']}")
        if mode == "mpl" and im.cb_fsize:  # 他のモードでは、カラースケールの文字はグラフの文字サイズ (gfSize) に従う
            kw.append(f"fsize={int(round(im.cb_fsize))}")
        if st.get("font") and st["font"] != "default":
            kw.append(f'font="{st["font"]}"')
        c(f"DoWindow/F {name}")
        c(f"ColorScale/C/N=cs0{flags} " + ",".join(kw))
        if im.log and st.get("cs_log_trip") is not None:
            c(f"ColorScale/C/N=cs0 logLTrip={_fmt(st['cs_log_trip'])}")
        if im.cbar_label:
            _style_check_label(im.cbar_label, "カラーバー", warn)
            c(f"ColorScale/C/N=cs0 \"{_label_literal(im.cbar_label, warn, italic_math)}\"")
        lbl_m = st.get("cs_lbl_margin_mpl") if mode == "mpl" else st.get("cs_lbl_margin")
        if lbl_m is not None:  # 公式: 既定は -5、正の値ほど軸から離れる
            c(f"ColorScale/C/N=cs0 lblMargin={_fmt(lbl_m)}")
    c(f"DoWindow/F {name}")
    if st.get("free_size", True):
        # 描画のあと、最後にサイズ指定を自動（既定の動作）に戻す。width/height を固定したままだと、Igor でウィンドウの
        # 大きさを変えられない。余白（margin）は固定のままなので、描いた時点のプロット領域の大きさは変わらず、
        # 以後ウィンドウの大きさに合わせてプロット領域が変わる。
        c(f"ModifyGraph{g} width=0,height=0")

    rep.commands = list(C)
    h5path = write_figure_h5(outdir, name, datasets, C, names, text_mode)
    rep.files.append(h5path)

    # --- 図ごとの .ipf（任意。読んだり直したりしたい人向け。ローダーが使えない環境の代替） ---
    if write_ipf:
        L = []
        a = L.append
        a("#pragma rtGlobals=3")
        a("")
        a(f"// {name}.ipf : generated by mpl_to_igor.export_igor on {datetime.date.today().isoformat()}")
        a(f"// Usage: compile this file, then run  Make_{name}()  and choose {name}.h5 in the dialog.")
        a(f"//        Make_{name}(h5Path=\"C:\\\\folder\\\\{name}.h5\") also works.")
        a("// (The same commands are embedded in the .h5 for ExportIgorGraphLoader.ipf.)")
        a("")
        a(f"Function Make_{name}([h5Path])")
        a("\tString h5Path")
        a("")
        a("\tVariable fileID, i, nW")
        a("\tString names, wn")
        a("")
        a("\tif (ParamIsDefault(h5Path))")
        a("\t\tHDF5OpenFile/R/I/Z fileID as \"\"")
        a("\telse")
        a("\t\tHDF5OpenFile/R/Z fileID as h5Path")
        a("\tendif")
        a("\tif (V_flag != 0)")
        a("\t\tPrint \"HDF5OpenFile failed or was canceled\"")
        a("\t\treturn -1")
        a("\tendif")
        a("")
        a("\tDFREF saveDF = GetDataFolderDFR()")
        a(f"\tNewDataFolder/O/S root:{name}")
        a("")
        a("\tnames = \"\"")
        for ch in _chunks(names, 4):
            a("\tnames += \"" + "".join(n + ";" for n in ch) + "\"")
        a("\tnW = ItemsInList(names)")
        a("\tfor (i = 0; i < nW; i += 1)")
        a("\t\twn = StringFromList(i, names)")
        a("\t\tHDF5LoadData/O/Z/Q/IGOR=-1 fileID, wn")
        a("\t\tif (V_flag != 0)")
        a("\t\t\tPrintf \"HDF5LoadData failed for %s\\r\", wn")
        a("\t\t\tHDF5CloseFile fileID")
        a("\t\t\tSetDataFolder saveDF")
        a("\t\t\treturn -1")
        a("\t\tendif")
        a("\tendfor")
        a("\tHDF5CloseFile fileID")
        a("")
        for n in names:
            a(f"\tWave {n}")
        a("")
        for cmd in C:
            a("\t" + cmd)
        a("")
        a("\tSetDataFolder saveDF")
        a("\treturn 0")
        a("End")
        ipfpath = os.path.join(outdir, f"{name}.ipf")
        with open(ipfpath, "w", newline="") as f:
            f.write("\r\n".join(L) + "\r\n")
        rep.files.append(ipfpath)
    return rep
