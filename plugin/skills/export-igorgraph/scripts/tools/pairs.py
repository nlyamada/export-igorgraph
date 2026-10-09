"""pairs.py: 並置の画像を作る（左: matplotlib / 右: Igor を、図ごとに縦に並べる）。

    python pairs.py <gallery フォルダ> <出力.png> <図の名前> [<図の名前> ...]

gallery フォルダには、mpl/<name>.png（matplotlib の基準画像）と <name>_igor.png（Igor の PNG）が要る。
"""
import os
import sys

from PIL import Image, ImageDraw


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 3:
        print(__doc__)
        return 2
    gal, out, names = argv[0], argv[1], argv[2:]
    rows = []
    for n in names:
        a = os.path.join(gal, "mpl", n + ".png")
        b = os.path.join(gal, n + "_igor.png")
        rows.append((n, Image.open(a).convert("RGB") if os.path.exists(a) else None,
                     Image.open(b).convert("RGB") if os.path.exists(b) else None))
    H = 520

    def fit(im):
        if im is None:
            return Image.new("RGB", (10, H), "white")
        r = H / im.height
        return im.resize((max(int(im.width * r), 1), H))

    cells = [(n, fit(a), fit(b)) for n, a, b in rows]
    colw = max(a.width for _, a, _ in cells), max(b.width for _, _, b in cells)
    sheet = Image.new("RGB", (colw[0] + colw[1] + 20, (H + 26) * len(cells)), "white")
    d = ImageDraw.Draw(sheet)
    for k, (n, a, b) in enumerate(cells):
        y = k * (H + 26)
        d.text((4, y + 6), f"{n}   (left: matplotlib / right: Igor)", fill="red")
        sheet.paste(a, (0, y + 26))
        sheet.paste(b, (colw[0] + 20, y + 26))
    sheet.save(out)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
