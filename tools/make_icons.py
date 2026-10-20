"""
Generates the Seamless application icons.

The artwork is the same mark the Android launcher icon uses: a deep teal
rounded square with a white lightning bolt. This script renders it at every
size the Windows shell, the taskbar and the web clients need.

Run with:
    python tools/make_icons.py

Generated files:
    assets/seamless.ico                    Windows executable icon
    assets/seamless-192.png                PWA / mobile manifest icon
    assets/seamless-512.png                PWA / mobile manifest icon
    windows-app/src/renderer/favicon.png   favicon for the Windows app window
    android-app/src/icon.png               192px icon for the mobile manifest
    android-app/src/icon-512.png           512px icon for the mobile manifest
"""
from pathlib import Path

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parent.parent

# Matches android-app/android/app/src/main/res/drawable/ic_launcher.xml
BACKGROUND = (23, 77, 88, 255)      # #174D58
BOLT = (255, 255, 255, 255)

# The bolt path from the Android vector, expressed on a 48 x 48 grid.
BOLT_POINTS_48 = [
    (27, 5), (13, 26), (22, 26), (21, 43), (36, 20), (26, 20), (27, 5)
]

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
PNG_SIZES = [192, 512]


def scaled_points(size: int):
    factor = size / 48.0
    return [(x * factor, y * factor) for x, y in BOLT_POINTS_48]


def render_icon(size: int) -> Image.Image:
    """Draws the Seamless mark at the requested square size."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Rounded square background, with a small inset so the shape does not
    # touch the edge of the icon and stays crisp at 16 pixels.
    inset = max(1, round(size * 0.02))
    radius = max(2, round(size * 0.18))
    draw.rounded_rectangle(
        [inset, inset, size - 1 - inset, size - 1 - inset],
        radius=radius,
        fill=BACKGROUND,
    )

    # The lightning bolt, inset to match the Android artwork proportions.
    points = scaled_points(size)
    margin = size * 0.14
    points = [
        (x * (size - 2 * margin) / size + margin,
         y * (size - 2 * margin) / size + margin)
        for x, y in points
    ]
    draw.polygon(points, fill=BOLT)
    return image


def main():
    outputs = []

    # Windows executable icon: a multi size .ico file.
    ico_path = REPO_ROOT / "assets" / "seamless.ico"
    ico_path.parent.mkdir(parents=True, exist_ok=True)
    icons = [render_icon(size) for size in ICO_SIZES]
    icons[-1].save(ico_path, format="ICO", sizes=[(s, s) for s in ICO_SIZES])
    outputs.append(ico_path)

    # PWA and mobile manifest icons.
    for size in PNG_SIZES:
        path = REPO_ROOT / "assets" / f"seamless-{size}.png"
        render_icon(size).save(path, format="PNG")
        outputs.append(path)

    # Favicon served with the Windows renderer, so the app window shows the
    # Seamless mark instead of the default page icon.
    favicon_path = REPO_ROOT / "windows-app" / "src" / "renderer" / "favicon.png"
    favicon_path.parent.mkdir(parents=True, exist_ok=True)
    render_icon(64).save(favicon_path, format="PNG")
    outputs.append(favicon_path)

    # Icon referenced by the mobile web manifest.
    mobile_icon_path = REPO_ROOT / "android-app" / "src" / "icon.png"
    mobile_icon_path.parent.mkdir(parents=True, exist_ok=True)
    render_icon(192).save(mobile_icon_path, format="PNG")
    outputs.append(mobile_icon_path)

    # The manifest also advertises a 512px icon for install prompts.
    mobile_icon_512_path = REPO_ROOT / "android-app" / "src" / "icon-512.png"
    render_icon(512).save(mobile_icon_512_path, format="PNG")
    outputs.append(mobile_icon_512_path)

    for path in outputs:
        print(f"Wrote {path.relative_to(REPO_ROOT)} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
