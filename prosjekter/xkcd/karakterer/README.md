# Character cards

One image per character, `name.jpg` in lower case. Expected here:

- `cueball.jpg`, `megan.jpg`, `blackhat.jpg` (made 2026-10-06 in ChatGPT).
  Blackhat also plays the sysadmin in 705; no separate card.
- `erik-nora.jpg`: the two extras on one sheet, from ChatGPT. `erik.jpg`
  and `nora.jpg` are the left and right halves of it, cut with Pillow, for
  strips with only one of them.
- `cueball-megan.jpg`: not made yet. A combined card is picked
  automatically when everyone on it is in the strip, and counts as one
  reference. That matters on Grok, which takes at most three.

What a card must show, because that is what the model holds on to: the
figure alone, full body, neutral background, three-quarter view, neutral
face. One clear colour on something fixed (Blackhat's hat, Megan's burgundy
top). Same drawing style as the strips: clean line art, flat colours,
soft cel shading. A card that smiles smiles in every strip.

The names in CANON.md, VISUAL_CANON.md and IMAGE_CANON.md must match the
file names. `make_cards.py cueball megan -P xkcd` builds a combined card
from the two singles (one image-model call).
