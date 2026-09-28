# -*- coding: utf-8 -*-
"""Turn the four PoM 1 Question Bank PDFs into pom1/data/questions/<slug>.json.

Purpose: parse the student-written PoM 1 block banks into the portal's question
         schema, answer keys, rationales and figures included.
Author:  Noor Sims
Date:    2026-09-25
Input:   the four "<system> - P1 QBank" PDFs (dir via $POM1_QBANK_DIR)
Output:  pom1/data/questions/cardio|resp|ent|gi|gu.json, and a report on stdout

The same volunteers laid these out the same way as the FoM banks a year earlier,
down to the indents: a question number at the left margin (x ~ 72), its stem one
indent in (x ~ 93), an option letter at a second (x ~ 115) and an option wrap at
a third (x ~ 136), with a 28pt week heading and 14-16pt section headings. So the
walker is FoM's, imported rather than copied, and what is written out here is
what actually differs - the files, the weeks, and the sections.

Two things differ from FoM and both are structural:

* **Sections.** FoM ran module / RA / SA / Meds2024 / new. PoM 1 runs module /
  weekly quiz / Meds2024 / new, with "Questions from the Week" as a *parent*
  heading over the first two. That parent is not a section and is ignored;
  because a week heading resets the section anyway, ignoring it cannot leave a
  question filed under the previous week's set.

* **An option letter alone on its line.** Most of these banks set an option as
  "A. Aortic" on one line, but a tab-stopped stretch of them sets the letter at
  x ~ 115 and its text at x ~ 143, in two line boxes. Reading only the first
  shape left 1,100 questions with their options buried in the stem and no
  letters to score against, which is what OPT_ONLY_RE is for: a bare letter
  opens an option whose body is whatever follows at the deeper indent.

* **A different option indent per PDF.** Cardiology and Respirology set their
  option letters at x ~ 115, Gastroenterology and Genitourinary at x ~ 100 -
  inside the band FoM's walker reads as the stem's own wrap. Rather than tune a
  number per file, an indented line opens an option when it is lettered *and*
  that letter is the one due next (A, then B, ...), which a wrapped stem line
  never is.

* **Five blocks out of four PDFs.** The Respirology bank covers weeks 6 to 9,
  and week 9 is ENT - a block of its own in the course's timetable and in the
  vault. So the Resp PDF is read once and split on the week number, which is
  the same rule the rest of the file already files by.

The "P1 Practice Questions, Class of 2024" PDF is deliberately **not** a fifth
set: the block banks' Meds2024 sections already re-file it week by week. See
check_practice.py, which is the test of that claim rather than an assertion of
it.
"""

import importlib.util
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(TOOLS, "fom"))

import question_figures                                          # noqa: E402
import parse_workbook_pom1                                       # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# FoM's parser, loaded under its own name so that two files called
# parse_qbank.py can coexist. Only its course-independent half is used: the
# geometry walker and the text helpers. Everything course-specific - which
# PDFs, which weeks, which sections, which course the figures belong to - is
# in this file.
fom = _load("fom_parse_qbank", os.path.join(TOOLS, "fom", "parse_qbank.py"))

flow, join, plain, drop_prefix = fom.flow, fom.join, fom.plain, fom.drop_prefix
runs_html, parse_key, align = fom.runs_html, fom.parse_key, fom.align
split_run_on, Q, Group = fom.split_run_on, fom.Q, fom.Group
NUM_RE, OPT_RE, ROMAN_RE, ITEM_RE = fom.NUM_RE, fom.OPT_RE, fom.ROMAN_RE, fom.ITEM_RE
LEADER_RE, NAV_RE, EMPTY_SEC, MULTI_RE = (fom.LEADER_RE, fom.NAV_RE,
                                          fom.EMPTY_SEC, fom.MULTI_RE)
X_MARGIN, X_OPTION, X_RIGHTCOL, X_ITEM = (fom.X_MARGIN, fom.X_OPTION,
                                          fom.X_RIGHTCOL, fom.X_ITEM)
Y_FOOTER = fom.Y_FOOTER

# An option letter with nothing after it: "A." at x ~ 115 whose text sits in a
# separate line box at x ~ 143. Held to a single letter and a delimiter so a
# stem line cannot open a phantom option.
OPT_ONLY_RE = re.compile(u"^([A-Za-z])[.)]\\s*$")

QBANK_DIR = os.environ.get(
    "POM1_QBANK_DIR",
    os.path.join(ROOT, "pom1", "Question Bank-20260926T005036Z-1-001",
                 "Question Bank"))

# pdf -> the weeks to take out of it. The Respirology bank is read twice
# because it holds two blocks: respirology in weeks 6-8 and ENT in week 9.
BLOCKS = [
    ("cardio", 1, u"Cardio - P1 QBank 2.1 2025 Version.pdf", [1, 2, 3, 4, 5]),
    ("resp",   2, u"Resp - P1 QBank 2.1 2025 Version.pdf",   [6, 7, 8]),
    ("ent",    3, u"Resp - P1 QBank 2.1 2025 Version.pdf",   [9]),
    ("gi",     4, u"GI - P1 QBank 2.1 2025 Version.pdf",     [10, 11, 12, 13]),
    ("gu",     5, u"GU - P1 QBank 2.1 2025 Version.pdf",     [14, 15, 16, 17]),
]

# Written from the lecture titles in the vault's "99 - PoM 1" tree, so the week
# a question is filed under is named the same way on the notes tab.
WEEK_LABEL = {
    1:  u"Week 1 - Cardiac Physiology, ECG & Cardiac Pharmacology",
    2:  u"Week 2 - Valvular Disease, Heart Sounds & Endocarditis",
    3:  u"Week 3 - Ischemic Heart Disease & Vascular Pathology",
    4:  u"Week 4 - Heart Failure, Hypertension & Congenital Disease",
    5:  u"Week 5 - Arrhythmias, Syncope & Atrial Fibrillation",
    6:  u"Week 6 - Lung Mechanics, Obstructive Disease & the Upper Airway",
    7:  u"Week 7 - Gas Exchange, Hypoxia & Interstitial Disease",
    8:  u"Week 8 - Pneumonia, Tuberculosis & Pulmonary Masses",
    9:  u"Week 9 - Head & Neck Anatomy, Masses & Infections",
    10: u"Week 10 - Motility, Dysphagia & Acid-Related Disease",
    11: u"Week 11 - Absorption, Diarrhea, IBD & Luminal Malignancy",
    12: u"Week 12 - Liver, Biliary Tract & Pancreas",
    13: u"Week 13 - Abdominal Pain, Obstruction & Anorectal Disease",
    14: u"Week 14 - Renal Anatomy, Filtration, Sodium, Water & Acid-Base",
    15: u"Week 15 - Renal Function, AKI & Chronic Kidney Disease",
    16: u"Week 16 - Urinary Infection, Obstruction & Urologic Malignancy",
    17: u"Week 17 - Incontinence, Stones & Renal Replacement",
}

# "Questions from the Week" is a parent heading over the first two, not a
# section, and is left out on purpose.
SECTIONS = [
    (u"Module Questions",                          "module",   u"Module questions"),
    (u"Weekly Quiz",                               "weekly",   u"Weekly quiz"),
    (u"Questions from the Meds2024 Question Bank", "meds2024", u"Meds 2024 bank"),
    (u"New Questions",                             "new",      u"Meds 2025"),
]
SEC_BY_HEAD = dict((h, k) for h, k, _l in SECTIONS)
SEC_LABEL = dict((k, l) for _h, k, l in SECTIONS)
SEC_ORDER = [k for _h, k, _l in SECTIONS]

SEC_META = {
    "module": (u"The knowledge checks inside the week's Elentra asynchronous learning "
               u"modules, transcribed into the Meds 2025 block bank."),
    "weekly": u"The week's quiz, as it was sat.",
    "meds2024": (u"The student-written bank the Class of 2024 Academic Directors built "
                 u"in May 2021 and the Meds 2025 volunteers re-filed week by week. About "
                 u"half the cardiology questions and a handful of the respirology ones "
                 u"were reviewed by faculty; the rest were not."),
    "new": (u"Written fresh by the Meds 2025 volunteers in 2022. The bank states on its "
            u"own second page that these were not verified by faculty."),
}


def fig_html(img):
    src = question_figures.write_asset("pom1", img["bytes"], img.get("ext") or "png")
    return (u'<figure><img loading="lazy" src="%s" '
            u'alt="Figure from the question bank, page %s"></figure>'
            % (src, img.get("page", "?")))


# --------------------------------------------------------------- the walker

def parse_block(pdf, weeks):
    """-> (questions, keys) as per-section lists in document order.

    A transcription of FoM's walker with this bank's section vocabulary. The
    geometry is identical, so the only substantive difference is which headings
    open a section and that a week outside `weeks` is skipped - which is what
    lets one PDF serve two blocks.
    """
    pages = flow(os.path.join(QBANK_DIR, pdf))

    week = section = None
    answers = started = False
    qsec, ksec = {}, {}
    cur = curkey = None
    mode = None
    instr, pend = [], None
    group, taken = None, 0
    qx = None

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

            # ---- headings, discriminated by type size. "Week N" is 28pt and
            # "Week N ANSWERS" is 20pt, so both clear the section headings.
            if size >= 20:
                m = re.match(u"^Week\\s+(\\d+)\\s*(ANSWERS|Answers)?\\s*$", txt)
                if m:
                    n = int(m.group(1))
                    week = n if n in weeks else None
                    answers = bool(m.group(2))
                    section = cur = curkey = mode = None
                    instr, pend, group, taken = [], None, None, 0
                    qx = None
                    started = True
                continue
            if 13.0 <= size < 20:
                head = re.sub(u"\\s+", u" ", txt).strip()
                if head in SEC_BY_HEAD:
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
                    taken += 1
                    if group.cap is not None and taken >= group.cap:
                        group = None
                instr, pend = [], None
                cur.stem.append(drop_prefix(raw, m.end()))
                mode = "stem"
                continue

            if x < X_MARGIN and (qx is None or abs(x - qx) <= 6.0):
                instr.append(raw)
                pend = Group(instr)
                cur, mode, group = None, "instr", None
                continue
            if X_MARGIN <= x < X_OPTION and (cur is not None or
                                             (mode == "instr" and pend is not None)):
                owner = cur if (mode != "instr" or pend is None) else pend
                if mode == "opt" and owner.opts and not owner.opts[-1][1]:
                    owner.opts[-1][1].append(raw)
                    continue
                if OPT_RE.match(txt) or OPT_ONLY_RE.match(txt):
                    letter = txt[0].upper()
                    due = (chr(ord(owner.opts[-1][0]) + 1) if owner.opts else u"A")
                    if letter == due:
                        body = drop_prefix(raw, 2).lstrip()
                        owner.opts.append([letter, [body] if plain(body).strip() else [], x])
                        if owner is cur:
                            mode = "opt"
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
                # an option opened but still empty takes the next line as its
                # text, whatever that line looks like - a numeric option ("0.6")
                # would otherwise read as a matching item
                if mode == "opt" and cur is not None and cur.opts and not cur.opts[-1][1]:
                    cur.opts[-1][1].append(raw)
                    continue
                if mode == "instr" and pend is not None and pend.opts and not pend.opts[-1][1]:
                    pend.opts[-1][1].append(raw)
                    continue
                if OPT_ONLY_RE.match(txt):
                    letter = txt[0].upper()
                    if mode == "instr" and pend is not None:
                        pend.opts.append([letter, [], x])
                    elif cur is not None:
                        cur.opts.append([letter, [], x])
                        mode = "opt"
                    continue
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


# ----------------------------------------------------------------- emission

def build(slug, pdf, weeks):
    qsec, ksec = parse_block(pdf, weeks)
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
                    if l in seen or not p:
                        continue
                    seen.add(l)
                    opts.append({"letter": l, "html": join(p)})
                opts = split_run_on(opts)

                k = pairs.get(i)
                letters, rationale, style = ([], u"", "missing")
                if k is not None:
                    letters, rationale, style = parse_key(k["parts"])

                rightcol = bool(q.opts) and min(x for _l, _p, x in q.opts) > X_RIGHTCOL
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
    grand = 0
    wb, wbrep = parse_workbook_pom1.build_blocks(WEEK_LABEL)
    weak = len([r for r in wbrep if r[4] < 0.25])
    print("workbook  %4d questions  %d filed by keyword, %d flagged as a guess"
          % (sum(len(v) for v in wb.values()), len(wbrep) - weak, weak))
    for slug, _bno, pdf, weeks in BLOCKS:
        qs, notes = build(slug, pdf, weeks)
        qs.extend(wb.get(slug, []))
        path = os.path.join(ROOT, "pom1", "data", "questions", "%s.json" % slug)
        # the Schulich Reviews set is hand-authored and no PDF here produces it,
        # so carry it over rather than letting this rewrite drop it
        if os.path.exists(path):
            qs.extend(q for q in json.load(io.open(path, encoding="utf-8"))
                      if q.get("family") in HAND_FAMILIES)
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))
        io.open(path, "w", encoding="utf-8", newline="\n").write(
            json.dumps(qs, ensure_ascii=False))
        grand += len(qs)
        kinds = {}
        for q in qs:
            kinds[q["kind"]] = kinds.get(q["kind"], 0) + 1
        figs = sum(q["stem"].count("<figure>") for q in qs)
        print("%-7s %4d questions  %-46s figures=%-3d %.1f MB"
              % (slug, len(qs), " ".join("%s=%d" % kv for kv in sorted(kinds.items())),
                 figs, os.path.getsize(path) / 1048576.0))
        for n in notes:
            print("        note: %s" % n)
    print("total %d questions" % grand)


if __name__ == "__main__":
    main()
