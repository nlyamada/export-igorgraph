"""check_igor_style.py のテスト。わざと誤りを入れたコードで、各規則が働くことを確認する。 python test_check_igor_style.py"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from export_igorgraph.check_igor_style import check

PRAGMA = "#pragma rtGlobals=3\n"
results = []


def codes(text):
    return {c for _, _, c, _ in check("t.ipf", text, text.encode("utf-8"))}


def expect(name, text, present=(), absent=()):
    got = codes(text)
    ok = all(c in got for c in present) and all(c not in got for c in absent)
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  [got {sorted(got)}]"))


GOOD = PRAGMA + """
Function Good(w)
	Wave w
	DFREF saveDF = GetDataFolderDFR()
	NewDataFolder/O/S root:tmp
	Variable i
	for (i = 0; i < numpnts(w); i += 1)
		if (w[i] > 0)
			w[i] = 0
		elseif (w[i] < -1)
			w[i] = -1
		else
			w[i] += 1
		endif
	endfor
	do
		i -= 1
	while (i > 0)
	switch (i)
		case 0:
			break
		default:
			break
	endswitch
	SetDataFolder saveDF
	return 0
End
"""
expect("正しいコードは指摘なし", GOOD, absent=("E001", "E010", "E070", "E080", "W090", "W095", "W020"))
expect("rtGlobals が無い", "Function F()\nEnd\n", present=("E001",))
expect("rtGlobals=1 は警告", "#pragma rtGlobals=1\nFunction F()\nEnd\n", present=("W002",), absent=("E001",))
expect("Execute はエラー", PRAGMA + "Function F()\n\tExecute \"print 1\"\nEnd\n", present=("E010",))
expect("style-allow の印がある行の Execute は許可", PRAGMA + "Function F(c)\n\tString c\n\tExecute/Z c\t// style-allow: Execute (checked)\nEnd\n", absent=("E010",))
expect("印がない行の Execute はエラーのまま", PRAGMA + "Function F(c)\n\tString c\n\tExecute/Z c\t// checked\nEnd\n", present=("E010",))
expect("コメント・文字列中の Execute は無視", PRAGMA + "Function F()\n\t// Execute is not used\n\tPrint \"Execute\"\nEnd\n", absent=("E010",))
expect("Macro は警告", PRAGMA + "Macro M()\n\tprint 1\nEnd\n", present=("W020",))
expect("endif が足りない", PRAGMA + "Function F(x)\n\tVariable x\n\tif (x > 0)\n\t\tx = 1\nEnd\n", present=("E080",))
expect("endfor の対応違い", PRAGMA + "Function F(x)\n\tVariable x\n\tfor (x = 0; x < 3; x += 1)\n\tendif\nEnd\n", present=("E080",))
expect("余分な endif", PRAGMA + "Function F(x)\n\tVariable x\n\tendif\nEnd\n", present=("E080",))
expect("End が無い", PRAGMA + "Function F(x)\n\tVariable x\n", present=("E080",))
expect("do-while は正しく対応", PRAGMA + "Function F(x)\n\tVariable x\n\tdo\n\t\tx += 1\n\twhile (x < 3)\nEnd\n", absent=("E080",))
expect("Wave 宣言なしの $ 代入（Function 内）", PRAGMA + "Function F(n)\n\tString n\n\t$n = 1\nEnd\n", present=("W090",))
expect("$ 代入でも Wave 宣言があれば問題なし（宣言行は代入ではない）",
       PRAGMA + "Function F(n)\n\tString n\n\tWave w = $n\n\tw = 1\nEnd\n", absent=("W090",))
expect("Macro 内の $ 代入は対象外", PRAGMA + "Macro M(n)\n\tString n\n\t$n = 1\nEnd\n", absent=("W090",))
expect("データフォルダを移動して戻さない", PRAGMA + "Function F()\n\tSetDataFolder root:\nEnd\n", present=("W095",))
expect("NewDataFolder/S で移動して戻さない", PRAGMA + "Function F()\n\tNewDataFolder/O/S root:x\nEnd\n", present=("W095",))
expect("GetDataFolderDFR で保存していれば問題なし",
       PRAGMA + "Function F()\n\tDFREF d = GetDataFolderDFR()\n\tSetDataFolder root:\n\tSetDataFolder d\nEnd\n", absent=("W095",))
expect("Label の Å は警告", PRAGMA + "Function F()\n\tLabel bottom \"Q [\\u00C5\\\\S-1\\\\M]\"\nEnd\n", present=("W040",))
expect("Label の ' / ' 形式は警告", PRAGMA + "Function F()\n\tLabel bottom \"Q / nm\"\nEnd\n", present=("W041",))
expect("Label の [ ] 形式は問題なし", PRAGMA + "Function F()\n\tLabel bottom \"Q [nm\\\\S-1\\\\M]\"\nEnd\n", absent=("W040", "W041"))
expect("文字列中の非ASCII は警告", PRAGMA + "Function F()\n\tPrint \"µm\"\nEnd\n", present=("W030",))
expect("閉じていない文字列", PRAGMA + "Function F()\n\tPrint \"abc\nEnd\n", present=("E070",))
expect("Igor 10 の Python 連携はエラー", PRAGMA + "Function F()\n\tPythonFile file=\"a.py\"\nEnd\n", present=("E020",))
print(f"\n{sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
