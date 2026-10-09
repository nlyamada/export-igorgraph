"""Run every test script.   python -X utf8 tests/run_all.py

Each test script prints "N/M passed". Needs numpy, matplotlib and h5py (pip install -e ".[test]").
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS = [
    "test_minimal_hdf5_writer.py",
    "test_mpl_to_igor.py",       # takes an output directory
    "test_layout.py",
    "test_contour.py",           # needs matplotlib >= 3.8
    "test_check_igor_style.py",
    "test_loader.py",
    "test_audit.py",
]
NEEDS_OUTDIR = {"test_mpl_to_igor.py"}


def mpl_version():
    import matplotlib
    return tuple(int(x) for x in re.findall(r"\d+", matplotlib.__version__)[:2])


def main() -> int:
    failed = []
    with tempfile.TemporaryDirectory() as tmp:
        for t in TESTS:
            if t == "test_contour.py" and mpl_version() < (3, 8):
                print(f"{t:32s} skipped (matplotlib < 3.8)")
                continue
            cmd = [sys.executable, "-X", "utf8", os.path.join(HERE, t)] + ([tmp] if t in NEEDS_OUTDIR else [])
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=tmp)
            m = re.findall(r"(\d+)/(\d+) passed", r.stdout)
            ok = r.returncode == 0 and bool(m) and m[-1][0] == m[-1][1]
            print(f"{t:32s} {m[-1][0] + '/' + m[-1][1] if m else '?':>8s}  {'OK' if ok else 'FAILED'}")
            if not ok:
                failed.append(t)
                print("\n".join(r.stdout.splitlines()[-15:]))
                print(r.stderr[-1500:])
    print("\nALL PASSED" if not failed else f"\nFAILED: {', '.join(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
