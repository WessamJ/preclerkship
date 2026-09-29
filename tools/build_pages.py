# -*- coding: utf-8 -*-
"""Regenerate every course's block pages from one template.

Purpose: build one page per block, for every course in the portal, so the four
         courses cannot drift into four layouts.
Author:  Noor Sims
Date:    2026-09-21
Input:   tools/portal.py (the course roster), each course's data/, and the page
         being replaced (for its blurb and accent, so hand edits survive)
Output:  <course>/<block>.html

Run from the repo root. A course with no blocks yet is skipped; its landing page
still renders from build_index.py, saying it is empty.
"""

import io, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portal

HOWTO = """<details class="howto">
<summary>Remember to save your progress</summary>
<div class="body">
<p>Your answers live in your browser&rsquo;s local storage. They don&rsquo;t follow you
on a different browser or laptop, and could be lost if the site data is cleared.</p>
<p>To save your progress, press <strong>Download all my progress</strong> below. On your other
device, press <strong>Restore from a file</strong>. A restore only adds and updates, so an out
of date file cannot wipe newer answers.</p>
<p class="storenote" id="storenote" hidden></p>
<div class="resets">
<button class="backup-btn" id="export-progress" type="button">Download all my progress</button>
<button class="backup-btn" id="import-progress" type="button">Restore from a file</button>
<input type="file" id="import-file" accept="application/json,.json" hidden>
<button class="danger" id="reset-shown" type="button" disabled>Reset the questions shown (0)</button>
<button class="danger" id="reset-all" type="button">Reset all progress</button>
</div>
</div>
</details>"""

# Used only when a page does not exist yet. After that the page itself is the
# source of truth for these three, so anything reworded by hand survives.
SEED = {
    ("fom", "b1"): (u"Weeks 1 to 4: what a physician actually does, the ethics and "
                    u"epidemiology underneath it, then cells and tissues, genetics and the "
                    u"newborn, and the health of children and adolescents.",
                    u"Practice questions for weeks 1 to 4 of Foundations of Medicine.",
                    u"--q-accent:#8a5320;--q-accent-soft:#f6e8d8;--q-accent-ink:#70431a;"),
    ("fom", "b2"): (u"Weeks 5 to 8: how the body holds its fluids and pressure steady, what "
                    u"goes wrong when growth stops obeying, how ageing changes the encounter, "
                    u"and the pharmacology that runs underneath all of it.",
                    u"Practice questions for weeks 5 to 8 of Foundations of Medicine.",
                    u"--q-accent:#2f6b4f;--q-accent-soft:#e2efe9;--q-accent-ink:#275844;"),
    ("fom", "b3"): (u"Weeks 9 to 12: the anemias, then bleeding and clotting, then the white "
                    u"cells and the malignancies that arise from them, ending in lymphoma and "
                    u"myeloma.",
                    u"Practice questions for weeks 9 to 12 of Foundations of Medicine.",
                    u"--q-accent:#9c2b2b;--q-accent-soft:#f7dedb;--q-accent-ink:#802222;"),
    ("fom", "b4"): (u"Weeks 13 to 15: fever and the microbes behind it, how infection travels "
                    u"and what is used against it, and what happens when the immune system is "
                    u"absent, overreacting, or turned on its owner.",
                    u"Practice questions for weeks 13 to 15 of Foundations of Medicine.",
                    u"--q-accent:#3d4f8f;--q-accent-soft:#e5e8f5;--q-accent-ink:#333f75;"),
    ("pom1", "cardio"): (u"Weeks 1 to 5: the heart as an electrical system and as a pump, "
                         u"then the valves and the sounds they make, the coronary arteries "
                         u"and what happens when one closes, failure and hypertension, and "
                         u"the rhythms.",
                         u"Practice questions for the cardiology weeks of Principles of "
                         u"Medicine 1.",
                         u"--q-accent:#9c2b2b;--q-accent-soft:#f7dedb;--q-accent-ink:#802222;"),
    ("pom1", "resp"): (u"Weeks 6 to 8: how air gets in and out and how gas crosses, what "
                       u"obstructs and what stiffens, then the infections, the nodules and "
                       u"the pleura.",
                       u"Practice questions for the respirology weeks of Principles of "
                       u"Medicine 1.",
                       u"--q-accent:#2f6b8f;--q-accent-soft:#e2ecf4;--q-accent-ink:#265673;"),
    ("pom1", "ent"): (u"Week 9, one week on its own: the anatomy of the neck, the masses "
                      u"found in it at every age, and the infections that fill it.",
                      u"Practice questions for the ear, nose and throat week of Principles "
                      u"of Medicine 1.",
                      u"--q-accent:#7a4a9c;--q-accent-soft:#eee3f6;--q-accent-ink:#623c7e;"),
    ("pom1", "gi"): (u"Weeks 10 to 13: the gut from mouth to anus - motility and acid, then "
                     u"absorption and the inflamed bowel, then the liver, biliary tree and "
                     u"pancreas, ending on the acute abdomen.",
                     u"Practice questions for the gastroenterology weeks of Principles of "
                     u"Medicine 1.",
                     u"--q-accent:#2f6b4f;--q-accent-soft:#e2efe9;--q-accent-ink:#275844;"),
    ("pom1", "gu"): (u"Weeks 14 to 17: the nephron and the electrolytes it sets, then "
                     u"failing kidneys acute and chronic, then the urinary tract - "
                     u"infection, obstruction, cancer and stones.",
                     u"Practice questions for the nephrology and urology weeks of "
                     u"Principles of Medicine 1.",
                     u"--q-accent:#8a5320;--q-accent-soft:#f6e8d8;--q-accent-ink:#70431a;"),
    ("t2c", "peds"): (u"Weeks 1 and 2: prescribing for a child, the acute asthma "
                      u"exacerbation, and the developmental surveillance that runs "
                      u"under every well-child visit.",
                      u"Practice questions for the pediatrics weeks of Transition to Clerkship.",
                      u"--q-accent:#0f6b6b;--q-accent-soft:#dcefef;--q-accent-ink:#0c5555;"),
    ("t2c", "surg"): (u"Weeks 3 and 4: the GI bleed from anatomy to disposition, then "
                      u"the paperwork that surgery actually runs on - perioperative "
                      u"care, the OR note, admission orders and a courteous consult.",
                      u"Practice questions for the surgery weeks of Transition to Clerkship.",
                      u"--q-accent:#7a4a9c;--q-accent-soft:#eee3f6;--q-accent-ink:#623c7e;"),
    ("t2c", "psych"): (u"Weeks 5 and 6: psychiatry on the wards, then delirium, the "
                       u"palliative emergencies, and managing pain and dyspnea at the "
                       u"end of life.",
                       u"Practice questions for the psychiatry and palliative weeks of "
                       u"Transition to Clerkship.",
                       u"--q-accent:#2f6b4f;--q-accent-soft:#e2efe9;--q-accent-ink:#275844;"),
    ("t2c", "em"): (u"Week 7, and the largest block here by some way: resuscitation and "
                    u"shock, cardiac arrest, trauma and ATLS, toxicology - and a "
                    u"37-question ER practice test sat as one paper.",
                    u"Practice questions for the emergency medicine week of Transition "
                    u"to Clerkship.",
                    u"--q-accent:#a83232;--q-accent-soft:#f8dedd;--q-accent-ink:#8a2828;"),
    ("t2c", "fmob"): (u"Weeks 8 and 9: family medicine and obstetrics. The thinnest "
                      u"block in the bank - eight questions between two rotations - "
                      u"and the gap is left visible rather than padded.",
                      u"Practice questions for the family medicine and obstetrics weeks "
                      u"of Transition to Clerkship.",
                      u"--q-accent:#8a5320;--q-accent-soft:#f6e8d8;--q-accent-ink:#70431a;"),
    ("t2c", "dermim"): (u"Weeks 10 to 13: the dermatology rotation, then internal "
                        u"medicine - the last two rotations before clerkship proper.",
                        u"Practice questions for the dermatology and internal medicine "
                        u"weeks of Transition to Clerkship.",
                        u"--q-accent:#35608f;--q-accent-soft:#e2ebf5;--q-accent-ink:#2b4d73;"),
}

FAVICON = {"fom": ("FM", "1f4e5f"), "pom2": ("P2", "84223b"),
           "pom1": ("P1", "6b5a2f"), "t2c": ("T2C", "3f4a5a")}


def existing(course, slug):
    p = os.path.join(course["slug"], "%s.html" % slug)
    if not os.path.exists(p):
        return SEED[(course["slug"], slug)]
    s = io.open(p, encoding="utf-8").read()
    lead = re.search(r'<p class="lead">\s*(.*?)\s*</p>', s, re.S).group(1)
    desc = re.search(r'<meta name="description" content="(.*?)">', s, re.S).group(1)
    accent = re.search(r'(--q-accent:.*?;--q-accent-soft:.*?;--q-accent-ink:.*?;)', s).group(1)
    return lead, desc, accent


def block_counts(course, slug):
    d = course["slug"]
    qs = json.load(io.open(os.path.join(d, "data", "questions", "%s.json" % slug),
                           encoding="utf-8"))
    nt = json.load(io.open(os.path.join(d, "data", "notes", "%s.json" % slug),
                           encoding="utf-8"))
    lects = [l for w in nt["weeks"] for l in w["lectures"]]
    # A lecture whose material is written up under a neighbouring lecture
    # counts as written: the note exists and the page says where. Counting it
    # as a gap would disagree with the coverage the page itself paints.
    written = [l for l in lects if l.get("hasNote") or l.get("coveredBy")]
    return len(qs), len(written), len(lects)


ANKI_EMPTY = u"""<div class="tab-empty">
<h2>The decks are not up yet.</h2>
<p>This is where the {course} Anki cards for weeks {weeks} will live, filed by week and
lecture the way the notes are &mdash; Christina&rsquo;s deck, brought up to date against this
year&rsquo;s lecture slides. Nothing has been uploaded into it yet.</p>
</div>"""


def anki_panel(course, slug, weeks):
    """The Anki tab: the deck if one has been exported, else the empty state.

    A block earns the real panel by having a manifest under data/anki/, which
    tools/build_anki.py writes beside the .apkg it exports. No manifest means no
    deck, and the tab says so rather than offering a dead download.
    """
    p = os.path.join(course["slug"], "data", "anki", "%s.json" % slug)
    if not os.path.exists(p):
        return ANKI_EMPTY.format(course=course["short"], weeks=weeks)
    m = json.load(io.open(p, encoding="utf-8"))

    mb = "%.0f MB" % (m["bytes"] / 1048576.0)
    out = ['<div class="deck">',
           '<div class="deck-head">',
           '<div class="deck-what">',
           '<h2>%s, weeks %s</h2>' % (course["short"], weeks),
           '<p class="deck-sum"><b>%d</b> cards from <b>%d</b> notes, '
           'across %d lectures. <b>%d</b> are marked high-yield.</p>'
           % (m["cards"], m["notes"],
              sum(len(w["lectures"]) for w in m["weeks"]), m["highyield"]),
           '<p class="deck-src">Christina&rsquo;s deck, brought up to date. It is the '
           'deck the classes pass down, re-exported against this year&rsquo;s lecture '
           'slides &mdash; lectures that changed are updated and new ones are added, so '
           'what you download matches the course as it is being taught now.</p>',
           '</div>',
           '<a class="deck-dl" href="%s" download>Download the deck '
           '<span class="sz">%s</span></a>' % (m["file"], mb),
           '</div>',
           '<div class="deck-how">',
           '<p><strong>To import it:</strong> open Anki on a computer, then '
           '<strong>File &rarr; Import</strong> and pick the file. It arrives as '
           '<code>%s</code> with the week and lecture subdecks intact, so it sits '
           'beside whatever you already have rather than merging into it.</p>' % m["deck"],
           '</div>',
           '<div class="deck-weeks">']
    for w in m["weeks"]:
        n = sum(l["cards"] for l in w["lectures"])
        out.append('<section class="deck-week">')
        out.append('<p class="panel-h">%s <span class="tc">%d</span></p>'
                   % (w["week"], n))
        out.append('<ul class="deck-lecs">')
        for l in w["lectures"]:
            hy = (' <span class="hy">&middot; %d high-yield</span>'
                  % l["highyield"]) if l["highyield"] else ''
            out.append('<li><span class="lc-n">%s</span>'
                       '<span class="lc-c"><b>%d</b>%s</span></li>'
                       % (l["name"], l["cards"], hy))
        out.append('</ul>')
        out.append('</section>')
    out.append('</div>')
    out.append('</div>')
    return "\n".join(out)


def anki_tc(course, slug):
    """The card count beside the Anki tab, or nothing while there is no deck."""
    p = os.path.join(course["slug"], "data", "anki", "%s.json" % slug)
    if not os.path.exists(p):
        return u""
    return u' <span class="tc">%d</span>' % json.load(
        io.open(p, encoding="utf-8"))["cards"]


def blocknav(course, active):
    rows = ['<a class="home" href="%s">All courses</a>' % portal.HUB_URL]
    for slug, n, name, _w in course["blocks"]:
        cls = ' class="here"' if slug == active else ''
        rows.append('<a href="%s.html"%s>%d &middot; %s</a>' % (slug, cls, n, name))
    # The questions live here now, so this is not one more way in - it is the
    # way in. It still sits in the block strip, because that is where someone
    # looking for a block's questions will look for them.
    if len(course["blocks"]) > 1:
        cls = "qbank here" if active == "qbank" else "qbank"
        rows.append('<a href="qbank.html" class="%s">Question bank</a>' % cls)
    return "\n".join(rows)


def tint(hex6, toward, amount):
    """hex6 mixed `amount` of the way towards white (1) or black (0).

    The term page needs the soft and ink shades of the course accent that each
    block page carries by hand, and portal.py holds one colour per course. One
    accent in, three out, so a course added to the roster needs no palette.
    """
    h = hex6.lstrip("#")
    rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    end = 255 if toward else 0
    return "#%02x%02x%02x" % tuple(
        int(round(c + (end - c) * amount)) for c in rgb)


def term_accent(course):
    a = course["accent"]
    return "--q-accent:%s;--q-accent-soft:%s;--q-accent-ink:%s;" % (
        a, tint(a, True, 0.88), tint(a, False, 0.18))


# Only until the page exists; after that its own copy is the source of truth,
# exactly as the block pages work.
QBANK_SEED = {
    "fom": (u"Every question in Foundations of Medicine in one bank: all four blocks, weeks 1 to 15. Filter it by block, week, question set, topic, or whether you got it right, then turn whatever is left into a practice test of any length and sit it against the clock.",
             u"The whole Foundations of Medicine question bank, filterable by block, week, question set and status."),
    "pom2": (u"Every question in Principles of Medicine 2 in one bank: all five blocks, weeks 1 to 20. Filter it by block, week, question set, topic, or whether you got it right, then turn whatever is left into a practice test of any length and sit it against the clock.",
             u"The whole Principles of Medicine 2 question bank, filterable by block, week, question set and status."),
    "pom1": (u"Every question in Principles of Medicine 1 in one bank: all five blocks, weeks 1 to 17. Filter it by block, week, question set, topic, or whether you got it right, then turn whatever is left into a practice test of any length and sit it against the clock.",
             u"The whole Principles of Medicine 1 question bank, filterable by block, week, question set and status."),
    "t2c": (u"Every question in Transition to Clerkship in one bank: all six rotations, weeks 1 to 13. Filter it by rotation, week, question set, or whether you got it right, then turn whatever is left into a practice test of any length and sit it against the clock.",
             u"The whole Transition to Clerkship question bank, filterable by rotation, week, question set and status."),
}


def existing_term(course):
    """The qbank page's lead and description, hand edits surviving a rebuild."""
    p = os.path.join(course["slug"], "qbank.html")
    if not os.path.exists(p):
        return QBANK_SEED[course["slug"]]
    t = io.open(p, encoding="utf-8").read()
    return (re.search(r'<p class="lead">\s*(.*?)\s*</p>', t, re.S).group(1),
            re.search(r'<meta name="description" content="(.*?)">', t, re.S).group(1))


# The questions panel, shared by a block page and the pooled term page -
# the toolbar, the stream and the sat-block bar are the same machine on
# both, and the block filter reveals itself from quiz.js where there is
# more than one block to choose between.
QPANEL = u"""<div class="q-shell q-flow" id="panel-questions" role="tabpanel" aria-labelledby="tab-questions" data-view="stream" data-mode="tutor"{hidden}>

<div class="qbar" id="qbar">

<div class="qbar-filters">
<div class="qsel" hidden id="f-block-wrap">
<span id="f-block-lab">Block</span>
<div class="msel">
<button class="msel-btn" id="f-block" type="button" aria-haspopup="true" aria-expanded="false" aria-labelledby="f-block-lab f-block-val"><span class="msel-val" id="f-block-val">Block</span><span class="msel-caret" aria-hidden="true">&#9662;</span></button>
<div class="msel-pop" id="f-block-pop" role="group" aria-labelledby="f-block-lab" hidden></div>
</div>
</div>
<div class="qsel" id="f-week-wrap">
<span id="f-week-lab">Week</span>
<div class="msel">
<button class="msel-btn" id="f-week" type="button" aria-haspopup="true" aria-expanded="false" aria-labelledby="f-week-lab f-week-val"><span class="msel-val" id="f-week-val">Week</span><span class="msel-caret" aria-hidden="true">&#9662;</span></button>
<div class="msel-pop" id="f-week-pop" role="group" aria-labelledby="f-week-lab" hidden></div>
</div>
</div>
<div class="qsel" id="f-family-wrap">
<span id="f-family-lab">Question set</span>
<div class="msel">
<button class="msel-btn" id="f-family" type="button" aria-haspopup="true" aria-expanded="false" aria-labelledby="f-family-lab f-family-val"><span class="msel-val" id="f-family-val">Question set</span><span class="msel-caret" aria-hidden="true">&#9662;</span></button>
<div class="msel-pop" id="f-family-pop" role="group" aria-labelledby="f-family-lab" hidden></div>
</div>
</div>
<div class="qsel" hidden id="f-tag-wrap">
<span id="f-tag-lab">Topic</span>
<div class="msel">
<button class="msel-btn" id="f-tag" type="button" aria-haspopup="true" aria-expanded="false" aria-labelledby="f-tag-lab f-tag-val"><span class="msel-val" id="f-tag-val">Topic</span><span class="msel-caret" aria-hidden="true">&#9662;</span></button>
<div class="msel-pop" id="f-tag-pop" role="group" aria-labelledby="f-tag-lab" hidden></div>
</div>
</div>
<div class="qsel" id="f-status-wrap">
<span id="f-status-lab">Status</span>
<div class="msel">
<button class="msel-btn" id="f-status" type="button" aria-haspopup="true" aria-expanded="false" aria-labelledby="f-status-lab f-status-val"><span class="msel-val" id="f-status-val">Status</span><span class="msel-caret" aria-hidden="true">&#9662;</span></button>
<div class="msel-pop" id="f-status-pop" role="group" aria-labelledby="f-status-lab" hidden></div>
</div>
</div>
<div class="qsel qsearch" id="f-search-wrap">
<span id="f-search-lab"><label for="bank-q">Search</label></span>
<div class="notesearch">
<input type="search" id="bank-q" placeholder="Search every question" autocomplete="off" spellcheck="false" title="Every word must appear somewhere in the question. Press / to jump here, Escape to clear.">
<button class="ns-clear" id="bank-q-clear" type="button" title="Clear the search" aria-label="Clear the search" hidden>&times;</button>
</div>
</div>
</div>

<div class="qbar-modes">
<div class="qseg-field">
<span id="view-lab">View</span>
<div class="qseg" id="view-seg" role="group" aria-labelledby="view-lab">
<button type="button" data-view="stream" aria-pressed="true">Continuous</button>
<button type="button" data-view="paged" aria-pressed="false">One at a time</button>
</div>
</div>
<div class="qseg-field">
<span id="order-lab">Order</span>
<div class="qseg" id="order-seg" role="group" aria-labelledby="order-lab">
<button type="button" data-order="bank" aria-pressed="true">In order</button>
<button type="button" data-order="shuffle" aria-pressed="false" title="Shuffle the questions. Pick it again to deal a new order.">Shuffled</button>
</div>
</div>
<div class="qseg-field">
<span id="mode-lab">Mode</span>
<div class="qseg" id="mode-seg" role="group" aria-labelledby="mode-lab">
<button type="button" data-mode="tutor" aria-pressed="true">Tutor</button>
<button type="button" data-mode="test" aria-pressed="false">Test</button>
</div>
</div>
</div>

<div class="applied" id="applied" hidden></div>

</div>

{howto}

<div class="testbar" id="testbar" hidden></div>

<main class="stream" id="stream">
<div class="q-loading">Loading {questions} questions&hellip;</div>
</main>

<div class="pagebar" id="pagebar" hidden></div>

<div class="posbar" id="posbar" hidden>
<span class="pb-where" id="pb-where"></span>
<span class="pb-count" id="pb-count"></span>
<span class="pb-steps">
<button class="pb-step pb-top" id="pb-top" type="button" title="Back to the top" aria-label="Back to the top">Top</button>
<button class="pb-step" id="pb-prev" type="button" title="Previous question (k)" aria-label="Previous question">&uarr;</button>
<button class="pb-step" id="pb-next" type="button" title="Next question (j)" aria-label="Next question">&darr;</button>
</span>
<button class="pb-mark" id="pb-mark" type="button" hidden></button>
</div>
</div>"""


PAGE = u"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} &middot; {course}</title>
<meta name="description" content="{desc}">
<meta name="robots" content="noindex, nofollow">
{favicon}

{nocache}
{fonts}
<link rel="stylesheet" href="{base_css}">
<link rel="stylesheet" href="{portal_css}">
<style>
:root{{{accent}}}
</style>
{cf}
</head>
<body>

<div class="pom2-page">

<nav class="blocknav">
{blocknav}
</nav>

<header class="q-masthead">
<div>
<p class="eyebrow" id="m-eyebrow"></p>
<h1>{name}</h1>
<p class="lead">{lead}</p>
</div>
<div class="scoreboard" id="sb-notes">
<div class="score"><b><span id="cv-notes">0</span><span class="of" id="cv-of"></span></b><span>Notes written</span></div>
<div class="score"><b><span id="cv-weeks">0</span><span class="of" id="cv-weeks-of"></span></b><span>Weeks covered</span></div>
</div>
</header>

<div class="tabs" role="tablist" aria-label="Notes or Anki">
<button type="button" id="tab-notes" role="tab" aria-selected="true" aria-controls="panel-notes">Notes <span class="tc" id="tc-notes">{written}/{lectures}</span></button>
<button type="button" id="tab-anki" role="tab" aria-selected="false" aria-controls="panel-anki">Anki{ankitc}</button>
<a class="tab-out" id="to-qbank" href="qbank.html#block={slug}">Practice questions <span class="tc">{questions}</span><span class="done" id="qb-done" hidden></span></a>
</div>

<div class="q-shell is-solo" id="panel-anki" role="tabpanel" aria-labelledby="tab-anki" hidden>
{anki}
</div>

<div class="q-shell" id="panel-notes" role="tabpanel" aria-labelledby="tab-notes">
<aside class="rail">

<section>
<p class="panel-h"><label for="note-q">Search</label></p>
<div class="notesearch">
<input type="search" id="note-q" placeholder="Search every note" autocomplete="off" spellcheck="false" title="Every word must appear somewhere in the note. Press / to jump here, Escape to clear.">
<button class="ns-clear" id="note-q-clear" type="button" title="Clear the search" aria-label="Clear the search" hidden>&times;</button>
</div>
<p class="railnote hits" id="note-q-count" hidden></p>
<div class="nsnav" id="note-nav" hidden>
<button class="ns-step" id="note-nav-prev" type="button" title="Previous match (Shift+Enter)" aria-label="Previous match">&uarr;</button>
<button class="ns-step" id="note-nav-next" type="button" title="Next match (Enter)" aria-label="Next match">&darr;</button>
<span class="ns-pos" id="note-nav-pos" aria-live="polite"></span>
</div>
</section>

<section>
<p class="panel-h">Week</p>
<div class="chips" id="note-week-chips"></div>
</section>

<section>
<p class="panel-h">Lectures</p>
<nav class="lecindex" id="note-index" aria-label="Jump to a lecture"></nav>
</section>

<section>
<p class="panel-h">Save as PDF</p>
<button class="print-cta" id="print-all" type="button" disabled>Save every note as one PDF</button>
<p class="railnote">Each note has its own <strong>PDF</strong> button, and each week can be
saved in one go. Print it, annotate it, keep it.</p>
</section>

</aside>

<main class="stream" id="note-stream">
<div class="q-loading">Loading notes&hellip;</div>
</main>

<div class="posbar notebar" id="notebar" hidden>
<button class="pb-step pb-top" id="nb-top" type="button" title="Back to the top" aria-label="Back to the top">Top</button>
</div>
</div>

<script>
window.QUIZ_BLOCK = {block_json};
</script>
<script src="{notes_js}"></script>
<script src="{portal_js}"></script>

{footer}

</div>

</body>
</html>
"""


QBANK_PAGE = u"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Question bank &middot; {course}</title>
<meta name="description" content="{desc}">
<meta name="robots" content="noindex, nofollow">
{favicon}

{nocache}
{fonts}
<link rel="stylesheet" href="{base_css}">
<link rel="stylesheet" href="{portal_css}">
<style>
:root{{{accent}}}
</style>
{cf}
</head>
<body>

<div class="pom2-page">

<nav class="blocknav">
{blocknav}
</nav>

<header class="q-masthead">
<div>
<p class="eyebrow" id="m-eyebrow"></p>
<h1>Question bank</h1>
<p class="lead">{lead}</p>
</div>
<div class="scoreboard" id="sb-questions">
<div class="score"><b><span id="sc-done">0</span><span class="of" id="sc-of"></span></b><span>Attempted</span></div>
<div class="score"><b id="sc-first">&ndash;</b><span>Correct</span></div>
<div class="score is-bad"><b id="sc-wrong">0</b><span>Wrong</span></div>
<div class="score is-star"><b id="sc-star">0</b><span>Starred</span></div>
</div>
</header>

{qpanel}

<script>
window.QUIZ_BLOCK = {block_json};
</script>
<script src="{quiz_js}"></script>
<script src="{portal_js}"></script>

{footer}

</div>

</body>
</html>
"""


def span(course):
    """First week of the first block to the last of the last."""
    dash = u"\u2013"
    first = course["blocks"][0][3].split(dash)[0]
    last = course["blocks"][-1][3].split(dash)[-1]
    return first + dash + last


def build_qbank(course):
    """The one page that serves a course's questions, every block pooled.

    This is the same engine the block pages used to run, handed a list of
    blocks instead of one - which is why there is no second quiz.js, and why
    an answer given here lands in that block's own store and shows up
    wherever else that block's progress is read.

    A block is one value of one filter, so a page per block was a page per
    filter value. What it cost was everything that crosses a block: review
    every wrong answer in the course, sit a hundred questions before the
    summative, drill weeks 7 to 11. None of those can be said on a page whose
    scope is one block, and they are what people ask for near an exam.
    """
    d = course["slug"]
    lead, desc = existing_term(course)
    blocks, total = [], 0
    for slug, n, name, weeks in course["blocks"]:
        qp = os.path.join(d, "data", "questions", "%s.json" % slug)
        total += len(json.load(io.open(qp, encoding="utf-8")))
        block = {"slug": slug, "n": n, "name": name, "weeks": weeks,
                 "qv": portal.digest(qp)}
        # The bank's note dialog fetches this block's notes on demand and needs
        # the same cache-busting hash the block page carries for them.
        npath = os.path.join(d, "data", "notes", "%s.json" % slug)
        if os.path.exists(npath):
            block["nv"] = portal.digest(npath)
        blocks.append(block)
    cfg = {
        "slug": "term", "name": u"the whole term", "course": course["short"],
        "store": course["store"], "families": course["families"],
        "eyebrow": u"Every block \u00b7 Weeks %s \u00b7 %d questions" % (span(course), total),
        "blocks": blocks,
        "dir": d, "contact": portal.CONTACT, "report": portal.REPORT_URL,
    }
    label, fill = FAVICON[d]
    html = QBANK_PAGE.format(
        base_css=portal.asset("base.css"), portal_css=portal.asset("portal.css"),
        quiz_js=portal.asset("quiz.js"), portal_js=portal.asset("portal.js"),
        course=course["short"], lead=lead, desc=desc, accent=term_accent(course),
        fonts=portal.FONTS, nocache=portal.NOCACHE, cf=portal.CF,
        footer=portal.footer(), favicon=portal.favicon(label, fill),
        blocknav=blocknav(course, "qbank"),
        qpanel=QPANEL.format(howto=HOWTO, questions=total, hidden=""),
        block_json=json.dumps(cfg, ensure_ascii=False))
    io.open(os.path.join(d, "qbank.html"), "w",
            encoding="utf-8", newline="\n").write(html)
    print("%-5s %-6s %d blocks pooled  %4d questions" % (d, "qbank", len(blocks), total))


def main():
    for course in portal.COURSES:
        for slug, n, name, weeks in course["blocks"]:
            lead, desc, accent = existing(course, slug)
            q, written, lectures = block_counts(course, slug)
            d = course["slug"]
            cfg = {
                "slug": slug, "n": n, "name": name, "weeks": weeks,
                "course": course["short"], "store": course["store"],
                "families": course["families"],
                "qv": portal.digest(os.path.join(d, "data", "questions", "%s.json" % slug)),
                "nv": portal.digest(os.path.join(d, "data", "notes", "%s.json" % slug)),
                "dir": d, "contact": portal.CONTACT, "report": portal.REPORT_URL,
            }
            label, fill = FAVICON[d]
            html = PAGE.format(
                base_css=portal.asset("base.css"), portal_css=portal.asset("portal.css"),
                quiz_js=portal.asset("quiz.js"), notes_js=portal.asset("notes.js"),
                portal_js=portal.asset("portal.js"),
                name=name, course=course["short"], weeks=weeks, lead=lead, desc=desc, accent=accent,
                fonts=portal.FONTS, nocache=portal.NOCACHE, cf=portal.CF, footer=portal.footer(), howto=HOWTO, favicon=portal.favicon(label, fill),
                blocknav=blocknav(course, slug), questions=q, slug=slug,
                anki=anki_panel(course, slug, weeks), ankitc=anki_tc(course, slug),
                written=written, lectures=lectures,
                block_json=json.dumps(cfg, ensure_ascii=False))
            io.open(os.path.join(d, "%s.html" % slug), "w",
                    encoding="utf-8", newline="\n").write(html)
            print("%-5s %-6s %2d/%d notes  %4d questions" % (d, slug, written, lectures, q))
        # a one-block course has nothing to pool, and no page to pool it on
        if len(course["blocks"]) > 1:
            build_qbank(course)


if __name__ == "__main__":
    main()
