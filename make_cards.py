#!/usr/bin/env python3
"""make_cards.py - combine character cards into one labeled reference sheet.

    make_cards.py kona tommy            -> <prosjekt>/generert/cards/kona-tommy-<stamp>.png
    make_cards.py missy saga -n 2       -> two candidates

Uses the Responses path ([openai] in keys.ini): gpt-6-sol gets the source
cards plus one finished strip for style, and drives the image tool. Pick the
candidate you like and copy it to karakterer/<a>-<b>.jpg.
"""

import argparse
import base64
import configparser
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import comic  # noqa: E402
from comic import card_path, data_url  # noqa: E402

INSTRUCTIONS = """You produce character reference sheets for the Norwegian webcomic
"Kona & Co". You receive two existing character cards and one finished strip.
Call the image generation tool exactly once and output ONE image: a single
combined reference sheet for both characters. Do not ask questions."""

PROMPT = """Combine the two attached character cards into ONE reference sheet,
landscape, split into a left half and a right half.

Left half: {a}. Right half: {b}. A thin vertical divider between them.

Each half contains:
- The character's name as a large hand-lettered label at the top: "{A}" and "{B}".
- A full-body front view and a 3/4 or back view.
- A portrait close-up.
- Three small expression thumbnails with one-word Norwegian labels.
- A short "Kjennetegn" box listing the key visual traits in Norwegian, taken
  from the source card.

Identity is the whole point: hair, glasses, cap, clothing, colors, body
proportions, coat markings, collar and tag must match the source cards
exactly. Do not beautify, slim, age or restyle anyone.

Draw both halves in the same style: the polished, warm, modern 3D webcomic
style of the attached finished strip. Plain cream background, light paw and
heart doodles allowed, no other text, no panels, no scene."""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("-n", type=int, default=1)
    ap.add_argument("-P", "--project", help="prosjekt under prosjekter/ (ellers keys.ini eller cwd)")
    ap.add_argument("-p", "--provider", default="openai")
    ap.add_argument("--size", default="1536x1024")
    ap.add_argument("--quality", default="high")
    ap.add_argument("--style-ref", default=None, help="ferdig stripe som stilreferanse (standard: første i prosjektets examples)")
    args = ap.parse_args()
    cp0 = configparser.ConfigParser(interpolation=None); cp0.read(ROOT / "keys.ini", encoding="utf-8")
    comic.PROJ = comic.resolve_project(cp0, args.project)
    OUT = comic.PROJ.generert / ("cards" if "cards" in __file__ else "header")

    from openai import OpenAI

    cp = configparser.ConfigParser(interpolation=None)
    cp.read(ROOT / "keys.ini", encoding="utf-8")
    sec = cp[args.provider]
    client = OpenAI(api_key=sec["api_key"])
    tool = {"type": "image_generation", "size": args.size, "quality": args.quality}
    if sec.get("image_model"):
        tool["model"] = sec["image_model"]

    a, b = args.a.lower(), args.b.lower()
    content = [
        {"type": "input_text", "text": f"Character card: {a}"},
        {"type": "input_image", "image_url": data_url(card_path(a)), "detail": "high"},
        {"type": "input_text", "text": f"Character card: {b}"},
        {"type": "input_image", "image_url": data_url(card_path(b)), "detail": "high"},
        {"type": "input_text", "text": "Finished strip, style reference only"},
        {"type": "input_image", "image_url": data_url(comic.PROJ.root / (args.style_ref or comic.split_list(comic.PROJ.get("examples") or "")[0])), "detail": "low"},
        {"type": "input_text", "text": PROMPT.format(a=a.capitalize(), b=b.capitalize(), A=a.upper(), B=b.upper())},
    ]

    OUT.mkdir(parents=True, exist_ok=True)
    for i in range(1, args.n + 1):
        resp = client.responses.create(
            model=sec.get("model", "gpt-6-sol"),
            instructions=INSTRUCTIONS,
            input=[{"role": "user", "content": content}],
            tools=[tool],
        )
        imgs = [o for o in resp.output if getattr(o, "type", "") == "image_generation_call" and getattr(o, "result", None)]
        if not imgs:
            print(f"ingen bilde i svar {i}: {getattr(resp, 'output_text', '')}", file=sys.stderr)
            continue
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        p = OUT / f"{a}-{b}-{stamp}.png"
        p.write_bytes(base64.b64decode(imgs[0].result))
        (OUT / f"{a}-{b}-{stamp}.prompt.txt").write_text(getattr(imgs[0], "revised_prompt", "") or "", encoding="utf-8")
        print(comic.PROJ.rel(p))


if __name__ == "__main__":
    main()
