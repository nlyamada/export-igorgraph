#!/usr/bin/env python3
"""
audit.py
========

Igor の RunGallery() が書いた igor_audit.txt（できあがったグラフの読み戻し）を、
expected.json（export_igor が出した命令）と照合する。

    python audit.py <gallery フォルダ>            # audit_report.md を書いて、要約を表示
    python audit.py <gallery フォルダ> --dump g06_loglog     # その図の読み戻しの生データを表示

見ているもの: 「送った命令が、Igor のグラフにその値で反映されているか」。
  - ModifyGraph / ModifyImage の各項目（キー・対象・値。数値は許容誤差つき）
  - SetAxis（読み戻した軸範囲 GetAxis とも照合）、Label の文字列、ErrorBars、Legend の文字列、ColorScale
  - トレース・画像の名前
matplotlib の見た目と一致するか（マッピングが正しいか）は、このスクリプトでは分からない。それは PNG の目視で見る。
Igor の WinRecreation の書式は、実機で初めて分かる部分があるので、MISSING / DIFF は、
「本当に反映されていない」か「読み戻しの書式の違い」かを、生データ（--dump）で確認する。
"""

from __future__ import annotations

import json
import os
import re
import sys

REL_TOL = 1e-3
ABS_TOL = 1e-6
_NUM = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


# ------------------------------ 読み戻しファイルの解析 ------------------------------
def parse_audit(text: str) -> dict:
    figs, cur, meta = {}, None, {}
    for raw in re.split(r"\r\n|\r|\n", text):
        if not raw:
            continue
        f = raw.split("\t")
        tag = f[0]
        if tag in ("IGORVERSION", "PLATFORM"):
            meta[tag] = f[1] if len(f) > 1 else ""
        elif tag == "FIGURE":
            cur = {"name": f[1], "load_status": int(float(f[2])) if len(f) > 2 else None,
                   "traces": [], "images": [], "axis": {}, "traceinfo": {}, "imageinfo": {},
                   "axisinfo": {}, "rec": [], "wsize": None, "psize": None, "annotlist": [], "annotinfo": {}}
            figs[f[1]] = cur
        elif cur is None:
            continue
        elif tag == "TRACES":
            cur["traces"] = [x for x in (f[1] if len(f) > 1 else "").split(";") if x]
        elif tag == "IMAGES":
            cur["images"] = [x for x in (f[1] if len(f) > 1 else "").split(";") if x]
        elif tag in ("WSIZE", "PSIZE") and len(f) >= 5:
            cur[tag.lower()] = tuple(float(x) for x in f[1:5])
        elif tag == "ANNOTLIST":
            cur["annotlist"] = [x for x in (f[1] if len(f) > 1 else "").split(";") if x]
        elif tag == "ANNOTINFO" and len(f) >= 3:
            cur["annotinfo"][f[1]] = "\t".join(f[2:])
        elif tag == "AXIS" and len(f) >= 5:
            cur["axis"][f[1]] = (float(f[2]), float(f[3]), int(float(f[4])))
        elif tag in ("TRACEINFO", "IMAGEINFO", "AXISINFO") and len(f) >= 3:
            cur[tag.lower()][f[1]] = "\t".join(f[2:])
        elif tag == "REC":
            cur["rec"].append("\t".join(f[1:]))
        elif tag == "ENDFIGURE":
            cur = None
    return {"meta": meta, "figures": figs}


# ------------------------------ 命令の解析 ------------------------------
def split_top(s: str, sep: str = ",") -> list:
    parts, depth, in_s, cur, i = [], 0, False, "", 0
    while i < len(s):
        ch = s[i]
        if in_s:
            cur += ch
            if ch == "\\" and i + 1 < len(s):
                cur += s[i + 1]
                i += 2
                continue
            if ch == '"':
                in_s = False
        elif ch == '"':
            in_s = True
            cur += ch
        elif ch in "({[":
            depth += 1
            cur += ch
        elif ch in ")}]":
            depth -= 1
            cur += ch
        elif ch == sep and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    parts.append(cur)
    return [p for p in parts if p != ""]


_ITEM = re.compile(r"^([A-Za-z]+)(?:\(([^)]*)\))?=(.*)$")


def parse_items(argstr: str) -> list:
    out = []
    for it in split_top(argstr.strip()):
        m = _ITEM.match(it.strip())
        if m:
            out.append((m.group(1), m.group(2), m.group(3).strip()))
    return out


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def values_equal(a: str, b: str) -> bool:
    na, nb = _NUM.findall(a), _NUM.findall(b)
    if na and nb and re.sub(_NUM, "#", a).replace(" ", "") == re.sub(_NUM, "#", b).replace(" ", ""):
        if len(na) != len(nb):
            return False
        return all(abs(float(x) - float(y)) <= max(ABS_TOL, REL_TOL * max(abs(float(x)), abs(float(y))))
                   for x, y in zip(na, nb))
    return norm(a) == norm(b)


def expectations(cmds: list) -> list:
    """命令から、照合する項目を取り出す。 (種類, 説明, データ)"""
    ex = []
    for c in cmds:
        verb = re.match(r"^([A-Za-z]+)", c).group(1)
        body = re.sub(r"^[A-Za-z]+(?:/[A-Za-z]+=?[^\s/]*)*\s*", "", c, count=1) if verb != "Display" else ""
        if verb == "ModifyGraph":
            for k, t, v in parse_items(body):
                ex.append(("item", f"ModifyGraph {k}({t})={v}" if t else f"ModifyGraph {k}={v}", ("ModifyGraph", k, t, v)))
        elif verb == "ModifyImage":
            wave, _, rest = body.partition(" ")
            for k, t, v in parse_items(rest):
                ex.append(("item", f"ModifyImage {k}={v}", ("ModifyImage", k, None, v)))
        elif verb == "SetAxis":
            m = re.match(r"^(bottom|left) ([^,]+),(.+)$", body)
            ex.append(("setaxis", f"SetAxis {m.group(1)} {m.group(2)},{m.group(3)}", (m.group(1), m.group(2), m.group(3))))
        elif verb == "Label":
            m = re.match(r'^(bottom|left) "(.*)"$', body)
            ex.append(("label", f"Label {m.group(1)}", (m.group(1), m.group(2))))
        elif verb == "ErrorBars":
            m = re.match(r"^(\S+), (.+)$", body)
            ex.append(("errorbars", f"ErrorBars {m.group(1)}", (m.group(1), norm(m.group(2)))))
        elif verb == "Legend":
            m = re.search(r'"(.*)"$', c)
            ex.append(("legend", "Legend text", m.group(1)))
        elif verb == "ColorScale":
            ex.append(("colorscale", "ColorScale " + c.split(" ", 1)[1][:40] if " " in c else "ColorScale", c))
        elif verb in ("Display", "AppendToGraph", "AppendImage"):
            mw = re.search(r"/W=\(([^)]*)\)", c) if verb == "Display" else None
            if mw:
                l, t, r, b = (float(x) for x in mw.group(1).split(","))
                ex.append(("window", "Display ウィンドウの大きさ", (r - l, b - t)))
            nm = re.sub(r"^\w+(?:/\w+=\S+)*\s*", "", c).split(" ")[0] if verb != "Display" or " vs " in c else None
            if nm:
                ex.append(("wave", f"{verb} {nm}", (verb, nm)))
    return ex


# ------------------------------ 照合 ------------------------------
def rec_items(rec_lines: list) -> dict:
    d = {}
    for ln in rec_lines:
        s = ln.strip()
        m = re.match(r"^(ModifyGraph|ModifyImage)\b[^ ]*\s+(.*)$", s)
        if not m:
            continue
        body = m.group(2)
        if m.group(1) == "ModifyImage":
            body = body.partition(" ")[2] if not re.match(r"^[A-Za-z]+(\(|=)", body) else body
        for k, t, v in parse_items(body):
            d.setdefault((m.group(1), k, t), []).append(v)
    return d


def unescape_u(text: str) -> str:
    """Igor の文字列リテラルの \\uXXXX を、実際の文字にする（Igor の記録マクロは文字そのものを書く）。"""
    return re.sub(r"\\u([0-9A-Fa-f]{4})", lambda m: chr(int(m.group(1), 16)), text)


def info_items(info: str) -> dict:
    """TraceInfo / AxisInfo / ImageInfo の RECREATION 部分を、{キー: 値} にする。(x) は対象の置き場所。"""
    m = re.search(r"RECREATION:(.*)$", info)
    out = {}
    if not m:
        return out
    for part in m.group(1).split(";"):
        mm = re.match(r"^\s*([A-Za-z]+)(?:\(x\))?\s*=\s*(.*?)\s*$", part)
        if mm:
            out[mm.group(1)] = mm.group(2)
    return out


def strip_df(s: str) -> str:
    """:folder:wave のデータフォルダ接頭辞を取る。"""
    return re.sub(r":[A-Za-z0-9_]+:", "", s)


def parse_flags(flagstr: str) -> dict:
    return {m.group(1): m.group(2) for m in re.finditer(r"/([A-Za-z]+)=(\([^)]*\)|[^/\s]+)", flagstr)}


PER_AXIS = ("log", "grid", "tick", "mirror", "standoff")


def compare_figure(name: str, exp: dict, got: dict) -> dict:
    res = {"name": name, "ok": 0, "diff": [], "missing": [], "notes": []}
    if got is None:
        res["missing"].append("この図は読み戻しにありません")
        return res
    if got["load_status"] not in (0, None):
        res["missing"].append(f"LoadPythonFigure が失敗 (戻り値 {got['load_status']})")
        return res
    rec_items_map = rec_items(got["rec"])
    rec_text = norm(unescape_u("\n".join(got["rec"])))
    tinfo = {t: info_items(i) for t, i in got["traceinfo"].items()}
    ainfo = {a: info_items(i) for a, i in got["axisinfo"].items()}
    iinfo = {t: info_items(i) for t, i in got["imageinfo"].items()}

    def judge(desc, want, have):
        if have is None:
            res["missing"].append(desc)
        elif values_equal(want, have):
            res["ok"] += 1
        else:
            res["diff"].append(f"{desc}  →  Igor: {have}")

    for kind, desc, data in expectations(exp["commands"]):
        if kind == "item":
            cmd, k, t, v = data
            if cmd == "ModifyGraph" and t is None and k in ("width", "height") and re.fullmatch(_NUM.pattern, v) and got.get("psize"):
                ps = got["psize"]
                have = (ps[2] - ps[0]) if k == "width" else (ps[3] - ps[1])
                if float(v) == 0:  # width=0,height=0（サイズ自動）。記録には出ない。プロット領域の大きさは、上の固定値で見る
                    continue
                if abs(have - float(v)) <= 1.5:
                    res["ok"] += 1
                else:
                    res["diff"].append(f"プロット領域の {k}: 期待 {float(v):g} pt  →  Igor: {have:g} pt")
            if cmd == "ModifyGraph" and t in tinfo:  # トレースの属性は、TraceInfo（既定値まで含む完全な状態）で見る
                judge(desc, v, tinfo[t].get(k))
            elif cmd == "ModifyGraph" and k in PER_AXIS:  # 軸の属性は AxisInfo で見る
                axes = [t] if t in ("bottom", "left") else ["bottom", "left"]
                for ax in axes:
                    judge(f"{desc} [{ax}]", v, ainfo.get(ax, {}).get(k))
            elif cmd == "ModifyImage":
                img = next(iter(iinfo.values()), {}) if iinfo else {}
                have = img.get(k)
                if k == "ctab" and have is not None:
                    judge(desc, strip_df(v), strip_df(have))
                else:
                    judge(desc, v, have)
            else:  # margin, gfSize, width, height などの全体の属性: 記録マクロ（既定値でなければ書かれる）
                cands = rec_items_map.get((cmd, k, t), [])
                if not cands:
                    cands = [x for (c2, k2, t2), vs in rec_items_map.items() if (c2, k2) == (cmd, k) for x in vs]
                if not cands and cmd == "ModifyGraph" and t is None and k in ("width", "height"):
                    continue  # 最後にサイズ自動（width=0,height=0）にするので、記録マクロには width/height が出ない
                if not cands:
                    res["missing"].append(desc)
                elif any(values_equal(v, c) for c in cands):
                    res["ok"] += 1
                else:
                    res["diff"].append(f"{desc}  →  Igor: {cands[-1]}")
        elif kind == "window":
            ws = got.get("wsize")
            if not ws:
                res["notes"].append("ウィンドウの大きさの読み戻しなし（古い RunGallery の出力）")
            else:
                w, h = ws[2] - ws[0], ws[3] - ws[1]
                if abs(w - data[0]) <= 1.5 and abs(h - data[1]) <= 1.5:
                    res["ok"] += 1
                else:
                    res["diff"].append(f"{desc}: 期待 {data[0]:g}x{data[1]:g} pt  →  Igor: {w:g}x{h:g} pt")
        elif kind == "setaxis":
            ax, lo, hi = data
            ra = got["axis"].get(ax)
            cmdtxt = ainfo_cmd = None
            m = re.search(r"SETAXISCMD:SetAxis (\w+) ([^,;]+),([^;]+)", got["axisinfo"].get(ax, ""))
            if m and values_equal(f"{lo},{hi}", f"{m.group(2)},{m.group(3)}"):
                res["ok"] += 1
            elif ra and values_equal(f"{lo},{hi}", f"{ra[0]},{ra[1]}"):
                res["ok"] += 1
            elif m:
                res["diff"].append(f"{desc}  →  Igor: SetAxis {m.group(2)},{m.group(3)}")
            elif ra:
                res["diff"].append(f"{desc}  →  Igor の軸範囲: {ra[0]:g},{ra[1]:g}")
            else:
                res["missing"].append(desc)
        elif kind == "label":
            ax, text = data
            pat = re.compile(rf'Label\s+(?:/\w+\s+)*{ax}\s+"(.*)"')
            m = next((pat.search(l) for l in got["rec"] if pat.search(l)), None)
            if m and unescape_u(m.group(1)) == unescape_u(text):
                res["ok"] += 1
            elif m:
                res["diff"].append(f"{desc}  期待: {text}  →  Igor: {m.group(1)}")
            else:
                res["missing"].append(desc)
        elif kind == "errorbars":
            tr, tail = data
            field = re.search(r"ERRORBARS:(ErrorBars[^;]*)", got["traceinfo"].get(tr, ""))
            if not field:
                res["missing"].append(f"{desc}（TraceInfo に ERRORBARS なし）")
                continue
            igor = field.group(1)
            fl_have = parse_flags(igor.split(" ")[0])
            fl_want = parse_flags(next((c for c in exp["commands"] if c.startswith("ErrorBars") and f" {tr}," in c), "").split(" ")[0])
            waves_have = norm(re.sub(r"(XY|X|Y),wave=", r"\1wave=", strip_df(igor.split(" ", 2)[-1] if " " in igor else igor)))
            waves_have = waves_have[waves_have.find(tr[-1]) + 0:] if False else waves_have
            ok_waves = tail.replace(" ", "") in waves_have or waves_have.endswith(tail.replace(" ", ""))
            bad = [f"/{k}: 期待 {fl_want[k]} → Igor {fl_have[k]}" for k in fl_have if k in fl_want
                   and k not in ("T",) and not values_equal(fl_want[k], fl_have[k])]
            if ok_waves and not bad:
                res["ok"] += 1
                miss = [k for k in fl_want if k not in fl_have]
                if miss:
                    res["notes"].append(f"{desc}: Igor は /{','.join(miss)} を省略（既定値または不要なため）")
            else:
                res["diff"].append(f"{desc}  →  Igor: {igor}  " + "; ".join(bad))
        elif kind == "legend":
            if norm(unescape_u(data)) in rec_text:
                res["ok"] += 1
            else:
                res["missing"].append("Legend の文字列")
        elif kind == "colorscale":
            c = data
            m = re.search(r"image=(\w+)", c)
            if m:
                cs_lines = [l for l in got["rec"] if "ColorScale" in l]
                ok = any(m.group(1) in l for l in cs_lines) and (",log=1" not in c or any("log" in l and "1" in l for l in cs_lines))
            elif re.search(r'ColorScale/C/N=\w+ "(.*)"$', c):
                txt = re.search(r'"(.*)"$', c).group(1)
                ok = norm(unescape_u(txt)) in rec_text  # 記録マクロでは AppendText "…" になる
            else:
                key = re.search(r" (logLTrip|lblMargin)=([^\s,]+)", c)
                pos = re.search(r"/X=([^/\s]+)/Y=([^/\s]+)", c)
                if key:
                    ok = any(key.group(1) in l and values_equal(key.group(2), re.search(key.group(1) + r"=([^,\s]+)", l).group(1))
                             for l in got["rec"] if key.group(1) in l)
                elif pos:
                    ok = any(re.search(r"/X=" + re.escape(pos.group(1)) + r"/Y=" + re.escape(pos.group(2)), l) or
                             values_equal(pos.group(1), (re.search(r"/X=([^/\s]+)", l) or [0, "nan"])[1]) for l in got["rec"] if "ColorScale" in l)
                else:
                    ok = True
            if ok:
                res["ok"] += 1
            else:
                res["missing"].append(desc)
        elif kind == "wave":
            verb, nm = data
            pool = got["images"] if verb == "AppendImage" else got["traces"]
            if nm in pool:
                res["ok"] += 1
            else:
                res["missing"].append(f"{desc}（{'画像' if verb == 'AppendImage' else 'トレース'}一覧にない）")
    return res


def build_report(audit: dict, expected: dict) -> tuple:
    figs = audit["figures"]
    rows, detail = [], []
    tot = {"ok": 0, "diff": 0, "missing": 0}
    for name, exp in expected.items():
        r = compare_figure(name, exp, figs.get(name))
        rows.append(f"| {name} | {r['ok']} | {len(r['diff'])} | {len(r['missing'])} |")
        tot["ok"] += r["ok"]; tot["diff"] += len(r["diff"]); tot["missing"] += len(r["missing"])
        if r["diff"] or r["missing"] or r["notes"]:
            detail.append(f"### {name}")
            detail += [f"- DIFF: {x}" for x in r["diff"]] + [f"- MISSING: {x}" for x in r["missing"]]
            detail += [f"- 注: {x}" for x in r["notes"]]
    head = ["# 再現度チェック: 命令 → Igor のグラフへの反映（読み戻し）", "",
            f"Igor: {audit['meta'].get('IGORVERSION', '?')} / {audit['meta'].get('PLATFORM', '?')}", "",
            "| 図 | OK | DIFF（値が違う） | MISSING（見つからない） |", "|---|---|---|---|"]
    summary = f"\n合計: OK {tot['ok']} / DIFF {tot['diff']} / MISSING {tot['missing']}\n"
    return "\n".join(head + rows) + summary + ("\n" + "\n".join(detail) + "\n" if detail else ""), tot


def main(argv=None):
    argv = argv or sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    folder = argv[0]
    text = open(os.path.join(folder, "igor_audit.txt"), encoding="utf-8", errors="replace", newline="").read()
    audit = parse_audit(text)
    if "--dump" in argv:
        fig = audit["figures"].get(argv[argv.index("--dump") + 1])
        print("\n".join(fig["rec"]) if fig else "その図はありません")
        return 0
    expected = json.load(open(os.path.join(folder, "expected.json"), encoding="utf-8"))
    report, tot = build_report(audit, expected)
    open(os.path.join(folder, "audit_report.md"), "w", encoding="utf-8").write(report)
    print(report)
    return 0 if tot["diff"] == 0 and tot["missing"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
