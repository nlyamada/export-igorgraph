#!/usr/bin/env python3
"""
make_probe.py
=============

Igor 8 で確認したい4点を、1回の実行で確かめるプローブ (igor_text_probe.h5 / .ipf) を作る。
    (1) 固定長文字列の HDF5 データセットを、HDF5LoadData がテキスト Wave として読めるか
    (2) 文字コードの整数配列（代替の方法）を元の文字列に戻せるか
    (3) Execute/Z が、正しい命令では V_flag=0、誤った命令では非0を返し、エラーダイアログを出さないか
    (4) GrepString の挙動（大文字小文字の区別、^$ の全文一致、制御文字の検出、引用符つき文字列の正規表現）

    python make_probe.py [出力ディレクトリ]
"""

from __future__ import annotations

import os
import sys

import numpy as np

from export_igorgraph import eig_allowlist as al
from export_igorgraph.minimal_hdf5_writer import text_to_codes, write_h5

PROBE_STRINGS = [
    "Display/N=fig1",
    'Label/W=fig1 bottom "a\\"b \\\\f02Q\\\\f00"',  # バックスラッシュと引用符を含む
    "x" * 100,
    "ModifyGraph/W=fig1 rgb(a)=(0,0,0)",
]


def build_ipf() -> str:
    L = []
    a = L.append
    qre = al.igor_literal(al.STR)  # 引用符つき文字列の正規表現（許可リストと同じもの）

    a("#pragma rtGlobals=3")
    a("")
    a("// igor_text_probe.ipf")
    a("// Checks in Igor (1) text dataset loading, (2) the char-code fallback, (3) Execute/Z, (4) GrepString.")
    a("// Run:  ProbeTextLoad()   -> choose igor_text_probe.h5. Paste the whole history output back to Claude.")
    a("")
    a("Function ProbeTextLoad()")
    a("")
    a("\tVariable fileID, i, k, n, ok")
    a("\tString s, line")
    a("\tDFREF saveDF = GetDataFolderDFR()")
    a("")
    a("\tHDF5OpenFile/R/I/Z fileID as \"\"")
    a("\tif (V_flag != 0)")
    a("\t\tPrint \"HDF5OpenFile failed or was canceled\"")
    a("\t\treturn -1")
    a("\tendif")
    a("\tNewDataFolder/O/S root:EIG_probe")
    a("\tPrintf \"IgorVersion = %g\\r\", IgorVersion()")
    a("")
    a("\t// (1) fixed-length string dataset -> text wave")
    a("\tHDF5LoadData/O/Z/Q fileID, \"probe_text\"")
    a("\tPrintf \"(1) HDF5LoadData probe_text: V_flag=%d (0 expected)\\r\", V_flag")
    a("\tWave/T/Z tw = probe_text")
    a("\tif (WaveExists(tw))")
    a("\t\tPrintf \"    WaveType(w,1)=%d (2 means text), points=%d (4 expected)\\r\", WaveType(tw, 1), numpnts(tw)")
    a("\t\tfor (i = 0; i < numpnts(tw); i += 1)")
    a("\t\t\ts = tw[i]")
    a("\t\t\tn = strlen(s)")
    a("\t\t\tif (strlen(s) > 60)")
    a("\t\t\t\ts = s[0, 59]")
    a("\t\t\tendif")
    a("\t\t\tPrintf \"    [%d] len=%d  %s\\r\", i, n, s")
    a("\t\tendfor")
    a("\telse")
    a("\t\tPrint \"    probe_text was NOT loaded as a wave\"")
    a("\tendif")
    a("")
    a("\t// (2) char codes (int32, each string followed by 0) -> strings")
    a("\tHDF5LoadData/O/Z/Q fileID, \"probe_codes\"")
    a("\tPrintf \"(2) HDF5LoadData probe_codes: V_flag=%d (0 expected)\\r\", V_flag")
    a("\tWave/Z cw = probe_codes")
    a("\tif (WaveExists(cw))")
    a("\t\tk = 0")
    a("\t\tok = 1")
    a("\t\tline = \"\"")
    a("\t\tfor (i = 0; i < numpnts(cw); i += 1)")
    a("\t\t\tif (cw[i] == 0)")
    a("\t\t\t\tif (WaveExists(tw) && k < numpnts(tw))")
    a("\t\t\t\t\tif (CmpStr(line, tw[k]) != 0)")
    a("\t\t\t\t\t\tok = 0")
    a("\t\t\t\t\tendif")
    a("\t\t\t\telse")
    a("\t\t\t\t\tok = 0")
    a("\t\t\t\tendif")
    a("\t\t\t\tk += 1")
    a("\t\t\t\tline = \"\"")
    a("\t\t\telse")
    a("\t\t\t\tline += num2char(cw[i])")
    a("\t\t\tendif")
    a("\t\tendfor")
    a("\t\tPrintf \"    decoded %d strings; identical to the text wave: %d (1 = yes)\\r\", k, ok")
    a("\telse")
    a("\t\tPrint \"    probe_codes was NOT loaded as a wave\"")
    a("\tendif")
    a("\tHDF5CloseFile fileID")
    a("")
    a("\t// (3) Execute/Z")
    a("\tExecute/Z \"Print \\\"  (Execute printed this line)\\\"\"\t// style-allow: Execute (probe)")
    a("\tPrintf \"(3) Execute/Z with a valid command: V_flag=%d (0 expected)\\r\", V_flag")
    a("\tExecute/Z \"ThisIsNotAnIgorCommand 123\"\t// style-allow: Execute (probe)")
    a("\tPrintf \"    Execute/Z with an invalid command: V_flag=%d (nonzero expected). No error dialog should have appeared.\\r\", V_flag")
    a("")
    a("\t// (4) GrepString")
    a("\tEIG_Chk(\"case-sensitive: GrepString(ABC, ^abc$)\", GrepString(\"ABC\", \"^abc$\"), 0)")
    a("\tEIG_Chk(\"full match: GrepString(abc, ^abc$)\", GrepString(\"abc\", \"^abc$\"), 1)")
    a("\tEIG_Chk(\"anchors: GrepString(abcd, ^abc$)\", GrepString(\"abcd\", \"^abc$\"), 0)")
    a("\tEIG_Chk(\"printable ASCII only: [^ -~] on 'a b'\", GrepString(\"a b\", \"[^ -~]\"), 0)")
    a("\tEIG_Chk(\"control character found: [^ -~] on a+LF+b\", GrepString(\"a\" + num2char(10) + \"b\", \"[^ -~]\"), 1)")
    a(f"\tString qre = \"^{qre}$\"\t\t\t\t// the string-literal pattern of the allowlist")
    a("\tEIG_Chk(\"quoted string: \\\"abc\\\"\", GrepString(\"\\\"abc\\\"\", qre), 1)")
    a("\tEIG_Chk(\"quoted string with escaped quote\", GrepString(\"\\\"a\\\\\\\"b\\\"\", qre), 1)")
    a("\tEIG_Chk(\"quoted string with an inner bare quote must NOT match\", GrepString(\"\\\"a\\\"b\\\"\", qre), 0)")
    a("\tEIG_Chk(\"quote then ;command must NOT match\", GrepString(\"\\\"a\\\";KillWaves/A;\\\"b\\\"\", qre), 0)")
    a("")
    a("\tKillDataFolder/Z root:EIG_probe")
    a("\tSetDataFolder saveDF")
    a("\tPrint \"ProbeTextLoad finished. Paste everything printed above back to Claude.\"")
    a("\treturn 0")
    a("End")
    a("")
    a("Function EIG_Chk(label, got, expected)")
    a("\tString label")
    a("\tVariable got, expected")
    a("")
    a("\tif (got == expected)")
    a("\t\tPrintf \"    PASS  %s\\r\", label")
    a("\telse")
    a("\t\tPrintf \"    FAIL  %s  (got %g, expected %g)\\r\", label, got, expected")
    a("\tendif")
    a("End")
    return "\r\n".join(L) + "\r\n"


def main(argv=None):
    if isinstance(argv, (str, os.PathLike)):
        argv = [os.fspath(argv)]
    out = (argv or sys.argv[1:] or ["."])[0]
    os.makedirs(out, exist_ok=True)
    write_h5(os.path.join(out, "igor_text_probe.h5"), {
        "probe_text": PROBE_STRINGS,
        "probe_codes": text_to_codes(PROBE_STRINGS),
        "probe_num": np.array([1.0, 2.0, 3.0]),
    })
    with open(os.path.join(out, "igor_text_probe.ipf"), "w", newline="") as f:
        f.write(build_ipf())
    print(f"wrote {out}/igor_text_probe.h5 and .ipf")


if __name__ == "__main__":
    main()
