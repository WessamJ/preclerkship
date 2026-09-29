# -*- coding: utf-8 -*-
"""What every course in the pre-clerkship portal shares.

Purpose: hold the course roster, the block-page template and the cache-busting
         helpers in one place, so four courses cannot drift into four dialects.
Author:  Noor Sims
Date:    2026-09-21

The portal is one site per year of pre-clerkship, all served from one origin and
all drawing on one engine (base.css, portal.css, quiz.js, notes.js, portal.js at
the repo root). A course is a directory, a block list and a set of question-set
families; everything else about it is data under its own directory.

Two of the four courses have no content yet. They are listed anyway, because the
portal's whole habit is to show the gap rather than hide it - a lecture with no
note still renders greyed, and a course with no blocks says so on the hub.
"""

import hashlib
import io
import json
import os

# Progress is per-course in localStorage. The prefixes must stay distinct or one
# course would read and overwrite another's answers, since they share an origin.
COURSES = [
    {
        "slug": "fom",
        "short": u"FoM",
        "name": u"Foundations of Medicine",
        "year": u"Year 1",
        "blurb": u"The first fifteen weeks: what a physician does, then the body from "
                 u"cells up, then blood, then infection and immunity.",
        "accent": u"#1f4e5f",
        "store": "nsq.fom.v1.",
        "blocks": [
            ("b1", 1, u"Principles & Development",      u"1–4"),
            ("b2", 2, u"Regulation, Neoplasia & Aging", u"5–8"),
            ("b3", 3, u"Hematology",                    u"9–12"),
            ("b4", 4, u"Infection & Immunity",          u"13–15"),
        ],
        "families": [
            {"key": "module", "name": u"Module questions",
             "blurb": u"The knowledge checks inside the week's Elentra asynchronous "
                      u"learning modules, transcribed into the Meds 2025 question bank."},
            {"key": "ra", "name": u"Readiness assessments",
             "blurb": u"The week's Readiness Assessment as it was sat. Several weeks "
                      u"never had one, and those say so rather than going missing."},
            {"key": "sa", "name": u"Self-assessments",
             "blurb": u"The week's Self-Assessment as it was released."},
            {"key": "meds2024", "name": u"Meds 2024 bank",
             "blurb": u"The student-written, instructor-approved bank built by the Class "
                      u"of 2024 Academic Directors in December 2020, re-filed week by "
                      u"week. Its questions went to the teaching faculty and the "
                      u"instructors' edits are folded in, except for a tail of each week "
                      u"that time ran out on."},
            {"key": "new", "name": u"Meds 2025",
             "blurb": u"Written fresh by the Meds 2025 volunteers in December 2021. The "
                      u"bank states on its own second page that these were not verified "
                      u"by faculty, so treat a disagreement as a question worth chasing "
                      u"rather than a correction to accept."},
            {"key": "workbook", "name": u"Pre-Clerkship Workbook",
             "blurb": u"The 2023 edition of the workbook handed down through the Schulich "
                      u"classes of 2015 to 2025: its Foundations, Hematology and "
                      u"Infection & Immunity chapters. The workbook files by subject "
                      u"rather than by week, so the block is its own but the week here is "
                      u"inferred; where nothing in a question placed it, it says so on "
                      u"its face. The Foundations chapter's own subject labels are in the "
                      u"Topic filter."},
            {"key": "reviews", "name": u"Schulich Reviews",
             "blurb": u"The Schulich Reviews sessions, run by upper years before each exam. "
                      u"Their own practice questions, keyed by the deck, plus questions "
                      u"written from their high-yield slides. Where a review disagrees "
                      u"with this year's lecture, the lecture wins and the question says so."},
        ],
    },
    {
        "slug": "pom1",
        "short": u"PoM 1",
        "name": u"Principles of Medicine 1",
        "year": u"Year 1",
        "blurb": u"The second half of first year, system by system.",
        "accent": u"#6b5a2f",
        "store": "nsq.pom1.v1.",
        "blocks": [
            ("cardio", 1, u"Cardiology",             u"1\u20135"),
            ("resp",   2, u"Respirology",            u"6\u20138"),
            ("ent",    3, u"Ear, Nose & Throat",     u"9"),
            ("gi",     4, u"Gastroenterology",       u"10\u201313"),
            ("gu",     5, u"Nephrology & Urology",   u"14\u201317"),
        ],
        "families": [
            {"key": "module", "name": u"Module questions",
             "blurb": u"The knowledge checks inside the week's Elentra asynchronous "
                      u"learning modules, transcribed into the Meds 2025 block banks."},
            {"key": "weekly", "name": u"Weekly quizzes",
             "blurb": u"The week's quiz as it was sat, kept whole as its own set so a "
                      u"week can be drilled the way it was written."},
            {"key": "meds2024", "name": u"Meds 2024 bank",
             "blurb": u"The student-written bank the Class of 2024 Academic Directors "
                      u"built in May 2021, re-filed week by week by the Meds 2025 "
                      u"volunteers. About half the cardiology questions and a handful of "
                      u"the respirology ones were reviewed by faculty; the rest were not, "
                      u"and the bank says so on its own second page."},
            {"key": "new", "name": u"Meds 2025",
             "blurb": u"Written fresh by the Meds 2025 volunteers through the spring of "
                      u"2022 to fill the gaps. Not verified by faculty, so treat a "
                      u"disagreement as a question worth chasing rather than a correction "
                      u"to accept."},
            {"key": "workbook", "name": u"Pre-Clerkship Workbook",
             "blurb": u"The 2023 edition of the workbook handed down through the Schulich "
                      u"classes of 2015 to 2025: its Cardiology, Respiration & Airways, "
                      u"Ear Nose & Throat, Gastroenterology and Genitourinary chapters. "
                      u"The workbook files by organ system rather than by week, so the "
                      u"block is its own and the week here is inferred; where nothing in "
                      u"a question placed it, it says so on its face."},
            {"key": "reviews", "name": u"Schulich Reviews",
             "blurb": u"The Schulich Reviews sessions, run by upper years before each exam. "
                      u"Their own practice questions, keyed by the deck, plus questions "
                      u"written from their high-yield slides. Where a review disagrees "
                      u"with this year's lecture, the lecture wins and the question says so."},
        ],
    },
    {
        "slug": "pom2",
        "short": u"PoM 2",
        "name": u"Principles of Medicine 2",
        "year": u"Year 2",
        "blurb": u"The five blocks of second year, with a written note for every "
                 u"lecture that has one and a coverage map for the rest.",
        "accent": u"#84223b",
        "store": "nsq.v1.",
        "blocks": [
            ("endo",  1, u"Endocrinology",   u"1–3"),
            ("repro", 2, u"Reproduction",    u"4–6"),
            ("msk",   3, u"Musculoskeletal", u"7–11"),
            ("neuro", 4, u"Neurology",       u"12–16"),
            ("psych", 5, u"Psychiatry",      u"17–20"),
        ],
        "families": [
            {"key": "module", "name": u"Course modules",
             "blurb": u"The Elentra module knowledge checks and the concept checks on the "
                      u"lecture slides. Cases live under Meds 2029 instead, wherever they "
                      u"came from."},
            {"key": "weekly", "name": u"Weekly quizzes",
             "blurb": u"The weekly quizzes, both the Microsoft Forms ones and the ones sat "
                      u"in Elentra. Kept whole as their own set, so a week's quiz can be "
                      u"drilled the way it was written."},
            {"key": "workbook", "name": u"Pre-Clerkship Workbook",
             "blurb": u"The Pre-Clerkship Workbook (2023 edition), the student bank passed "
                      u"down through the Schulich classes of 2015-2025. It has a written "
                      u"key, but the key is peer-written and contains real errors. Every "
                      u"one found is flagged on the question."},
            {"key": "meds2029", "name": u"Meds 2029",
             "blurb": u"Questions built from patient cases in the modules, DSSGs and "
                      u"in-class lectures, since exams tend to recycle similar cases."},
            {"key": "reviews", "name": u"Schulich Reviews",
             "blurb": u"The Schulich Reviews sessions, run by upper years before each exam. "
                      u"Their own practice questions, keyed by the deck, plus questions "
                      u"written from their high-yield slides. Where a review disagrees "
                      u"with this year's lecture, the lecture wins and the question says so."},
            {"key": "hipponotes", "name": u"HippoNotes",
             "blurb": u"The question banks at the back of the Meds 2025 HippoNotes "
                      u"(Academic Resources Team, May 2023) - one document per block, "
                      u"written by the class two years ahead. Peer-written like the "
                      u"Workbook, so the key is worth checking rather than trusting; "
                      u"the source groups by week only, with no per-lecture attribution."},
        ],
    },
    {
        "slug": "t2c",
        "short": u"T2C",
        "name": u"Transition to Clerkship",
        "year": u"Year 2",
        "blurb": u"The bridge into clerkship at the end of second year.",
        "accent": u"#3f4a5a",
        "store": "nsq.t2c.v1.",
        "blocks": [
            ("peds",   1, u"Pediatrics",                          u"1\u20132"),
            ("surg",   2, u"Surgery",                             u"3\u20134"),
            ("psych",  3, u"Psychiatry, Palliative & Geriatrics", u"5\u20136"),
            ("em",     4, u"Emergency Medicine",                  u"7"),
            ("fmob",   5, u"Family Medicine & Obstetrics",        u"8\u20139"),
            ("dermim", 6, u"Dermatology & Internal Medicine",     u"10\u201313"),
        ],
        "families": [
            {"key": "hipponotes", "name": u"HippoNotes",
             "blurb": u"The T2C question bank at the back of the Meds 2025 HippoNotes "
                      u"(Academic Resources Team, May 2023), filed under the rotation "
                      u"each question was written for. Peer-written, so the key is "
                      u"worth checking rather than trusting."},
        ],
    },
]

BY_SLUG = dict((c["slug"], c) for c in COURSES)

# the engine, shared by every course and living at the repo root
ASSETS = ["base.css", "portal.css", "portal.js", "quiz.js", "notes.js"]


def digest(path):
    """The content hash of a file, for cache busting."""
    return hashlib.md5(io.open(path, "rb").read()).hexdigest()[:8]


def asset(name):
    """<../name>?v=<hash>, as a course page one level down refers to it.

    Static hosts serve these with a cache lifetime of several minutes, long
    enough for a browser to paint new markup with last deploy's rules. Stamping
    the content hash into the URL makes a changed file a different URL; an
    unchanged one keeps its hash and stays cached. Re-run the builders after
    editing any of the hand-maintained css or js, or the pages keep pointing at
    the previous hash.
    """
    return "../%s?v=%s" % (name, digest(name))


def counts(course):
    """(questions, notes written, lectures) for a course, from its own data."""
    d = course["slug"]
    q = w = l = 0
    for slug, _n, _name, _weeks in course["blocks"]:
        qp = os.path.join(d, "data", "questions", "%s.json" % slug)
        np = os.path.join(d, "data", "notes", "%s.json" % slug)
        if os.path.exists(qp):
            q += len(json.load(io.open(qp, encoding="utf-8")))
        if os.path.exists(np):
            lects = [x for wk in json.load(io.open(np, encoding="utf-8"))["weeks"]
                     for x in wk["lectures"]]
            l += len(lects)
            # A lecture whose material is written up under a neighbouring lecture
    # counts as written: the note exists and the page says where. Counting it
    # as a gap would disagree with the coverage the page itself paints.
            w += len([x for x in lects
                      if x.get("hasNote") or x.get("coveredBy")])
    return q, w, l


FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;'
         '9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">')

# The CSS, JS and JSON are all content-hashed, so the browser may cache them
# forever. The pages that name those hashes must NOT be cached that way, or a
# rebuild is invisible until someone thinks to hard-refresh - which is exactly
# what happened. "no-cache" is not "don't store": it stores the page and asks
# whether it changed, so an unchanged page still costs one 304 and no download.
NOCACHE = ('<meta http-equiv="Cache-Control" content="no-cache, must-revalidate">\n'
           '<meta http-equiv="Pragma" content="no-cache">')

# Cloudflare Web Analytics: counts visits without cookies, so it needs no consent
# banner. The token is from the dashboard's Web Analytics > schulichmed.github.io
# snippet; it is public (it ships in every page) and not a secret. Leave it empty
# and the pages go out with no analytics at all.
CF_TOKEN = "d66f0003318d42f1bd62e0a2c3e216af"
CF = (f"<script type='module' src='https://static.cloudflareinsights.com/beacon.min.js' "
      f"data-cf-beacon='{{\"token\": \"{CF_TOKEN}\"}}'></script>") if CF_TOKEN else ""


# Where "All courses" points. Absolute, not relative: the portal is served from
# more than one place, and the hub every page should return to is this one
# wherever the copy being read happens to live.
HUB_URL = "https://schulichmed.github.io/preclerkship/"


def uplink(depth=None):
    """The one way back up to the hub, for pages that have no block nav."""
    return '<a class="uplink" href="%s">&larr; All courses</a>' % HUB_URL


CONTACT = "schulichmedfriends@gmail.com"
# Where the bank's Report button posts. Empty until the relay in
# tools/report-worker/ is deployed; empty, the button emails CONTACT instead.
REPORT_URL = "https://preclerkship-report.schulichmed.workers.dev/"


def footer():
    return ('<footer>\nFor questions, email '
            '<a href="mailto:%s">%s</a>\n</footer>' % (CONTACT, CONTACT))


def favicon(label="PC", fill="1f4e5f"):
    return ("<link rel=\"icon\" href=\"data:image/svg+xml,"
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
            "<rect width='32' height='32' rx='7' fill='%%23%s'/>"
            "<text x='16' y='23' font-family='Georgia,serif' font-size='%d' "
            "font-weight='600' fill='%%23ffffff' text-anchor='middle'>%s</text>"
            "</svg>\">" % (fill, 17 if len(label) < 3 else 13, label))
