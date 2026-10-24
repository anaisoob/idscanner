"""Draw the application icon: an ID card under a scanner beam.

Run from the project root with `uv run python tools/make_icon.py`.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
OUT = Path(__file__).resolve().parent.parent / "src" / "idscanner"


def gradient(size, top, bottom):
    column = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        column.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom, strict=True)))
    return column.resize((size, size))


def draw():
    icon = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle((40, 40, SIZE - 40, SIZE - 40), radius=210, fill=255)
    icon.paste(gradient(SIZE, (59, 142, 208), (22, 82, 140)), mask=mask)

    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((170, 300, 870, 760), radius=56, fill=(8, 30, 60, 110))
    icon.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(24)))

    card = ImageDraw.Draw(icon)
    card.rounded_rectangle((152, 272, 872, 732), radius=56, fill=(250, 252, 255))
    card.rounded_rectangle((152, 272, 872, 352), radius=56, fill=(218, 230, 244))
    card.rectangle((152, 312, 872, 352), fill=(218, 230, 244))
    card.rounded_rectangle((212, 402, 412, 662), radius=28, fill=(201, 218, 238))
    card.ellipse((262, 432, 362, 532), fill=(110, 148, 192))
    card.pieslice((232, 542, 392, 702), 180, 360, fill=(110, 148, 192))
    card.rectangle((212, 622, 412, 662), fill=(201, 218, 238))
    for y, right in ((432, 812), (502, 752), (572, 792), (632, 702)):
        card.rounded_rectangle((462, y, right, y + 30), radius=15, fill=(186, 200, 218))

    beam = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(beam).rectangle((110, 486, 914, 518), fill=(94, 234, 212, 200))
    icon.alpha_composite(beam.filter(ImageFilter.GaussianBlur(22)))
    ImageDraw.Draw(icon).rounded_rectangle((110, 494, 914, 510), radius=8, fill=(204, 251, 241))
    return icon


def main():
    icon = draw()
    icon.resize((256, 256), Image.LANCZOS).save(OUT / "icon.png")
    icon.save(OUT / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()
