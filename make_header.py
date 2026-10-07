#!/usr/bin/env python3
"""make_header.py - regenerate assets/header.png at higher resolution.

Uses the Images API (images.edit) with the current header as the reference,
asks for a wide banner on white, then auto-crops the white margins.

    make_header.py [-p openai] [-m gpt-image-2.5-flare] [-n 2]

Candidates land in <prosjekt>/generert/header/; copy the one you like to
assets/header.png.
"""

import argparse
import base64
import configparser
import datetime as dt
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent
import sys  # noqa: E402
sys.path.insert(0, str(ROOT))
import comic  # noqa: E402

PROMPT = """Redraw this comic strip title banner at high resolution, same design:
hand-painted brush lettering "KONA & CO." in dark navy, a small black paw
print and a small hand-drawn heart after the text, a soft orange brush
stroke under the lettering, a pale orange sun, and a silhouette landscape of
Norwegian pine forest and mountains in muted blue-grey and olive along the
bottom. Light cream/white background.

The banner must be a very wide horizontal strip, about 8 times wider than it
is tall, centered vertically in the image with plain white above and below
it. No border, no panels, no characters, no other text."""


def autocrop_white(im: Image.Image, thresh: int = 245, pad: int = 6) -> Image.Image:
    g = im.convert("L")
    mask = g.point(lambda v: 255 if v < thresh else 0)
    box = mask.getbbox()
    if not box:
        return im
    l, t, r, b = box
    return im.crop((max(0, l - pad), max(0, t - pad), min(im.width, r + pad), min(im.height, b + pad)))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-P", "--project", help="prosjekt under prosjekter/ (ellers keys.ini eller cwd)")
    ap.add_argument("-p", "--provider", default="openai", help="seksjon i keys.ini med api_key")
    ap.add_argument("-m", "--model", default="gpt-image-2.5-flare")
    ap.add_argument("-n", type=int, default=2)
    ap.add_argument("--size", default="1536x1024")
    ap.add_argument("--quality", default="high")
    ap.add_argument("--no-ref", action="store_true", help="images.generate uten referanse")
    args = ap.parse_args()
    cp0 = configparser.ConfigParser(interpolation=None); cp0.read(ROOT / "keys.ini", encoding="utf-8")
    comic.PROJ = comic.resolve_project(cp0, args.project)
    OUT = comic.PROJ.generert / ("cards" if "cards" in __file__ else "header")

    from openai import OpenAI

    cp = configparser.ConfigParser(interpolation=None)
    cp.read(ROOT / "keys.ini", encoding="utf-8")
    sec = cp[args.provider]
    kw = {"api_key": sec["api_key"]}
    if sec.get("base_url"):
        kw["base_url"] = sec["base_url"]
    client = OpenAI(**kw)

    common = dict(model=args.model, prompt=PROMPT, n=args.n, size=args.size, quality=args.quality)
    if args.no_ref:
        resp = client.images.generate(**common)
    else:
        with open(comic.PROJ.root / (comic.PROJ.get("header") or "assets/header.png"), "rb") as f:
            try:
                resp = client.images.edit(image=[f], input_fidelity="high", **common)
            except Exception as e:  # model without input_fidelity
                print(f"retry uten input_fidelity: {e}")
                f.seek(0)
                resp = client.images.edit(image=[f], **common)

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    for i, d in enumerate(resp.data, 1):
        raw = Image.open(__import__("io").BytesIO(base64.b64decode(d.b64_json))).convert("RGB")
        raw_path = OUT / f"{stamp}-{i}-raw.png"
        raw.save(raw_path)
        crop = autocrop_white(raw)
        crop_path = OUT / f"{stamp}-{i}.png"
        crop.save(crop_path)
        print(f"{comic.PROJ.rel(crop_path)}  {crop.width}x{crop.height}  (raw {raw.width}x{raw.height})")


if __name__ == "__main__":
    main()
