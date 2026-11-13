"""Draws the Framewring icon (packaging/framewring.ico). Needs Pillow (build only).

Idea: a film frame squeezed from both sides by arrows - "squeezing the frames".
"""
from pathlib import Path

from PIL import Image, ImageDraw

S = 1024  # draw large, then downscale - this gives smooth edges
BG, CARD, ACC, ACC2, FG = "#0f1115", "#171a21", "#7c5cff", "#2bd9a8", "#e8eaf0"


def draw():
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((40, 40, S - 40, S - 40), radius=210, fill=BG, outline=ACC, width=28)
    # film frame, flattened vertically
    x0, x1, y0, y1 = 250, S - 250, 380, S - 380
    d.rounded_rectangle((x0, y0, x1, y1), radius=40, fill=ACC)
    for i in range(5):  # perforation
        cx = x0 + 70 + i * (x1 - x0 - 140) / 4
        for cy in (y0 + 42, y1 - 42):
            d.rounded_rectangle((cx - 26, cy - 18, cx + 26, cy + 18), radius=8, fill=BG)
    d.rectangle((x0 + 40, y0 + 84, x1 - 40, y1 - 84), fill=ACC2)
    # arrows above and below - pressing on the frame
    for top in (True, False):
        tip = y0 - 40 if top else y1 + 40
        base = tip - 170 if top else tip + 170
        d.polygon([(S / 2 - 150, base), (S / 2 + 150, base), (S / 2, tip)], fill=FG)
    return im


def main():
    here = Path(__file__).resolve().parent
    big = draw()
    sizes = [16, 24, 32, 48, 64, 128, 256]
    big.resize((256, 256), Image.LANCZOS).save(here / "framewring.ico", sizes=[(n, n) for n in sizes])
    big.resize((512, 512), Image.LANCZOS).save(here / "framewring.png")
    print("ok", here / "framewring.ico")


if __name__ == "__main__":
    main()
