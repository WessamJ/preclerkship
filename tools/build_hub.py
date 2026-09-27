# -*- coding: utf-8 -*-
"""Build the portal's front door: one card per course, with real counts.

Purpose: the root landing page of the pre-clerkship portal.
Author:  Noor Sims
Date:    2026-09-21
Input:   tools/portal.py and each course's data/
Output:  index.html

Run from the repo root, last. A course with nothing in it still gets a card,
greyed and unlinked, saying so - the portal shows the gap rather than hiding it,
which is the same reason a lecture with no note still renders on the notes tab.
"""

import io, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portal


def cards():
    out = []
    for c in portal.COURSES:
        q, w, l = portal.counts(c)
        if not c["blocks"]:
            out.append(
                u'<div class="block-card is-empty" style="--hue:%s">\n'
                u'<p class="bmeta">%s</p>\n'
                u'<h2>%s</h2>\n<p>%s</p>\n'
                u'<span class="tally"><span>not built yet</span></span>\n'
                u'</div>' % (c["accent"], c["year"], c["name"], c["blurb"]))
            continue
        notes = (u'<span><b>%d</b> of %d lecture notes</span>' % (w, l)) if l else u''
        out.append(
            u'<a class="block-card" href="%s/index.html" style="--hue:%s">\n'
            u'<p class="bmeta">%s &middot; %d blocks</p>\n'
            u'<h2>%s</h2>\n<p>%s</p>\n'
            u'<span class="tally">\n%s\n'
            u'<span><b>%s</b> practice questions</span>\n'
            u'</span>\n'
            u'</a>' % (c["slug"], c["accent"], c["year"], len(c["blocks"]),
                       c["name"], c["blurb"], notes, "{:,}".format(q)))
    return "\n".join(out)


def totals():
    q = w = l = 0
    for c in portal.COURSES:
        a, b, d = portal.counts(c)
        q += a; w += b; l += d
    return q, w, l


TEMPLATE = u"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Schulich Pre-clerkship</title>
<meta name="description" content="Notes and practice questions for the pre-clerkship years at Schulich: Foundations of Medicine, Principles of Medicine 1 and 2, and Transition to Clerkship.">
<meta name="robots" content="noindex, nofollow">
{favicon}

{nocache}
{fonts}
<link rel="stylesheet" href="{base_css}">
<link rel="stylesheet" href="{portal_css}">
<style>
:root{{--q-accent:#1f4e5f;--q-accent-soft:#dfecf0;--q-accent-ink:#193f4d;}}
</style>
{cf}
</head>
<body>

<div class="pom2-page">

<div class="page-hero">
<h1>Schulich Pre-clerkship.</h1>
<p>
A centralized, dynamic, up-to-date resource for all Schulich med students in
pre-clerkship.
</p>
</div>

<div class="block-grid hub-grid">
{cards}
</div>

<div class="prose">

<details class="fold">
<summary>Where the practice questions come from</summary>
<div class="body">

<p>
No AI-generated trivia questions. Every question traces back to a source in our
curriculum, keeps the set it arrived in, and can be filtered by that set on the block
page it sits on. The two built courses draw on different banks, so they are listed apart.
</p>

<p>
<strong>Foundations of Medicine.</strong> All of it is the FoM question bank the Schulich
classes pass down, transcribed out of the PDFs rather than rewritten.
</p>

<ul>
<li><strong>Module questions.</strong> The knowledge checks inside each week&rsquo;s Elentra asynchronous learning modules.</li>
<li><strong>Readiness assessments</strong> and <strong>self-assessments.</strong> The week&rsquo;s RA and SA as they were sat and released. Several early weeks never had one; those say so rather than going quietly missing.</li>
<li><strong>Meds 2024 bank.</strong> The student-written, <strong>instructor-approved</strong> bank the Class of 2024 Academic Directors built in December 2020. Their questions went to the teaching faculty and the instructors&rsquo; edits are folded in, except for a tail of each week that time ran out on.</li>
<li><strong>New questions.</strong> Written by the Meds 2025 volunteers in December 2021 to fill the gaps. The bank says on its own second page that these were <strong>not verified by faculty</strong>.</li>
<li><strong>Pre-Clerkship Workbook.</strong> The 2023 edition handed down through the Schulich classes of 2015 to 2025: its Foundations, Hematology and Infection &amp; Immunity chapters. Peer-written across a decade, and the only set here not organised by week.</li>
</ul>

<p>
<strong>Principles of Medicine 2.</strong>
</p>

<ul>
<li><strong>Course modules.</strong> Elentra knowledge checks, the concept checks in the lecture slides, and the weekly quizzes.</li>
<li><strong>Pre-Clerkship Workbook.</strong> The 2023 student bank handed down through the Schulich classes of 2015&ndash;2025. Peer-written, so its errors are flagged on the question.</li>
<li><strong>Meds 2029.</strong> Questions written from the patient cases in the modules, the DSSGs and the in-class sessions.</li>
<li><strong>Schulich Reviews.</strong> Both the practice questions and the summary content. TBD.</li>
</ul>

<p>
Where a bank handed between years has a gap or an error, it is flagged on the face of the
question rather than quietly patched, so you can see what you are trusting before you
trust it.
</p>

<p>
What they are written to, from the syllabus:
</p>

<blockquote>
<p>
Most of the questions will involve clinical scenarios which will assess clinical decision
making around: <strong>localization, differential diagnosis, ordering appropriate
investigations, or management</strong> of the patient. The questions will not be simple
recall questions, and the student will need to apply foundational knowledge to clinical
scenarios.
</p>
</blockquote>

<p>
And on integrating across blocks:
</p>

<blockquote>
<p>
As outlined in the syllabus, approximately <strong>20% of Progress Test #2</strong> will
consist of <strong>integration questions</strong>. These may require you to draw on
foundational knowledge from <strong>FOM, P1, and the first half of P2</strong> to reason
through a <strong>new MCC-style clinical presentation</strong>. The purpose is not to
re-examine previous blocks, but to assess your ability to <strong>apply previously learned
knowledge in a new clinical context</strong>.
</p>
<p>
When preparing, think broadly about <strong>clinical presentations</strong> rather than
focusing only on the body system currently being taught. You should be able to
<strong>integrate knowledge across systems</strong> and consider appropriate
<strong>differential diagnoses</strong>. Examples include <strong>abdominal pain</strong>,
<strong>shortness of breath</strong>, <strong>cardiac rhythm disturbances</strong>,
<strong>anemia</strong>, <strong>pulmonary embolism</strong>, and <strong>deep vein
thrombosis</strong>.
</p>
</blockquote>

</div>
</details>

<details class="fold">
<summary>Open source: customize or improve</summary>
<div class="body">

<p>
The portal is open source at
<a href="https://github.com/schulichmed/preclerkship" target="_blank" rel="noopener noreferrer">github.com/schulichmed/preclerkship</a>.
</p>

<p>
The beauty of open-source is anyone can access the work, improve it or customize it to their
needs. It&rsquo;s crowdsourced expertise that creates user-vetted products.
</p>

<p>
<strong>To customize it.</strong> Anything here can change, from the courses it covers and
the questions in them to the wording, the layout and the tooling around it. Paste this into
Claude Code:
</p>

<p class="prompt">Clone https://github.com/schulichmed/preclerkship and read the README so you understand how the portal is built. I want to make it mine: [what you want changed, for example: cut it down to the blocks I am on, import my own lecture notes and questions, restyle the pages, or build an Anki deck from only the questions I got wrong]. Work out which files that touches, make the change, and rebuild the pages with the scripts in tools/.</p>

<p>
You can also just take the material out. The questions and the notes are both plain JSON under
each course&rsquo;s <code>data/</code>, so you can extract either one into whatever you already
study from. Keep in mind they are being updated week by week, so what you pull is a snapshot
of that week.
</p>

<p>
<strong>To improve it.</strong> Suggest a feature, fix an answer you think is wrong, or send
in questions of your own. You need a GitHub account; Claude Code can do the rest. Paste
this into it:
</p>

<p class="prompt">Clone https://github.com/schulichmed/preclerkship and read the README so you understand how the portal is built. I want to contribute: [what you are adding, for example: the questions from the week 8 MSK module, a correction to an answer, or a feature]. Match the format the existing files use, rebuild the pages with the scripts in tools/, then create a branch, commit, and open a pull request against schulichmedfriend/preclerkship explaining what changed and why.</p>

<p>
Corrections and questions are the two most useful things to send.
</p>

<p>
<strong>Or just email.</strong> You do not need GitHub, or any of the above, to get in
touch. Anything at all &mdash; a correction, a question, a request, a course you want
added &mdash; goes to
<a href="mailto:schulichmedfriends@gmail.com">schulichmedfriends@gmail.com</a>.
</p>

</div>
</details>

<details class="fold">
<summary>Credits</summary>
<div class="body">

<p>
A collaborative initiative by the Schulich <strong>Open-Source Medicine</strong> and
<strong>AI in Medicine</strong> clubs.
</p>

<p>
<strong>Co-developers.</strong> Noor Simsam and Nora Treleaven.
</p>

<p>
<strong>Contributors.</strong> Ashish Saragadam, Negar Goodarzynejad, Jessica Wang,
Tamjeed Nawaz, Yasmine Madan.
</p>

<p>
<strong>Upper-year resource credits.</strong> Nicole&rsquo;s Notes, Maggie&rsquo;s Notes,
Christina&rsquo;s Anki, Hippo Council Qbank.
</p>

<p>
Want to be added to the credits? Contribute or make some edits via a GitHub PR:
instructions are under <strong>Open source: customize or improve</strong> above.
</p>

</div>
</details>

</div>

{footer}

</div>

</body>
</html>
"""


def main():
    q, w, l = totals()
    html = TEMPLATE.format(
        favicon=portal.favicon("PC", "1f4e5f"), fonts=portal.FONTS, nocache=portal.NOCACHE,
        base_css="base.css?v=" + portal.digest("base.css"),
        portal_css="portal.css?v=" + portal.digest("portal.css"),
        cf=portal.CF, cards=cards(), footer=portal.footer())
    io.open("index.html", "w", encoding="utf-8", newline="\n").write(html)
    print("index.html: %d courses, %d built, %d questions, %d/%d lecture notes"
          % (len(portal.COURSES),
             len([c for c in portal.COURSES if c["blocks"]]), q, w, l))


if __name__ == "__main__":
    main()
