"""
minimal_hdf5_writer.py
======================

h5py が使えない環境（claude.ai サンドボックス等）で、Igor Pro が読める HDF5 ファイルを
書き出すための最小限の自前HDF5ライターです。minimal_hdf5_reader.py と対になります。

出力する構造（Igor Pro が実際に書き出した .h5 のバイト列を調べて合わせたもの）:
    - Superblock version 0 (group leaf K=4, internal K=16)
    - Root group: 旧形式シンボルテーブル (B-tree v1 + Local Heap + SNOD)
    - Object Header version 1
    - Dataspace message version 1 (Simple, max dims 付き)
    - Datatype message version 1 (float32/float64/int32/int64/uint32/uint64)
    - Data Layout message version 3, class=Contiguous（圧縮・チャンクなし）
    - Attribute message version 1:
        IGORWaveType    : int32 スカラー（Igor の Wave 型コード）
        IGORWaveScaling : float64 (rank+1, 2)。row0 はダミー、row i+1 が次元 i の (delta, offset)

文字列（テキスト Wave）のデータセットも書ける:
    - リスト `["abc", "de"]` か、numpy の文字列配列を渡す（tuple は (配列, scaling) と区別できないので不可）。
    - 固定長の文字列（ASCII、終端 NUL、長さ = 最長 + 1）。IGOR 用の属性は付けない。
    - Igor 8 で HDF5LoadData が読めるかは、igor_text_probe で確認する。読めない場合の代替として、
      text_to_codes() で文字コードの整数配列にして渡す方法がある。

汎用HDF5ライターではありません。
    - データセットはルートグループ直下のみ（サブグループなし）。最大 256 個。
    - 配列は C 順（行優先）の連続領域として、numpy の shape をそのまま HDF5 の次元にします。
      「Igor の行・列が HDF5 のどの次元に対応するか」は書き出し側では変換しません
      （igor_hdf5_probe.ipf で実機確認する前提です）。

使い方:
    from export_igorgraph.minimal_hdf5_writer import write_h5
    write_h5("out.h5", {
        "x": np.linspace(0, 1, 101),                       # スケーリングなし (delta=1, offset=0)
        "y": (y_array, [(0.01, 0.0)]),                      # (配列, [(delta, offset), ...]) 次元ごと
    })
"""

from __future__ import annotations

import re
import struct
import time
from typing import Mapping, Optional, Sequence

import numpy as np

# --- HDF5 定数 -------------------------------------------------------------
UNDEF = 0xFFFFFFFFFFFFFFFF
LEAF_K = 4  # group leaf node K  -> SNOD は最大 2K = 8 シンボル
INTERNAL_K = 16  # group internal node K -> B-tree ノードは最大 2K = 32 子
SNOD_CAPACITY = 2 * LEAF_K
MAX_SNODS = 2 * INTERNAL_K
MAX_DATASETS = SNOD_CAPACITY * MAX_SNODS  # 256

_HEAP_FREE_BLOCK = 32  # Igor が書くローカルヒープ末尾の空きブロックと同じ大きさ

# Igor の Wave 型コード。float32 のみ実ファイルで確認済み。
# それ以外は Igor マニュアルの WaveType の型コード表に基づく（実機での確認は未了）。
_IGOR_WAVE_TYPE = {
    ("f", 4): 0x02,
    ("f", 8): 0x04,
    ("i", 4): 0x20,
    ("u", 4): 0x20 | 0x40,
    ("i", 8): 0x80,
    ("u", 8): 0x80 | 0x40,
}

_IGOR_STD_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,30}$")


class UnsupportedHDF5Data(Exception):
    """このライターが書けないデータが渡された場合に送出"""


# --- 小物 ------------------------------------------------------------------
def _pad8(n: int) -> int:
    return (n + 7) // 8 * 8


def _padb(b: bytes) -> bytes:
    return b + b"\x00" * (_pad8(len(b)) - len(b))


# --- メッセージ本体の組み立て ------------------------------------------------
_FLOAT_PARAMS = {
    # size: (sign位置, precision, exponent位置, exponentサイズ, mantissaサイズ, bias)
    4: (31, 32, 23, 8, 23, 127),
    8: (63, 64, 52, 11, 52, 1023),
}


def _datatype_bytes(dtype: np.dtype) -> bytes:
    """Datatype message (version 1) 本体。パディングなし。"""
    size = dtype.itemsize
    if dtype.kind == "f" and size in _FLOAT_PARAMS:
        sign, prec, eloc, esz, msz, bias = _FLOAT_PARAMS[size]
        head = bytes([0x11, 0x20, sign, 0x00]) + struct.pack("<I", size)
        props = struct.pack("<HHBBBBI", 0, prec, eloc, esz, 0, msz, bias)
        return head + props
    if dtype.kind in "iu" and size in (4, 8):
        signed = 0x08 if dtype.kind == "i" else 0x00
        head = bytes([0x10, signed, 0x00, 0x00]) + struct.pack("<I", size)
        props = struct.pack("<HH", 0, 8 * size)
        return head + props
    raise UnsupportedHDF5Data(
        f"dtype {dtype} は未対応です（float32/float64/int32/int64/uint32/uint64のみ）"
    )


def _dataspace_bytes(shape: Sequence[int], with_max: bool) -> bytes:
    """Dataspace message (version 1, Simple)。max dims は dims と同じ値にする。"""
    rank = len(shape)
    b = bytes([1, rank, 1 if with_max else 0, 0, 0, 0, 0, 0])
    b += struct.pack(f"<{rank}Q", *shape)
    if with_max:
        b += struct.pack(f"<{rank}Q", *shape)
    return b


def _attribute_bytes(name: str, dtype_msg: bytes, ds_msg: bytes, data: bytes) -> bytes:
    """Attribute message (version 1)。全体を8byte境界にパディング。"""
    nb = name.encode("ascii") + b"\x00"
    body = struct.pack("<BBHHH", 1, 0, len(nb), len(dtype_msg), len(ds_msg))
    body += _padb(nb) + _padb(dtype_msg) + _padb(ds_msg) + data
    return _padb(body)


def _message(mtype: int, body: bytes, flags: int = 0) -> bytes:
    assert len(body) % 8 == 0, "message body は8byteの倍数である必要があります"
    return struct.pack("<HHB3x", mtype, len(body), flags) + body


def _object_header(messages: Sequence[bytes]) -> bytes:
    body = b"".join(messages)
    return struct.pack("<BBHII4x", 1, 0, len(messages), 1, len(body)) + body


def _string_datatype_bytes(length: int) -> bytes:
    """Datatype message (version 1, String)。固定長・終端 NUL・ASCII。"""
    return bytes([0x13, 0x00, 0x00, 0x00]) + struct.pack("<I", length)


def text_to_codes(strings) -> np.ndarray:
    """文字列のリストを、ASCII コードの int32 配列にする（各文字列の後ろに 0 を1つ置く）。
    Igor 側では num2char で元に戻せる。固定長文字列を Igor 8 が読めない場合の代替。"""
    out = []
    for t in strings:
        b = t.encode("ascii")
        if 0 in b:
            raise ValueError("NUL を含む文字列は渡せません")
        out += list(b) + [0]
    return np.asarray(out, dtype="<i4")


def _is_text_spec(spec) -> bool:
    if isinstance(spec, (list, np.ndarray)):
        arr = np.asarray(spec)
        return arr.dtype.kind in "US" and arr.ndim == 1
    return False


def _normalize_text(name: str, spec):
    strings = [x.decode("ascii") if isinstance(x, bytes) else str(x) for x in np.asarray(spec).tolist()]
    if not strings:
        raise UnsupportedHDF5Data(f"'{name}': 空の文字列リストは書けません")
    try:
        raw = [t.encode("ascii") for t in strings]
    except UnicodeEncodeError:
        raise UnsupportedHDF5Data(f"'{name}': 文字列は ASCII のみです（非ASCIIは \\uXXXX などで表す）") from None
    if any(b"\x00" in b for b in raw):
        raise UnsupportedHDF5Data(f"'{name}': NUL を含む文字列は書けません")
    length = max(len(b) for b in raw) + 1
    return np.array(raw, dtype=f"S{length}"), None


# --- 入力の正規化 -------------------------------------------------------------
def _normalize(name: str, spec, strict_names: bool):
    if not isinstance(name, str) or not name:
        raise ValueError("データセット名は空でない文字列にしてください")
    try:
        name.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError(f"'{name}': データセット名はASCIIのみ使えます") from None
    if "/" in name or "\x00" in name:
        raise ValueError(f"'{name}': '/' や NUL は使えません")
    if strict_names and not _IGOR_STD_NAME.match(name):
        raise ValueError(
            f"'{name}': Igor の標準Wave名（英字で始まり英数字と_のみ、31文字以内）ではありません"
        )

    if _is_text_spec(spec):
        return _normalize_text(name, spec)

    scaling = None
    if hasattr(spec, "data"):  # minimal_hdf5_reader.Dataset 互換
        arr, scaling = spec.data, getattr(spec, "scaling", None)
    elif isinstance(spec, tuple) and len(spec) == 2:
        arr, scaling = spec
    else:
        arr = spec

    arr = np.asarray(arr)
    if arr.ndim < 1 or arr.size == 0:
        raise UnsupportedHDF5Data(f"'{name}': 0次元・空の配列は書けません")
    if arr.ndim > 4:
        raise UnsupportedHDF5Data(f"'{name}': Igor の Wave は4次元までです")
    dt = arr.dtype.newbyteorder("<")
    _datatype_bytes(dt)  # 対応可否のチェック
    arr = np.ascontiguousarray(arr, dtype=dt)

    if scaling is None:
        scaling = [(1.0, 0.0)] * arr.ndim
    scaling = [(float(d), float(o)) for d, o in scaling]
    if len(scaling) != arr.ndim:
        raise ValueError(
            f"'{name}': scaling の要素数 {len(scaling)} が次元数 {arr.ndim} と一致しません"
        )
    return arr, scaling


# --- データセットのオブジェクトヘッダ -------------------------------------------
def _dataset_header(arr: np.ndarray, scaling, data_addr: int, mtime: int) -> bytes:
    if arr.dtype.kind == "S":  # 文字列: IGOR 用の属性は付けない
        layout = struct.pack("<BBQQ6x", 3, 1, data_addr, arr.nbytes)
        return _object_header([
            _message(0x0001, _padb(_dataspace_bytes(arr.shape, with_max=True))),
            _message(0x0003, _padb(_string_datatype_bytes(arr.dtype.itemsize)), flags=0x01),
            _message(0x0005, bytes([2, 2, 2, 1, 0, 0, 0, 0]), flags=0x01),
            _message(0x0008, layout),
            _message(0x0012, struct.pack("<B3xI", 1, mtime)),
        ])
    key = (arr.dtype.kind, arr.dtype.itemsize)
    wave_type = _IGOR_WAVE_TYPE[key]
    i32 = np.dtype("<i4")
    f64 = np.dtype("<f8")

    layout = struct.pack("<BBQQ6x", 3, 1, data_addr, arr.nbytes)
    type_attr = _attribute_bytes(
        "IGORWaveType",
        _datatype_bytes(i32),
        _dataspace_bytes((), with_max=False),
        struct.pack("<i", wave_type),
    )
    sc = np.zeros((arr.ndim + 1, 2), dtype=f64)  # row0 はダミー
    for i, (delta, offset) in enumerate(scaling):
        sc[i + 1] = (delta, offset)
    scaling_attr = _attribute_bytes(
        "IGORWaveScaling",
        _datatype_bytes(f64),
        _dataspace_bytes(sc.shape, with_max=True),
        sc.tobytes(),
    )
    messages = [
        _message(0x0001, _padb(_dataspace_bytes(arr.shape, with_max=True))),
        _message(0x0003, _padb(_datatype_bytes(arr.dtype)), flags=0x01),
        _message(0x0005, bytes([2, 2, 2, 1, 0, 0, 0, 0]), flags=0x01),  # Fill Value
        _message(0x0008, layout),
        _message(0x0012, struct.pack("<B3xI", 1, mtime)),  # Modification Time
        _message(0x000C, type_attr),
        _message(0x000C, scaling_attr),
    ]
    return _object_header(messages)


# --- 公開API ---------------------------------------------------------------
def write_h5(
    path: str,
    datasets: Mapping[str, object],
    *,
    mtime: Optional[int] = None,
    strict_names: bool = True,
) -> int:
    """
    datasets: {名前: 配列 | (配列, [(delta, offset), ...]) | .data/.scaling を持つオブジェクト}
        scaling は numpy の軸順（= 書き出す HDF5 の次元順）で、次元ごとに (delta, offset)。
    mtime: オブジェクト更新時刻（UNIX秒）。省略時は現在時刻。再現性が要るテストでは固定する。
    strict_names: True なら Igor の標準Wave名に合わないデータセット名を拒否する。
    戻り値: 書き込んだバイト数
    """
    if not datasets:
        raise ValueError("データセットが1つもありません")
    if len(datasets) > MAX_DATASETS:
        raise UnsupportedHDF5Data(
            f"データセット数 {len(datasets)} は上限 {MAX_DATASETS} を超えています"
        )
    if mtime is None:
        mtime = int(time.time())

    items = {n: _normalize(n, s, strict_names) for n, s in datasets.items()}
    names = sorted(items, key=lambda s: s.encode("ascii"))  # SNOD は名前の昇順が必須

    # --- ローカルヒープ（名前文字列） ---
    name_off = {}
    off = 8  # offset 0 は空文字列
    for n in names:
        name_off[n] = off
        off += _pad8(len(n) + 1)
    heap_used = off
    heap_seg_size = heap_used + _HEAP_FREE_BLOCK
    heap_data = bytearray(heap_seg_size)
    for n in names:
        heap_data[name_off[n] : name_off[n] + len(n)] = n.encode("ascii")
    heap_data[heap_used : heap_used + 16] = struct.pack("<QQ", 1, _HEAP_FREE_BLOCK)

    # --- アドレス割り当て ---
    n_snod = (len(names) + SNOD_CAPACITY - 1) // SNOD_CAPACITY
    root_ohdr_addr = 96
    root_ohdr_size = 16 + 8 + 16
    btree_addr = root_ohdr_addr + root_ohdr_size
    btree_size = 24 + (2 * INTERNAL_K + 1) * 8 + 2 * INTERNAL_K * 8
    heap_addr = btree_addr + btree_size
    heap_data_addr = heap_addr + 32
    snod_addr0 = heap_data_addr + heap_seg_size
    snod_size = 8 + SNOD_CAPACITY * 40
    cursor = snod_addr0 + n_snod * snod_size

    ohdr_addr, data_addr = {}, {}
    ohdr_len = {}
    for n in names:
        arr, scaling = items[n]
        ohdr_len[n] = len(_dataset_header(arr, scaling, 0, mtime))  # 長さはアドレスに依存しない
        ohdr_addr[n] = cursor
        cursor += ohdr_len[n]
        data_addr[n] = cursor
        cursor += _pad8(arr.nbytes)
    eof = cursor

    # --- 書き込み ---
    buf = bytearray(eof)

    # Superblock (56 byte) + Root symbol table entry (40 byte)
    sb = b"\x89HDF\r\n\x1a\n"
    sb += bytes([0, 0, 0, 0, 0])  # sb/freespace/root group/reserved/shared-header version
    sb += bytes([8, 8, 0])  # size of offsets, size of lengths, reserved
    sb += struct.pack("<HH", LEAF_K, INTERNAL_K)
    sb += struct.pack("<I", 0)  # file consistency flags
    sb += struct.pack("<QQQQ", 0, UNDEF, eof, UNDEF)  # base, free space, EOF, driver info
    sb += struct.pack("<QQII", 0, root_ohdr_addr, 1, 0)  # link name off, ohdr, cache type, reserved
    sb += struct.pack("<QQ", btree_addr, heap_addr)  # scratch: B-tree, heap
    assert len(sb) == 96
    buf[0:96] = sb

    # Root group object header: Symbol Table message
    root_hdr = _object_header([_message(0x0011, struct.pack("<QQ", btree_addr, heap_addr))])
    assert len(root_hdr) == root_ohdr_size
    buf[root_ohdr_addr : root_ohdr_addr + root_ohdr_size] = root_hdr

    # Group B-tree (node type 0, level 0)
    node = b"TREE" + struct.pack("<BBHQQ", 0, 0, n_snod, UNDEF, UNDEF)
    node += struct.pack("<Q", 0)  # key0: 空文字列のオフセット
    for c in range(n_snod):
        chunk = names[c * SNOD_CAPACITY : (c + 1) * SNOD_CAPACITY]
        node += struct.pack("<QQ", snod_addr0 + c * snod_size, name_off[chunk[-1]])
    buf[btree_addr : btree_addr + len(node)] = node  # 残りはゼロ埋め

    # Local heap
    buf[heap_addr : heap_addr + 32] = (
        b"HEAP"
        + bytes([0, 0, 0, 0])
        + struct.pack("<QQQ", heap_seg_size, heap_used, heap_data_addr)
    )
    buf[heap_data_addr : heap_data_addr + heap_seg_size] = heap_data

    # Symbol table nodes
    for c in range(n_snod):
        chunk = names[c * SNOD_CAPACITY : (c + 1) * SNOD_CAPACITY]
        snod = b"SNOD" + struct.pack("<BBH", 1, 0, len(chunk))
        for n in chunk:
            snod += struct.pack("<QQII16x", name_off[n], ohdr_addr[n], 0, 0)
        a = snod_addr0 + c * snod_size
        buf[a : a + len(snod)] = snod

    # Datasets
    for n in names:
        arr, scaling = items[n]
        hdr = _dataset_header(arr, scaling, data_addr[n], mtime)
        assert len(hdr) == ohdr_len[n]
        buf[ohdr_addr[n] : ohdr_addr[n] + len(hdr)] = hdr
        buf[data_addr[n] : data_addr[n] + arr.nbytes] = arr.tobytes()

    with open(path, "wb") as f:
        f.write(buf)
    return len(buf)


if __name__ == "__main__":
    import sys

    out = sys.argv[1] if len(sys.argv) > 1 else "demo.h5"
    x = np.linspace(0.0, 1.0, 101)
    n = write_h5(out, {"x": (x, [(0.01, 0.0)]), "y": np.sin(2 * np.pi * x)})
    print(f"wrote {n} bytes to {out}")
