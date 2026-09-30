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
