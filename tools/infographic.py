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
from collections.abc import Callable
from pathlib import Path

import requests

LOG = logging.getLogger("infographic")

VAULT = Path(os.environ.get("MEDWIKI_VAULT", "/mnt/c/Users/nsims/medwiki"))
LECTURES = "01 - Lectures"
ATTACHMENTS = "Attachments"
SUFFIX = " (generated infographic).png"

# gemini-2.5-flash-image is still served but now limited to accounts that already
# used it, so a new key starts on the current stable Flash image model.
MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
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

    Parameters
    ----------
    text : str
        The raw note, frontmatter included.

    Returns
    -------
    str
        Plain text ending in exactly one newline.
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


class ApiKeyMissing(RuntimeError):
    """GEMINI_API_KEY is not set."""


def read_api_key() -> str:
    """Read the Gemini key from the environment; never from a file or an argument.

    Returns
    -------
    str
        The key, stripped of surrounding whitespace.

    Raises
    ------
    ApiKeyMissing
        The variable is unset or blank; the message says how to make a key.
    """
    key = os.environ.get(KEY_VAR, "").strip()
    if not key:
        raise ApiKeyMissing(
            f"{KEY_VAR} is not set. Create a key at https://aistudio.google.com (Get API key), "
            f"then: echo 'export {KEY_VAR}=<key>' >> ~/.bashrc and open a new terminal. "
            "The key can only call the Gemini API and can be revoked on the same page."
        )
    return key


def _extract_image(payload: dict) -> bytes:
    """Pull the first inline image out of a generateContent response, or raise.

    Parameters
    ----------
    payload : dict
        The decoded JSON body of a 200 response.

    Returns
    -------
    bytes
        The decoded image.

    Raises
    ------
    RuntimeError
        No part carries image data; the message quotes whatever text came back.
    """
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


def generate_image(
    prompt: str, api_key: str, model: str = MODEL, sleep: Callable[[float], None] = time.sleep
) -> bytes:
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

    Returns
    -------
    bytes
        The image the model drew.

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
        if resp.status_code not in RETRY_STATUSES or attempt == RETRIES - 1:
            break
        wait = 5 * (2 ** attempt)
        LOG.warning("HTTP %s from Gemini, retrying in %ss (%s/%s)", resp.status_code, wait, attempt + 1, RETRIES)
        sleep(wait)
    raise RuntimeError(f"Gemini returned HTTP {last.status_code}: {last.text[:500]}")


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

    Returns
    -------
    str
        The full text sent to the model.

    Raises
    ------
    ValueError
        Unknown detail level.
    """
    if detail not in DETAIL_LEVELS:
        raise ValueError(f"detail must be one of {sorted(DETAIL_LEVELS)}, not {detail!r}")
    return PROMPT_TEMPLATE.format(title=title, detail_rule=DETAIL_LEVELS[detail], note=note_text)


def note_title(path: Path) -> str:
    """Strip the ``NN - `` ordering prefix off a lecture filename.

    Parameters
    ----------
    path : Path
        The lecture note.

    Returns
    -------
    str
        The stem without its leading ordinal, e.g. ``"Pathology of 1st Trimester Bleeding"``.
    """
    return re.sub(r"^\d+\s*-\s*", "", path.stem)


def output_path(vault: Path, note: Path, out: Path | None) -> Path:
    """Where the PNG goes: ``--out`` if given, else the vault's Attachments folder.

    Parameters
    ----------
    vault : Path
        The medwiki vault root.
    note : Path
        The lecture note the picture is drawn from.
    out : Path or None
        An explicit destination, from ``--out``.

    Returns
    -------
    Path
        ``out``, or ``<vault>/Attachments/<note stem> (generated infographic).png``.
    """
    return out if out is not None else vault / ATTACHMENTS / f"{note.stem}{SUFFIX}"


_CHART_END = re.compile(r"\n---\n")


def embed_in_note(note: Path, image_name: str) -> bool:
    """Insert ``![[image_name]]`` at the end of the note's chart region.

    The chart region is everything between the H1 and the first ``---`` rule
    after it. With no such rule the line is appended at the end. The search
    never starts inside the frontmatter, whose closing ``---`` is not a rule.

    Parameters
    ----------
    note : Path
        The lecture note, modified in place.
    image_name : str
        Filename of the picture in Attachments/.

    Returns
    -------
    bool
        True if the line was inserted; False, touching nothing, if it was
        already there.
    """
    text = note.read_text(encoding="utf-8")
    line = f"![[{image_name}]]"
    if line in text:
        return False
    front = _FRONTMATTER.match(text)
    floor = front.end() if front else 0
    h1 = text.find("\n# ", max(floor - 1, 0))
    start = h1 + 1 if h1 >= 0 else floor
    match = _CHART_END.search(text, start)
    if match:
        # A blank line both sides: a line directly above ``---`` would turn it
        # into a setext heading instead of a rule.
        text = text[: match.start()].rstrip("\n") + f"\n\n{line}\n" + text[match.start():]
    else:
        text = text.rstrip("\n") + f"\n\n{line}\n"
    note.write_text(text, encoding="utf-8")
    return True


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the command line.

    Parameters
    ----------
    argv : list of str or None
        Arguments without the program name; ``None`` reads ``sys.argv``.

    Returns
    -------
    argparse.Namespace
        ``query``, ``dry_run``, ``detail``, ``embed``, ``force`` and ``out``.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("query", help="lecture note path, or a fragment of its filename")
    parser.add_argument("--dry-run", action="store_true", help="print the prompt; do not call the API")
    parser.add_argument("--detail", choices=sorted(DETAIL_LEVELS), default="detailed")
    parser.add_argument("--embed", action="store_true", help="insert the ![[...]] into the note")
    parser.add_argument("--force", action="store_true", help="overwrite an existing PNG")
    parser.add_argument("--out", type=Path, default=None, help="write the PNG here instead of Attachments/")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI.

    Parameters
    ----------
    argv : list of str or None
        Arguments without the program name; ``None`` reads ``sys.argv``.

    Returns
    -------
    int
        Exit status: 0 success, 2 note not found or ambiguous, 3 output exists
        without --force, 4 no API key, 5 the API call failed.
    """
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


if __name__ == "__main__":
    sys.exit(main())
