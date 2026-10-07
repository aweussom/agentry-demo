#!/usr/bin/env python3
"""video.py - film from a strip: key frames, review, clips, film.

    video.py keyframes prosjekter/kona/video/021-torrfor.md [3 7 ...] [--redo]
    video.py review    prosjekter/kona/video/021-torrfor.md
    video.py clips     prosjekter/kona/video/021-torrfor.md [3 7 ...] [--redo]
    video.py film      prosjekter/kona/video/021-torrfor.md

The script (video/<slug>.md) is written by the assistant from an approved
strip; its format is described at the top of each script and in
VIDEO-NOTAT.md. Settings shared by every film (provider, character
descriptions, dog scale, room templates, intro/outro) live under [video] in
prosjekt.ini.

Output goes to generert/<slug>/video/: keyframes/sNN-vK.*, clips/sNN-vK.mp4
(named after the key frame they animate), review.json, film/<slug>-<time>.mp4
with a .srt beside it; the newest film is also copied to <project>/filmer/
<slug>.mp4, next to the strips in striper/. Nothing is overwritten; --redo makes a new version
and the newest version of each shot is the one used.
"""
from __future__ import annotations

import argparse
import base64
import configparser
import datetime as dt
import html
import json
import math
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import comic  # noqa: E402
from comic import _port_in_use  # noqa: E402

FIELDS = {"personer", "rom", "svart-hvitt", "replikk", "tekst", "varighet", "bilde", "bevegelse"}
DOGS = {"missy", "saga"}
ROOM_EN = {"kjokken": "kitchen", "bad": "bathroom", "stue": "living room", "gang": "hallway",
           "soverom": "bedroom", "kontor": "office", "serverrom": "server room"}
HEAD = (
    "Vertical 2:3 key frame for an animated short: one single full-bleed image, no "
    "panels, no borders, no speech bubbles, no thought bubbles, no captions, no labels. "
    "Polished modern 3D cartoon webcomic style, warm light, expressive faces. "
    "The reference images are character cards: use them only for identity, and "
    "draw no text from them. Only the characters named below are in the image."
)
KEEP = (" Keep the exact art style, colours, lighting and character designs of the image. "
        "Static camera, no cuts, no zoom. No text, no speech bubbles, no new characters or "
        "objects. Nobody speaks.")
BW_CLIP = " The whole clip stays black-and-white; only the collars are in colour."
W, H, FPS = 720, 1080, 30


def die(msg: str) -> None:
    sys.exit(f"video.py: {msg}")


# --------------------------------------------------------------------------
# Script and project
# --------------------------------------------------------------------------

class Film:
    def __init__(self, manus: str):
        self.path = Path(manus).resolve()
        if not self.path.exists():
            die(f"finner ikke {manus}")
        self.cp = comic.load_config()
        comic.PROJ = self.proj = comic.resolve_project(self.cp, None, str(self.path))
        pc = configparser.ConfigParser(interpolation=None)
        pc.read(self.proj.root / "prosjekt.ini", encoding="utf-8")
        self.v = pc["video"] if "video" in pc else {}
        self.slug = self.path.stem
        self.front, self.shots = parse_manus(self.path.read_text(encoding="utf-8"))
        self.work = self.proj.generert / self.slug / "video"
        self.kf_dir, self.clip_dir, self.film_dir = (self.work / d for d in ("keyframes", "clips", "film"))
        for d in (self.kf_dir, self.clip_dir, self.film_dir):
            d.mkdir(parents=True, exist_ok=True)

    def asset(self, key: str) -> Path | None:
        s = self.v.get(key)
        p = self.proj.root / s if s else None
        return p if p and p.exists() else None

    def keyframes(self, n: int) -> list[Path]:
        """All versions of shot n, oldest first."""
        fs = [p for p in self.kf_dir.glob(f"s{n:02d}-v*.*") if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
        return sorted(fs, key=lambda p: int(re.search(r"-v(\d+)", p.stem).group(1)))

    def latest(self, n: int) -> Path | None:
        k = self.keyframes(n)
        return k[-1] if k else None

    def clip_for(self, kf: Path) -> Path:
        """The clip to use for a key frame: the newest of <stem>.mp4 and the
        --redo versions <stem>-HHMMSS.mp4. A path that does not exist yet
        when there is none."""
        found = sorted(self.clip_dir.glob(f"{kf.stem}.mp4")) + sorted(self.clip_dir.glob(f"{kf.stem}-*.mp4"))
        return max(found, key=lambda p: p.stat().st_mtime) if found else self.clip_dir / f"{kf.stem}.mp4"

    def provider(self):
        name = self.v.get("provider") or "grok-agentry"
        return comic.get_provider(self.cp, name)

    def clip_provider(self, override: str | None = None):
        """The clip maker: `clip_provider` under [video] in prosjekt.ini, else
        the key-frame provider. A keys.ini section with `type = grok_video`
        goes to xAI's API directly; anything else is agentry's /v1/videos."""
        name = override or self.v.get("clip_provider") or self.v.get("provider") or "grok-agentry"
        if name not in self.cp:
            die(f"ukjent leverandør [{name}] i keys.ini")
        sec = self.cp[name]
        if sec.get("type") == "grok_video":
            return XaiVideoClips(name, sec, self.cp)
        return AgentryClips(comic.get_provider(self.cp, name))


def parse_manus(md: str) -> tuple[dict, list[dict]]:
    front = {}
    m = re.match(r"^---\n(.*?)\n---\n", md, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                front[k.strip()] = v.strip()
    shots = []
    for num, body in re.findall(r"^Skudd (\d+): (.*?)(?=^Skudd \d+:|\Z)", md, re.S | re.M):
        shot = {"n": int(num), "desc": ""}
        cur = "desc"
        for line in body.strip().splitlines():
            f = re.match(r"^([A-Za-zæøåÆØÅ-]+):\s*(.*)$", line)
            if f and f.group(1).lower() in FIELDS:
                cur = f.group(1).lower()
                shot[cur] = f.group(2).strip()
            elif line.strip():
                shot[cur] = (shot.get(cur, "") + " " + line.strip()).strip()
        shot["personer"] = [p.strip().lower() for p in shot.get("personer", "").split(",") if p.strip()]
        shot["bw"] = shot.get("svart-hvitt", "").lower() in ("ja", "yes", "true")
        shot["seconds"] = float(shot.get("varighet") or 2)
        r = re.match(r'^(.+?):\s*"(.+)"\s*$', shot.get("replikk", ""))
        shot["speaker"], shot["line"] = (r.group(1), r.group(2)) if r else ("", "")
        shots.append(shot)
    return front, shots


def pick_shots(film: Film, nums: list[int]) -> list[dict]:
    if not nums:
        return film.shots
    by = {s["n"]: s for s in film.shots}
    bad = [n for n in nums if n not in by]
    if bad:
        die(f"ukjente skudd: {bad}; manuset har {sorted(by)}")
    return [by[n] for n in nums]


# --------------------------------------------------------------------------
# keyframes
# --------------------------------------------------------------------------

def cards_for(film: Film, people: list[str]) -> list[Path]:
    """Combined cards when everyone on them is present, else single cards.
    A combined dog card in a one-dog shot invites a second dog."""
    left, out = set(people), []
    combos = sorted((p for p in film.proj.karakterer.glob("*-*.jpg")),
                    key=lambda p: -len(p.stem.split("-")))
    for p in combos:
        combo = set(p.stem.lower().split("-"))
        if combo <= left:
            out.append(p)
            left -= combo
    for name in sorted(left):
        p = film.proj.karakterer / f"{name}.jpg"
        if p.exists():
            out.append(p)
    return out


def keyframe_request(film: Film, shot: dict) -> tuple[list[Path], str]:
    people = shot["personer"]
    refs = cards_for(film, people)[:2]
    parts = [HEAD, shot.get("bilde", shot["desc"])]
    desc = []
    for p in people:
        d = film.v.get(f"beskriv_{p}", "")
        extra = film.front.get(f"tillegg_{p}", "")
        if d or extra:
            desc.append(f"{d}; {extra}" if d and extra else d or extra)
    if desc:
        parts.append("Characters: " + " | ".join(desc) + ".")
    if DOGS & set(people) and film.v.get("skala"):
        parts.append(film.v["skala"])
    tpl = film.asset("svart_hvitt_mal") if shot["bw"] else None
    room = film.asset(f"rom_{shot.get('rom', '')}") if shot.get("rom") else None
    if tpl:
        refs.append(tpl)
        parts.append("The last reference image is the STYLE TEMPLATE for this shot: render it exactly like "
                     "that image, a grainy black-and-white film frame where the fur, the floor and the room "
                     "are all shades of gray. Only the dogs' collars keep their colour.")
    elif room:
        refs.append(room)
        parts.append(f"The last reference image is the empty {ROOM_EN.get(shot['rom'], shot['rom'])} of this film: same house, style "
                     "and light. No people or animals from it; only those named above.")
    return refs, "\n\n".join(parts)


def _image_bytes(resp) -> bytes:
    d = resp.data[0]
    if getattr(d, "b64_json", None):
        return base64.b64decode(d.b64_json)
    return urllib.request.urlopen(d.url).read()


def cmd_keyframes(args) -> None:
    film = Film(args.manus)
    todo = [s for s in pick_shots(film, args.shots) if args.redo or not film.latest(s["n"])]
    if not todo:
        print("Alle skudd har key frame. Bruk --redo og skuddnumre for nye versjoner.")
        return
    prov = film.provider()
    log = film.work / "keyframes.jsonl"

    def one(shot):
        refs, prompt = keyframe_request(film, shot)
        if args.dry_run:
            return f"s{shot['n']:02d}: {[r.name for r in refs]}\n{prompt}\n"
        t = time.time()
        files = [(r.name, r.read_bytes(), "image/png" if r.suffix == ".png" else "image/jpeg") for r in refs]
        kw = {"model": prov.opt("image_model"), "prompt": prompt, "size": "1024x1536"}
        resp = prov._client().images.edit(image=files, **kw) if files else prov._client().images.generate(**kw)
        raw = _image_bytes(resp)
        ext = ".png" if raw[:4] == b"\x89PNG" else ".jpg"
        ver = len(film.keyframes(shot["n"])) + 1
        out = film.kf_dir / f"s{shot['n']:02d}-v{ver}{ext}"
        out.write_bytes(raw)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"image": out.name, "refs": [r.name for r in refs], "prompt": prompt,
                                "provider": prov.name, "seconds": round(time.time() - t),
                                "time": dt.datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False) + "\n")
        return f"{out.name}  {time.time() - t:.0f} s"

    with ThreadPoolExecutor(1 if args.dry_run else 2) as ex:
        for line in ex.map(one, todo):
            print(line, flush=True)


# --------------------------------------------------------------------------
# clips
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Clip providers: agentry's Sora-shaped /v1/videos over Grok Build, or xAI's
# own API (POST /v1/videos/generations, poll GET /v1/videos/{id}).
# --------------------------------------------------------------------------

class AgentryClips:
    """Grok Build image_to_video through agentry. 6 s is the tool's floor;
    the size follows the reference. Two attempts, as before."""

    def __init__(self, prov):
        self.prov = prov
        self.name = prov.name

    def describe(self) -> str:
        return f"[{self.name}] agentry /v1/videos, 6 s, size follows the key frame"

    def make(self, kf: Path, prompt: str, seconds: float, out: Path) -> bool:
        import requests

        base = self.prov._base_url().rstrip("/")
        for attempt in (1, 2):
            t = time.time()
            r = requests.post(f"{base}/videos", data={"prompt": prompt, "seconds": "6"},
                              files={"input_reference": (kf.name, kf.read_bytes(), "image/jpeg")}, timeout=900)
            obj = r.json()
            if r.status_code == 200 and obj.get("status") == "completed":
                out.write_bytes(requests.get(f"{base}/videos/{obj['id']}/content", timeout=300).content)
                print(f"{out.name}  {obj.get('size')}  {time.time() - t:.0f} s", flush=True)
                return True
            print(f"{out.stem} feilet (forsøk {attempt}): {json.dumps(obj.get('error') or obj)[:200]}", flush=True)
        return False


class XaiVideoClips:
    """xAI API image-to-video. keys.ini section:

        [grok-video]
        type = grok_video
        api_key = xai-...        (or left out: taken from [grok])
        model = grok-imagine-video-1.5-lite
        resolution = 480p
        duration =               (fixed seconds; empty = shot length + 1, 4..15)

    Billed per second (2026-10-07: lite $0.02, grok-imagine-video $0.05,
    1.5 $0.08). The image goes in as a base64 data URI; aspect_ratio is
    taken from the key frame and dropped if the API rejects it."""

    def __init__(self, name: str, sec, cp):
        self.name, self.sec = name, sec
        key = (sec.get("api_key") or "").strip()
        if (not key or key.endswith("...")) and "grok" in cp:
            key = (cp["grok"].get("api_key") or "").strip()
        if not key.startswith("xai-"):
            die(f"[{name}] api_key mangler (eller under [grok])")
        self.key = key
        self.base = (sec.get("base_url") or "https://api.x.ai/v1").rstrip("/")
        self.model = sec.get("model") or sec.get("video_model") or "grok-imagine-video-1.5-lite"
        self.resolution = sec.get("resolution") or "480p"
        self.fixed = int(sec["duration"]) if (sec.get("duration") or "").strip() else None
        self.min_s = int(sec.get("min_duration") or 4)

    def describe(self) -> str:
        d = f"{self.fixed} s" if self.fixed else f"shot length + 1 ({self.min_s}..15 s)"
        return f"[{self.name}] xAI API {self.model} {self.resolution}, {d}"

    def duration_for(self, seconds: float) -> int:
        if self.fixed:
            return self.fixed
        return max(self.min_s, min(15, math.ceil(seconds + 1)))

    @staticmethod
    def aspect_of(kf: Path) -> str | None:
        from PIL import Image

        w, h = Image.open(kf).size
        r = w / h
        for name, val in (("2:3", 2 / 3), ("9:16", 9 / 16), ("3:2", 3 / 2), ("16:9", 16 / 9), ("1:1", 1.0)):
            if abs(r - val) < 0.03:
                return name
        return None

    def _post(self, body: dict) -> dict:
        import urllib.request

        req = urllib.request.Request(f"{self.base}/videos/generations", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {self.key}"}, method="POST")
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())

    def make(self, kf: Path, prompt: str, seconds: float, out: Path) -> bool:
        import base64
        import urllib.error
        import urllib.request

        mime = "image/png" if kf.suffix.lower() == ".png" else "image/jpeg"
        body = {"model": self.model, "prompt": prompt,
                "image": {"url": f"data:{mime};base64," + base64.b64encode(kf.read_bytes()).decode()},
                "duration": self.duration_for(seconds), "resolution": self.resolution}
        aspect = self.aspect_of(kf)
        if aspect:
            body["aspect_ratio"] = aspect
        t = time.time()
        try:
            start = self._post(body)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            if "aspect_ratio" in body and "aspect" in msg.lower():
                body.pop("aspect_ratio")
                start = self._post(body)
            else:
                print(f"{out.stem} feilet: HTTP {e.code} {msg[:300]}", flush=True)
                return False
        rid = start.get("request_id") or start.get("id")
        hdr = {"Authorization": f"Bearer {self.key}"}
        while True:
            with urllib.request.urlopen(urllib.request.Request(f"{self.base}/videos/{rid}", headers=hdr),
                                        timeout=60) as r:
                st = json.loads(r.read())
            if st.get("status") == "done":
                break
            if st.get("status") in ("failed", "expired"):
                print(f"{out.stem} feilet: {json.dumps(st)[:300]}", flush=True)
                return False
            time.sleep(5)
        with urllib.request.urlopen(st["video"]["url"], timeout=300) as r:
            out.write_bytes(r.read())
        body["image"] = "<data uri>"
        out.with_suffix(".json").write_text(json.dumps({"request": body, "response": st,
                                                        "seconds": round(time.time() - t)}, indent=2),
                                            encoding="utf-8")
        print(f"{out.name}  {body['duration']} s {self.resolution}  {time.time() - t:.0f} s", flush=True)
        return True


def cmd_clips(args) -> None:
    import requests

    film = Film(args.manus)
    todo = []
    for s in pick_shots(film, args.shots):
        kf = film.latest(s["n"])
        if not s.get("bevegelse") or not kf:
            continue
        if args.redo or not film.clip_for(kf).exists():
            todo.append((s, kf))
    if not todo:
        print("Ingen klipp å lage (skudd uten Bevegelse blir stillbilder; --redo lager nye).")
        return
    maker = film.clip_provider(getattr(args, "clip_provider", None))
    print(f"clips      : {maker.describe()}")
    for s, kf in todo:
        prompt = s["bevegelse"] + (BW_CLIP if s["bw"] else "") + KEEP
        if args.dry_run:
            print(f"s{s['n']:02d} {kf.name} ({s['seconds']} s i filmen): {prompt}")
            continue
        out = film.clip_dir / f"{kf.stem}.mp4"
        if out.exists():
            out = out.with_name(f"{kf.stem}-{dt.datetime.now():%H%M%S}.mp4")
        maker.make(kf, prompt, s["seconds"], out)


# --------------------------------------------------------------------------
# film
# --------------------------------------------------------------------------

VF = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1"


def ffmpeg(*a: str) -> None:
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *a], check=True)


def enc(out: Path) -> list[str]:
    return ["-an", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", str(out)]


def duration(p: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def still(img: Path, secs: float, out: Path) -> None:
    """Slow push-in on a still: 5 percent over the shot."""
    n = max(1, round(secs * FPS))
    ffmpeg("-loop", "1", "-i", str(img), "-vf",
           f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
           f"zoompan=z='1+0.05*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps={FPS},setsar=1",
           "-frames:v", str(n), *enc(out))


def text_layer(lines: list[str], font: str, out: Path) -> None:
    """Transparent W x H PNG with the lines centred in the upper part."""
    from PIL import Image, ImageDraw, ImageFont

    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    y = round(H * 0.095)
    for i, text in enumerate(lines):
        f = ImageFont.truetype(font, 38 if i == 0 else 32)
        x = (W - d.textlength(text, font=f)) / 2
        for o in (1, 2):
            d.text((x + o, y + o), text, font=f, fill=(255, 240, 220, 160))
        d.text((x, y), text, font=f, fill=(25, 30, 45, 255))
        y += f.size + 24
    lay.save(out)


def cmd_felles(args) -> None:
    """intro.mp4 from the poster, outro.mp4 from the outro image with the
    text from prosjekt.ini laid still on top. Both a slow push-in."""
    cp = comic.load_config()
    proj = comic.resolve_project(cp, args.project, None)
    pc = configparser.ConfigParser(interpolation=None)
    pc.read(proj.root / "prosjekt.ini", encoding="utf-8")
    v = pc["video"]
    src = lambda k: proj.root / v[k]
    still(src("plakat"), float(v.get("intro_sekunder", 4)), src("intro"))
    print(proj.rel(src("intro")))
    tmp = src("outro").with_name("outro-uten-tekst.mp4")
    still(src("outro_bilde"), float(v.get("outro_sekunder", 5)), tmp)
    layer = src("outro").with_name("outro-tekst.png")
    text_layer([t.strip() for t in v.get("outro_tekst", "").split("|") if t.strip()],
               v.get("tekst_font", "C:/Windows/Fonts/Inkfree.ttf"), layer)
    ffmpeg("-i", str(tmp), "-i", str(layer), "-filter_complex", "[0:v][1:v]overlay=0:0", *enc(src("outro")))
    tmp.unlink()
    print(proj.rel(src("outro")))


def srt_time(s: float) -> str:
    ms = round(s * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def cmd_film(args) -> None:
    film = Film(args.manus)
    stamp = f"{dt.datetime.now():%Y%m%d-%H%M}"
    parts_dir = film.film_dir / f"deler-{stamp}"
    parts_dir.mkdir()
    parts, srt, t0, used = [], [], 0.0, []

    def add_fixed(key):
        nonlocal t0
        p = film.asset(key)
        if not p:
            print(f"({key} mangler, hoppes over)")
            return
        out = parts_dir / f"{key}.mp4"
        ffmpeg("-i", str(p), "-vf", VF, *enc(out))
        parts.append(out)
        t0 += duration(out)

    add_fixed("intro")
    for s in film.shots:
        kf = film.latest(s["n"])
        if not kf:
            die(f"skudd {s['n']} har ingen key frame; kjør keyframes først")
        out = parts_dir / f"s{s['n']:02d}.mp4"
        clip = film.clip_for(kf)
        if clip.exists():
            ffmpeg("-ss", "0.6", "-t", str(s["seconds"]), "-i", str(clip), "-vf", VF, *enc(out))
            used.append(f"{s['n']}: {clip.name}")
        else:
            still(kf, s["seconds"], out)
            used.append(f"{s['n']}: {kf.name} (stillbilde)")
        texts = ([f"{s['speaker']}: «{s['line']}»"] if s["line"] else []) + ([s["tekst"]] if s.get("tekst") else [])
        for text in texts:
            if srt and srt[-1][2] == text and abs(srt[-1][1] - t0) < 0.01:
                srt[-1][1] = t0 + s["seconds"]  # same caption on the next shot: extend it
            else:
                srt.append([t0, t0 + s["seconds"], text])
        parts.append(out)
        t0 += s["seconds"]
    add_fixed("outro")
    lst = parts_dir / "liste.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    mp4 = film.film_dir / f"{film.slug}-{stamp}.mp4"
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(mp4))
    mp4.with_suffix(".srt").write_text("\n".join(
        f"{i}\n{srt_time(a)} --> {srt_time(b - 0.1)}\n{t}\n" for i, (a, b, t) in enumerate(srt, 1)), encoding="utf-8")
    out_dir = film.proj.root / "filmer"
    out_dir.mkdir(exist_ok=True)
    for src in (mp4, mp4.with_suffix(".srt")):
        shutil.copyfile(src, out_dir / f"{film.slug}{src.suffix}")
    print("\n".join(used))
    print(f"{film.proj.rel(out_dir / (film.slug + '.mp4'))}  {t0:.0f} s, {W}x{H}, undertekst i .srt "
          f"(versjonen ligger også i {film.proj.rel(mp4)})")


# --------------------------------------------------------------------------
# review
# --------------------------------------------------------------------------

PAGE = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ --bg:#17181c; --card:#222329; --ink:#e6e4df; --dim:#9b988f; --line:#3a3c45;
          --ok:#4caf50; --hi:#d4a24e; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:16px 20px 60px; background:var(--bg); color:var(--ink);
         font:14px/1.45 system-ui, sans-serif; }}
  h1 {{ font-size:18px; margin:0 0 4px; }}  .sub {{ color:var(--dim); margin:0 0 12px; }}
  .bar {{ position:sticky; top:0; z-index:5; background:var(--bg); padding:8px 0 10px;
          border-bottom:1px solid var(--line); display:flex; gap:14px; align-items:center; flex-wrap:wrap; }}
  .bar .st {{ color:var(--dim); min-width:170px; }}  .bar .st.err {{ color:#e57373; }}
  button {{ border:0; border-radius:5px; padding:6px 14px; font:inherit; font-weight:700; cursor:pointer; }}
  button.ok {{ background:var(--ok); color:#000; }}
  button.play {{ background:var(--hi); color:#000; }}
  button.ghost {{ background:transparent; color:var(--dim); border:1px solid var(--line); }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax({w}px, 1fr)); gap:16px; margin-top:16px; }}
  .shot {{ background:var(--card); border:2px solid var(--line); border-radius:8px; overflow:hidden;
           display:flex; flex-direction:column; }}
  .shot.okd {{ border-color:var(--ok); }}  .shot.has {{ border-color:var(--hi); }}
  .shot img {{ display:block; width:100%; aspect-ratio:2/3; object-fit:cover; cursor:zoom-in; }}
  .shot header {{ display:flex; justify-content:space-between; align-items:center; padding:6px 10px; }}
  .shot header b {{ font-size:15px; }}  .shot header span {{ color:var(--dim); font-size:12px; }}
  .shot header label {{ font-size:12px; color:var(--dim); cursor:pointer; user-select:none; }}
  .desc {{ padding:0 10px 6px; font-size:12px; color:var(--dim); }}
  .say {{ padding:0 10px 6px; font-size:13px; }}  .say i {{ color:var(--hi); font-style:normal; }}
  textarea {{ width:calc(100% - 20px); margin:0 10px 10px; min-height:40px; background:#1b1c21; color:var(--ink);
              border:1px solid var(--line); border-radius:4px; padding:5px 7px; font:inherit; }}
  textarea.gen {{ width:36%; margin:0; min-height:44px; }}
  #player {{ position:fixed; inset:0; background:#000; z-index:20; display:none;
             flex-direction:column; align-items:center; justify-content:center; }}
  #player img {{ max-height:calc(100vh - 70px); max-width:100vw; aspect-ratio:2/3; object-fit:contain; }}
  #player .cap {{ position:absolute; bottom:80px; left:0; right:0; text-align:center; }}
  #player .cap span {{ background:rgba(0,0,0,.7); color:#fff; font-size:22px; padding:4px 12px; border-radius:4px; }}
  #player .info {{ color:var(--dim); height:40px; line-height:40px; font-size:13px; }}
  #player .x {{ position:absolute; top:10px; right:14px; }}
  #zoom {{ position:fixed; inset:0; background:rgba(0,0,0,.92); z-index:15; display:none;
           align-items:center; justify-content:center; cursor:zoom-out; }}
  #zoom img {{ max-height:100vh; max-width:100vw; }}
</style>
<h1>{title}</h1>
<p class="sub">Ett kort per skudd i rekkefølge. Kryss av OK, eller skriv hva som er galt.
"Spill av" viser skuddene med varighetene fra manuset og replikkene som undertekst.
Alt lagres automatisk til <code>{out}</code>.</p>
<div class="bar">
  <button id="play" class="play">Spill av ({total} s)</button>
  <span class="st" id="st">lagret</span>
  <button id="done" class="ok">Ferdig, send til assistenten</button>
  <button id="export" class="ghost">Eksporter JSON</button>
  <label style="margin-left:auto;color:var(--dim)">Generell kommentar:</label>
  <textarea class="gen" id="gen" placeholder="f.eks. kjøkkenet må være likt i alle skudd"></textarea>
</div>
<p class="sub" id="next" style="display:none;margin-top:10px;color:var(--ok)"></p>
<div class="grid">{cards}</div>
<div id="player"><button class="ghost x" id="px">Lukk (Esc)</button><img id="pimg">
  <div class="cap"><span id="pcap"></span></div><div class="info" id="pinfo"></div></div>
<div id="zoom"><img id="zimg"></div>
<script>
const shots = {shots};
const state = {state};
state.shots = state.shots || {{}};
const stEl = document.getElementById("st");
let timer = null;
async function flush() {{
  try {{
    const r = await fetch("/save", {{method:"POST", headers:{{"Content-Type":"application/json"}}, body:JSON.stringify(state)}});
    if (!r.ok) throw new Error(r.status);
    stEl.textContent = "lagret " + new Date().toLocaleTimeString(); stEl.className = "st";
  }} catch (e) {{
    try {{ localStorage.setItem("review_{slug}", JSON.stringify(state)); }} catch (_) {{}}
    stEl.textContent = "server borte, lagret lokalt i nettleseren"; stEl.className = "st err";
  }}
}}
function save() {{ clearTimeout(timer); timer = setTimeout(flush, 300); render(); }}
function render() {{
  document.querySelectorAll(".shot").forEach(el => {{
    const s = state.shots[el.dataset.n] || {{}};
    el.classList.toggle("okd", !!s.ok); el.classList.toggle("has", !s.ok && !!(s.comment || "").trim());
  }});
}}
document.querySelectorAll(".shot").forEach(el => {{
  const n = el.dataset.n, s = state.shots[n] || {{}};
  const cb = el.querySelector("input"), ta = el.querySelector("textarea");
  cb.checked = !!s.ok; ta.value = s.comment || "";
  const put = () => {{
    const v = {{ok: cb.checked, comment: ta.value.trim()}};
    if (!v.ok && !v.comment) delete state.shots[n]; else state.shots[n] = v;
    save();
  }};
  cb.onchange = put; ta.oninput = put;
  el.querySelector("img").onclick = () => {{
    document.getElementById("zimg").src = el.querySelector("img").src;
    document.getElementById("zoom").style.display = "flex";
  }};
}});
document.getElementById("zoom").onclick = e => e.currentTarget.style.display = "none";
const gen = document.getElementById("gen");
gen.value = state.note || "";
gen.oninput = () => {{ state.note = gen.value; save(); }};
document.getElementById("export").onclick = () => {{
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(state, null, 2)], {{type:"application/json"}}));
  a.download = "review_{slug}.json"; a.click();
}};
document.getElementById("done").onclick = async () => {{
  state.done = new Date().toISOString(); clearTimeout(timer); await flush();
  const v = Object.values(state.shots);
  const ok = v.filter(s => s.ok).length, com = v.filter(s => !s.ok && s.comment).length;
  const nx = document.getElementById("next"); nx.style.display = "block";
  nx.textContent = (stEl.className.includes("err")
    ? "Serveren svarer ikke. Trykk Eksporter JSON og gi fila til assistenten. "
    : "Lagret. Si til assistenten: \\"les review.json for {slug}\\". ") +
    ok + " av " + shots.length + " OK, " + com + " med kommentar.";
}};
// play-through
const player = document.getElementById("player"), pimg = document.getElementById("pimg");
let ptimer = null;
shots.forEach(s => {{ const i = new Image(); i.src = s.image; }});
function stop() {{ clearTimeout(ptimer); player.style.display = "none"; }}
function show(i) {{
  if (i >= shots.length) return stop();
  const s = shots[i];
  pimg.src = s.image;
  document.getElementById("pcap").textContent = s.line ? s.speaker + ": " + s.line : "";
  document.getElementById("pcap").style.display = s.line ? "inline" : "none";
  document.getElementById("pinfo").textContent = "Skudd " + s.n + " · " + s.seconds + " s";
  ptimer = setTimeout(() => show(i + 1), s.seconds * 1000);
}}
document.getElementById("play").onclick = () => {{ player.style.display = "flex"; show(0); }};
document.getElementById("px").onclick = stop;
document.addEventListener("keydown", e => {{ if (e.key === "Escape") {{ stop(); document.getElementById("zoom").style.display = "none"; }} }});
render();
</script>
"""

CARD = """<div class="shot" data-n="{n}">
<header><b>{n}</b><span>{seconds} s</span><label><input type="checkbox"> OK</label></header>
<img src="{image}" loading="lazy">
<div class="say">{say}</div>
<div class="desc">{desc}</div>
<textarea placeholder="Hva er galt i skudd {n}?"></textarea>
</div>"""


def cmd_review(args) -> None:
    import http.server
    import socketserver
    import threading
    import webbrowser

    film = Film(args.manus)
    out = film.work / "review.json"
    state = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    state.setdefault("manus", film.proj.rel(film.path))
    shots, cards = [], []
    for s in film.shots:
        kf = film.latest(s["n"])
        if not kf:
            continue
        img = f"keyframes/{kf.name}"
        sh = {"n": s["n"], "image": img, "seconds": s["seconds"], "speaker": s["speaker"], "line": s["line"]}
        shots.append(sh)
        say = f'<i>{html.escape(s["speaker"])}:</i> "{html.escape(s["line"])}"' if s["line"] else ""
        clip = film.clip_for(kf)
        if clip.exists():
            say += f' <a href="clips/{clip.name}" target="_blank" style="color:var(--hi)">klipp</a>'
        cards.append(CARD.format(n=s["n"], seconds=f"{s['seconds']:g}", image=img, say=say,
                                 desc=html.escape(f"{kf.name}. {s['desc']}")))
    if not shots:
        die("ingen key frames ennå; kjør keyframes først")
    page = PAGE.format(title=f"{film.slug}: key frames", slug=film.slug, w=args.width, out=film.proj.rel(out),
                       total=f"{sum(s['seconds'] for s in shots):g}", cards="".join(cards),
                       shots=json.dumps(shots, ensure_ascii=False), state=json.dumps(state, ensure_ascii=False))
    (film.work / "review.html").write_text(page, encoding="utf-8")

    port = args.port
    while _port_in_use(port):
        port += 1
    folder = str(film.work)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=folder, **k)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.path = "/review.html"
            return super().do_GET()

        def do_POST(self):
            if self.path != "/save":
                self.send_error(404); return
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8"))
            data["saved"] = dt.datetime.now().isoformat(timespec="seconds")
            out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.send_response(204); self.end_headers()

        def log_message(self, fmt, *a):
            pass

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"{url}  ({len(shots)} skudd; lagres i {film.proj.rel(out)}; Ctrl-C avslutter)", flush=True)
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, hlp in (("keyframes", "lag key frames (bare manglende, eller nye versjoner med --redo)"),
                      ("clips", "lag klipp for skudd med Bevegelse (manglende, eller nye med --redo)")):
        p = sub.add_parser(name, help=hlp)
        p.add_argument("manus")
        p.add_argument("shots", nargs="*", type=int, help="skuddnumre (standard: alle)")
        p.add_argument("--redo", action="store_true", help="ny versjon selv om det finnes en")
        p.add_argument("--dry-run", action="store_true", help="vis referanser og prompt, ikke kall")
        if name == "clips":
            p.add_argument("-p", "--clip-provider", help="keys.ini-seksjon for klipp (standard: clip_provider "
                           "under [video] i prosjekt.ini, ellers provider). type = grok_video går rett på xAI")
    p = sub.add_parser("review", help="nettleserside: gå gjennom key frames, lagres i review.json")
    p.add_argument("manus")
    p.add_argument("--port", type=int, default=8781)
    p.add_argument("--width", type=int, default=260, help="minste kortbredde i px")
    p.add_argument("--no-browser", action="store_true")
    p = sub.add_parser("film", help="sett sammen intro, skudd (klipp eller stillbilde med zoom) og outro")
    p.add_argument("manus")
    p = sub.add_parser("felles", help="bygg intro.mp4 og outro.mp4 fra plakat, outro-bilde og outro_tekst")
    p.add_argument("-P", "--project", help="prosjektnavn eller sti (standard: fra keys.ini/cwd)")
    args = ap.parse_args()
    {"keyframes": cmd_keyframes, "clips": cmd_clips, "review": cmd_review, "film": cmd_film,
     "felles": cmd_felles}[args.cmd](args)


if __name__ == "__main__":
    main()
