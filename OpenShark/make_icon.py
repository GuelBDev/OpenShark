"""Generate the application icon from the dashboard's visual identity."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def main():
    image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((12, 12, 244, 244), radius=62, fill="#D5F279")
    try:
        font = ImageFont.truetype("bahnschrift.ttf", 178)
    except OSError:
        font = ImageFont.truetype("arialbd.ttf", 178)
    bounds = draw.textbbox((0, 0), "S", font=font)
    draw.text(((256 - (bounds[2] - bounds[0])) / 2 - bounds[0],
               (256 - (bounds[3] - bounds[1])) / 2 - bounds[1] - 6),
              "S", fill="#101411", font=font)
    target = Path(__file__).with_name("openshark.ico")
    image.save(target, sizes=[(16, 16), (32, 32), (48, 48), (64, 64),
                              (128, 128), (256, 256)])
    print(target)


if __name__ == "__main__":
    main()
