# Lecture Infographic Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One command, `python tools/infographic.py "<lecture title>"`, that reads a medwiki lecture note, asks Google's Gemini image model for a poster-style study infographic of it, and saves the PNG into the vault's `Attachments/`, with no browser cookies and no NotebookLM.

**Architecture:** A single script, `tools/infographic.py`, in four pure functions plus a thin CLI: find and clean the note, build the focus prompt, call the Gemini `generateContent` REST endpoint with plain `requests`, write the PNG (and optionally embed it in the note). Everything before the network call is testable offline; the network call is tested against a mocked `requests.post`. The API key comes from `GEMINI_API_KEY` only; the script never reads browser state.

**Tech Stack:** Python 3.14 (miniconda), `requests` (installed), `pytest` (installed), Gemini REST API (`generativelanguage.googleapis.com`). No new dependencies.

**Spec:** This conversation, 2026-09-29. The user wants NotebookLM-style AI infographics of lecture notes, automated, and refuses to hand any tool their Google login cookies. A scoped API key was agreed as the alternative. First target: `01 - Lectures/99 - PoM 2/02 - Repro/Week 5/09 - Pathology of 1st Trimester Bleeding.md`.

## Global Constraints

- Vault root is `$MEDWIKI_VAULT`, default `/mnt/c/Users/nsims/medwiki` (same variable and default as `tools/review_lectures.py:69`). Lecture notes live under `<vault>/01 - Lectures/`; images live in `<vault>/Attachments/`.
- The API key is read from `GEMINI_API_KEY` **only**. Never log it, never write it to disk, never accept it as a CLI argument (it would land in shell history).
- Model name from `GEMINI_IMAGE_MODEL`, default `gemini-2.5-flash-image`. Endpoint: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`, auth header `x-goog-api-key`.
- Output filename: `<note stem> (generated infographic).png`. The words "generated infographic" are mandatory in the name so a generated picture is never mistaken for a slide. Slides are the gold standard; this is a study aid.
- Code style: snake_case, type hints on every signature, numpy-style docstrings, `pathlib` not `os.path`, `logging` not `print` (the CLI may print the final path to stdout), a module header with Purpose/Author/Date/Input/Output like `tools/figures.py`.
- Never overwrite an existing output file unless `--force` is given.
- The vault note is modified only when `--embed` is passed, and then only by inserting one line.

## Review Focus

1. A note title that matches two files (e.g. "Approach to First Trimester Bleeding" is both a Week 5 lecture and a clinical-skills note): the script must refuse and list both, not pick one silently. Test in Task 1.
2. A note whose Obsidian syntax is heavier than the target's: nested `> [!multi-column]` callouts, `<mark>` tags, `<font color>` spans, `![[img.png|600]]` embeds with width hints, `[[a\|b]]` escaped pipes inside tables. Cleaning must leave readable prose with no `[[`, `]]`, `![[`, or `<` left behind. Test in Task 1.
3. Gemini returning a 200 with a text-only answer (safety refusal, or a model that ignores the image modality): the script must fail with a clear message quoting the text, not write a 0-byte PNG. Test in Task 3.
4. HTTP 429 / 503 on a free-tier key: retry three times with backoff, then fail with the status and body, never loop forever. Test in Task 3.
5. `--embed` on a note that already carries the embed line: must not add a second one. Test in Task 4.

---

### Task 1: Find and clean the lecture note

**Files:**
- Create: `tools/infographic.py`
- Create: `tools/tests/__init__.py` (empty)
- Create: `tools/tests/test_infographic.py`

**Interfaces:**
- Produces: `find_note(vault: Path, query: str) -> Path` — `query` is either a path to a `.md` file (returned as-is if it exists) or a case-insensitive substring of a note filename under `<vault>/01 - Lectures`. Raises `FileNotFoundError` for zero matches and `ValueError` listing every match for more than one.
- Produces: `clean_markdown(text: str) -> str` — Obsidian markdown to plain text the image model can read.
- Produces: `VAULT: Path` module constant from `MEDWIKI_VAULT`.

- [ ] **Step 1: Write the failing tests**

```python
# tools/tests/test_infographic.py
# -*- coding: utf-8 -*-
"""Tests for tools/infographic.py. Run: python -m pytest tools/tests -v"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import infographic as ig  # noqa: E402


def make_vault(tmp_path: Path) -> Path:
    lectures = tmp_path / "01 - Lectures" / "99 - PoM 2" / "02 - Repro" / "Week 5"
    lectures.mkdir(parents=True)
    (lectures / "09 - Pathology of 1st Trimester Bleeding.md").write_text("# a\n", encoding="utf-8")
    (lectures / "11 - Approach to First Trimester Bleeding & Ultrasound.md").write_text("# b\n", encoding="utf-8")
    (tmp_path / "Attachments").mkdir()
    return tmp_path


def test_find_note_by_substring(tmp_path):
    vault = make_vault(tmp_path)
    found = ig.find_note(vault, "pathology of 1st trimester")
    assert found.name == "09 - Pathology of 1st Trimester Bleeding.md"


def test_find_note_accepts_a_path(tmp_path):
    vault = make_vault(tmp_path)
    target = next(vault.rglob("09 - *.md"))
    assert ig.find_note(vault, str(target)) == target


def test_find_note_refuses_ambiguity(tmp_path):
    vault = make_vault(tmp_path)
    with pytest.raises(ValueError) as err:
        ig.find_note(vault, "trimester bleeding")
    assert "09 - Pathology" in str(err.value)
    assert "11 - Approach" in str(err.value)


def test_find_note_missing(tmp_path):
    vault = make_vault(tmp_path)
    with pytest.raises(FileNotFoundError):
        ig.find_note(vault, "no such lecture")


OBSIDIAN = """---
type: LectureNote
tags: LectureNote, -nograph
---
# Overview chart: <u>Pathology of first trimester bleeding</u>

**Three causes** worked up by **[[beta hCG|β-hCG]] + ultrasound**.

![[hydatidiform mole.png|600]]

| | **[[spontaneous abortion\\|Spontaneous abortion]]** | [[ectopic pregnancy]] |
| --- | --- | --- |
| **Causes** | <mark class="hltr-orange">PID</mark> · <font color="#e424b7">cyto</font> | x |

> [!multi-column]
>> [!pink] Maternal
>> - basal plate
>
>> [!purple] Fetal
>> - chorionic plate

> [!check] Objectives
> 1. Describe implantation
"""


def test_clean_markdown_strips_obsidian_syntax():
    out = ig.clean_markdown(OBSIDIAN)
    for bad in ("[[", "]]", "![[", "<u>", "<mark", "<font", "[!pink]", "[!multi-column]", "type: LectureNote"):
        assert bad not in out, bad
    assert "β-hCG" in out
    assert "Spontaneous abortion" in out
    assert "ectopic pregnancy" in out
    assert "PID" in out and "cyto" in out
    assert "Maternal" in out and "basal plate" in out
    assert "Objectives" in out and "Describe implantation" in out
    assert "hydatidiform mole.png" not in out
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/repos/preclerkship && python -m pytest tools/tests -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'infographic'`

- [ ] **Step 3: Write the module with the first two functions**

```python
# tools/infographic.py
# -*- coding: utf-8 -*-
"""Generate a poster-style study infographic of one lecture note with Gemini's image model.

Purpose: the NotebookLM "Infographic" button without NotebookLM - no browser
         cookies, no third-party login; one scoped API key that can only call
         the Gemini API and can be revoked in a click.
Author:  Noor Simsam
Date:    2026-09-29
Input:   a medwiki lecture note ($MEDWIKI_VAULT/01 - Lectures/**), read-only
         unless --embed; $GEMINI_API_KEY in the environment
Output:  <vault>/Attachments/<note stem> (generated infographic).png, and with
         --embed one ![[...]] line inserted at the end of the note's chart region

Slides are the gold standard. The picture this writes is a study aid drawn by
an image model from the note, and image models garble small text, so the
filename says "generated infographic" and every number on it is to be checked
against the slides before it is trusted. It never becomes a source of truth.

Run from the repo root:

    python tools/infographic.py "pathology of 1st trimester"            # writes the PNG
    python tools/infographic.py "pathology of 1st trimester" --dry-run  # prints the prompt only
    python tools/infographic.py "pathology of 1st trimester" --embed    # also inserts the embed
"""

import argparse
import base64
import logging
import os
import re
import sys
import time
from pathlib import Path

import requests

LOG = logging.getLogger("infographic")

VAULT = Path(os.environ.get("MEDWIKI_VAULT", "/mnt/c/Users/nsims/medwiki"))
LECTURES = "01 - Lectures"
ATTACHMENTS = "Attachments"
SUFFIX = " (generated infographic).png"

MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
KEY_VAR = "GEMINI_API_KEY"
RETRIES = 3
RETRY_STATUSES = (429, 500, 503)
TIMEOUT_S = 180


def find_note(vault: Path, query: str) -> Path:
    """Resolve a lecture note from a path or a filename fragment.

    Parameters
    ----------
    vault : Path
        The medwiki vault root.
    query : str
        Either a path to an existing ``.md`` file, or a case-insensitive
        substring of a note filename under ``<vault>/01 - Lectures``.

    Returns
    -------
    Path
        The single matching note.

    Raises
    ------
    FileNotFoundError
        No note matches.
    ValueError
        More than one note matches; the message lists them all.
    """
    as_path = Path(query)
    if as_path.suffix == ".md" and as_path.is_file():
        return as_path
    needle = query.lower()
    matches = sorted(
        p for p in (vault / LECTURES).rglob("*.md") if needle in p.name.lower()
    )
    if not matches:
        raise FileNotFoundError(f"no lecture note matching {query!r} under {vault / LECTURES}")
    if len(matches) > 1:
        listing = "\n  ".join(str(p.relative_to(vault)) for p in matches)
        raise ValueError(f"{len(matches)} notes match {query!r}; be more specific:\n  {listing}")
    return matches[0]


# Order matters: embeds before wikilinks (an embed is a wikilink with a bang),
# escaped table pipes before the alias split, tags last so their text survives.
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
_EMBED = re.compile(r"!\[\[[^\]]*\]\]")
_ALIASED_LINK = re.compile(r"\[\[[^\]|]*\|([^\]]*)\]\]")
_PLAIN_LINK = re.compile(r"\[\[([^\]]*)\]\]")
_CALLOUT_TAG = re.compile(r"\[![\w-]+(\|[\w-]+)?\]\s*")
_QUOTE_PREFIX = re.compile(r"^(>\s*)+", re.M)
_HTML_TAG = re.compile(r"<[^>]+>")
_BLANK_RUN = re.compile(r"\n{3,}")


def clean_markdown(text: str) -> str:
    """Turn Obsidian markdown into plain text an image model can read.

    Drops frontmatter and image embeds; keeps the display text of wikilinks,
    the contents of callouts and HTML spans, and all table cells.
    """
    text = _FRONTMATTER.sub("", text)
    text = _EMBED.sub("", text)
    text = text.replace("\\|", "|")
    text = _ALIASED_LINK.sub(r"\1", text)
    text = _PLAIN_LINK.sub(r"\1", text)
    text = _CALLOUT_TAG.sub("", text)
    text = _QUOTE_PREFIX.sub("", text)
    text = _HTML_TAG.sub("", text)
    text = _BLANK_RUN.sub("\n\n", text)
    return text.strip() + "\n"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/repos/preclerkship && python -m pytest tools/tests -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
cd ~/repos/preclerkship
git add tools/infographic.py tools/tests/__init__.py tools/tests/test_infographic.py
git commit -m "Add infographic.py: find and clean a lecture note"
```

---

### Task 2: Build the focus prompt and the `--dry-run` CLI

**Files:**
- Modify: `tools/infographic.py`
- Modify: `tools/tests/test_infographic.py`

**Interfaces:**
- Consumes: `find_note`, `clean_markdown` from Task 1.
- Produces: `build_prompt(title: str, note_text: str, detail: str = "detailed") -> str` — the full text sent to the model. `detail` is `"concise"` or `"detailed"`; anything else raises `ValueError`.
- Produces: `main(argv: list[str] | None = None) -> int` with flags `query`, `--dry-run`, `--detail {concise,detailed}`, `--embed`, `--force`, `--out PATH`. In this task only `--dry-run` has to work end to end; the other flags are parsed and wired in Tasks 3 and 4.

- [ ] **Step 1: Write the failing tests**

Append to `tools/tests/test_infographic.py`:

```python
def test_build_prompt_carries_title_note_and_rules():
    prompt = ig.build_prompt("Pathology of first trimester bleeding", "Complete mole: 46 XX.\n", "detailed")
    assert "Pathology of first trimester bleeding" in prompt
    assert "Complete mole: 46 XX." in prompt
    assert "only facts from the source" in prompt.lower() or "only facts in the source" in prompt.lower()
    assert "portrait" in prompt.lower()
    assert "detailed" in prompt.lower()


def test_build_prompt_concise_differs():
    a = ig.build_prompt("T", "body\n", "concise")
    b = ig.build_prompt("T", "body\n", "detailed")
    assert a != b
    assert "concise" in a.lower()


def test_build_prompt_rejects_unknown_detail():
    with pytest.raises(ValueError):
        ig.build_prompt("T", "body\n", "lavish")


def test_dry_run_prints_prompt_and_writes_nothing(tmp_path, monkeypatch, capsys):
    vault = make_vault(tmp_path)
    monkeypatch.setattr(ig, "VAULT", vault)
    monkeypatch.delenv(ig.KEY_VAR, raising=False)
    rc = ig.main(["pathology of 1st", "--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Pathology of 1st Trimester Bleeding" in out
    assert not list((vault / "Attachments").iterdir())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/repos/preclerkship && python -m pytest tools/tests -v`
Expected: 4 new FAIL with `AttributeError: module 'infographic' has no attribute 'build_prompt'` / `'main'`

- [ ] **Step 3: Add `build_prompt` and `main`**

Append to `tools/infographic.py`:

```python
DETAIL_LEVELS = {
    "concise": (
        "Concise: at most six panels, headline facts only, large type. "
        "Prefer one comparison table or one decision flow over many small boxes."
    ),
    "detailed": (
        "Detailed: a decision flow at the top, then one panel per entity with its key "
        "mechanism, pathology, presentation and numbers, then a strip of high-yield traps "
        "and exam discriminators at the bottom."
    ),
}

PROMPT_TEMPLATE = """Design a single portrait study infographic for a second-year medical student.

Topic: {title}

Layout instructions. {detail_rule}
Use a clean, modern medical-education style: white or very pale background, a restrained
palette of two or three accent colours, clear panel borders, generous margins, simple flat
icons only where they aid recall. All text must be large enough to read on a phone; never
render text smaller than a caption. Spell every medical term exactly as the source spells it.

Content rules. Use only facts from the source below; do not add, infer or round any number,
percentage, gene, drug or chromosome count. Lead with whatever the source marks as the
overview or chart. Where the source compares entities in a table, keep that comparison
side by side. Where the source gives a workup or decision sequence, draw it as a flow.
If a fact does not fit, leave it out rather than compress it into unreadable text.

Source:
{note}
"""


def build_prompt(title: str, note_text: str, detail: str = "detailed") -> str:
    """Compose the generation prompt from the note and the detail level.

    Parameters
    ----------
    title : str
        Human title of the lecture, used as the poster heading.
    note_text : str
        The cleaned note (from ``clean_markdown``).
    detail : str
        ``"concise"`` or ``"detailed"``.

    Raises
    ------
    ValueError
        Unknown detail level.
    """
    if detail not in DETAIL_LEVELS:
        raise ValueError(f"detail must be one of {sorted(DETAIL_LEVELS)}, not {detail!r}")
    return PROMPT_TEMPLATE.format(title=title, detail_rule=DETAIL_LEVELS[detail], note=note_text)


def note_title(path: Path) -> str:
    """Strip the ``NN - `` ordering prefix off a lecture filename."""
    return re.sub(r"^\d+\s*-\s*", "", path.stem)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("query", help="lecture note path, or a fragment of its filename")
    parser.add_argument("--dry-run", action="store_true", help="print the prompt; do not call the API")
    parser.add_argument("--detail", choices=sorted(DETAIL_LEVELS), default="detailed")
    parser.add_argument("--embed", action="store_true", help="insert the ![[...]] into the note")
    parser.add_argument("--force", action="store_true", help="overwrite an existing PNG")
    parser.add_argument("--out", type=Path, default=None, help="write the PNG here instead of Attachments/")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)
    try:
        note = find_note(VAULT, args.query)
    except (FileNotFoundError, ValueError) as err:
        LOG.error("%s", err)
        return 2
    prompt = build_prompt(note_title(note), clean_markdown(note.read_text(encoding="utf-8")), args.detail)
    if args.dry_run:
        print(prompt)
        return 0
    LOG.error("generation is not wired up yet")  # replaced in Task 3
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/repos/preclerkship && python -m pytest tools/tests -v`
Expected: 9 PASS

- [ ] **Step 5: Try it on the real note**

Run: `cd ~/repos/preclerkship && python tools/infographic.py "pathology of 1st trimester" --dry-run | head -40`
Expected: the prompt, heading `Topic: Pathology of 1st Trimester Bleeding`, followed by clean prose starting `Overview chart: Pathology of first trimester bleeding` with no `[[` anywhere. Then: `python tools/infographic.py "pathology of 1st trimester" --dry-run | grep -c '\[\['` → `0`.

- [ ] **Step 6: Commit**

```bash
cd ~/repos/preclerkship
git add tools/infographic.py tools/tests/test_infographic.py
git commit -m "infographic.py: build the prompt, add --dry-run"
```

---

### Task 3: Call Gemini and decode the image

**Files:**
- Modify: `tools/infographic.py`
- Modify: `tools/tests/test_infographic.py`

**Interfaces:**
- Consumes: `build_prompt`, `MODEL`, `ENDPOINT`, `KEY_VAR`, `RETRIES`, `RETRY_STATUSES`, `TIMEOUT_S`.
- Produces: `generate_image(prompt: str, api_key: str, model: str = MODEL, sleep=time.sleep) -> bytes` — PNG bytes. Raises `RuntimeError` on a non-retryable HTTP error, on retries exhausted, or on a 200 with no image part (message includes any text the model returned).
- Produces: `class ApiKeyMissing(RuntimeError)`.
- Produces: `read_api_key() -> str` — from `os.environ[KEY_VAR]`, raises `ApiKeyMissing` with instructions.

- [ ] **Step 0: Confirm the request and response shape against the live docs**

Before writing code, fetch `https://ai.google.dev/gemini-api/docs/image-generation` and confirm three things, adjusting the constants in Step 3 if they differ: (a) the current model id for image output (default here `gemini-2.5-flash-image`), (b) that `generationConfig.responseModalities: ["TEXT","IMAGE"]` and `generationConfig.imageConfig.aspectRatio` are the field names, (c) that the image comes back as `candidates[0].content.parts[i].inlineData.{mimeType,data}` base64. Note what you found in the commit message. The tests below encode this shape; if the docs disagree, change the code **and** the fixture together.

- [ ] **Step 1: Write the failing tests**

Append to `tools/tests/test_infographic.py`:

```python
import base64


class FakeResponse:
    def __init__(self, status: int, payload: dict | None = None, text: str = ""):
        self.status_code = status
        self._payload = payload or {}
        self.text = text or str(payload)

    def json(self):
        return self._payload


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake"


def image_payload() -> dict:
    return {"candidates": [{"content": {"parts": [
        {"text": "Here is your infographic."},
        {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(PNG_BYTES).decode()}},
    ]}}]}


def test_generate_image_returns_png_bytes(monkeypatch):
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append((url, headers, json))
        return FakeResponse(200, image_payload())

    monkeypatch.setattr(ig.requests, "post", fake_post)
    out = ig.generate_image("draw", "KEY123", model="m-test")
    assert out == PNG_BYTES
    url, headers, body = calls[0]
    assert url.endswith("/models/m-test:generateContent")
    assert headers["x-goog-api-key"] == "KEY123"
    assert body["contents"][0]["parts"][0]["text"] == "draw"
    assert "IMAGE" in body["generationConfig"]["responseModalities"]


def test_generate_image_retries_then_succeeds(monkeypatch):
    seq = [FakeResponse(429, text="slow down"), FakeResponse(503, text="busy"), FakeResponse(200, image_payload())]
    slept = []
    monkeypatch.setattr(ig.requests, "post", lambda *a, **k: seq.pop(0))
    out = ig.generate_image("draw", "K", sleep=slept.append)
    assert out == PNG_BYTES
    assert len(slept) == 2


def test_generate_image_gives_up_after_retries(monkeypatch):
    monkeypatch.setattr(ig.requests, "post", lambda *a, **k: FakeResponse(429, text="quota"))
    with pytest.raises(RuntimeError) as err:
        ig.generate_image("draw", "K", sleep=lambda s: None)
    assert "429" in str(err.value) and "quota" in str(err.value)


def test_generate_image_fails_fast_on_400(monkeypatch):
    posts = []
    monkeypatch.setattr(ig.requests, "post", lambda *a, **k: posts.append(1) or FakeResponse(400, text="bad key"))
    with pytest.raises(RuntimeError) as err:
        ig.generate_image("draw", "K", sleep=lambda s: None)
    assert "400" in str(err.value) and len(posts) == 1


def test_generate_image_text_only_is_an_error(monkeypatch):
    payload = {"candidates": [{"content": {"parts": [{"text": "I cannot draw that."}]}}]}
    monkeypatch.setattr(ig.requests, "post", lambda *a, **k: FakeResponse(200, payload))
    with pytest.raises(RuntimeError) as err:
        ig.generate_image("draw", "K")
    assert "I cannot draw that." in str(err.value)


def test_read_api_key_missing(monkeypatch):
    monkeypatch.delenv(ig.KEY_VAR, raising=False)
    with pytest.raises(ig.ApiKeyMissing) as err:
        ig.read_api_key()
    assert "aistudio.google.com" in str(err.value)


def test_read_api_key_present(monkeypatch):
    monkeypatch.setenv(ig.KEY_VAR, "abc")
    assert ig.read_api_key() == "abc"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/repos/preclerkship && python -m pytest tools/tests -v`
Expected: 7 new FAIL with `AttributeError` on `generate_image` / `ApiKeyMissing` / `read_api_key`

- [ ] **Step 3: Implement the API call**

Insert into `tools/infographic.py` after `clean_markdown` and before `DETAIL_LEVELS`:

```python
class ApiKeyMissing(RuntimeError):
    """GEMINI_API_KEY is not set."""


def read_api_key() -> str:
    """Read the Gemini key from the environment; never from a file or an argument."""
    key = os.environ.get(KEY_VAR, "").strip()
    if not key:
        raise ApiKeyMissing(
            f"{KEY_VAR} is not set. Create a key at https://aistudio.google.com (Get API key), "
            f"then: echo 'export {KEY_VAR}=<key>' >> ~/.bashrc and open a new terminal. "
            "The key can only call the Gemini API and can be revoked on the same page."
        )
    return key


def _extract_image(payload: dict) -> bytes:
    """Pull the first inline image out of a generateContent response, or raise."""
    texts: list[str] = []
    for candidate in payload.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
            if part.get("text"):
                texts.append(part["text"])
    reason = " / ".join(texts) if texts else str(payload)[:500]
    raise RuntimeError(f"the model returned no image. It said: {reason}")


def generate_image(prompt: str, api_key: str, model: str = MODEL, sleep=time.sleep) -> bytes:
    """POST the prompt to Gemini's generateContent and return PNG bytes.

    Parameters
    ----------
    prompt : str
        Output of ``build_prompt``.
    api_key : str
        Output of ``read_api_key``. Sent in the ``x-goog-api-key`` header only.
    model : str
        Gemini image-capable model id.
    sleep : callable
        Injected for tests; receives the backoff in seconds.

    Raises
    ------
    RuntimeError
        Non-retryable HTTP status, retries exhausted, or a text-only answer.
    """
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": "3:4"},
        },
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    url = ENDPOINT.format(model=model)
    last = None
    for attempt in range(RETRIES):
        resp = requests.post(url, headers=headers, json=body, timeout=TIMEOUT_S)
        if resp.status_code == 200:
            return _extract_image(resp.json())
        last = resp
        if resp.status_code not in RETRY_STATUSES:
            break
        wait = 5 * (2 ** attempt)
        LOG.warning("HTTP %s from Gemini, retrying in %ss (%s/%s)", resp.status_code, wait, attempt + 1, RETRIES)
        sleep(wait)
    raise RuntimeError(f"Gemini returned HTTP {last.status_code}: {last.text[:500]}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/repos/preclerkship && python -m pytest tools/tests -v`
Expected: 16 PASS

- [ ] **Step 5: Commit**

```bash
cd ~/repos/preclerkship
git add tools/infographic.py tools/tests/test_infographic.py
git commit -m "infographic.py: call Gemini generateContent with retry, decode the PNG"
```

---

### Task 4: Write the PNG, optionally embed it, finish the CLI

**Files:**
- Modify: `tools/infographic.py`
- Modify: `tools/tests/test_infographic.py`
- Modify: `tools/README.md` (append a section)

**Interfaces:**
- Consumes: everything above.
- Produces: `output_path(vault: Path, note: Path, out: Path | None) -> Path` — `out` if given, else `<vault>/Attachments/<note.stem><SUFFIX>`.
- Produces: `embed_in_note(note: Path, image_name: str) -> bool` — inserts `![[<image_name>]]` on its own line just before the first `\n---\n` that follows the H1 (the end of the chart region); if no such separator, appends at end. Returns `False` and changes nothing if the line is already present.
- Produces: `main` fully wired: key → prompt → generate → write → embed.

- [ ] **Step 1: Write the failing tests**

Append to `tools/tests/test_infographic.py`:

```python
def test_output_path_default_and_override(tmp_path):
    vault = make_vault(tmp_path)
    note = next(vault.rglob("09 - *.md"))
    default = ig.output_path(vault, note, None)
    assert default.parent == vault / "Attachments"
    assert default.name == "09 - Pathology of 1st Trimester Bleeding (generated infographic).png"
    assert ig.output_path(vault, note, tmp_path / "x.png") == tmp_path / "x.png"


CHART_NOTE = """---
type: LectureNote
---
# Overview chart: Thing

table here

**High-yield discriminators:** stuff

---

> [!check] Objectives
> 1. one

# Body
"""


def test_embed_in_note_inserts_before_chart_separator(tmp_path):
    note = tmp_path / "n.md"
    note.write_text(CHART_NOTE, encoding="utf-8")
    assert ig.embed_in_note(note, "n (generated infographic).png") is True
    text = note.read_text(encoding="utf-8")
    embed_at = text.index("![[n (generated infographic).png]]")
    assert embed_at < text.index("\n---\n\n> [!check]")
    assert embed_at > text.index("High-yield discriminators")


def test_embed_in_note_is_idempotent(tmp_path):
    note = tmp_path / "n.md"
    note.write_text(CHART_NOTE, encoding="utf-8")
    ig.embed_in_note(note, "pic.png")
    once = note.read_text(encoding="utf-8")
    assert ig.embed_in_note(note, "pic.png") is False
    assert note.read_text(encoding="utf-8") == once
    assert once.count("![[pic.png]]") == 1


def test_embed_in_note_appends_when_no_separator(tmp_path):
    note = tmp_path / "n.md"
    note.write_text("# Only a heading\n\nprose\n", encoding="utf-8")
    ig.embed_in_note(note, "pic.png")
    assert note.read_text(encoding="utf-8").endswith("![[pic.png]]\n")


def test_main_writes_png_and_embeds(tmp_path, monkeypatch):
    vault = make_vault(tmp_path)
    note = next(vault.rglob("09 - *.md"))
    note.write_text(CHART_NOTE, encoding="utf-8")
    monkeypatch.setattr(ig, "VAULT", vault)
    monkeypatch.setenv(ig.KEY_VAR, "k")
    monkeypatch.setattr(ig.requests, "post", lambda *a, **k: FakeResponse(200, image_payload()))
    rc = ig.main(["pathology of 1st", "--embed"])
    assert rc == 0
    png = vault / "Attachments" / "09 - Pathology of 1st Trimester Bleeding (generated infographic).png"
    assert png.read_bytes() == PNG_BYTES
    assert "![[09 - Pathology of 1st Trimester Bleeding (generated infographic).png]]" in note.read_text(encoding="utf-8")


def test_main_refuses_to_overwrite_without_force(tmp_path, monkeypatch):
    vault = make_vault(tmp_path)
    png = vault / "Attachments" / "09 - Pathology of 1st Trimester Bleeding (generated infographic).png"
    png.write_bytes(b"old")
    monkeypatch.setattr(ig, "VAULT", vault)
    monkeypatch.setenv(ig.KEY_VAR, "k")
    monkeypatch.setattr(ig.requests, "post", lambda *a, **k: FakeResponse(200, image_payload()))
    assert ig.main(["pathology of 1st"]) == 3
    assert png.read_bytes() == b"old"
    assert ig.main(["pathology of 1st", "--force"]) == 0
    assert png.read_bytes() == PNG_BYTES


def test_main_without_key_exits_cleanly(tmp_path, monkeypatch):
    vault = make_vault(tmp_path)
    monkeypatch.setattr(ig, "VAULT", vault)
    monkeypatch.delenv(ig.KEY_VAR, raising=False)
    assert ig.main(["pathology of 1st"]) == 4
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/repos/preclerkship && python -m pytest tools/tests -v`
Expected: 7 new FAIL (`output_path` / `embed_in_note` missing; `main` returns 1)

- [ ] **Step 3: Add the writers and finish `main`**

Insert before `parse_args` in `tools/infographic.py`:

```python
def output_path(vault: Path, note: Path, out: Path | None) -> Path:
    """Where the PNG goes: ``--out`` if given, else the vault's Attachments folder."""
    return out if out is not None else vault / ATTACHMENTS / f"{note.stem}{SUFFIX}"


_CHART_END = re.compile(r"\n---\n")


def embed_in_note(note: Path, image_name: str) -> bool:
    """Insert ``![[image_name]]`` at the end of the note's chart region.

    The chart region is everything between the H1 and the first ``---`` rule
    after it. Returns False, touching nothing, if the embed is already there.
    """
    text = note.read_text(encoding="utf-8")
    line = f"![[{image_name}]]"
    if line in text:
        return False
    h1 = text.find("\n# ")
    start = h1 + 1 if h1 >= 0 else 0
    match = _CHART_END.search(text, start)
    if match:
        text = text[: match.start()] + f"\n\n{line}" + text[match.start():]
    else:
        text = text.rstrip("\n") + f"\n\n{line}\n"
    note.write_text(text, encoding="utf-8")
    return True
```

Replace the tail of `main` (from `if args.dry_run:` to `return 1`) with:

```python
    if args.dry_run:
        print(prompt)
        return 0
    target = output_path(VAULT, note, args.out)
    if target.exists() and not args.force:
        LOG.error("%s exists; pass --force to overwrite it", target)
        return 3
    try:
        key = read_api_key()
    except ApiKeyMissing as err:
        LOG.error("%s", err)
        return 4
    LOG.info("asking %s for a %s infographic of %r", MODEL, args.detail, note_title(note))
    try:
        png = generate_image(prompt, key)
    except RuntimeError as err:
        LOG.error("%s", err)
        return 5
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(png)
    LOG.info("wrote %s (%d KB)", target, len(png) // 1024)
    if args.embed and embed_in_note(note, target.name):
        LOG.info("embedded in %s", note.name)
    print(target)
    return 0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/repos/preclerkship && python -m pytest tools/tests -v`
Expected: 23 PASS

- [ ] **Step 5: Document it**

Append to `tools/README.md`:

```markdown
---

## Infographics without NotebookLM

`infographic.py` is the NotebookLM "Infographic" button with the login taken
out: it reads one lecture note, cleans the Obsidian syntax off it, and asks
Gemini's image model for a portrait study poster, which lands in the vault's
`Attachments/` as `<note> (generated infographic).png`. It needs `requests`
and a `GEMINI_API_KEY` in the environment (make one at aistudio.google.com;
it can only call the Gemini API and is revoked on the same page). It never
reads browser cookies.

```bash
python tools/infographic.py "pathology of 1st trimester" --dry-run   # see the prompt
python tools/infographic.py "pathology of 1st trimester"             # write the PNG
python tools/infographic.py "pathology of 1st trimester" --embed     # and link it under the chart
```

Slides are the gold standard. The picture is drawn by an image model and image
models garble small text, so check every number on it against the slides; the
filename says "generated infographic" so it is never mistaken for one. Tests:
`python -m pytest tools/tests -v`.
```

- [ ] **Step 6: Commit**

```bash
cd ~/repos/preclerkship
git add tools/infographic.py tools/tests/test_infographic.py tools/README.md
git commit -m "infographic.py: write the PNG, --embed, --force; document it"
```

---

### Task 5: Live run (only when `GEMINI_API_KEY` is set)

**Files:** none changed.

- [ ] **Step 1: Check for the key without printing it**

Run: `[ -n "$GEMINI_API_KEY" ] && echo set || echo unset`
If `unset`: stop here and report that Tasks 1-4 are done and tested, and that the live run is waiting on the key. Do not attempt any other way of obtaining credentials.

- [ ] **Step 2: Generate the first infographic**

Run: `cd ~/repos/preclerkship && python tools/infographic.py "pathology of 1st trimester"`
Expected: `INFO wrote /mnt/c/Users/nsims/medwiki/Attachments/09 - Pathology of 1st Trimester Bleeding (generated infographic).png (N KB)` and the path on stdout. Open the PNG with the Read tool and check: five entities present, complete mole 46 XX/XY vs partial 69 XXX/XXY, choriocarcinoma "no villi", ">90% lung metastases". Report any garbled number verbatim; do not fix it in the image.

- [ ] **Step 3: Do not `--embed` and do not commit anything to the vault.** The user decides whether the picture goes in the note after seeing it.
