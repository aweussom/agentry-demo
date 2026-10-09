# xkcd, redrawn: project rules

This folder lives in two places: as `prosjekter/xkcd/` in the private tool
repo (konaogco), and as a mirrored copy in the public `agentry-demo`
repo. The tool's rules are `AGENTS.md` at the repo root. Edit the konaogco copy;
`sync_demo.py` pushes it over. This file is what applies only to this
project. Cast and writing notes in CANON.md, image rules in VISUAL_CANON.md,
IMAGE_CANON.md and IMAGE_CANON_GROK.md, sources and credits in SOURCES.md.

## Purpose

This is the demo for agentry (plan and measurements in DEMO-NOTAT.md in the
tool repo): eight classic
xkcd strips redrawn as a modern vertical webtoon with a recurring cast, and
one of them, #162 Angular Momentum, as a short vertical film. Everything is
generated through agentry on a subscription, no API key. The point of the
demo is continuity: the same faces across all strips and the film.

## Source and credit

Proper credit is the one thing that must not slip here. The strips are
Randall Munroe's, CC BY-NC 2.5. Whether that licence covers a redrawn
version used as a demo is not settled; Tommy's position (2026-10-06) is to
credit fully and visibly, and take it down if Munroe objects.

How credit travels, all four at once:

1. Inside every approved image: `approve` draws a footer with Pillow from
   `credit` in prosjekt.ini and the draft's `nr` and `tittel`: author,
   title, source URL, licence, and that it is a redrawing. Pillow, not the
   image model, so the text is exact.
2. In every draft's frontmatter (`nr:`, `kilde:`), and the film's.
3. In SOURCES.md, with links, and the originals in `sources/`.
4. In the text of every post, README section or article that shows one.

Dialogue is kept word for word, including the profanity; drawings and panel
split are ours. Nothing from this project is sold or used in advertising.

## Ask before a draft is finalised

In one message:

1. Whether the strip keeps the original panel count or is re-split for
   the vertical format. Each draft states its count explicitly.
2. For 705 Devotion to Duty: panel 4 is our addition, with Blackhat as the
   sysadmin (decided 2026-10-06). Not in the original.

## Fixed moves in this project

- English dialogue, exactly as xkcd wrote it. Do not soften "fucking" or
  "asshole"; if a provider refuses, note it in TODONT.md and try the other
  provider, do not rewrite Munroe.
- Cast names are working names from the xkcd community: `cueball`,
  `megan`, `blackhat`, plus the extras `erik` and `nora`. They live in the card file names, the
  `### Name` headings and the `karakterer:` line, nowhere in the images.
- Grok takes at most 3 references. Prefer the combined card
  `cueball-megan.jpg` when both are in the strip.
- Tommy approves, never the assistant.
