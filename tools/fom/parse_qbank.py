# -*- coding: utf-8 -*-
"""Turn the four FoM Question Bank PDFs into fom/data/questions/b<n>.json.

Purpose: parse the student-written FoM question banks into the portal's
         question schema, answer keys, rationales and figures included.
Author:  Noor Sims
Date:    2026-09-20
Input:   the four "Block N - FoM QBank" PDFs (dir via $FOM_QBANK_DIR)
Output:  fom/data/questions/b1.json .. b4.json, and a parse report on stdout

Why coordinates rather than flat text
-------------------------------------
All four PDFs lay out the same grid: a question number sits at the left margin
(x ~ 72), its stem wraps one indent in (x ~ 93), an option letter sits at a
second indent (x ~ 117) and an option wraps at a third (x ~ 136). Headings are
set in larger type - 28pt for a week, 14pt for a section. Reading x and the
font size makes the parse structural instead of a pile of regexes guessing at
"1.", which matters because these stems are full of sentences that open with a
number and a period, and full of fill-in-the-blank runs of underscores.

Three shapes need the geometry specifically:

* **Extended-match groups.** A left-margin line that is not a number, followed
  by a block of options, followed by a run of bare numbered stems: one option
  list serving several questions. Those stems parse as optionless and are given
  the group's options and its instruction as a preamble.
* **Two-column matching.** The items run down x ~ 122 and the choices down
  x ~ 324. An option column that starts past x = 250 means the question is a
  matching one, which the portal scores by self-report rather than by letter.
* **Figures.** An image block's y puts it between the stem it illustrates and
  that question's first option, so it is attached to whichever question is open
  when the flow reaches it, and written to fom/assets/figures/ by
  question_figures.write_asset - named after its own bytes, so the same picture
  appearing under four questions costs one file.
"""

import io
import json
import os
import re
import sys

import pymupdf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import parse_workbook
import question_figures

QBANK_DIR = os.environ.get(
    "FOM_QBANK_DIR",
    u"/mnt/c/Users/nsims/OneDrive/Documents/Question Bank")

BLOCKS = [
    ("b1", 1, u"Block 1 - FoM QBank 2.1 2025 Version.pdf",  [1, 2, 3, 4]),
    ("b2", 2, u"Block 2 - FoM QBank 2.2 2025 Version.pdf",  [5, 6, 7, 8]),
    ("b3", 3, u"Block 3 - FoM QBank 2.2 2025 Version.pdf",  [9, 10, 11, 12]),
    ("b4", 4, u"Block 4 - FoM QBank 2.1 2025 Version .pdf", [13, 14, 15]),
]

WEEK_LABEL = {
    1:  u"Week 1 - Physicianship, Ethics & Population Health",
    2:  u"Week 2 - Cells, Tissues & Homeostasis",
    3:  u"Week 3 - Genetics, the Newborn & Nutrition",
    4:  u"Week 4 - Child & Adolescent Health, Immunity & Vaccines",
    5:  u"Week 5 - Body Fluids, Blood Pressure & Screening",
    6:  u"Week 6 - Lumps, Bumps & Neoplasia",
    7:  u"Week 7 - Healthy Aging & Geriatrics",
    8:  u"Week 8 - Pharmacology & Therapeutics",
    9:  u"Week 9 - Hematopoiesis & the Anemias",
    10: u"Week 10 - Hemostasis, Bleeding & Thrombosis",
    11: u"Week 11 - White Cells & Leukemia",
    12: u"Week 12 - Adaptive Immunity & Lymphoma",
    13: u"Week 13 - Fever, Microbes & Innate Immunity",
    14: u"Week 14 - Transmission, Antimicrobials & Vaccines",
    15: u"Week 15 - Immunocompromise, Allergy & Autoimmunity",
}

SECTIONS = [
    (u"Module Questions",                          "module",   u"Module questions"),
    (u"Readiness Assessment",                      "ra",       u"Readiness assessment"),
    (u"Self-Assessment",                           "sa",       u"Self-assessment"),
    (u"Questions from the Meds2024 Question Bank", "meds2024", u"Meds 2024 bank"),
    (u"New Questions",                             "new",      u"New questions"),
]
SEC_BY_HEAD = dict((h, k) for h, k, _l in SECTIONS)
SEC_LABEL = dict((k, l) for _h, k, l in SECTIONS)
SEC_ORDER = [k for _h, k, _l in SECTIONS]

SEC_META = {
    "module": (u"The knowledge checks inside the week's Elentra asynchronous learning "
               u"modules, transcribed into the Meds 2025 question bank."),
    "ra": u"The week's Readiness Assessment, as it was sat.",
    "sa": u"The week's Self-Assessment, as it was released.",
    "meds2024": (u"The student-written, instructor-approved bank built by the Class of "
                 u"2024 Academic Directors (December 2020) and re-filed per week by the "
                 u"Meds 2025 volunteers."),
    "new": (u"Written fresh by the Meds 2025 volunteers (December 2021). The bank states "
            u"on its own second page that these were not verified by faculty."),
}

X_MARGIN = 88.0          # question numbers and group instructions live left of this
X_OPTION = 110.0         # option letters start here
X_RIGHTCOL = 250.0       # an option column past this means a two-column matching item
Y_FOOTER = 728.0

NUM_RE    = re.compile(u"^(\\d{1,3})(?:[.)]\\s*|\\s+(?=[A-Z(]))")
OPT_RE    = re.compile(u"^([A-Z]|[a-h])[.)]\\s+\\S")
ROMAN_RE  = re.compile(u"^(i{1,3}|iv|vi{0,3}|ix|x)[.)]\\s+\\S", re.I)
ITEM_RE   = re.compile(u"^\\d{1,3}[.)]\\s+\\S")
# "for the next TWO questions", "for all the questions on this page (28-32)"
COUNT_RE  = re.compile(u"(?:next|following)\\s+(two|three|four|five|six|seven|eight|nine|ten|\\d{1,2})"
                       u"\\s+questions|\\((\\d{1,3})\\s*[-\\u2013]\\s*(\\d{1,3})\\)", re.I)
WORD_N    = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
             "seven": 7, "eight": 8, "nine": 9, "ten": 10}
X_ITEM    = 130.0        # matching items sit deeper than option letters
LEADER_RE = re.compile(u"_{4,}|\\.{5,}")
NAV_RE    = re.compile(u"^\\[To (Answers|Questions)\\]\\s*$")
EMPTY_SEC = re.compile(u"^\\s*(No (RA|SA|R\\.?A\\.?|readiness|self)\\b.*|Not yet released.*|"
                       u"There (is|are) no\\b.*|N/?A\\.?)\\s*$", re.I)
MULTI_RE  = re.compile(u"select all that apply|choose all that apply"
                       u"|select (?:the )?(two|three|four|2|3|4)\\b"
                       u"|\\(select (two|three|four|\\d)\\)", re.I)
MATCH_RE  = re.compile(u"\\bmatch(?:ing)?\\b.*\\b(to|with|the)\\b|\\bmatch the\\b", re.I)
TAGS_RE   = re.compile(u"<[^>]+>")


# --------------------------------------------------------------- extraction

def flow(pdf):
    """Every page as a list of text lines and image blocks, ordered down the page."""
    doc = pymupdf.open(pdf)
    pages = []
    for pno, page in enumerate(doc):
        items = []
        for b in page.get_text("dict")["blocks"]:
            if b["type"] == 1:
                items.append({"t": "img", "y": b["bbox"][1], "x": b["bbox"][0],
                              "w": b["bbox"][2] - b["bbox"][0],
                              "h": b["bbox"][3] - b["bbox"][1],
                              "bytes": b.get("image"), "ext": b.get("ext") or "png"})
                continue
            for line in b["lines"]:
                runs = [(s["text"], bool(s["flags"] & 16), bool(s["flags"] & 2))
                        for s in line["spans"] if s["text"]]
                if not u"".join(r[0] for r in runs).strip():
                    continue
                items.append({"t": "txt", "y": line["bbox"][1], "x": line["bbox"][0],
                              "size": max(s["size"] for s in line["spans"]),
                              "runs": runs, "page": pno + 1})
        items.sort(key=lambda i: (round(i["y"], 1), i["x"]))
        pages.append(items)
    doc.close()
    return pages


# ------------------------------------------------------------------- markup

def esc(s):
    return s.replace(u"&", u"&amp;").replace(u"<", u"&lt;").replace(u">", u"&gt;")


def runs_html(runs):
    """Keep the bold and italic the bank uses to point at the operative word."""
    out = []
    for text, bold, ital in runs:
        t = esc(text)
        if t.strip():
            if bold:
                t = u"<strong>%s</strong>" % t
            if ital:
                t = u"<em>%s</em>" % t
        out.append(t)
    return u"".join(out)


def plain(html):
    t = TAGS_RE.sub(u"", html)
    return (t.replace(u"&amp;", u"&").replace(u"&lt;", u"<").replace(u"&gt;", u">"))


def join(parts):
    """Glue wrapped PDF lines back into running text."""
    out = u""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if not out:
            out = p
        elif re.search(u"[a-z]-(?:</strong>|</em>)*$", out):
            out = re.sub(u"-((?:</strong>|</em>)*)$", u"\\1", out) + p
        else:
            out = out + u" " + p
    out = re.sub(u"\\s{2,}", u" ", out).strip()
    return re.sub(u"(<(?:strong|em)>)\\s*(</(?:strong|em)>)", u"", out)


def drop_prefix(html, n):
    """Drop the first n visible characters of an HTML string, tags left intact."""
    out, seen, i = [], 0, 0
    while i < len(html):
        if html[i] == u"<":
            j = html.index(u">", i)
            out.append(html[i:j + 1])
            i = j + 1
            continue
        if html.startswith(u"&", i):
            m = re.match(u"&\\w+;", html[i:])
            if m:
                if seen >= n:
                    out.append(m.group(0))
                seen += 1
                i += len(m.group(0))
                continue
        if seen >= n:
            out.append(html[i])
        seen += 1
        i += 1
    return u"".join(out).lstrip()


def fig_html(img):
    src = question_figures.write_asset("fom", img["bytes"], img.get("ext") or "png")
    return (u'<figure><img loading="lazy" src="%s" '
            u'alt="Figure from the question bank, page %s"></figure>'
            % (src, img.get("page", "?")))


# --------------------------------------------------------------- the walker

class Q(object):
    def __init__(self, num, week, section, page):
        self.num, self.week, self.section, self.page = num, week, section, page
        self.stem = []        # wrapped lines of the stem
        self.opts = []        # [letter, [lines], min_x]
        self.items = []       # i./ii./iii. or 1./2./3. items of a matching question
        self.imgs = []
        self.preamble = None


class Group(object):
    """One option list serving a run of questions (an extended-match block)."""
    def __init__(self, instr_lines):
        self.lines = list(instr_lines)
        self.opts = []
        self.cap = None                  # how many questions it covers, if stated
        txt = plain(u" ".join(instr_lines))
        m = COUNT_RE.search(txt)
        if m:
            if m.group(1):
                g = m.group(1).lower()
                self.cap = WORD_N.get(g) or int(g)
            else:
                self.cap = int(m.group(3)) - int(m.group(2)) + 1

    def html(self):
        return u"".join(u"<p>%s</p>" % l for l in self.lines)


def parse_block(slug, bno, pdf, weeks):
    """-> (questions, keys) as per-section lists in document order.

    Both are keyed by (week, section) and hold entries in the order the bank
    prints them, because the bank's own numbering is not always trustworthy -
    see align() for what that costs.
    """
    pages = flow(os.path.join(QBANK_DIR, pdf))

    week = section = None
    answers = started = False
    qsec, ksec = {}, {}          # (week, section) -> list
    cur = curkey = None
    mode = None                  # stem | opt | item | key | instr
    instr, pend = [], None
    group, taken = None, 0
    qx = None                    # x the current section sets its question numbers at

    def flush_group():
        return pend if (pend is not None and pend.opts) else None

    for items in pages:
        pageno = None
        for it in items:
            if it["t"] == "img":
                if cur is not None and it["w"] > 60 and it["h"] > 40 and it.get("bytes"):
                    it["page"] = pageno
                    cur.imgs.append(it)
                continue

            raw = join([runs_html(it["runs"])])
            txt = plain(raw).strip()
            if not txt:
                continue
            x, size = it["x"], it["size"]
            pageno = it["page"]

            if it["y"] > Y_FOOTER and re.match(u"^\\d{1,3}$", txt):
                continue
            if not started and LEADER_RE.search(txt):
                continue                                   # table of contents
            if NAV_RE.match(txt):
                continue

            # ---- headings, discriminated by type size
            if size >= 20:
                m = re.match(u"^Week\\s+(\\d+)\\s*(ANSWERS|Answers)?\\s*$", txt)
                if m and int(m.group(1)) in weeks:
                    week, answers = int(m.group(1)), bool(m.group(2))
                    section = cur = curkey = mode = None
                    instr, pend, group, taken = [], None, None, 0
                    qx = None
                    started = True
                continue
            if 13.0 <= size < 20:
                head = re.sub(u"\\s+", u" ", txt).strip()
                if head in SEC_BY_HEAD:
                    g = flush_group()
                    if g is not None:
                        group, taken = g, 0
                    section = SEC_BY_HEAD[head]
                    cur = curkey = mode = None
                    instr, pend, group, taken = [], None, None, 0
                    qx = None
                continue

            if not started or week is None or section is None:
                continue

            # ---- the answers half of a week
            if answers:
                m = NUM_RE.match(txt)
                if x < X_MARGIN and m:
                    curkey = {"num": int(m.group(1)), "parts": [drop_prefix(raw, m.end())]}
                    ksec.setdefault((week, section), []).append(curkey)
                    mode = "key"
                elif mode == "key" and curkey is not None:
                    curkey["parts"].append(raw)
                continue

            # ---- the questions half of a week
            if EMPTY_SEC.match(txt):
                continue

            lst = qsec.setdefault((week, section), [])
            m = NUM_RE.match(txt)
            # a numbered question: at the left margin, or a little right of it
            # when the number simply continues the section's run (the bank's
            # indentation slips in a handful of places)
            if m and (x < X_MARGIN or
                      (x < 105.0 and int(m.group(1)) == (lst[-1].num + 1 if lst else 1))):
                g = flush_group()
                if g is not None:
                    group, taken = g, 0
                cur = Q(int(m.group(1)), week, section, it["page"])
                qx = x
                lst.append(cur)
                if instr and pend is not None and not pend.opts:
                    cur.preamble = pend.html()
                elif group is not None and (group.cap is None or taken < group.cap):
                    cur.opts = [[l, list(p), xx] for l, p, xx in group.opts]
                    cur.preamble = group.html()
                    cur.from_group = True
                    taken += 1
                    if group.cap is not None and taken >= group.cap:
                        group = None
                instr, pend = [], None
                cur.stem.append(drop_prefix(raw, m.end()))
                mode = "stem"
                continue

            # A left-margin line that is not a number is a shared instruction -
            # but only if it starts where this section's question numbers start.
            # One page sets its numbers at x=68 and wraps their stems to x=86,
            # both inside the margin band, and reading that wrap as a new
            # instruction handed the question's options to a phantom group.
            if x < X_MARGIN and (qx is None or abs(x - qx) <= 6.0):
                instr.append(raw)
                pend = Group(instr)
                cur, mode, group = None, "instr", None
                continue
            if x < X_MARGIN:
                if cur is None:
                    continue
                if mode == "opt" and cur.opts:
                    cur.opts[-1][1].append(raw)
                elif mode == "item" and cur.items:
                    cur.items[-1] = cur.items[-1] + u" " + raw
                else:
                    cur.stem.append(raw)
                continue

            # ---- the indented bands
            if x >= X_OPTION:
                # matching items sit deeper than option letters, and are
                # labelled with roman numerals or digits, never with a letter
                if (x >= X_ITEM and ROMAN_RE.match(txt)) or ITEM_RE.match(txt):
                    if cur is not None:
                        cur.items.append(raw)
                        mode = "item"
                        continue
                if OPT_RE.match(txt):
                    letter = txt[0].upper()
                    body = drop_prefix(raw, 2).lstrip()
                    if mode == "instr" and pend is not None:
                        pend.opts.append([letter, [body], x])
                    elif cur is not None:
                        cur.opts.append([letter, [body], x])
                        mode = "opt"
                    continue
                if mode == "instr" and pend is not None and pend.opts:
                    pend.opts[-1][1].append(raw)
                elif cur is None:
                    continue
                elif mode == "opt" and cur.opts:
                    cur.opts[-1][1].append(raw)
                elif mode == "item" and cur.items:
                    cur.items[-1] = cur.items[-1] + u" " + raw
                else:
                    cur.stem.append(raw)
                continue

            # the stem indent
            if cur is None:
                continue
            if mode == "opt" and cur.opts:
                cur.opts[-1][1].append(raw)
            elif mode == "item" and cur.items:
                cur.items[-1] = cur.items[-1] + u" " + raw
            else:
                cur.stem.append(raw)

    return qsec, ksec


# ------------------------------------------------------------------ the key

LETTERS_RE = re.compile(u"^([A-Z])((?:\\s*(?:,|;|and|&|/|or)\\s*[A-Z])*)\\s*[.,:)]?(\\s|$)")

# A mapping answer pairs each item with its choice and says nothing else:
# "A = ii, B = iii, C = i", "1 - A ; 2 - F ; 3 - D", "1. A, H ; 2. G, I".
# It has to match the WHOLE answer. An earlier version only looked for a couple
# of "x - y" pairs anywhere in the text, which quietly swallowed any rationale
# that happened to contain a semicolon and two hyphenated words - "Think about a
# hose; the water stream ..." - and threw that question's answer letter away.
_SIDE = u"[A-Za-z0-9]{1,4}"
_RHS = u"%s(?:\\s*,\\s*%s)*" % (_SIDE, _SIDE)
MAP_DASH_RE = re.compile(
    u"^(?:%s\\s*\\.?\\s*[-\u2013\u2014=]\\s*%s)(?:\\s*[;,]\\s*%s\\s*\\.?\\s*[-\u2013\u2014=]"
    u"\\s*%s)+\\s*\\.?\\s*$" % (_SIDE, _RHS, _SIDE, _RHS))
MAP_DOT_RE = re.compile(
    u"^(?:\\d{1,3}\\s*[.)]\\s*%s)(?:\\s*[;,]\\s*\\d{1,3}\\s*[.)]\\s*%s)+\\s*\\.?\\s*$"
    % (_RHS, _RHS))


def is_map(txt):
    """True only when the whole answer is item-to-choice pairs and nothing else."""
    return bool(MAP_DASH_RE.match(txt) or MAP_DOT_RE.match(txt))


def parse_key(parts):
    """-> (letters, rationale_html, style); style is letter | map | prose | empty."""
    raw = join(parts)
    txt = plain(raw).strip()
    if not txt:
        return [], u"", "empty"
    if is_map(txt):
        return [], u"<p>%s</p>" % raw, "map"
    m = LETTERS_RE.match(txt)
    if not m:
        return [], u"<p>%s</p>" % raw, "prose"
    span = len(m.group(1)) + len(m.group(2))
    letters = re.findall(u"[A-Z]", m.group(1) + m.group(2))
    rest = drop_prefix(raw, span).lstrip()
    rest = re.sub(u"^((?:<[^>]+>)*)[.,:)]\\s*", u"\\1", rest).lstrip()
    return letters, (u"<p>%s</p>" % rest if plain(rest).strip() else u""), "letter"


def align(qs, ks):
    """Pair each question with its answer.

    The printed numbers agree almost everywhere, and where they do they are
    used, because that survives a question the parser may have dropped. Where
    they do not - Block 1's week 4 Self-Assessment prints its questions 8-15
    and then restarts at 9, while its answers run 1-12 - position in the
    section is what the bank actually means, so an equal-length run is paired
    off in order. Anything else is left unkeyed rather than mis-keyed.
    """
    qn = [q.num for q in qs]
    kn = [k["num"] for k in ks]
    if qn == kn:
        return dict(zip(range(len(qs)), ks)), "by-number"
    if len(qs) == len(ks) and len(set(qn)) != len(qn):
        return dict(zip(range(len(qs)), ks)), "positional"
    bynum = {}
    for k in ks:
        bynum.setdefault(k["num"], k)
    out = {}
    for i, q in enumerate(qs):
        if q.num in bynum and qn.count(q.num) == 1:
            out[i] = bynum[q.num]
    return out, "by-number (partial)"


# ----------------------------------------------------------------- emission

def split_run_on(opts):
    """Split an option that swallowed the next one.

    A handful of option lists set two choices on one PDF line - almost always
    "H. Thymus I. Hemiazygous vein", where the I sits alongside the H rather
    than under it. Only a letter that is missing from the list and follows the
    one it is buried in counts, so a stem that merely mentions "option I" is
    left alone.
    """
    out, i = list(opts), 0
    while i < len(out):
        letters = set(o["letter"] for o in out)
        nxt = chr(ord(out[i]["letter"]) + 1)
        if nxt <= "Z" and nxt not in letters:
            m = re.search(u"\\s%s[.)]\\s+(?=[A-Z(])" % nxt, plain(out[i]["html"]))
            if m:
                cut = m.start()
                head = drop_prefix(out[i]["html"], 0)
                htxt, ttxt = plain(head)[:cut], plain(head)[cut:]
                out[i] = {"letter": out[i]["letter"], "html": esc(htxt.strip())}
                out.insert(i + 1, {"letter": nxt,
                                   "html": esc(re.sub(u"^\\s*[A-Z][.)]\\s*", u"", ttxt).strip())})
        i += 1
    return out


def build(slug, bno, pdf, weeks):
    qsec, ksec = parse_block(slug, bno, pdf, weeks)
    out, notes = [], []

    for section in SEC_ORDER:
        for week in weeks:
            qs = qsec.get((week, section), [])
            if not qs:
                continue
            ks = ksec.get((week, section), [])
            pairs, how = align(qs, ks)
            renum = (how == "positional")
            if how != "by-number":
                notes.append(u"W%-3d %-9s %s (%d questions, %d answers)"
                             % (week, section, how, len(qs), len(ks)))

            for i, q in enumerate(qs):
                stem = join(q.stem)
                stem_html = u"<p>%s</p>" % stem if stem else u""
                if q.items:
                    stem_html += u"<ol class=\"match-items\">%s</ol>" % u"".join(
                        u"<li>%s</li>" % re.sub(
                            u"^((?:<[^>]+>)*)(?:[IVXivx]{1,4}|\\d{1,3})[.)]\\s*", u"\\1", it)
                        for it in q.items)
                for img in q.imgs:
                    stem_html += fig_html(img)

                seen, opts = set(), []
                for l, p, _x in q.opts:
                    if l in seen:
                        continue
                    seen.add(l)
                    opts.append({"letter": l, "html": join(p)})
                opts = split_run_on(opts)

                k = pairs.get(i)
                letters, rationale, style = ([], u"", "missing")
                if k is not None:
                    letters, rationale, style = parse_key(k["parts"])

                rightcol = bool(q.opts) and min(x for _l, _p, x in q.opts) > X_RIGHTCOL
                # roman-numeral items are usually sub-statements of the stem, with
                # the options combining them ("A. i and ii"), so they only mean a
                # matching question when there is no answer letter to pick
                is_match = rightcol or style == "map" or (bool(q.items) and not letters)
                valid = [o["letter"] for o in opts]
                if valid:
                    letters = [l for l in letters if l in valid]
                multi = len(letters) > 1 or bool(MULTI_RE.search(plain(stem)))

                kind, free, unscorable, keyed = "mcq", False, False, True
                flags = []
                num = i + 1 if renum else q.num
                if renum:
                    flags.append({
                        "type": "note", "title": "Renumbered",
                        "html": u"<p>The bank prints this one as <strong>%d</strong>, but its "
                                u"numbering restarts part way through this section while the "
                                u"answer key runs straight through. It is numbered here by its "
                                u"position, which is what the key actually answers.</p>" % q.num})

                if style in ("missing", "empty"):
                    kind, keyed, unscorable = "broken", False, True
                    answer = (u"<p>The bank prints no answer for this one, so there is "
                              u"nothing to transcribe and nothing to score against.</p>")
                    flags.append({
                        "type": "warning", "title": "No key in the source",
                        "html": u"<p>Left out of the accuracy figures on purpose. Work it "
                                u"through, then check it against the week&rsquo;s material.</p>"})
                elif is_match or not letters:
                    kind = "matching" if is_match else "short"
                    free = True
                    answer = rationale or u"<p>%s</p>" % join(k["parts"])
                else:
                    answer = (u"<p><strong>The correct answer is %s.</strong></p>"
                              % u", ".join(letters)) + rationale
                    if not rationale:
                        flags.append({
                            "type": "note", "title": "Letter only",
                            "html": u"<p>The bank gives the letter with no written rationale. "
                                    u"Reason it out from the week&rsquo;s material rather than "
                                    u"taking the letter on faith.</p>"})

                if not opts and not free and keyed:
                    kind, free = "short", True

                out.append({
                    "qid": u"%s-w%d-%s-q%d-%d" % (slug, week, section, num, i + 1),
                    "num": u"%d" % num,
                    "week": week,
                    "weekLabel": WEEK_LABEL[week],
                    "retired": False,
                    "family": section,
                    "source": section,
                    "sourceLabel": SEC_LABEL[section],
                    "lecture": SEC_LABEL[section],
                    "lectureMeta": SEC_META[section],
                    "tags": [],
                    "preamble": ({"title": "Shared instructions", "html": q.preamble}
                                 if q.preamble else None),
                    "stem": stem_html,
                    "kind": kind,
                    "options": opts,
                    "correct": [] if free else letters,
                    "multi": bool(multi and letters and not free),
                    "free": free,
                    "unscorable": unscorable,
                    "keyed": keyed,
                    "answerTitle": "Answer",
                    "answer": answer,
                    "flags": flags,
                })

    return out, notes


# families authored by hand into data/questions/, which a rerun must keep
HAND_FAMILIES = ("reviews",)


def main():
    # tools/fom/ -> tools/ -> the repo root; the course's data sits under fom/
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    grand = 0
    # the Pre-Clerkship Workbook is a separate document with a separate parser;
    # its three FoM chapters are filed into these blocks and appended here
    wb, wbrep = parse_workbook.build_blocks(WEEK_LABEL)
    weak = len([r for r in wbrep if not isinstance(r[4], str) and r[4] < 0.25])
    print("workbook  %4d questions  %d filed by their own subject label, %d by "
          "keyword, %d flagged as a guess"
          % (sum(len(v) for v in wb.values()),
             len([r for r in wbrep if r[4] == "subject"]),
             len([r for r in wbrep if r[4] != "subject"]) - weak, weak))
    for slug, bno, pdf, weeks in BLOCKS:
        qs, notes = build(slug, bno, pdf, weeks)
        qs.extend(wb.get(slug, []))
        path = os.path.join(root, "fom", "data", "questions", "%s.json" % slug)
        # the Schulich Reviews set is hand-authored and no PDF here produces it,
        # so carry it over rather than letting this rewrite drop it
        if os.path.exists(path):
            qs.extend(q for q in json.load(io.open(path, encoding="utf-8"))
                      if q.get("family") in HAND_FAMILIES)
        io.open(path, "w", encoding="utf-8", newline="\n").write(
            json.dumps(qs, ensure_ascii=False))
        grand += len(qs)
        kinds = {}
        for q in qs:
            kinds[q["kind"]] = kinds.get(q["kind"], 0) + 1
        figs = sum(q["stem"].count("<figure>") for q in qs)
        print("%s  %4d questions  %-46s figures=%-3d %.1f MB"
              % (slug, len(qs), " ".join("%s=%d" % kv for kv in sorted(kinds.items())),
                 figs, os.path.getsize(path) / 1048576.0))
        for n in notes:
            print("        note: %s" % n)
    print("total %d questions" % grand)


if __name__ == "__main__":
    main()
