"""Command line: python -m export_igorgraph --version | loader [DIR] | check FILE.ipf [--strict]"""
import os
import sys

from . import __version__

USAGE = """\
usage: python -m export_igorgraph --version
       python -m export_igorgraph loader [DIR]      write ExportIgorGraphLoader.ipf (default: current directory)
       python -m export_igorgraph check FILE.ipf [--strict]   style-check an Igor procedure file
       python -m export_igorgraph style-check FILE.json       validate a style file (keys and values)
"""


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return 0 if argv else 2
    if argv[0] in ("--version", "-V"):
        print(__version__)
        return 0
    if argv[0] == "loader":
        from . import make_loader
        out = argv[1] if len(argv) > 1 else "."
        os.makedirs(out, exist_ok=True)
        make_loader.main(out)
        print("Put ExportIgorGraphLoader.ipf into 'Documents\\WaveMetrics\\Igor Pro 8 User Files\\Igor Procedures\\' "
              "(it is then loaded when Igor starts); in Igor run LoadPythonFigure().")
        return 0
    if argv[0] == "style-check":
        from .mpl_to_igor import check_style_file
        if len(argv) < 2:
            print(USAGE)
            return 2
        try:
            st, warn = check_style_file(argv[1])
        except Exception as e:  # JSON の誤り・値の誤り
            print(f"NG: {e}")
            return 1
        print(f"OK: {len(st)} keys: {', '.join(sorted(st))}")
        for w in warn:
            print("warning:", w)
        return 0
    if argv[0] == "check":
        from . import check_igor_style
        return int(check_igor_style.main(argv[1:]) or 0)
    print(USAGE)
    return 2


if __name__ == "__main__":
    sys.exit(main())
