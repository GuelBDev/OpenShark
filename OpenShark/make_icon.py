"""Convert the supplied OpenShark artwork into the Windows application icon."""

from pathlib import Path
from PIL import Image


def main():
    source = Path(__file__).parent / "assets" / "app-logo.png"
    target = Path(__file__).with_name("openshark.ico")
    with Image.open(source) as artwork:
        artwork.convert("RGBA").save(
            target, format="ICO",
            sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                   (64, 64), (128, 128), (256, 256)],
        )
    print(target)


if __name__ == "__main__":
    main()
