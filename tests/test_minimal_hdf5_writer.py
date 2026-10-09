"""
test_minimal_hdf5_writer.py
===========================

minimal_hdf5_writer.py の検証。次の4種類の読み手で、書いたファイルが読めることを確認する。
    1. minimal_hdf5_reader.py        （自作リーダー）
    2. h5py                          （HDF5 公式Cライブラリ。仕様に厳格）
    3. pyfive                        （独立実装の純Pythonリーダー）
    4. Igor が実際に書いた .h5（構造の一致を確認。任意）

実行: python test_minimal_hdf5_writer.py [Igor が書いた .h5 へのパス]
h5py / pyfive が無い場合、その検証はスキップされる。
"""

import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from export_igorgraph.minimal_hdf5_writer import MAX_DATASETS, UnsupportedHDF5Data, write_h5

try:
    from minimal_hdf5_reader import MinimalHDF5Reader
except ImportError:
    MinimalHDF5Reader = None
try:
    import h5py
except ImportError:
    h5py = None
try:
    import pyfive
except ImportError:
    pyfive = None

FIXED_MTIME = 0x6A5251EC  # Igor が書いた参照ファイルに入っていた更新時刻
results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  [{detail}]" if detail and not cond else ""))


def sample_datasets():
    rng = np.random.default_rng(0)
    f32 = rng.normal(size=(3, 5)).astype("<f4")
    f32[0, 0] = np.nan
    return {
        "a_1d_f64": (np.linspace(0, 1, 11), [(0.1, 0.0)]),
        "b_2d_f32": (f32, [(0.5, 10.0), (2.0, -1.0)]),
        "c_3d_f32": (np.arange(24, dtype="<f4").reshape(2, 3, 4), [(1, 0), (10, 5), (100, -5)]),
        "d_i32": np.arange(7, dtype="<i4") - 3,
        "e_u32": np.arange(5, dtype="<u4") * 1000000000,
        "f_i64": (np.arange(4, dtype="<i8") - 2) * 2**40,
        "g_f64_noscale": np.random.default_rng(1).normal(size=(4, 4)),
    }


def test_roundtrip_all_readers(tmp):
    ds = sample_datasets()
    path = os.path.join(tmp, "rt.h5")
    write_h5(path, ds, mtime=FIXED_MTIME)

    def expected(name):
        spec = ds[name]
        arr, sc = (spec if isinstance(spec, tuple) else (spec, None))
        arr = np.asarray(arr)
        return arr, (sc if sc is not None else [(1.0, 0.0)] * arr.ndim)

    if MinimalHDF5Reader is not None:
        got = MinimalHDF5Reader(path).read_all()
        check("minimal reader: データセット名", sorted(got) == sorted(ds))
        ok = True
        for n, d in got.items():
            arr, sc = expected(n)
            ok &= d.shape == arr.shape and d.dtype == arr.dtype
            ok &= np.array_equal(d.data, arr, equal_nan=arr.dtype.kind == "f")
            ok &= d.scaling is not None and np.allclose(d.scaling, sc)
        check("minimal reader: 形・型・値・スケーリング", ok)

    if h5py is not None:
        with h5py.File(path, "r") as f:
            check("h5py: データセット名", sorted(f.keys()) == sorted(ds))
            ok = True
            for n in ds:
                arr, sc = expected(n)
                d = f[n]
                ok &= d.shape == arr.shape and d.dtype == arr.dtype
                ok &= np.array_equal(d[()], arr, equal_nan=arr.dtype.kind == "f")
                s = d.attrs["IGORWaveScaling"]
                ok &= s.shape == (arr.ndim + 1, 2) and s.dtype == np.float64
                ok &= np.allclose(s[0], 0) and np.allclose(s[1:], sc)
                ok &= d.attrs["IGORWaveType"].dtype == np.int32
            check("h5py: 形・型・値・IGORWaveScaling・IGORWaveType", ok)
            check("h5py: IGORWaveType (f32=2, f64=4, i32=32)",
                  f["b_2d_f32"].attrs["IGORWaveType"] == 2
                  and f["a_1d_f64"].attrs["IGORWaveType"] == 4
                  and f["d_i32"].attrs["IGORWaveType"] == 0x20)

    if pyfive is not None:
        f = pyfive.File(path)
        ok = sorted(f.keys()) == sorted(ds)
        for n in ds:
            arr, sc = expected(n)
            ok &= np.array_equal(f[n][()], arr, equal_nan=arr.dtype.kind == "f")
            ok &= np.allclose(f[n].attrs["IGORWaveScaling"][1:], sc)
        check("pyfive: 名前・値・IGORWaveScaling", ok)


def test_many_datasets(tmp):
    """SNODは8個まで。9個・64個・256個で複数SNODに分かれても名前引きできること。"""
    for n in (1, 8, 9, 20, 64, MAX_DATASETS):
        ds = {f"w{i:03d}": np.full((2, 3), i, dtype="<f4") for i in range(n)}
        path = os.path.join(tmp, f"many{n}.h5")
        write_h5(path, ds, mtime=FIXED_MTIME)
        ok = True
        if h5py is not None:
            with h5py.File(path, "r") as f:
                ok &= len(f) == n
                for i in range(n):  # 名前引き（B-treeのキー検索を通る）
                    ok &= float(f[f"w{i:03d}"][0, 0]) == i
        if MinimalHDF5Reader is not None:
            r = MinimalHDF5Reader(path)
            ok &= len(r.dataset_names()) == n
            ok &= float(r.read_dataset(f"w{n - 1:03d}").data[0, 0]) == n - 1
        if pyfive is not None:
            f = pyfive.File(path)
            ok &= len(list(f.keys())) == n and float(f[f"w{n - 1:03d}"][0, 0]) == n - 1
        check(f"データセット {n} 個", ok)


def test_input_variants(tmp):
    path = os.path.join(tmp, "var.h5")
    big = np.arange(12, dtype=">f8").reshape(3, 4)  # ビッグエンディアン入力
    nc = np.arange(20, dtype="<f4").reshape(4, 5)[:, ::2]  # 非連続（スライス）
    write_h5(path, {"big": big, "noncontig": nc, "x": (np.arange(3.0), [(1.0, 0.0)])},
             mtime=FIXED_MTIME)
    with h5py.File(path, "r") as f:
        check("ビッグエンディアン入力 → リトルエンディアンで保存",
              f["big"].dtype == np.dtype("<f8") and np.array_equal(f["big"][()], big))
        check("非連続配列の値が保たれる", np.array_equal(f["noncontig"][()], nc))
        check("写像の軸順: numpy shape がそのままHDF5の次元", f["big"].shape == (3, 4))


def test_errors(tmp):
    path = os.path.join(tmp, "err.h5")

    def raises(exc, **kw):
        try:
            write_h5(path, kw.pop("ds"), **kw)
        except exc:
            return True
        except Exception as e:  # 想定外の例外型
            print("   unexpected:", type(e).__name__, e)
            return False
        return False

    check("空の辞書は拒否", raises(ValueError, ds={}))
    check("257個は拒否", raises(UnsupportedHDF5Data,
                              ds={f"w{i}": np.zeros(2) for i in range(MAX_DATASETS + 1)}))
    check("日本語の名前は拒否", raises(ValueError, ds={"波": np.zeros(2)}))
    check("Igor標準名でない名前は strict で拒否", raises(ValueError, ds={"1abc": np.zeros(2)}))
    check("strict=False なら通る", not raises(ValueError, ds={"1abc": np.zeros(2)}, strict_names=False))
    check("int16 は未対応として拒否", raises(UnsupportedHDF5Data, ds={"w": np.zeros(2, "<i2")}))
    check("複素数は未対応として拒否", raises(UnsupportedHDF5Data, ds={"w": np.zeros(2, "<c16")}))
    check("5次元は拒否", raises(UnsupportedHDF5Data, ds={"w": np.zeros((1,) * 5)}))
    check("scaling 要素数の不一致は拒否", raises(ValueError, ds={"w": (np.zeros((2, 2)), [(1, 0)])}))


def test_against_igor_file(igor_path, tmp):
    """Igor が書いた .h5 の内容を読み出し、同じ内容を書き直して比較する。"""
    if not (igor_path and os.path.exists(igor_path)):
        print("SKIP Igor製ファイルとの比較（ファイルなし）")
        return
    orig = MinimalHDF5Reader(igor_path).read_all()
    path = os.path.join(tmp, "igor_copy.h5")
    write_h5(path, orig, mtime=FIXED_MTIME)

    if h5py is not None:
        with h5py.File(igor_path, "r") as a, h5py.File(path, "r") as b:
            ok = sorted(a.keys()) == sorted(b.keys())
            for n in a:
                ok &= a[n].shape == b[n].shape and a[n].dtype == b[n].dtype
                ok &= np.array_equal(a[n][()], b[n][()])
                ok &= sorted(a[n].attrs.keys()) == sorted(b[n].attrs.keys())
                for k in a[n].attrs:
                    ok &= np.array_equal(a[n].attrs[k], b[n].attrs[k])
                    ok &= a[n].attrs[k].dtype == b[n].attrs[k].dtype
            check("Igor製ファイルと h5py 上で同一（形・型・値・全属性）", ok)

    # バイト列の比較: Igor製の先頭 0x320 バイト（superblock・ルートOHDR・B-tree枠・ヒープ）は、
    # 同じ名前の集合なら EOF アドレスと B-tree の子ポインタ以外すべて一致するはず。
    A = open(igor_path, "rb").read()
    B = open(path, "rb").read()
    diff = [i for i in range(0x320) if A[i] != B[i]]
    # 許容: EOF(0x28-0x2f)、B-treeの子ポインタ(0xa8-0xaf: 0x88+header24+key0 8)
    allowed = set(range(0x28, 0x30)) | set(range(0xA8, 0xB0))
    check("Igor製の先頭0x320バイトと、EOF・B-tree子ポインタ以外は完全一致",
          set(diff) <= allowed, f"想定外の差: {[hex(i) for i in diff if i not in allowed][:12]}")

    # 属性メッセージ1個ぶん（IGORWaveScaling, 136B）が同一バイト列か
    needle = A[0x6E8 + 8 : 0x6E8 + 8 + 136]  # mapY の IGORWaveScaling 本体
    check("IGORWaveScaling 属性メッセージのバイト列が Igor と一致", needle in B)
    needle2 = A[0x6A8 + 8 : 0x6A8 + 8 + 56]  # IGORWaveType 本体
    check("IGORWaveType 属性メッセージのバイト列が Igor と一致", needle2 in B)


if __name__ == "__main__":
    igor = sys.argv[1] if len(sys.argv) > 1 else "igor_reference.h5"
    print(f"h5py={'有' if h5py else '無'} pyfive={'有' if pyfive else '無'} "
          f"minimal_reader={'有' if MinimalHDF5Reader else '無'}\n")
    with tempfile.TemporaryDirectory() as tmp:
        test_roundtrip_all_readers(tmp)
        test_many_datasets(tmp)
        if h5py is not None:
            test_input_variants(tmp)
        test_errors(tmp)
        if MinimalHDF5Reader is not None:
            test_against_igor_file(igor, tmp)
    bad = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(bad)}/{len(results)} passed")
    sys.exit(1 if bad else 0)
