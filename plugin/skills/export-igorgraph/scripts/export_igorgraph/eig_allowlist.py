"""
eig_allowlist.py
================

h5 に埋め込んだ命令を Igor 側のローダーが Execute で実行するときの「許可リスト」。

背景: Execute は、渡された文字列を「コマンドラインに打ったもの」として何でも実行する
（ExecuteScriptText を使えば Windows のコマンドラインまで届く）。人から受け取った h5 を開くだけで
任意のコマンドが走るのを防ぐため、ローダーは**この許可リストに全文一致した命令だけ**を実行する。

方針
    - 命令の種類ごとに、全文一致（^ … $）の正規表現を1つ持つ。部分一致は使わない。
    - 使える文字・キーワードを列挙する。`;`（命令の連結）は、引用符の中以外では通らない。
    - 文字列リテラルは `"(?:[^"\\\\]|\\\\.)*"`（エスケープされていない `"` を含まない）だけを通す。
      これで、ラベルの文字列から引用符を抜けて別の命令を差し込むことができない。
    - 制御文字（改行など）と 2400 バイトを超える命令は、無条件に拒否する（Execute の上限は 2500 バイト）。

このファイルが唯一の定義。次の3か所が同じパターンを使う（食い違わないようにするため）:
    1. mpl_to_igor.export_igor: 生成した全命令がここを通ることを、書き出し時に検査する
    2. make_loader.py: Igor 側ローダー (.ipf) の GrepString 用の文字列を、ここから生成する
    3. テスト: 正常な命令と、悪意のある命令の見本で確認する

正規表現は、Python の re と Igor の GrepString（PCRE）の両方で同じ意味になる範囲に限る
（非捕獲グループ (?:…)、文字クラス、{n,m}、\\x の指定は使わない）。
"""

from __future__ import annotations

import re

MAX_COMMAND_BYTES = 2400  # Execute の上限は 2500 バイト。余裕を見る

NAME = r"[A-Za-z][A-Za-z0-9_]{0,30}"
NUM = r"-?[0-9]+(?:\.[0-9]+)?(?:[eE][-+]?[0-9]+)?"
RGB = rf"\({NUM},{NUM},{NUM}\)"
STR = r'"(?:[^"\\]|\\.)*"'
AXIS = r"(?:bottom|left)"
ANCHOR = r"(?:LT|MT|RT|LC|MC|RC|LB|MB|RB)"
WIN = rf"/W={NAME}"
RECT = rf"\({NUM},{NUM},{NUM},{NUM}\)"
# ModifyGraph / ColorScale の font=・gFont= に使えるフォント名。任意の文字列は通さない（列挙したものだけ）。
# 足すときは、名前を FONT_NAMES に足して、ローダーを再生成する（python make_loader.py）。
FONT_NAMES = ["Arial", "Helvetica", "Times New Roman", "Times", "Courier New", "Courier", "Calibri", "Verdana", "Tahoma",
              "Segoe UI", "Georgia", "Cambria", "Meiryo", "Yu Gothic", "MS Gothic", "MS PGothic", "default"]
FONT = '"(?:' + "|".join(FONT_NAMES) + ')"'

# ModifyGraph で使ってよい「キー(対象)=値」の1項目。export_igor が出すキーだけ。
MG_ITEM = (
    rf"(?:margin\((?:left|bottom|top|right)\)={NUM}"
    rf"|gfSize={NUM}"
    rf"|width={NUM}"
    rf"|height=(?:{NUM}|\{{Aspect,{NUM}\}})"
    rf"|tick={NUM}|mirror={NUM}|standoff={NUM}"
    rf"|(?:log|grid)\({AXIS}\)={NUM}"
    rf"|(?:mode|marker|msize|mrkThick|opaque|lSize|lStyle)\({NAME}\)={NUM}"
    rf"|(?:lSize|lStyle)={NUM}"                 # 全トレース（等高線のレベルのトレース名は図ごとに変わるので、全体に掛ける）
    rf"|rgb\({NAME}\)={RGB}"
    rf"|(?:font|gFont)={FONT}"
    rf"|gridRGB\({AXIS}\)={RGB}"
    rf"|(?:gridStyle|lblPos|lblMargin|logLTrip|logHTrip)\({AXIS}\)={NUM})"
)

# ColorScale のキーワード（公式ドキュメントにあるものから、export_igor が使うものだけ）
CS_KEY = (
    rf"(?:image={NAME}|log=[01]|logLTrip={NUM}|lblMargin={NUM}|width={NUM}|height={NUM}"
    rf"|heightPct={NUM}|widthPct={NUM}|frame={NUM}|nticks={NUM}|fsize={NUM}|font={FONT}|side=[12]|tickLen={NUM}|minor=[01])"
)

# ModifyContour のキーワード（公式ドキュメントにあるものから、export_igor が使うものだけ）
MC_KEY = (
    rf"(?:manLevels={NAME}|rgbLines={RGB}|ctabLines=\{{{NUM},{NUM},{NAME},[01]\}}|labels=[0-4]|labelFSize={NUM}"
    rf"|fill=[01]|rgbFill={RGB}|cTabFill=\{{{NUM},{NUM},{NAME},[01]\}})"
)

# (ラベル, 正規表現)。命令の種類ごとに1つ。
PATTERNS: list[tuple[str, str]] = [
    ("DoWindow/K", rf"^DoWindow/K {NAME}$"),
    ("DoWindow/F", rf"^DoWindow/F {NAME}$"),
    ("Display", rf"^Display/N={NAME}(?:/W={RECT})?(?: {NAME} vs {NAME})?$"),
    ("AppendToGraph", rf"^AppendToGraph{WIN} {NAME} vs {NAME}$"),
    ("AppendImage", rf"^AppendImage{WIN} {NAME} vs \{{{NAME},{NAME}\}}$"),
    ("ModifyGraph", rf"^ModifyGraph{WIN} {MG_ITEM}(?:,{MG_ITEM})*$"),
    ("ModifyImage", rf"^ModifyImage{WIN} {NAME} ctab=\{{{NUM},{NUM},{NAME},[01]\}}(?:,log=1)?$"),
    ("AppendMatrixContour", rf"^AppendMatrixContour{WIN} {NAME} vs \{{{NAME},{NAME}\}}$"),
    ("ModifyContour", rf"^ModifyContour{WIN} {NAME}, {MC_KEY}(?:,{MC_KEY})*$"),
    ("ErrorBars",
     rf"^ErrorBars{WIN}(?:/(?:T|L|X|Y)={NUM})*(?:/RGB={RGB})? {NAME}, (?:X|Y|XY) "
     rf"wave=\({NAME},{NAME}\)(?:, wave=\({NAME},{NAME}\))?$"),
    ("SetAxis", rf"^SetAxis{WIN} {AXIS} {NUM},{NUM}$"),
    ("Label", rf"^Label{WIN} {AXIS} {STR}$"),
    ("Legend", rf"^Legend{WIN}/N={NAME}(?:/F=[012])?(?:/M=[01])?(?:/H={NUM})?(?:/E=[012])?/A={ANCHOR}"
               rf"(?:/X={NUM})?(?:/Y={NUM})? {STR}$"),
    ("ColorScale",
     rf"^ColorScale/C/N={NAME}(?:/F=[012])?(?:/E=[012])?(?:/A={ANCHOR})?(?:/X={NUM})?(?:/Y={NUM})?"
     rf"(?: {CS_KEY}(?:,{CS_KEY})*)?(?: {STR})?$"),
    ("Redimension", rf"^Redimension/U/W {NAME}$"),
]
_COMPILED = [(label, re.compile(rx)) for label, rx in PATTERNS]

# ワークスペースの名前に使う正規表現（ローダーが、図の名前とデータセット名を検査するのに使う）
RE_FIGURE_NAME = r"^[A-Za-z][A-Za-z0-9_]{0,15}$"
RE_WAVE_NAME = rf"^{NAME}$"


def match_label(cmd: str):
    """許可リストに全文一致した命令の種類（ラベル）を返す。通らなければ None。"""
    if not cmd or len(cmd.encode("ascii", "replace")) > MAX_COMMAND_BYTES:
        return None
    if any(ord(c) < 32 or ord(c) > 126 for c in cmd):  # 制御文字・非ASCII は拒否（非ASCIIは \uXXXX で書く）
        return None
    for label, rx in _COMPILED:
        if rx.fullmatch(cmd):
            return label
    return None


def is_allowed(cmd: str) -> bool:
    return match_label(cmd) is not None


# --- Igor の文字列リテラルへの変換（ローダーの生成用） ---
def igor_literal(s: str) -> str:
    """Python の文字列を、Igor の文字列リテラルの中身（引用符の内側）にする。"""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def chunk_regex(rx: str, size: int = 220) -> list[str]:
    """正規表現を、エスケープ（バックスラッシュ + 1文字）を壊さずに size 文字前後で分割する。"""
    parts, cur, i = [], "", 0
    while i < len(rx):
        unit = rx[i : i + 2] if rx[i] == "\\" and i + 1 < len(rx) else rx[i]
        cur += unit
        i += len(unit)
        if len(cur) >= size:
            parts.append(cur)
            cur = ""
    if cur:
        parts.append(cur)
    return parts


# --- 自己検査用の見本 ---
GOOD_SAMPLES = [
    "DoWindow/K fig1",
    "DoWindow/F fig1",
    "Display/N=fig1",
    "Display/N=fig1/W=(40,40,328,256)",
    "Display/N=fig1/W=(40,40,328,256) fig1_t0_y vs fig1_t0_x",
    "Display/N=fig1 fig1_t0_y vs fig1_t0_x",
    "AppendToGraph/W=fig1 fig1_t1_y vs fig1_t1_x",
    "AppendImage/W=fig1 fig1_i0_z vs {fig1_i0_xe,fig1_i0_ye}",
    "ModifyGraph/W=fig1 margin(left)=43,margin(bottom)=37,margin(top)=14,margin(right)=14",
    "ModifyGraph/W=fig1 gfSize=14,width=226.772,height={Aspect,0.8}",
    "ModifyGraph/W=fig1 tick=2,mirror=1,standoff=0",
    "ModifyGraph/W=fig1 log(bottom)=1",
    "ModifyGraph/W=fig1 grid(left)=1",
    "ModifyGraph/W=fig1 mode(fig1_t0_y)=3,rgb(fig1_t0_y)=(54998,10023,10280),marker(fig1_t0_y)=19,"
    "msize(fig1_t0_y)=1.5,mrkThick(fig1_t0_y)=1,opaque(fig1_t0_y)=0,lSize(fig1_t0_y)=1.5",
    "ModifyImage/W=fig1 fig1_i0_z ctab={1,1e+06,fig1_i0_ct,0},log=1",
    "ModifyImage/W=fig1 fig1_i0_z ctab={-0.5,25,Rainbow,1}",
    "ErrorBars/W=fig1/T=1/L=0.8/X=2/Y=2 fig1_t0_y, Y wave=(fig1_t0_eyp,fig1_t0_eyn)",
    "ErrorBars/W=fig1/T=0/L=1/RGB=(0,0,0) fig1_t1_y, XY wave=(fig1_t1_ex,fig1_t1_ex), wave=(fig1_t1_ey,fig1_t1_ey)",
    "SetAxis/W=fig1 left 2.5,-0.5",
    'Label/W=fig1 bottom "\\\\f02Q\\\\f00\\\\Bz\\\\M [nm\\\\S-1\\\\M]"',
    'Label/W=fig1 left "semi;colon and \\"quote\\" inside \\u00C5"',
    'Legend/W=fig1/N=legend0/F=0/A=RT "\\\\s(fig1_t1_y) fit\\rdata"',
    'Legend/W=fig1/N=legend0/F=0/M=1/A=RT "\\\\s(fig1_t1_y) fit"',
    'Legend/W=fig1/N=legend0/F=2/M=1/H=40/E=0/A=LB/X=2/Y=3 "x"',
    "ColorScale/C/N=cs0/A=MC image=fig1_i0_z,log=1",
    "ColorScale/C/N=cs0 logLTrip=0.1",
    'ColorScale/C/N=cs0 "Intensity [a.u.]"',
    "ColorScale/C/N=cs0 lblMargin=15",
    "ColorScale/C/N=cs0/X=56.00/Y=16.00",
    "ColorScale/C/N=cs0/F=0/E=2/A=LT/X=84.5/Y=12.3 image=fig1_i0_z,log=1,width=15,height=120,frame=0,nticks=5,fsize=10,font=\"Arial\",lblMargin=5",
    "ColorScale/C/N=cs0/F=0/E=1/A=RC/X=0/Y=0 image=fig1_i0_z,heightPct=100,widthPct=5,frame=0",
    "ModifyGraph/W=fig1 font=\"Arial\"",
    "ModifyGraph/W=fig1 gFont=\"Yu Gothic\"",
    "ModifyGraph/W=fig1 grid(bottom)=2,gridRGB(bottom)=(45232,45232,45232),gridStyle(bottom)=5",
    "ModifyGraph/W=fig1 lStyle(fig1_t0_y)=3,gridRGB(left)=(45232,45232,45232),gridStyle(left)=0,lblPos(bottom)=34,lblMargin(left)=2",
    "ModifyGraph/W=fig1 logLTrip(bottom)=1e+10,logHTrip(left)=0.5",
    "Redimension/U/W fig1_i0_ct",
    "AppendMatrixContour/W=fig1 fig1_c0_z vs {fig1_c0_x,fig1_c0_y}",
    "ModifyContour/W=fig1 fig1_c0_z, manLevels=fig1_c0_lv,rgbLines=(0,0,0),labels=0",
    "ModifyContour/W=fig1 fig1_c0_z, manLevels=fig1_c0_lv,ctabLines={0,1.05,fig1_c0_ct,0},labels=3,labelFSize=9",
    "ModifyContour/W=fig1 fig1_c0_z, fill=1,cTabFill={0,1.05,fig1_c0_ct,0}",
    "ModifyGraph/W=fig1 lSize=1.5,lStyle=3",
]

BAD_SAMPLES = [
    'ExecuteScriptText "cmd /c calc"',
    "KillWaves/A",
    "KillDataFolder root:",
    "Execute \"Print 1\"",
    "Make/O w=1",
    "ModifyGraph/W=fig1 rgb(x)=(0,0,0);KillWaves/A",
    "ModifyGraph/W=fig1 mode(x)=1;ModifyGraph/W=fig1 mode(y)=2",
    "ModifyGraph/W=fig1 foo(x)=1",
    "ModifyGraph/W=fig1 mode(x)=1,",
    "ModifyGraph mode(x)=3",
    'Label/W=fig1 bottom "a";KillWaves/A;"b"',
    'Label/W=fig1 bottom "a\\"',
    'Label/W=fig1 bottom "a"\nKillWaves/A',
    'Label/W=fig1 bottom "a"\rKillWaves/A',
    'Label/W=fig1 right "a"',
    "Display/N=fig1 a vs b;Print 1",
    'Display/N="fig1"',
    "Display/N=fig1 root:a vs b",
    "SetAxis/W=fig1 bottom 1,2;DoWindow/K x",
    "SetAxis/W=fig1 bottom 1e,2",
    "DoWindow/K root:fig1",
    "DoWindow/K fig 1",
    "DoWindow/K " + "a" * 40,
    "AppendImage/W=fig1 a vs {b}",
    "Legend/W=fig1/N=l/A=ZZ \"x\"",
    "ColorScale/C/N=cs0 image=z;KillWaves/A",
    "ErrorBars/W=fig1/Q y, Y wave=(a,b)",
    'ModifyGraph/W=fig1 font="Evil;KillWaves/A"',
    'ModifyGraph/W=fig1 font="Arial";KillWaves/A',
    'ModifyGraph/W=fig1 gFont="Evil;KillWaves/A"',
    'ModifyGraph/W=fig1 gFont="Arial Black"',
    "ModifyGraph/W=fig1 gFont=Arial",
    "ModifyGraph/W=fig1 font=Arial",
    "ColorScale/C/N=cs0 foo=1",
    "ColorScale/C/N=cs0 image=z;KillWaves/A",
    "ColorScale/C/N=cs0 font=\"Evil;Kill\"",
    "ColorScale/K/N=cs0",
    "ColorScale/C/N=cs0/Z=1 image=z",
    "Legend/W=fig1/N=l/M=7/A=RT \"x\"",
    "Legend/W=fig1/N=l/K/A=RT \"x\"",
    "Display/N=fig1/W=(1,2,3)",
    "Display/N=fig1/W=(1,2,3,4);Print 1",
    "Redimension/N=1000000000 w",
    "AppendMatrixContour/W=fig1 z vs {x,y};KillWaves/A",
    "AppendMatrixContour/W=fig1 root:z vs {x,y}",
    "ModifyContour/W=fig1 z, manLevels=w;KillWaves/A",
    "ModifyContour/W=fig1 z, foo=1",
    "ModifyContour/W=fig1 z, labels=9",
    "ModifyContour/W=fig1 z, fill=1,",
    "ModifyGraph/W=fig1 lSize=1.5;KillWaves/A",
    "HDF5LoadData fileID, \"x\"",
    "",
    "Label/W=fig1 bottom \"" + "a" * 3000 + "\"",
    "Label/W=fig1 bottom \"\u00c5\"",
]
