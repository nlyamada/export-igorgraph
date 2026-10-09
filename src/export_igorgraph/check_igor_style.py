#!/usr/bin/env python3
"""
check_igor_style.py
===================

Igor procedure (.ipf / .txt) を、このスキルの規約に照らして静的にチェックする。
Igor でのコンパイルの代わりにはならない。「規約違反と機械的な誤りを、ユーザーに渡す前に潰す」ための道具。

    python check_igor_style.py file.ipf [more.ipf ...] [--strict]

終了コード: エラーがあれば 1（--strict なら警告があっても 1）、なければ 0。

チェック項目
    E001  #pragma rtGlobals=3 が無い
    E010  Execute を使っている（Function 中心で書けば不要。代替は references/style.md）
          どうしても必要な行（許可リストで検査済みのローダーなど）だけ、行末のコメントに
          `style-allow: Execute` と書くと許可される。
    E020  Igor 10 の Python 連携（Python / PythonFile / PythonEnv, igorpro）を使っている
    E070  文字列リテラルが閉じていない（行内で " の対応が取れない）
    E080  Function 内の if / for / do-while / switch / try と End の対応が取れない
    W002  rtGlobals が 3 以外
    W020  Macro / Proc / Window の定義がある（新規コードは Function で書く）
    W030  非ASCII文字がある（文字列内は \\uXXXX にする。コメントだけなら #pragma TextEncoding="UTF-8"）
    W040  Label / Legend / TextBox / ColorScale の文字列に Å がある（nm 系の単位で書く規則）
    W041  Label の文字列で単位が [ ] で囲まれていない（"Q / nm" 形式）
    W060  改行コードが混在している
    W070  400文字を超える長い行
    W090  Function 内で `$名前 = …` と、Wave を宣言せずに直接代入している（rtGlobals=3 ではエラー）
    W095  Function 内でデータフォルダを移動しているが、元に戻す処理（GetDataFolderDFR → SetDataFolder）が無い
"""

import argparse
import re
import sys


def scan_line(line):
    """1行を走査して (コード部分, 文字列リテラルのリスト, 閉じていない文字列があるか) を返す。"""
    code, strings, cur = [], [], []
    in_str = False
    i = 0
    while i < len(line):
        ch = line[i]
        if in_str:
            if ch == "\\" and i + 1 < len(line):
                cur.append(line[i : i + 2])
                i += 2
                continue
            if ch == '"':
                strings.append("".join(cur))
                cur, in_str = [], False
            else:
                cur.append(ch)
        else:
            if ch == '"':
                in_str = True
            elif ch == "/" and line[i : i + 2] == "//":
                break
            else:
                code.append(ch)
        i += 1
    return "".join(code), strings, in_str


OPENERS = {"if": "endif", "for": "endfor", "do": "while", "switch": "endswitch",
           "strswitch": "endswitch", "try": "endtry"}
CLOSERS = {"endif", "endfor", "while", "endswitch", "endtry"}
FUNC_START = re.compile(r"^\s*(?:static\s+|threadsafe\s+)*Function(?:/\w+)*\s+(\w+)", re.I)
OTHER_START = re.compile(r"^\s*(Macro|Proc|Window)\s+\w+", re.I)
DF_MOVE = re.compile(r"\bSetDataFolder\b|\bNewDataFolder\b[^\n]*/S\b", re.I)
DF_SAVE = re.compile(r"\bGetDataFolderDFR\b|\bGetDataFolder\s*\(", re.I)
DOLLAR_ASSIGN = re.compile(r"^\s*\$[^=]*[^=<>!]=(?!=)")

ANNOT_CMD = re.compile(r"^\s*(Label|Legend|TextBox|ColorScale|Tag)\b", re.I)
ANGSTROM = re.compile(r"Å|\\u00C5|\\u212B|\\xC5|\\\\AA|\bAng\b", re.I)


def check(path, text, raw):
    issues = []  # (line, level, code, message)

    def add(ln, level, code, msg):
        issues.append((ln, level, code, msg))

    if b"\r\n" in raw and re.search(rb"(?<!\r)\n", raw):
        add(0, "W", "W060", "改行コードが CRLF と LF で混在している")

    lines = text.replace("\r\n", "\n").split("\n")
    rt = None
    has_encoding_pragma = False
    nonascii_lines = []
    nonascii_in_string = []
    fn = None  # 現在の Function: {"name", "start", "stack", "body"}
    in_other = False  # Macro / Proc / Window の中
    for n, line in enumerate(lines, 1):
        code, strings, unterminated = scan_line(line)
        # --- Function ごとのブロック対応・$代入・データフォルダ ---
        tok = re.match(r"^\s*([A-Za-z_]+)", code)
        word = tok.group(1).lower() if tok else ""
        m_fn = FUNC_START.match(code)
        if m_fn and fn is None:
            fn = {"name": m_fn.group(1), "start": n, "stack": [], "body": []}
            in_other = False
        elif OTHER_START.match(code) and fn is None:
            in_other = True
        elif fn is not None:
            fn["body"].append(code)
            if word in OPENERS:
                fn["stack"].append((word, n))
            elif word in CLOSERS:
                if fn["stack"] and OPENERS[fn["stack"][-1][0]] == word:
                    fn["stack"].pop()
                else:
                    want = OPENERS[fn["stack"][-1][0]] if fn["stack"] else "（開いているブロックなし）"
                    add(n, "E", "E080", f"Function {fn['name']}: {word} の対応が取れない（期待: {want}）")
                    if fn["stack"]:
                        fn["stack"].pop()
            elif word == "end":
                for op, ln in fn["stack"]:
                    add(ln, "E", "E080", f"Function {fn['name']}: {op} が閉じていない（{OPENERS[op]} が無い）")
                text_body = "\n".join(fn["body"])
                if DF_MOVE.search(text_body) and not DF_SAVE.search(text_body):
                    add(fn["start"], "W", "W095",
                        f"Function {fn['name']}: データフォルダを移動しているが、元に戻す処理が見当たらない"
                        "（DFREF saveDF = GetDataFolderDFR() → 最後に SetDataFolder saveDF）")
                fn = None
            if fn is not None and DOLLAR_ASSIGN.match(code):
                add(n, "W", "W090", "Wave を宣言せずに $名前 へ直接代入している。"
                    "rtGlobals=3 では Wave w = $名前 を先に書く: " + line.strip()[:50])
        elif in_other and word in ("end", "endmacro"):
            in_other = False
        m = re.match(r"^\s*#pragma\s+rtGlobals\s*=\s*(\d)", line, re.I)
        if m:
            rt = int(m.group(1))
        if re.match(r"^\s*#pragma\s+TextEncoding", line, re.I):
            has_encoding_pragma = True
        if unterminated:
            add(n, "E", "E070", "文字列リテラルが閉じていない: " + line.strip()[:60])
        if re.search(r"\bExecute\b", code, re.I) and "style-allow: execute" not in line.lower():
            add(n, "E", "E010", "Execute を使っている（許可する行には、コメントで style-allow: Execute と書く）: " + line.strip()[:70])
        if re.search(r"^\s*(PythonFile|PythonEnv)\b", code, re.I) or re.search(r"^\s*Python\s", code) or "igorpro" in code:
            add(n, "E", "E020", "Igor 10 の Python 連携は使わない: " + line.strip()[:70])
        m = re.match(r"^\s*(Macro|Proc|Window)\s+(\w+)", code, re.I)
        if m and "style-allow: macro" not in line.lower():
            add(n, "W", "W020", f"{m.group(1)} {m.group(2)}: 新規コードは Function で書く")
        if any(ord(c) > 127 for c in line):
            nonascii_lines.append(n)
            if any(any(ord(c) > 127 for c in s) for s in strings):
                nonascii_in_string.append(n)
        if ANNOT_CMD.match(code):
            for s in strings:
                if ANGSTROM.search(s):
                    add(n, "W", "W040", "Å を使っている。nm 系の単位で書く規則（Å のデータは nm^-1 に換算）: " + s[:50])
            if re.match(r"^\s*Label\b", code, re.I):
                for s in strings:
                    if re.search(r"\s/\s*\S", s) and "[" not in s:
                        add(n, "W", "W041", "単位が [ ] で囲まれていない（例: Q [nm\\\\S-1\\\\M]）: " + s[:50])
        if len(line) > 400:
            add(n, "W", "W070", "400文字を超える長い行")

    if fn is not None:
        add(fn["start"], "E", "E080", f"Function {fn['name']}: End が無い")
    if rt is None:
        add(0, "E", "E001", "#pragma rtGlobals=3 が無い")
    elif rt != 3:
        add(0, "W", "W002", f"rtGlobals={rt}。新規コードは rtGlobals=3")
    if nonascii_in_string:
        add(nonascii_in_string[0], "W", "W030",
            f"文字列リテラルに非ASCII文字がある（{len(nonascii_in_string)}行）。\\uXXXX にすると文字コードに依存しない")
    elif nonascii_lines and not has_encoding_pragma:
        add(nonascii_lines[0], "W", "W030",
            f"コメントに非ASCII文字がある（{len(nonascii_lines)}行）。#pragma TextEncoding=\"UTF-8\" を付けるか ASCII にする")
    return sorted(issues, key=lambda x: (x[0], x[2]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--strict", action="store_true", help="警告があっても終了コード 1 にする")
    args = ap.parse_args(argv)
    n_err = n_warn = 0
    for path in args.files:
        raw = open(path, "rb").read()
        text = raw.decode("utf-8", errors="replace")
        issues = check(path, text, raw)
        for ln, level, code, msg in issues:
            loc = f"{path}:{ln}" if ln else path
            print(f"{loc}: [{level}] {code} {msg}")
        e = sum(1 for i in issues if i[1] == "E")
        w = sum(1 for i in issues if i[1] == "W")
        n_err, n_warn = n_err + e, n_warn + w
        print(f"== {path}: エラー {e}, 警告 {w}")
    return 1 if (n_err or (args.strict and n_warn)) else 0


if __name__ == "__main__":
    sys.exit(main())
