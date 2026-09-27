# -*- coding: utf-8 -*-
"""Read OneNote pages from the local desktop app, with no Graph API and no login.

The Graph route (the ms365 MCP server) needs a live token, and that token has
been refused since 2026-09-07 with AADSTS50158 — a Duo challenge on a stale
refresh token. This script does not touch the network at all. It drives the
installed OneNote desktop app through its COM automation interface, which is
already signed in and holds the same notebooks.

Two things come back that the Graph route made hard:

  * **Her typed notes**, as ``<one:T>`` blocks — the half of a page that is hers
    rather than the lecturer's, and the half worth carrying into a vault note.
  * **The slide text**, as ``<one:OCRText>`` — OneNote has already run OCR over
    every slide printout, so the words on the slides are plain text here. Over
    Graph these were images that had to be downloaded and read one by one.

Usage, from the repo root::

    python tools/onenote_local.py list                       # every notebook
    python tools/onenote_local.py list "Principles of Medicine 2"
    python tools/onenote_local.py page "<page id>"           # one page, as text
    python tools/onenote_local.py page --find "hypothyroid"  # or by title match

Requires Windows OneNote (Office 16) reachable as ``powershell.exe`` — true from
WSL, which is where this runs. If the app is closed, COM starts it.

If COM is ever unavailable, the fallback is the automatic backups under
``%LOCALAPPDATA%/Microsoft/OneNote/16.0/Backup``: ``strings -el`` on a ``.one``
section file yields the same text without any app at all, but loses the page
structure that separates her notes from the slides.
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
import os
import tempfile
from pathlib import Path
from typing import Iterator, NamedTuple

# hsPages — notebooks, section groups, sections and pages, the whole tree
HIERARCHY_SCOPE_PAGES = 4

PS = "powershell.exe"


class Page(NamedTuple):
    """One OneNote page, located by its path through the notebook tree."""

    path: str
    title: str
    page_id: str


def _run_powershell(script: str) -> str:
    """Run a PowerShell snippet on the Windows side and return its stdout.

    Raises
    ------
    RuntimeError
        If PowerShell is missing, or the snippet fails. COM errors surface as
        a ``COM-ERR:`` line, which is turned into the exception message.
    """
    try:
        done = subprocess.run(
            [PS, "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=180,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "powershell.exe not found — this needs to run where Windows "
            "OneNote is installed (WSL on her laptop)."
        )
    out = done.stdout.strip()
    if out.startswith("COM-ERR:") or done.returncode != 0:
        raise RuntimeError(out or done.stderr.strip() or "PowerShell failed")
    return out


def _com_preamble(body: str) -> str:
    """Wrap a snippet so COM failures come back as one readable line."""
    return (
        '$ErrorActionPreference="Stop"; try { '
        '$on = New-Object -ComObject OneNote.Application; ' + body +
        ' } catch { "COM-ERR: " + $_.Exception.Message }'
    )


def list_pages(notebook: str | None = None) -> list[Page]:
    """Walk the notebook tree and return every page in it.

    Parameters
    ----------
    notebook : str or None
        Restrict to one notebook by exact name. ``None`` walks them all.
    """
    where = ""
    if notebook:
        safe = notebook.replace("'", "''")
        where = "| Where-Object { $_.name -eq '%s' }" % safe
    body = (
        '$xml=""; $on.GetHierarchy("", %d, [ref]$xml); $d=[xml]$xml; '
        'function Walk($n,$p){ '
        '  foreach($sg in $n.SectionGroup){ Walk $sg ($p+"/"+$sg.name) } '
        '  foreach($s in $n.Section){ foreach($pg in $s.Page){ '
        '    "{0}/{1}|@|{2}|@|{3}" -f $p,$s.name,$pg.name,$pg.ID } } }; '
        'foreach($nb in ($d.Notebooks.Notebook %s)){ Walk $nb $nb.name }'
        % (HIERARCHY_SCOPE_PAGES, where)
    )
    pages: list[Page] = []
    for line in _run_powershell(_com_preamble(body)).splitlines():
        parts = line.split("|@|")
        if len(parts) == 3:
            pages.append(Page(parts[0], parts[1], parts[2]))
    return pages


def _windows_path(path: Path) -> str:
    """Express a path the way the Windows side of the fence will understand it.

    Under WSL that means translating with ``wslpath``; under a native Windows
    interpreter the path is already Windows-shaped and needs nothing.
    """
    if not str(path).startswith("/"):
        return str(path)
    try:
        done = subprocess.run(["wslpath", "-w", str(path)],
                              capture_output=True, text=True)
        if done.returncode == 0 and done.stdout.strip():
            return done.stdout.strip()
    except FileNotFoundError:
        pass
    return r"C:\Windows\Temp\onenote_local_page.xml"


def fetch_page_xml(page_id: str) -> str:
    """Return one page's raw OneNote XML.

    The XML is written to a temp file on the Windows side rather than returned
    through stdout: a lecture page runs to roughly a megabyte, and the console
    mangles it.
    """
    # one file per call: a shared name let two concurrent calls read back each
    # other's page, silently, since both files parse as a valid lecture
    fd, name = tempfile.mkstemp(prefix="onenote_local_", suffix=".xml")
    os.close(fd)
    tmp = Path(name)
    win_tmp = _windows_path(tmp)
    safe_id = page_id.replace("'", "''")
    body = (
        '$c=""; $on.GetPageContent(\'%s\',[ref]$c,0); '
        '$c | Out-File -Encoding utf8 \'%s\'; "ok"'
        % (safe_id, win_tmp.replace("'", "''"))
    )
    try:
        _run_powershell(_com_preamble(body))
        return tmp.read_text(encoding="utf-8-sig")
    finally:
        tmp.unlink(missing_ok=True)


def _strip_markup(fragment: str) -> str:
    """OneNote wraps typed runs in spans; keep the words, drop the styling."""
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def typed_notes(page_xml: str) -> Iterator[str]:
    """Yield her own typed text blocks, in page order.

    These are the ``<one:T>`` elements — everything she wrote on the page, as
    opposed to the slide printouts she wrote it next to.
    """
    for block in re.findall(r"<one:T><!\[CDATA\[(.*?)\]\]></one:T>", page_xml, re.S):
        text = _strip_markup(block)
        if text:
            yield text


def slide_text(page_xml: str) -> Iterator[str]:
    """Yield the OCR text OneNote has already extracted from each slide image."""
    for block in re.findall(r"<one:OCRText><!\[CDATA\[(.*?)\]\]></one:OCRText>",
                            page_xml, re.S):
        text = _strip_markup(block)
        if text:
            yield text


def _cmd_list(args: argparse.Namespace) -> int:
    for page in list_pages(args.notebook):
        print("%s :: %s :: %s" % (page.path, page.title, page.page_id))
    return 0


def _cmd_page(args: argparse.Namespace) -> int:
    page_id = args.page_id
    if args.find:
        needle = args.find.lower()
        hits = [p for p in list_pages(args.notebook) if needle in p.title.lower()]
        if not hits:
            print("no page title matches %r" % args.find, file=sys.stderr)
            return 1
        if len(hits) > 1:
            print("%d pages match %r:" % (len(hits), args.find), file=sys.stderr)
            for hit in hits:
                print("  %s :: %s" % (hit.path, hit.title), file=sys.stderr)
            return 1
        page_id = hits[0].page_id
        print("# %s :: %s\n" % (hits[0].path, hits[0].title))
    if not page_id:
        print("give a page id, or --find <title fragment>", file=sys.stderr)
        return 1

    page_xml = fetch_page_xml(page_id)
    if args.raw:
        print(page_xml)
        return 0

    print("## typed notes")
    for note in typed_notes(page_xml):
        print(note)
    if args.slides:
        print("\n## slide text (OCR)")
        for text in slide_text(page_xml):
            print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subs = parser.add_subparsers(dest="cmd", required=True)

    p_list = subs.add_parser("list", help="every page, as path :: title :: id")
    p_list.add_argument("notebook", nargs="?", help="restrict to one notebook")
    p_list.set_defaults(func=_cmd_list)

    p_page = subs.add_parser("page", help="one page's text")
    p_page.add_argument("page_id", nargs="?", help="page id from `list`")
    p_page.add_argument("--find", help="locate the page by title fragment instead")
    p_page.add_argument("--notebook", help="narrow --find to one notebook")
    p_page.add_argument("--slides", action="store_true",
                        help="also print the OCR text of the slide printouts")
    p_page.add_argument("--raw", action="store_true", help="dump the page XML")
    p_page.set_defaults(func=_cmd_page)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RuntimeError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
