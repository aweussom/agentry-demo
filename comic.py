#!/usr/bin/env python3
"""comic.py - generate Kona & Co strips from markdown drafts.

    comic.py new  utkast/001-radyr.md [-p PROVIDER] [-n N] [--no-examples]
    comic.py fix  utkast/001-radyr.md "Missy er for fluffy." [-p PROVIDER]
    comic.py approve utkast/001-radyr.md [IMAGE]
    comic.py providers

Config lives in keys.ini (see keys.ini.template). Output goes to
generert/<draft-stem>/ with a state.json log; approved strips are copied to
striper/ by hand or with `approve`.
"""

from __future__ import annotations

import argparse
import base64
import configparser
import datetime as dt
import json
import mimetypes
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # the tool
INI = ROOT / "keys.ini"                           # secrets + providers, per machine
PROJECTS = ROOT / "prosjekter"                    # one folder per comic


class Project:
    """A comic: its canon, cards, examples, drafts and output. Everything
    content-related lives under one folder with a prosjekt.ini; keys.ini
    holds only secrets and provider endpoints, so one keys.ini serves every
    project on the machine."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.name = self.root.name
        cp = configparser.ConfigParser(interpolation=None)
        cp.read(self.root / "prosjekt.ini", encoding="utf-8")
        self.sec = cp["prosjekt"] if "prosjekt" in cp else cp["DEFAULT"]

    def get(self, key: str, default: str | None = None) -> str | None:
        v = self.sec.get(key, default)
        return v if v not in (None, "") else default

    @property
    def karakterer(self) -> Path:
        return self.root / "karakterer"

    @property
    def generert(self) -> Path:
        return self.root / "generert"

    @property
    def striper(self) -> Path:
        return self.root / "striper"

    @property
    def utkast(self) -> Path:
        return self.root / "utkast"

    def canon_for(self, provider_type: str, provider_name: str | None = None) -> list[str]:
        """Canon files for a provider: `canon_<provider name>` in prosjekt.ini
        when set (a provider that needs its own style wording, Grok for one),
        else canon_responses / canon_direct by provider type."""
        if provider_name and self.get(f"canon_{provider_name}"):
            return split_list(self.get(f"canon_{provider_name}"))
        key = "canon_responses" if provider_type == "openai_responses" else "canon_direct"
        return split_list(self.get(key) or self.get("canon") or "")

    def rel(self, p: Path) -> str:
        """Path relative to the project, forward slashes, for state.json and
        printing. Falls back to the absolute path outside the project."""
        p = Path(p)
        try:
            return p.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return p.as_posix()

    def abs(self, s: str) -> Path:
        """Inverse of rel(); tolerates old backslash paths."""
        q = Path(s.replace("\\", "/"))
        return q if q.is_absolute() else self.root / q


PROJ: Project  # set in main() before any command runs


def find_project_from(path: Path) -> Project | None:
    """Nearest ancestor (or self) holding a prosjekt.ini."""
    path = path.resolve()
    for d in [path] + list(path.parents):
        if (d / "prosjekt.ini").exists():
            return Project(d)
    return None


def resolve_project(cp: configparser.ConfigParser, name: str | None, draft: str | None = None) -> Project:
    """Order: the draft's folder tree, then -P/--project (a name under
    prosjekter/ or a path), then project= under [comic], then the cwd."""
    if draft:
        d = Path(draft)
        pr = find_project_from(d.parent if d.exists() else d)
        if pr:
            return pr
    cand = name or (cp["comic"].get("project") if "comic" in cp else None)
    if cand:
        d = Path(cand)
        if not d.is_dir():
            d = PROJECTS / cand
        if (d / "prosjekt.ini").exists():
            return Project(d)
        die(f"Fant ikke prosjekt '{cand}' (ingen prosjekt.ini i {d})")
    pr = find_project_from(Path.cwd())
    if pr:
        return pr
    have = sorted(q.name for q in PROJECTS.iterdir() if (q / "prosjekt.ini").exists()) if PROJECTS.exists() else []
    die("Ingen prosjekt valgt. Bruk -P <navn>, sett project= under [comic] i keys.ini, "
        f"eller kjør fra prosjektmappa. Finnes: {', '.join(have) or '-'}")
    raise AssertionError

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def die(msg: str, code: int = 1) -> None:
    print(f"comic.py: {msg}", file=sys.stderr)
    sys.exit(code)


def split_list(s: str) -> list[str]:
    return [x.strip() for x in re.split(r"[,\n]", s or "") if x.strip()]


# --------------------------------------------------------------------------
# Config, drafts, assets
# --------------------------------------------------------------------------

def load_config(path: Path = INI) -> configparser.ConfigParser:
    if not path.exists():
        die(f"{path.name} mangler. Kopier keys.ini.template til keys.ini og fyll inn.")
    cp = configparser.ConfigParser(interpolation=None)
    cp.read(path, encoding="utf-8")
    if "comic" not in cp:
        die(f"{path.name} mangler [comic]-seksjon")
    return cp


@dataclass
class Draft:
    path: Path
    meta: dict[str, str]
    characters: list[str]
    body: str

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def workdir(self) -> Path:
        return PROJ.generert / self.stem


def parse_draft(path: Path) -> Draft:
    if not path.exists() and (PROJ.root / path).exists():
        path = PROJ.root / path
    path = path.resolve()
    if not path.exists():
        die(f"Fant ikke utkast {path}")
    text = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
        body = m.group(2)
    chars = split_list(meta.get("karakterer") or meta.get("characters") or "")
    if not chars:
        die(f"{path.name}: frontmatter mangler 'karakterer: tommy, kona, ...'")
    return Draft(path, meta, [c.lower() for c in chars], body.strip())


def card_path(name: str) -> Path:
    for ext in IMAGE_EXTS:
        p = PROJ.karakterer / f"{name}{ext}"
        if p.exists():
            return p
    die(f"Fant ikke character card for '{name}' i {PROJ.karakterer}")
    raise AssertionError


def select_cards(characters: list[str]) -> list[tuple[str, Path]]:
    """Pick the fewest card files covering the characters. A combined card is
    a file named like karakterer/kona-tommy.jpg and is used when every
    character on it is in the strip. Returns (label, path) pairs."""
    needed = [c.lower() for c in characters]
    combined = []
    for p in PROJ.karakterer.iterdir():
        if p.suffix.lower() in IMAGE_EXTS and "-" in p.stem:
            names = p.stem.lower().split("-")
            if all(n in needed for n in names):
                combined.append((names, p))
    combined.sort(key=lambda t: -len(t[0]))
    out: list[tuple[str, Path]] = []
    left = list(needed)
    for names, p in combined:
        if all(n in left for n in names):
            out.append((", ".join(names), p))
            left = [n for n in left if n not in names]
    for n in needed:
        if n in left:
            out.append((n, card_path(n)))
    return out


def data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def prepared_example(p: Path) -> Path:
    """Example strip with its title header cropped off, cached under
    generert/_eksempler/. The model then has no header to imitate; compose()
    adds the real one afterwards."""
    from PIL import Image

    cache = PROJ.generert / "_eksempler" / (p.stem + ".jpg")
    if cache.exists() and cache.stat().st_mtime >= p.stat().st_mtime:
        return cache
    im = Image.open(p).convert("RGB")
    n = detect_header_rows(im)
    if n:
        im = im.crop((0, n, im.width, im.height))
    cache.parent.mkdir(parents=True, exist_ok=True)
    im.save(cache, quality=90)
    return cache


def known_characters() -> set[str]:
    if not PROJ.karakterer.exists():
        return set()
    return {p.stem.lower() for p in PROJ.karakterer.iterdir() if p.suffix.lower() in IMAGE_EXTS}


def filter_characters(text: str, characters: list[str]) -> str:
    """Drop '### Name' sections for established characters who are not in
    this strip. A section ends at the next heading of any level."""
    known = known_characters()
    out: list[str] = []
    skip = False
    for line in text.splitlines():
        m = re.match(r"^#{1,6}\s+(.*?)\s*$", line)
        if m:
            name = m.group(1).lower()
            skip = name in known and name not in characters
        if not skip:
            out.append(line)
    return "\n".join(out).strip()


def read_canon(files: list[str], characters: list[str]) -> str:
    parts = []
    for f in files:
        p = PROJ.root / f
        if not p.exists():
            die(f"Canon-fil mangler: {p}")
        parts.append(filter_characters(p.read_text(encoding="utf-8"), characters))
    return "\n\n---\n\n".join(parts)


# --------------------------------------------------------------------------
# State per draft
# --------------------------------------------------------------------------

def load_state(draft: Draft) -> dict:
    p = draft.workdir / "state.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"draft": PROJ.rel(draft.path), "runs": []}


def save_state(draft: Draft, state: dict) -> None:
    draft.workdir.mkdir(parents=True, exist_ok=True)
    (draft.workdir / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def last_run(state: dict) -> dict | None:
    return state["runs"][-1] if state["runs"] else None


def save_images(draft: Draft, kind: str, images: list[tuple[bytes, str]]) -> list[str]:
    """images: list of (bytes, ext). Returns paths relative to the project."""
    draft.workdir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = []
    for i, (data, ext) in enumerate(images, 1):
        p = draft.workdir / f"{stamp}-{kind}-{i}.{ext}"
        p.write_bytes(data)
        out.append(PROJ.rel(p))
    return out


# --------------------------------------------------------------------------
# Jobs and providers
# --------------------------------------------------------------------------

@dataclass
class Job:
    draft: Draft
    canon: str
    cards: list[tuple[str, Path]]
    examples: list[Path]
    n: int = 1
    correction: str | None = None
    previous: dict | None = None  # last run from state, for fix
    canon_files: list[str] = field(default_factory=list)
    mask: tuple[int, int, int, int] | None = None  # x,y,w,h in image pixels; only this area is repainted
    panel: int | None = None  # 1-based: edit only this panel, paste it back in place


@dataclass
class Result:
    images: list[tuple[bytes, str]]
    response_id: str | None = None
    text: str = ""
    revised_prompts: list[str] = field(default_factory=list)
    prompt: str = ""


class Provider:
    type_name = ""

    def __init__(self, name: str, section: configparser.SectionProxy):
        self.name = name
        self.sec = section

    def opt(self, key: str, default: str | None = None) -> str | None:
        v = self.sec.get(key, default)
        return v if v not in (None, "") else default

    def describe(self) -> str:
        raise NotImplementedError

    def generate(self, job: Job) -> Result:
        raise NotImplementedError

    def fix(self, job: Job) -> Result:
        raise NotImplementedError

    def truthy(self, key: str, default: str = "false") -> bool:
        return (self.opt(key, default) or "").lower() in ("1", "true", "yes", "on")

    def _base_url(self) -> str | None:
        url = self.opt("base_url")
        if url and self.truthy("autostart"):
            url = ensure_agentry(self, url)
        return url

    def _client(self):
        from openai import OpenAI

        key = self.opt("api_key")
        base_url = self._base_url()
        if not key or key.endswith("..."):
            if base_url:
                key = "not-needed"  # local proxy such as agentry
            else:
                die(f"[{self.name}] api_key er ikke satt i keys.ini")
        kw: dict = {"api_key": key}
        if base_url:
            kw["base_url"] = base_url
        if self.opt("timeout"):
            kw["timeout"] = float(self.opt("timeout"))
        return OpenAI(**kw)


# --------------------------------------------------------------------------
# Local agentry: start our own instance on a free port, leave production alone
# --------------------------------------------------------------------------

def _port_answers(port: int, path: str = "/v1/models", timeout: float = 2.0) -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://localhost:{port}{path}", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _port_in_use(port: int) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def ensure_agentry(provider: Provider, url: str) -> str:
    """Return a base_url for a running agentry. If nothing answers on the
    configured port, start one from agentry_dir on that port (or the next
    free one) and wait until /v1/models answers. The process is detached and
    keeps running for later calls; its log is generert/agentry-<port>.log."""
    import shlex
    import subprocess
    import time

    m = re.match(r"^(https?://[^/:]+):(\d+)(/.*)?$", url)
    if not m:
        return url
    host, port, path = m.group(1), int(m.group(2)), m.group(3) or "/v1"

    if _port_answers(port):
        return url  # already running (ours or the user's)

    # Something else may hold the port; find a free one.
    while _port_in_use(port):
        port += 1

    agentry_dir = Path(provider.opt("agentry_dir") or "")
    if agentry_dir and not agentry_dir.is_absolute():
        agentry_dir = (ROOT / agentry_dir).resolve()  # "../agentry" next to the tool
    if sys.platform == "win32":
        start = agentry_dir / "start.ps1"
        pwsh = shutil.which("pwsh") or shutil.which("powershell")
        if not pwsh:
            die("autostart: fant verken pwsh eller powershell")
        launcher = [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(start), "-Port", str(port)]
    else:
        start = agentry_dir / "start.sh"
        launcher = ["bash", str(start), "--port", str(port)]
    if not start.exists():
        die(f"[{provider.name}] autostart: fant ikke {start}. Sett agentry_dir i keys.ini "
            "eller autostart = false og start agentry selv.")

    PROJ.generert.mkdir(parents=True, exist_ok=True)
    log = PROJ.generert / f"agentry-{port}.log"
    cmd = launcher + shlex.split(provider.opt("agentry_args") or "")
    print(f"[{provider.name}] starter agentry på port {port}: {' '.join(cmd[1:])}  (logg: {PROJ.rel(log)})",
          file=sys.stderr)
    flags = 0
    if sys.platform == "win32":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    with open(log, "ab") as lf:
        subprocess.Popen(cmd, cwd=str(agentry_dir), stdout=lf, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, creationflags=flags)

    deadline = time.time() + float(provider.opt("autostart_timeout") or 120)
    while time.time() < deadline:
        if _port_answers(port):
            print(f"[{provider.name}] agentry svarer på port {port}", file=sys.stderr)
            return f"{host}:{port}{path}"
        time.sleep(1.0)
    die(f"[{provider.name}] agentry svarte ikke på port {port} innen fristen. Se {log}")
    raise AssertionError


class OpenAIResponses(Provider):
    """Responses API with the hosted image_generation tool. An LLM reads the
    canon, cards and draft, then calls the image tool. previous_response_id
    gives multi-turn corrections."""

    type_name = "openai_responses"
    TOOL_KEYS = ("size", "quality", "input_fidelity", "background", "output_format", "moderation")

    def describe(self) -> str:
        return (f"{self.type_name} model={self.opt('model', 'gpt-5')} "
                f"image_model={self.opt('image_model', 'default')} ") + " ".join(
            f"{k}={self.opt(k)}" for k in self.TOOL_KEYS if self.opt(k)
        )

    def _tool(self) -> dict:
        tool: dict = {"type": "image_generation"}
        if self.opt("image_model"):
            tool["model"] = self.opt("image_model")
        for k in self.TOOL_KEYS:
            if self.opt(k):
                tool[k] = self.opt(k)
        return tool

    @staticmethod
    def _image_item(label: str, path: Path) -> list[dict]:
        return [
            {"type": "input_text", "text": label},
            {"type": "input_image", "image_url": data_url(path), "detail": "high"},
        ]

    def _content(self, job: Job, text: str, with_examples: bool) -> list[dict]:
        content: list[dict] = []
        for name, path in job.cards:
            content += self._image_item(f"Character card: {name} (identity reference only)", path)
        if with_examples:
            for p in job.examples:
                content += self._image_item("Finished strip, style reference only", p)
        content.append({"type": "input_text", "text": text})
        return content

    def _call(self, job: Job, content: list[dict], previous_id: str | None) -> Result:
        client = self._client()
        kwargs: dict = {
            "model": self.opt("model", "gpt-5"),
            "input": [{"role": "user", "content": content}],
            "tools": [self._tool()],
        }
        if previous_id:
            kwargs["previous_response_id"] = previous_id
        else:
            kwargs["instructions"] = job.canon
        resp = client.responses.create(**kwargs)

        images: list[tuple[bytes, str]] = []
        revised: list[str] = []
        for o in resp.output:
            if getattr(o, "type", "") == "image_generation_call" and getattr(o, "result", None):
                ext = getattr(o, "output_format", None) or self.opt("output_format") or "png"
                images.append((base64.b64decode(o.result), ext))
                if getattr(o, "revised_prompt", None):
                    revised.append(o.revised_prompt)
        text = getattr(resp, "output_text", "") or ""
        return Result(images=images, response_id=resp.id, text=text, revised_prompts=revised)

    def generate(self, job: Job) -> Result:
        text = f"Draft for a new strip ({job.draft.stem}):\n\n{job.draft.body}"
        res = self._call(job, self._content(job, text, with_examples=True), None)
        res.prompt = text
        return res

    def fix(self, job: Job) -> Result:
        prev = job.previous or {}
        if prev.get("provider") != self.name or not prev.get("response_id"):
            die(
                f"Siste kjøring for {job.draft.stem} er ikke fra [{self.name}] "
                "med en response_id. Kjør 'new' med denne leverandøren først."
            )
        text = (
            "Correction to the strip you just generated. Apply exactly this and "
            f"change nothing else:\n\n{job.correction}"
        )
        res = self._call(job, self._content(job, text, with_examples=False), prev["response_id"])
        res.prompt = text
        return res


class OpenAIImages(Provider):
    """OpenAI-compatible Images API. No LLM in between; the canon text and
    draft go straight to the image model. edit=true uses images.edit with
    reference images, edit=false uses images.generate (text only)."""

    type_name = "openai_images"
    EXTRA_KEYS = ("size", "quality", "input_fidelity", "background", "output_format")

    def describe(self) -> str:
        return (
            f"{self.type_name} image_model={self.opt('image_model')} "
            f"edit={self.edit} base_url={self.opt('base_url', 'openai')} "
            + " ".join(f"{k}={self.opt(k)}" for k in self.EXTRA_KEYS + ("max_refs",) if self.opt(k))
        )

    @property
    def edit(self) -> bool:
        return (self.opt("edit", "true") or "").lower() in ("1", "true", "yes", "on")

    def _extra(self) -> dict:
        return {k: self.opt(k) for k in self.EXTRA_KEYS if self.opt(k)}

    def _cap_refs(self, must: list[Path], optional: list[Path]) -> list[Path]:
        """Trim optional refs (examples) to fit max_refs; die if the required
        ones alone do not fit."""
        cap = self.opt("max_refs")
        if not cap:
            return must + optional
        cap_n = int(cap)
        if len(must) > cap_n:
            die(f"[{self.name}] tar maks {cap_n} referansebilder, men {len(must)} er påkrevd "
                "(character cards / forrige bilde). Reduser antall karakterer eller bruk --no-cards.")
        room = cap_n - len(must)
        if len(optional) > room:
            print(f"[{self.name}] max_refs={cap_n}: dropper {len(optional) - room} eksempelstripe(r)",
                  file=sys.stderr)
        return must + optional[:room]

    def _prompt_new(self, job: Job) -> str:
        refs = ""
        if self.edit:
            names = ", ".join(n for n, _ in job.cards)
            refs = (
                f"\n\nReference images, in order: character cards for {names}"
                + (", then finished strips as style references." if job.examples else ".")
            )
        return f"{job.canon}{refs}\n\n---\n\nDraft:\n\n{job.draft.body}"

    def _prompt_fix(self, job: Job) -> str:
        # The model has the picture; canon is noise here. Name the change only.
        names = ", ".join(n for n, _ in job.cards)
        cards = f" The other images are character cards for {names}, identity references only." if job.cards else ""
        return (
            "The first image is the current version of a four-panel comic strip." + cards +
            " Apply exactly this change and keep everything else identical: layout, poses, "
            "faces, lettering, backgrounds.\n\n" + (job.correction or "")
        )

    def _run(self, prompt: str, refs: list[Path], n: int, size: str | None = None) -> Result:
        client = self._client()
        model = self.opt("image_model")
        if not model:
            die(f"[{self.name}] image_model mangler")
        kwargs: dict = {"model": model, "prompt": prompt, "n": n, **self._extra()}
        if size:
            kwargs["size"] = size
        if refs:
            files = [open(p, "rb") for p in refs]
            try:
                resp = client.images.edit(image=files, **kwargs)
            finally:
                for f in files:
                    f.close()
        else:
            resp = client.images.generate(**kwargs)
        ext = getattr(resp, "output_format", None) or self.opt("output_format") or "png"
        ext = {"jpeg": "jpg"}.get(ext, ext)
        images: list[tuple[bytes, str]] = []
        revised: list[str] = []
        for d in resp.data:
            if getattr(d, "b64_json", None):
                images.append((base64.b64decode(d.b64_json), ext))
            elif getattr(d, "url", None):
                import urllib.request

                with urllib.request.urlopen(d.url) as r:
                    images.append((r.read(), ext))
            if getattr(d, "revised_prompt", None):
                revised.append(d.revised_prompt)
        return Result(images=images, revised_prompts=revised, prompt=prompt)

    def generate(self, job: Job) -> Result:
        refs: list[Path] = []
        if self.edit:
            refs = self._cap_refs([p for _, p in job.cards], list(job.examples))
            job.examples = [p for p in job.examples if p in refs]
        else:
            print(f"[{self.name}] edit=false: character cards og eksempler sendes IKKE", file=sys.stderr)
        return self._run(self._prompt_new(job), refs, job.n)

    def fix(self, job: Job) -> Result:
        prev = job.previous or {}
        if not prev.get("images"):
            die(f"Ingen tidligere bilder for {job.draft.stem}. Kjør 'new' først.")
        if not self.edit:
            die(f"[{self.name}] har edit=false og kan ikke korrigere et eksisterende bilde")
        last_img = PROJ.abs(prev["images"][-1])
        if job.panel:
            return self._run_panel(last_img, job)
        if job.mask:
            return self._run_masked(last_img, job)
        refs = self._cap_refs([last_img] + [p for _, p in job.cards], [])
        return self._run(self._prompt_fix(job), refs, 1)

    def _run_masked(self, src: Path, job: Job) -> Result:
        """images.edit with a mask: only the transparent rectangle is
        repainted, everything else is kept byte-for-byte. The prompt should
        describe what belongs INSIDE the rectangle, not what to remove.
        Character cards are not sent; the mask is too small for identity."""
        import io

        from PIL import Image

        x, y, w, h = job.mask
        im = Image.open(src).convert("RGBA")
        if x < 0 or y < 0 or x + w > im.width or y + h > im.height:
            die(f"--mask {x},{y},{w},{h} ligger utenfor bildet ({im.width}x{im.height})")
        mask = Image.new("RGBA", im.size, (0, 0, 0, 255))
        mask.paste((0, 0, 0, 0), (x, y, x + w, y + h))
        ib, mb = io.BytesIO(), io.BytesIO()
        im.save(ib, "PNG"); ib.seek(0); ib.name = "strip.png"
        mask.save(mb, "PNG"); mb.seek(0); mb.name = "mask.png"

        client = self._client()
        model = self.opt("image_model")
        if not model:
            die(f"[{self.name}] image_model mangler")
        kwargs: dict = {"model": model, "prompt": job.correction or "", "n": 1, **self._extra()}
        kwargs.pop("input_fidelity", None)
        resp = client.images.edit(image=ib, mask=mb, **kwargs)
        ext = getattr(resp, "output_format", None) or self.opt("output_format") or "png"
        ext = {"jpeg": "jpg"}.get(ext, ext)
        images = [(base64.b64decode(d.b64_json), ext) for d in resp.data if getattr(d, "b64_json", None)]
        return Result(images=images, prompt=f"[mask {x},{y},{w},{h}] " + (job.correction or ""))

    # Sizes the Images API accepts; we pick the one closest to the panel's aspect.
    API_SIZES = ((1024, 1024), (1536, 1024), (1024, 1536))

    def _run_panel(self, src: Path, job: Job) -> Result:
        """Cut one panel out of the strip, send only that panel (plus character
        cards) to images.edit, scale the result back to the panel's exact
        pixel size and paste it in place. No other panel is ever sent, so no
        other panel can drift. The panel is placed on a white canvas in the
        nearest API aspect so nothing is stretched; the same region is cut
        back out afterwards."""
        import io

        from PIL import Image

        strip = Image.open(src).convert("RGB")
        panels = detect_panels(strip)
        n = job.panel or 0
        if not 1 <= n <= len(panels):
            die(f"--panel {n}: fant {len(panels)} paneler i {src.name}")
        top, bot = panels[n - 1]
        panel = strip.crop((0, top, strip.width, bot))
        pw, ph = panel.size

        # canvas in the API aspect closest to the panel, panel scaled to fit width
        ratio = pw / ph
        cw, ch = min(self.API_SIZES, key=lambda s: abs(s[0] / s[1] - ratio))
        scale = min(cw / pw, ch / ph)
        sw, sh = round(pw * scale), round(ph * scale)
        canvas = Image.new("RGB", (cw, ch), "white")
        ox, oy = (cw - sw) // 2, (ch - sh) // 2
        canvas.paste(panel.resize((sw, sh), Image.LANCZOS), (ox, oy))

        ib = io.BytesIO(); canvas.save(ib, "PNG"); ib.seek(0); ib.name = "panel.png"
        files = [ib] + [open(p, "rb") for _, p in job.cards]
        prompt = (
            "The first image is one panel of a comic strip, centered on a white canvas. "
            + (f"The other images are character cards for {', '.join(n for n, _ in job.cards)}, identity references only. " if job.cards else "")
            + "Apply exactly this change to the panel and keep everything else in it identical, "
            "including its position and size on the canvas:\n\n" + (job.correction or "")
        )
        client = self._client()
        model = self.opt("image_model")
        if not model:
            die(f"[{self.name}] image_model mangler")
        kwargs: dict = {"model": model, "prompt": prompt, "n": 1, **self._extra()}
        kwargs["size"] = f"{cw}x{ch}"
        try:
            resp = client.images.edit(image=files, **kwargs)
        finally:
            for f in files[1:]:
                f.close()
        d = resp.data[0]
        out = Image.open(io.BytesIO(base64.b64decode(d.b64_json))).convert("RGB")
        if out.size != (cw, ch):
            out = out.resize((cw, ch), Image.LANCZOS)
        edited = out.crop((ox, oy, ox + sw, oy + sh)).resize((pw, ph), Image.LANCZOS)

        result = strip.copy()
        result.paste(edited, (0, top))
        buf = io.BytesIO(); result.save(buf, "PNG")
        return Result(images=[(buf.getvalue(), "png")],
                      prompt=f"[panel {n} of {len(panels)}, rows {top}-{bot}, sent {cw}x{ch}] " + (job.correction or ""))


PROVIDER_TYPES = {cls.type_name: cls for cls in (OpenAIResponses, OpenAIImages)}


def get_provider(cp: configparser.ConfigParser, name: str | None) -> Provider:
    name = name or PROJ.get("provider") or (cp["comic"].get("provider") if "comic" in cp else None)
    if not name:
        die("Ingen leverandør valgt: sett provider= under [comic] eller bruk --provider")
    if name not in cp or name == "comic":
        die(f"Ukjent leverandør [{name}] i keys.ini")
    sec = cp[name]
    t = sec.get("type")
    if t not in PROVIDER_TYPES:
        die(f"[{name}] har ukjent type '{t}'. Gyldige: {', '.join(PROVIDER_TYPES)}")
    return PROVIDER_TYPES[t](name, sec)


# --------------------------------------------------------------------------
# Post-processing: header + white border
# --------------------------------------------------------------------------

def detect_panels(im) -> list[tuple[int, int]]:
    """(top, bottom) row spans of the panels in a vertical strip. Panels are
    separated by thin white gutters (3 to 24 rows, >60% near-white pixels)."""
    g = im.convert("L")
    w, h = g.size
    px = g.load()
    # A gutter row is mostly near-white; anti-aliased borders and drop
    # shadows pull some gutters down to ~65%, so the bar is 0.6. A gutter is
    # also THIN (3 to 24 rows); a bright sky inside a panel is not.
    white = [sum(1 for x in range(0, w, 2) if px[x, y] > 235) / (w / 2) > 0.6 for y in range(h)]
    gutters: list[tuple[int, int]] = []
    y = 0
    while y < h:
        if white[y]:
            s = y
            while y < h and white[y]:
                y += 1
            if 3 <= y - s <= 24:
                gutters.append((s, y))
        else:
            y += 1
    bounds: list[tuple[int, int]] = []
    prev = 0
    for s, e in gutters:
        if s - prev > 50:
            bounds.append((prev, s))
        prev = e
    if h - prev > 50:
        bounds.append((prev, h))
    return bounds


def detect_header_rows(im) -> int:
    """Rows to crop from the top if the model drew its own header: the first
    mostly-dark horizontal line (panel border) within the top 200 px, else 0."""
    g = im.convert("L")
    w, h = g.size
    px = g.load()
    for y in range(60, min(200, h)):
        dark = sum(1 for x in range(0, w, 2) if px[x, y] < 60) / (w / 2)
        if dark > 0.6:
            return y
    return 0


def add_credit_footer(im, text: str, sec):
    """A white strip under the image with `text` in small dark-grey type,
    wrapped to the width. Font from `credit_font` in prosjekt.ini, else a
    system sans; size `credit_size` in px (default 2.2 % of the width)."""
    from PIL import Image, ImageDraw, ImageFont

    size = int((sec.get("credit_size") or "").strip() or round(im.width * 0.022))
    font = None
    for cand in [(sec.get("credit_font") or "").strip(), "C:/Windows/Fonts/segoeui.ttf",
                 "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if cand and Path(cand).exists():
            font = ImageFont.truetype(cand, size)
            break
    if font is None:
        font = ImageFont.load_default()
    pad = round(size * 0.8)
    draw = ImageDraw.Draw(im)
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if draw.textlength(t, font=font) <= im.width - 2 * pad or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    lh = round(size * 1.35)
    h = pad + lh * len(lines) + pad
    canvas = Image.new("RGB", (im.width, im.height + h), "white")
    canvas.paste(im, (0, 0))
    d = ImageDraw.Draw(canvas)
    for i, line in enumerate(lines):
        d.text((pad, im.height + pad + i * lh), line, fill=(70, 70, 70), font=font)
    return canvas


def compose(src: Path, dst: Path, cp: configparser.ConfigParser, crop_top: str | None = None,
            credit: str | None = None) -> None:
    """Header on top, optional credit footer below, white border around.
    `credit` is a text line drawn with Pillow under the strip (attribution
    for redrawn sources; lettering by the image model is not reliable)."""
    from PIL import Image

    sec = PROJ.sec
    im = Image.open(src).convert("RGB")

    if crop_top == "auto":
        n = detect_header_rows(im)
    else:
        n = int(crop_top or 0)
    if n:
        im = im.crop((0, n, im.width, im.height))
        print(f"crop_top   : {n} px")

    out_w = (sec.get("out_width") or "").strip()
    if out_w:
        tw = int(out_w)
        im = im.resize((tw, round(im.height * tw / im.width)), Image.LANCZOS)

    header_file = (sec.get("header") or "").strip()
    if header_file:
        hp = PROJ.root / header_file
        if not hp.exists():
            die(f"Header mangler: {hp}")
        hd = Image.open(hp).convert("RGB")
        hd = hd.resize((im.width, round(hd.height * im.width / hd.width)), Image.LANCZOS)
        canvas = Image.new("RGB", (im.width, hd.height + im.height), "white")
        canvas.paste(hd, (0, 0))
        canvas.paste(im, (0, hd.height))
        im = canvas

    if credit:
        im = add_credit_footer(im, credit, sec)

    border = int((sec.get("border") or "0").strip() or 0)
    if border:
        canvas = Image.new("RGB", (im.width + 2 * border, im.height + 2 * border), "white")
        canvas.paste(im, (border, border))
        im = canvas

    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst)
    shown = PROJ.rel(dst)
    print(f"{shown}  {im.width}x{im.height}")


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

def build_job(cp, args, provider: Provider, draft: Draft, correction: str | None = None, previous: dict | None = None) -> Job:
    canon_files = (split_list(getattr(args, "canon", None) or "")
                   or split_list(provider.opt("canon") or "")
                   or PROJ.canon_for(provider.type_name, provider.name))
    if not canon_files:
        die("Ingen canon-filer: sett canon_responses/canon_direct i prosjekt.ini eller bruk --canon")

    cards = [] if getattr(args, "no_cards", False) else select_cards(draft.characters)
    examples: list[Path] = []
    if correction is None and not getattr(args, "no_examples", False):
        wanted = getattr(args, "examples", None) or PROJ.get("examples") or ""
        for e in split_list(wanted):
            p = PROJ.root / e
            if not p.exists():
                die(f"Eksempelstripe mangler: {p}")
            examples.append(prepared_example(p))
    return Job(
        draft=draft,
        canon=read_canon(canon_files, draft.characters),
        cards=cards,
        examples=examples,
        n=getattr(args, "n", 1) or 1,
        correction=correction,
        previous=previous,
        canon_files=canon_files,
        mask=parse_mask(getattr(args, "mask", None)),
        panel=getattr(args, "panel", None),
    )


def parse_mask(s: str | None) -> tuple[int, int, int, int] | None:
    if not s:
        return None
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 4 or not all(p.lstrip("-").isdigit() for p in parts):
        die(f"--mask må være x,y,w,h i piksler, fikk '{s}'")
    x, y, w, h = (int(p) for p in parts)
    if w <= 0 or h <= 0:
        die("--mask: bredde og høyde må være større enn 0")
    return (x, y, w, h)


def print_plan(provider: Provider, job: Job, kind: str) -> None:
    print(f"== {kind}: {job.draft.stem}")
    print(f"provider   : [{provider.name}] {provider.describe()}")
    print(f"canon      : {len(job.canon)} tegn ({', '.join(job.canon_files)})")
    print(f"cards      : {', '.join(f'{n} ({p.name})' for n, p in job.cards) or '-'}")
    print(f"examples   : {', '.join(p.name for p in job.examples) or '-'}")
    if job.correction is not None:
        print(f"previous   : {job.previous.get('response_id') or job.previous.get('images', ['-'])[-1] if job.previous else '-'}")
        print(f"correction : {job.correction}")
        if job.mask:
            print(f"mask       : x={job.mask[0]} y={job.mask[1]} w={job.mask[2]} h={job.mask[3]} (kun dette området males på nytt)")
    else:
        print(f"n          : {job.n}")
        print("draft      :")
        for line in job.draft.body.splitlines():
            print("  " + line)


def record(draft: Draft, provider: Provider, kind: str, job: Job, res: Result, extra: dict | None = None) -> None:
    if not res.images:
        print("Ingen bilder i svaret.", file=sys.stderr)
        if res.text:
            print("Modellen sa:\n" + res.text, file=sys.stderr)
        sys.exit(2)
    paths = save_images(draft, kind, res.images)
    state = load_state(draft)
    run = {
        "time": dt.datetime.now().isoformat(timespec="seconds"),
        "kind": kind,
        "provider": provider.name,
        "type": provider.type_name,
        "response_id": res.response_id,
        "cards": [n for n, _ in job.cards],
        "examples": [p.name for p in job.examples],
        "prompt": res.prompt,
        "correction": job.correction,
        "revised_prompts": res.revised_prompts,
        "model_text": res.text,
        "images": paths,
    }
    if extra:
        run.update(extra)
    state["runs"].append(run)
    save_state(draft, state)
    for p in paths:
        print(p)
    # revised_prompt is what the image tool actually received. On the
    # openai_images path the chat/tool layer may shorten a long prompt;
    # flag it when much of the text went missing.
    if res.prompt and res.revised_prompts:
        got, sent = len(res.revised_prompts[0]), len(res.prompt)
        if got < 0.8 * sent:
            print(f"ADVARSEL: revised_prompt er {got} tegn, sendt prompt {sent}. "
                  "Sjekk state.json; verktøyet fikk ikke hele teksten.", file=sys.stderr)
    if res.text.strip():
        print("--\n" + res.text.strip())


def cmd_new(cp, args) -> None:
    draft = parse_draft(Path(args.draft))
    provider = get_provider(cp, args.provider)
    job = build_job(cp, args, provider, draft)
    if getattr(args, "panels", False):
        return new_panels(cp, args, provider, draft, job)
    print_plan(provider, job, "new")
    if args.dry_run:
        return
    record(draft, provider, "new", job, provider.generate(job))


# --------------------------------------------------------------------------
# new --panels: one image-model call per panel, stitched with Pillow.
# For providers that keep identity in one scene but swap roles when asked
# for four at once (Grok via agentry, measured 2026-10-04 and 2026-10-06).
# Panel 1 is sent as a style reference to the later panels.
# --------------------------------------------------------------------------

PANEL_RE = re.compile(r"^Panel (\d+):\s*(.*?)(?=^Panel \d+:|\Z)", re.S | re.M)


def split_panels(body: str) -> tuple[str, list[tuple[int, str]]]:
    """(preamble, [(n, text)]) from a draft body. The preamble is everything
    before 'Panel 1:', the shared setting and notes."""
    m = PANEL_RE.search(body)
    pre = body[: m.start()].strip() if m else body.strip()
    panels = [(int(n), " ".join(t.split())) for n, t in PANEL_RE.findall(body)]
    return pre, panels


def chars_in(text: str, characters: list[str]) -> list[str]:
    """Established characters named in a panel paragraph, in draft order.
    Falls back to all of them when none is named."""
    found = [c for c in characters if re.search(rf"\b{re.escape(c)}\b", text, re.I)]
    return found or list(characters)


def stitch_panels(images: list[Path], width: int, gutter: int = 14, line: int = 3):
    """Stack panels top to bottom at a common width, each with a thin black
    border, white gutters between. Same look as a one-shot strip, so
    detect_panels() and `fix --panel` work on the result."""
    from PIL import Image, ImageOps

    tiles = []
    for p in images:
        im = Image.open(p).convert("RGB")
        inner = width - 2 * line
        im = im.resize((inner, round(im.height * inner / im.width)), Image.LANCZOS)
        tiles.append(ImageOps.expand(im, border=line, fill="black"))
    h = sum(t.height for t in tiles) + gutter * (len(tiles) - 1)
    out = Image.new("RGB", (width, h), "white")
    y = 0
    for t in tiles:
        out.paste(t, (0, y))
        y += t.height + gutter
    return out


def new_panels(cp, args, provider: Provider, draft: Draft, job: Job) -> None:
    import io
    from concurrent.futures import ThreadPoolExecutor

    if provider.type_name != "openai_images" or not getattr(provider, "edit", False):
        die("--panels krever en openai_images-leverandør med edit=true (kortene må sendes per panel)")
    pre, panels = split_panels(draft.body)
    if len(panels) < 2:
        die(f"--panels: fant {len(panels)} 'Panel N:'-avsnitt i utkastet; trenger minst to")
    m = len(panels)
    size = getattr(args, "panel_size", None) or PROJ.get("panel_size") or provider.opt("panel_size") or "1536x1024"
    width = int((provider.opt("size") or "1024x1536").split("x")[0])

    use_bg = bool(getattr(args, "background", False))

    def prompt_for(n: int, text: str, chars: list[str], with_style: bool) -> str:
        names = ", ".join(chars)
        canon = read_canon(job.canon_files, chars)
        refs = f"Reference images, in order: character cards for {names}"
        if with_style and use_bg:
            refs += (", then the EMPTY setting of this strip with nobody in it: draw this panel in "
                     "that exact place, style and light, adding only the characters named above.")
        elif with_style:
            refs += (", then the finished panel 1 of this same strip: match its drawing style, "
                     "colours, light and the exact same setting.")
        else:
            refs += "."
        return (
            f"Draw ONLY panel {n} of {m} of a comic strip, as ONE single landscape image that fills "
            "the whole picture edge to edge: no panel border, no gutters, no other panels, no title. "
            "Any instruction below about stacking several panels does not apply to this image. "
            "Speech bubbles are read top to bottom, then left to right: the line spoken FIRST sits "
            "clearly higher in the panel than the reply, and a reply never sits level with or above "
            "the line it answers.\n\n"
            f"{canon}\n\n{refs}\n\n---\n\nThe strip, for context (do not draw the other panels):\n\n"
            f"{pre}\n\nThis panel:\n\n{text}"
        )

    plan = []
    for n, text in panels:
        chars = chars_in(text, draft.characters)
        plan.append((n, text, chars, select_cards(chars)))
    print(f"== new --panels: {draft.stem}")
    print(f"provider   : [{provider.name}] {provider.describe()}")
    print(f"panels     : {m}, size {size} each, stitched to {width} px wide")
    if use_bg:
        print("  background: empty setting from the preamble, text only, sent to every panel")
    for n, text, chars, cards in plan:
        ref = " + background" if use_bg else ("" if n == plan[0][0] else " + panel 1")
        print(f"  panel {n}: cards {', '.join(p.name for _, p in cards)}{ref}")
    if args.dry_run:
        print("prompt for panel 1:")
        for line in prompt_for(plan[0][0], plan[0][1], plan[0][2], False).splitlines():
            print("  " + line)
        return

    draft.workdir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    results: dict[int, Path] = {}

    def run_one(n, text, chars, cards, style):
        refs = provider._cap_refs([p for _, p in cards], [style] if style else [])
        t0 = dt.datetime.now()
        res = provider._run(prompt_for(n, text, chars, style is not None), refs, 1, size)
        if not res.images:
            die(f"panel {n}: ingen bilder i svaret")
        data, ext = res.images[0]
        out = draft.workdir / f"{stamp}-panel-{n}.{ext}"
        out.write_bytes(data)
        print(f"  panel {n}: {PROJ.rel(out)}  {(dt.datetime.now() - t0).seconds} s", flush=True)
        return out

    workers = int(provider.opt("parallel") or 2)
    if use_bg:
        style_canon = read_canon(job.canon_files, [])
        bg_prompt = (
            "The empty setting for a comic strip, as ONE single landscape image filling the whole "
            "picture: the place described below with NOBODY in it, no people, no animals, no text, "
            "no speech bubbles, no panel borders. Any instruction below about stacking several "
            f"panels does not apply.\n\n{style_canon}\n\n---\n\nThe setting:\n\n{pre}"
        )
        t0 = dt.datetime.now()
        res = provider._run(bg_prompt, [], 1, size)
        if not res.images:
            die("background: ingen bilder i svaret")
        data, ext = res.images[0]
        style = draft.workdir / f"{stamp}-panel-0-background.{ext}"
        style.write_bytes(data)
        print(f"  background: {PROJ.rel(style)}  {(dt.datetime.now() - t0).seconds} s", flush=True)
        todo = plan
    else:
        first = plan[0]
        results[first[0]] = run_one(*first, None)
        style = results[first[0]]
        todo = plan[1:]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(run_one, *pl, style): pl[0] for pl in todo}
        for f, n in futs.items():
            results[n] = f.result()

    ordered = [results[n] for n, *_ in plan]
    strip = stitch_panels(ordered, width)
    buf = io.BytesIO()
    strip.save(buf, format="PNG")
    res = Result(images=[(buf.getvalue(), "png")], prompt=prompt_for(first[0], first[1], first[2], False))
    extra = {"panels": [PROJ.rel(p) for p in ordered], "panel_size": size}
    if use_bg:
        extra["background"] = PROJ.rel(style)
    record(draft, provider, "new", job, res, extra=extra)


def cmd_fix(cp, args) -> None:
    draft = parse_draft(Path(args.draft))
    state = load_state(draft)
    runs = state["runs"]
    if not runs:
        die(f"Ingen tidligere kjøringer for {draft.stem}. Kjør 'new' først.")
    try:
        prev = runs[args.run - 1 if args.run > 0 else args.run]
    except IndexError:
        die(f"Finnes ingen kjøring nr {args.run} (det er {len(runs)} kjøringer)")
    # Corrections default to [comic] fix_provider (an images.edit path keeps
    # the rest of the strip intact), else the provider that made the run.
    provider = get_provider(cp, args.provider or PROJ.get("fix_provider") or cp["comic"].get("fix_provider") or prev.get("provider"))
    job = build_job(cp, args, provider, draft, correction=args.text, previous=prev)
    print_plan(provider, job, "fix")
    if args.dry_run:
        return
    record(draft, provider, "fix", job, provider.fix(job))


def credit_for(draft: Draft) -> str | None:
    """The credit footer for a strip: `credit` in prosjekt.ini, formatted
    with the draft's frontmatter ("{kilde}" etc.). None when unset or when
    a referenced field is missing from the draft."""
    tpl = (PROJ.get("credit") or "").strip()
    if not tpl:
        return None
    try:
        return tpl.format(**draft.meta)
    except (KeyError, IndexError):
        print(f"(credit: utkastet mangler feltet som {tpl!r} trenger; ingen footer)")
        return None


def cmd_approve(cp, args) -> None:
    draft = parse_draft(Path(args.draft))
    if args.image:
        src = Path(args.image).resolve()
    else:
        prev = last_run(load_state(draft))
        if not prev or not prev.get("images"):
            die(f"Ingen genererte bilder for {draft.stem}")
        src = PROJ.abs(prev["images"][-1])
    if not src.exists():
        die(f"Finnes ikke: {src}")
    PROJ.striper.mkdir(exist_ok=True)
    if args.raw:
        dst = PROJ.striper / f"{draft.stem}{src.suffix}"
        shutil.copy2(src, dst)
        print(PROJ.rel(dst))
    else:
        compose(src, PROJ.striper / f"{draft.stem}.png", cp, args.crop_top, credit_for(draft))


def cmd_compose(cp, args) -> None:
    src = Path(args.image).resolve()
    if not src.exists():
        die(f"Finnes ikke: {src}")
    dst = Path(args.out).resolve() if args.out else src.with_name(src.stem + "-final.png")
    compose(src, dst, cp, args.crop_top)


# --------------------------------------------------------------------------
# pick: browser page with every run of a strip, click a panel to comment,
# pick one run. Saves to generert/<slug>/picks.json on every change.
# --------------------------------------------------------------------------

PICK_PAGE = """<!doctype html>
<meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{ --bg:#17181c; --card:#222329; --ink:#e6e4df; --dim:#9b988f; --line:#3a3c45;
          --ok:#4caf50; --hi:#d4a24e; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:16px 20px 60px; background:var(--bg); color:var(--ink);
         font:14px/1.45 system-ui, sans-serif; }}
  h1 {{ font-size:18px; margin:0 0 4px; }}  .sub {{ color:var(--dim); margin:0 0 16px; }}
  .bar {{ position:sticky; top:0; z-index:5; background:var(--bg); padding:8px 0 10px;
          border-bottom:1px solid var(--line); display:flex; gap:14px; align-items:center; }}
  .bar .st {{ color:var(--dim); min-width:170px; }}  .bar .st.err {{ color:#e57373; }}
  .bar button {{ border:0; border-radius:5px; padding:6px 14px; font:inherit; font-weight:700; cursor:pointer; }}
  .bar button.ok {{ background:var(--ok); color:#000; }}
  .bar button.ghost {{ background:transparent; color:var(--dim); border:1px solid var(--line); }}
  .runs {{ display:flex; flex-wrap:wrap; gap:18px; margin-top:16px; align-items:flex-start; }}
  .run {{ width:{w}px; background:var(--card); border:2px solid var(--line); border-radius:8px;
          overflow:hidden; }}
  .run.picked {{ border-color:var(--ok); }}
  .run header {{ display:flex; justify-content:space-between; align-items:center; gap:8px;
                 padding:8px 10px; font-size:12px; color:var(--dim); }}
  .run header b {{ color:var(--ink); }}
  .run header button {{ background:var(--ok); color:#000; border:0; border-radius:4px;
                        padding:4px 10px; font-weight:700; cursor:pointer; }}
  .run.picked header button {{ background:var(--line); color:var(--dim); }}
  .img {{ position:relative; }}  .img img {{ display:block; width:100%; height:auto; }}
  .pan {{ position:absolute; left:0; right:0; cursor:pointer; border:2px solid transparent; }}
  .pan:hover {{ border-color:var(--hi); background:rgba(212,162,78,.08); }}
  .pan.has {{ border-color:var(--hi); }}
  .pan .n {{ position:absolute; top:4px; left:6px; font-size:11px; font-weight:700;
             color:var(--hi); text-shadow:0 0 3px #000; }}
  .pan .c {{ position:absolute; right:6px; top:4px; max-width:70%; font-size:11px;
             background:rgba(0,0,0,.65); color:var(--hi); padding:2px 6px; border-radius:3px;
             white-space:pre-wrap; }}
  .notes {{ padding:8px 10px; display:grid; gap:6px; }}
  .notes label {{ font-size:11px; color:var(--dim); }}
  textarea {{ width:100%; min-height:38px; background:#1b1c21; color:var(--ink);
              border:1px solid var(--line); border-radius:4px; padding:5px 7px; font:inherit; }}
  textarea.gen {{ min-height:48px; }}
</style>
<h1>{title}</h1>
<p class="sub">Klikk på et panel for å kommentere det. "Velg denne" merker kjøringen som
den som skal videre. Alt lagres automatisk til <code>{picks}</code>, som
assistenten (Claude Code eller codex) leser når du sier fra. Ingenting leses
fra nettleseren.</p>
<div class="bar">
  <span class="st" id="st">lagret</span>
  <button id="done" class="ok">Ferdig, send til assistenten</button>
  <button id="export" class="ghost" title="Last ned picks.json; trengs bare om serveren er borte">Eksporter JSON</button>
  <label style="margin-left:auto;color:var(--dim)">Generell kommentar:</label>
  <textarea class="gen" id="gen" style="width:36%" placeholder="f.eks. bytt panel 2 fra kjøring 3 inn i kjøring 5"></textarea>
</div>
<p class="sub" id="next" style="display:none;margin-top:10px;color:var(--ok)"></p>
<div class="runs">{runs}</div>
<script>
const state = {state};
const stEl = document.getElementById("st");
let timer = null;
async function flush() {{
  try {{
    const r = await fetch("/save", {{method:"POST", headers:{{"Content-Type":"application/json"}},
                                   body: JSON.stringify(state)}});
    if (!r.ok) throw new Error(r.status);
    stEl.textContent = "lagret " + new Date().toLocaleTimeString(); stEl.className = "st";
  }} catch (e) {{
    localStorage.setItem("picks_{slug}", JSON.stringify(state));
    stEl.textContent = "server borte, lagret lokalt i nettleseren"; stEl.className = "st err";
  }}
}}
function save() {{ clearTimeout(timer); timer = setTimeout(flush, 300); render(); }}
function render() {{
  document.querySelectorAll(".run").forEach(r => r.classList.toggle("picked", state.picked === r.dataset.img));
  document.querySelectorAll(".pan").forEach(p => {{
    const c = ((state.panels || {{}})[p.dataset.img] || {{}})[p.dataset.n] || "";
    p.classList.toggle("has", !!c);
    p.querySelector(".c").textContent = c;
  }});
}}
document.querySelectorAll(".run header button").forEach(b => b.onclick = () => {{
  state.picked = (state.picked === b.dataset.img) ? null : b.dataset.img; save(); }});
document.querySelectorAll(".pan").forEach(p => p.onclick = () => {{
  const img = p.dataset.img, n = p.dataset.n;
  state.panels = state.panels || {{}}; state.panels[img] = state.panels[img] || {{}};
  const cur = state.panels[img][n] || "";
  const v = prompt("Kommentar til panel " + n + " (tom = slett):", cur);
  if (v === null) return;
  if (v.trim()) state.panels[img][n] = v.trim(); else delete state.panels[img][n];
  save();
}});
const gen = document.getElementById("gen");
gen.value = state.note || "";
gen.oninput = () => {{ state.note = gen.value; save(); }};
document.getElementById("export").onclick = () => {{
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([JSON.stringify(state, null, 2)], {{type:"application/json"}}));
  a.download = "picks_{slug}.json"; a.click();
}};
document.getElementById("done").onclick = async () => {{
  state.done = new Date().toISOString(); clearTimeout(timer); await flush();
  const n = Object.values(state.panels || {{}}).reduce((s, p) => s + Object.keys(p).length, 0);
  const nx = document.getElementById("next");
  nx.style.display = "block";
  nx.textContent = (stEl.className.includes("err")
    ? "Serveren svarer ikke. Trykk Eksporter JSON og gi fila til assistenten."
    : "Lagret. Si til assistenten: \\"les picks.json for {slug}\\". ") +
    (state.picked ? "Valgt: " + state.picked + ". " : "Ingen kjøring valgt. ") + n + " panelkommentar(er)." +
    (state.note && state.note.trim() ? " Generell kommentar: \\u201c" + state.note.trim() + "\\u201d" : "");
}};
render();
</script>
"""

PICK_RUN = """<div class="run" data-img="{img}">
<header><span><b>#{i}</b> {kind} · {provider} · {time}</span>
<button data-img="{img}">Velg denne</button></header>
<div class="img"><img src="{img}" loading="lazy">{panels}</div>
</div>"""

PICK_PANEL = """<div class="pan" data-img="{img}" data-n="{n}" style="top:{top}%;height:{h}%">
<span class="n">{n}</span><span class="c"></span></div>"""


def build_pick_page(draft: Draft, width: int = 420) -> tuple[str, Path]:
    """HTML listing every image in the draft's generert folder, newest last,
    with one clickable overlay per detected panel. Returns (html, picks_path)."""
    from PIL import Image

    state = load_state(draft)
    meta: dict[str, dict] = {}
    for i, r in enumerate(state["runs"], 1):
        for img in r.get("images", []):
            meta[Path(img.replace("\\", "/")).name] = {"i": i, "kind": r["kind"], "provider": r["provider"],
                                                      "time": (r.get("time") or "")[11:16]}
    files = sorted(p for p in draft.workdir.iterdir() if p.suffix.lower() in IMAGE_EXTS and not p.name.startswith("compare"))
    picks_path = draft.workdir / "picks.json"
    picks = json.loads(picks_path.read_text(encoding="utf-8")) if picks_path.exists() else {}
    picks.setdefault("draft", PROJ.rel(draft.path))
    runs = []
    for p in files:
        m = meta.get(p.name, {"i": "-", "kind": "compose" if "compose" in p.name else "fil", "provider": "", "time": ""})
        im = Image.open(p)
        H = im.height
        panels = "".join(PICK_PANEL.format(img=p.name, n=n, top=round(100 * t / H, 2), h=round(100 * (b - t) / H, 2))
                         for n, (t, b) in enumerate(detect_panels(im), 1))
        runs.append(PICK_RUN.format(img=p.name, i=m["i"], kind=m["kind"], provider=m["provider"], time=m["time"], panels=panels))
    html = PICK_PAGE.format(title=f"{draft.stem}: velg og kommenter", slug=draft.stem, w=width,
                            picks=PROJ.rel(picks_path), runs="".join(runs), state=json.dumps(picks, ensure_ascii=False))
    return html, picks_path


def cmd_pick(cp, args) -> None:
    import http.server
    import socketserver
    import threading
    import webbrowser

    draft = parse_draft(Path(args.draft))
    if not draft.workdir.exists():
        die(f"Ingen kjøringer for {draft.stem} ennå.")
    html, picks_path = build_pick_page(draft, args.width)
    (draft.workdir / "pick.html").write_text(html, encoding="utf-8")
    port = args.port
    while _port_in_use(port):
        port += 1
    folder = str(draft.workdir)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=folder, **k)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.path = "/pick.html"
            return super().do_GET()

        def do_POST(self):
            if self.path != "/save":
                self.send_error(404); return
            n = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(n)
            try:
                data = json.loads(raw.decode("utf-8"))
            except UnicodeDecodeError:
                data = json.loads(raw.decode("latin-1"))
            data["saved"] = dt.datetime.now().isoformat(timespec="seconds")
            picks_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.send_response(204); self.end_headers()

        def log_message(self, fmt, *a):  # quiet
            pass

    socketserver.ThreadingTCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"{url}  ({len(list(draft.workdir.glob('*.png')))} bilder; valg lagres i {PROJ.rel(picks_path)}; Ctrl-C avslutter)")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def cmd_providers(cp, args) -> None:
    default = PROJ.get("provider") or cp["comic"].get("provider", "")
    for name in cp.sections():
        if name == "comic":
            continue
        sec = cp[name]
        t = sec.get("type", "?")
        key = sec.get("api_key", "")
        if key and not key.endswith("..."):
            has_key = "nøkkel satt"
        elif sec.get("base_url", "").startswith("http://localhost"):
            has_key = "lokal, ingen nøkkel"
        else:
            has_key = "INGEN NØKKEL"
        mark = "*" if name == default else " "
        try:
            desc = PROVIDER_TYPES[t](name, sec).describe()
        except KeyError:
            desc = f"ukjent type '{t}'"
        print(f"{mark} [{name}] {has_key}: {desc}")
    print("\n* = standard (provider= under [comic])")


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ini", default=str(INI), help="konfigfil (standard keys.ini)")
    ap.add_argument("-P", "--project", help="prosjektnavn under prosjekter/ eller sti; ellers utledet fra utkastets sti, keys.ini eller cwd")
    sub = ap.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-p", "--provider", help="leverandør-seksjon i keys.ini")
    common.add_argument("--canon", help="kommaseparert liste canon-filer (overstyrer [comic] canon)")
    common.add_argument("--dry-run", action="store_true", help="vis hva som ville blitt sendt, ikke kall API")

    p = sub.add_parser("new", parents=[common], help="generer ny stripe fra utkast")
    p.add_argument("draft")
    p.add_argument("-n", type=int, default=1, help="antall varianter (kun openai_images)")
    p.add_argument("--no-examples", action="store_true", help="ikke send eksempelstriper")
    p.add_argument("--examples", help="kommaseparert liste eksempelstriper (overstyrer [comic] examples)")
    p.add_argument("--panels", action="store_true", help="ett kall per panel med kortene hver gang, panel 1 som stilreferanse, stiftet sammen med Pillow (for Grok)")
    p.add_argument("--background", action="store_true", help="med --panels: tegn først det tomme stedet fra "
                   "innledningen (tekst alene) og send det som referanse til hvert panel i stedet for panel 1; "
                   "for striper der figurene varierer mellom panelene")
    p.add_argument("--panel-size", help="størrelse per panel ved --panels (standard panel_size i prosjekt.ini, ellers 1536x1024)")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("fix", parents=[common], help="korriger siste genererte bilde")
    p.add_argument("draft")
    p.add_argument("text", help="korreksjonstekst")
    p.add_argument("--no-cards", action="store_true", help="ikke send character cards på nytt")
    p.add_argument("--run", type=int, default=-1, help="hvilken kjøring som korrigeres: 1, 2, ... eller -1 for siste (standard)")
    p.add_argument("--panel", type=int, help="1-basert panelnummer: bare dette panelet sendes til modellen "
                                             "(med character cards) og limes tilbake på plass. De andre panelene røres ikke.")
    p.add_argument("--mask", help="x,y,w,h i piksler: kun dette rektangelet males på nytt, resten beholdes eksakt. "
                                  "Teksten beskriver da hva som skal være INNI rektangelet.")
    p.set_defaults(func=cmd_fix)

    p = sub.add_parser("approve", help="legg på header/kant og lagre siste (eller gitt) bilde i striper/")
    p.add_argument("draft")
    p.add_argument("image", nargs="?")
    p.add_argument("--raw", action="store_true", help="kopier uendret, ingen header/kant")
    p.add_argument("--crop-top", help="piksler å klippe fra toppen, eller 'auto' (modellen tegnet egen header)")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("compose", help="legg header/kant på et vilkårlig bilde")
    p.add_argument("image")
    p.add_argument("-o", "--out", help="utfil (standard <navn>-final.png ved siden av)")
    p.add_argument("--crop-top", help="piksler å klippe fra toppen, eller 'auto'")
    p.set_defaults(func=cmd_compose)

    p = sub.add_parser("pick", help="nettleserside: velg kjøring og kommenter paneler, lagres i picks.json")
    p.add_argument("draft")
    p.add_argument("--port", type=int, default=8780)
    p.add_argument("--width", type=int, default=420, help="bredde per stripe i px")
    p.add_argument("--no-browser", action="store_true")
    p.set_defaults(func=cmd_pick)

    p = sub.add_parser("providers", help="list leverandører i keys.ini")
    p.set_defaults(func=cmd_providers)

    args = ap.parse_args(argv)
    cp = load_config(Path(args.ini))
    global PROJ
    PROJ = resolve_project(cp, args.project, getattr(args, "draft", None))
    args.func(cp, args)


if __name__ == "__main__":
    main()
