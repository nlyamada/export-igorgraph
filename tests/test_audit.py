"""audit.py のテスト。Igor 8.04 (Windows) の実機の読み戻し（fixtures/igor_audit_8.04_win.txt）を資料にして、
(1) 実機の出力で、送った命令の大半が一致と判定されること、
(2) その読み戻しを書き換えたとき、値の違い・欠落・読み込み失敗を検出できること、を確認する。
python test_audit.py"""
import os, re, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import audit

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures", "igor_audit_8.04_win.txt")
EXP = os.path.join(HERE, "fixtures", "expected_round1.json")  # 第1回のギャラリーの期待値（そのときの命令）
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ")+name+("" if cond else f"  [{detail}]"))

def report_of(text, expected):
    return audit.build_report(audit.parse_audit(text), expected)

def main():
    import json
    expected = json.load(open(EXP, encoding="utf-8"))
    text = open(FIX, encoding="utf-8", errors="replace", newline="").read()
    a = audit.parse_audit(text)
    check("実機の読み戻し: 23 図を読める・Igor 8.04", len(a["figures"]) == 23 and a["meta"]["IGORVERSION"] == "8.04")
    rep, tot = audit.build_report(a, expected)
    check(f"実機の読み戻し: MISSING=0（OK {tot['ok']} 項目）", tot["missing"] == 0, rep[-500:])
    check("実機の読み戻し: DIFF は、Igor が余白を整数に丸めた 2 項目だけ",
          tot["diff"] == 2 and rep.count("margin(") == 2, rep[-500:])
    check("実機の読み戻し: OK が 500 項目以上", tot["ok"] >= 500, str(tot))

    def mutated(sub, new, count=1):
        assert sub in text, sub
        return text.replace(sub, new, count)

    # 値の違い: g01 の1本目の線幅 1.5 → 3（TraceInfo の読み戻しを書き換える）
    t = re.sub(r"(TRACEINFO\tg01_line_t0_y\t[^\r]*?lSize\(x\)=)1\.5", r"\g<1>3", text, count=1)
    _, tot2 = report_of(t, expected)
    check("線幅の違いを DIFF として検出", tot2["diff"] == 3 and tot2["missing"] == 0, str(tot2))

    # 数値の書式の違いは同じ値とみなす
    t = re.sub(r"(TRACEINFO\tg01_line_t0_y\t[^\r]*?lSize\(x\)=)1\.5", r"\g<1>1.50000", text, count=1)
    _, tot3 = report_of(t, expected)
    check("数値の書式の違い（1.5 と 1.50000）は同じ値", tot3["diff"] == 2, str(tot3))

    # Label の欠落（記録マクロの Label bottom の行を消す）
    t = re.sub(r"REC\t\tLabel bottom [^\r]*\r", "", text, count=1)
    _, tot4 = report_of(t, expected)
    check("Label の欠落を MISSING として検出", tot4["missing"] >= 1, str(tot4))

    # 軸の対数が反映されていない（g06 の AxisInfo の log(x)=1 → 0）
    t = re.sub(r"(AXISINFO\tbottom\tAXTYPE:bottom[^\r]*?log\(x\)=)1", r"\g<1>0", text.split("FIGURE\tg07_semilogx")[0], count=1)
    t = t + "FIGURE\tg07_semilogx" + text.split("FIGURE\tg07_semilogx", 1)[1]
    _, tot5 = report_of(t, expected)
    check("軸の対数が反映されていない場合を DIFF として検出", tot5["diff"] >= 3, str(tot5))

    # 画像の色テーブルの範囲が違う
    t = mutated("ctab= {1,200,", "ctab= {1,150,")
    _, tot6 = report_of(t, expected)
    check("画像の ctab の範囲の違いを検出", tot6["diff"] >= 3, str(tot6))

    # 読み込み失敗・図の欠落
    t = text.replace("FIGURE\tg02_markers\t0", "FIGURE\tg02_markers\t-1", 1)
    rep7, tot7 = report_of(t, expected)
    check("LoadPythonFigure の失敗（戻り値 -1）を検出", "LoadPythonFigure が失敗" in rep7 and tot7["missing"] >= 1)
    t = re.sub(r"FIGURE\tg03_err_ysym.*?ENDFIGURE\r", "", text, flags=re.S)
    rep8, _ = report_of(t, expected)
    check("読み戻しに無い図を検出", "この図は読み戻しにありません" in rep8)

    # エラーバーの値が違う
    t = mutated("Y,wave=(:g06_loglog:g06_loglog_t0_eyp,:g06_loglog:g06_loglog_t0_eyn)",
                "Y,wave=(:g06_loglog:g06_loglog_t0_eyn,:g06_loglog:g06_loglog_t0_eyp)")
    _, tot9 = report_of(t, expected)
    check("エラーバーの Wave の取り違え（正負の入れ替え）を検出", tot9["diff"] >= 3, str(tot9))

    # \u エスケープと実際の文字の同一視（g07 のラベル ω）
    check("Label: \\u03C9 と 実際の文字 ω は同じ", audit.unescape_u("\\u03C9 [rad]") == "ω [rad]")
    check("parse_items: 入れ子のカッコ・ブレースを分けない",
          audit.parse_items("height={Aspect,0.8},rgb(a)=(1,2,3)") == [("height", None, "{Aspect,0.8}"), ("rgb", "a", "(1,2,3)")])
    check("values_equal: 大きな違いは検出し、書式の違いと ±1 の丸めは許容",
          audit.values_equal("(54998,10023,10280)", "(54998,10023,20280)") is False
          and audit.values_equal("(54998,10023,10280)", "(54998,10023,10281)")
          and audit.values_equal("226.772", "226.7720") and audit.values_equal("{Aspect,0.8}", "{Aspect, 0.80}"))
    print(f"\n{sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1

if __name__ == "__main__":
    sys.exit(main())
