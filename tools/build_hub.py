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
        notes = (u'<span><b>%d</b> lecture notes</span>' % w) if l else u''
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
<summary>What is the Schulich Pre-Clerkship Portal?</summary>
<div class="body">

<p>
Picture this: it is the first week of a new term. You sit down to get organized and somehow
end up with 20 tabs open: upper-year notes, Christina&rsquo;s Anki deck, three Q-banks, old
lecture slides, a group-chat message calling something &ldquo;high-yield,&rdquo; and a Drive
folder you do not remember getting access to.
</p>

<p>
Then you find out the block changed. The notes no longer match the modules, some Anki cards
are old, and the Q-bank is asking about material you are not even covering anymore.
</p>

<p>
<strong>Cue the Schulich Pre-Clerkship Portal.</strong>
</p>

<p>
It is a centralized, dynamic, up-to-date resource for all Schulich medical students in
pre-clerkship.
</p>

<p>
It includes:
</p>

<ul>
<li><strong>Notes:</strong> Summary notes, charts, flowcharts, illustrations, and Schulich Reviews, organized by block, week, and lecture. Any note can be exported to PDF and annotated.</li>
<li><strong>Anki:</strong> An updated version of Christina&rsquo;s Anki deck, organized by block, week, and lecture.</li>
<li><strong>Question bank:</strong> A Q-bank that students can filter by block, week, or source, then use to make their own custom practice tests. Progress is saved, so you can revisit questions you got wrong. Every question is directly from our curriculum, including module questions and weekly quizzes, or from previous student Q-banks, including Hippo Council, Schulich Reviews, and the Pre-Clerkship Workbook. New questions come from DSSGs, in-class sessions, and modules, not low-yield AI-generated trivia.</li>
</ul>

<p>
The best part is that it is open-source. Anyone can pick up where we left off, improve it,
and keep it current. Through collaborations with the <strong>Open-Source Medicine Club</strong> + <strong>AI in
Medicine</strong>, incoming students can learn to use our AI automation pipeline to maintain and
quality-control the Portal, helping it stay dynamic and sustainable beyond any one person&rsquo;s
term.
</p>

</div>
</details>

<details class="fold">
<summary>Open source: contribute or customize</summary>
<div class="body">

<p>
The portal is open source at
<a href="https://github.com/schulichmed/preclerkship" target="_blank" rel="noopener noreferrer">github.com/schulichmed/preclerkship</a>.
</p>

<p>
The beauty of open-source is anyone can access the work, contribute to it or customize it to
their needs. It&rsquo;s crowdsourced expertise that creates user-vetted products.
</p>

<p>
<strong>To contribute.</strong> Suggest a feature, fix an answer you think is wrong, or send
in questions of your own, and it goes into the portal for everyone. You need a GitHub
account; Claude Code can do the rest. Paste this into it:
</p>

<p class="prompt">Clone https://github.com/schulichmed/preclerkship and read the README so you understand how the portal is built. I want to contribute: [what you are adding, for example: the questions from the week 8 MSK module, a correction to an answer, or a feature]. Match the format the existing files use, rebuild the pages with the scripts in tools/, then create a branch, commit, and open a pull request against schulichmedfriend/preclerkship explaining what changed and why.</p>

<p>
Corrections and questions are the two most useful things to send.
</p>

<p>
<strong>To customize.</strong> Make your own copy and change anything in it, from the courses
it covers and the questions in them to the wording, the layout and the tooling around it.
Paste this into Claude Code:
</p>

<p class="prompt">Clone https://github.com/schulichmed/preclerkship and read the README so you understand how the portal is built. I want to make it mine: [what you want changed, for example: cut it down to the blocks I am on, import my own lecture notes and questions, restyle the pages, or build an Anki deck from only the questions I got wrong]. Work out which files that touches, make the change, and rebuild the pages with the scripts in tools/.</p>

<p>
You can also just take the material out. The questions and the notes are both plain JSON under
each course&rsquo;s <code>data/</code>, so you can extract either one into whatever you already
study from. Keep in mind they are being updated week by week, so what you pull is a snapshot
of that week.
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
<strong>Co-developers.</strong> Noor Simsam and Nora Treleaven, Class of 2029.
</p>

<p>
<strong>Contributors.</strong> Ashish Saragadam, Negar Goodarzynejad, Jessica Wang,
Tamjeed Nawaz, Yasmine Madan, Class of 2029.
Wessam Al Jawhri, Class of 2030.
</p>

<p>
<strong>Upper-year resource credits.</strong> Nicole&rsquo;s Notes, Maggie&rsquo;s Notes,
Christina&rsquo;s Anki, Hippo Council Qbank, Schulich Reviews.
</p>

<p>
Want to be added to the credits? Contribute or make some edits via a GitHub PR:
instructions are under <strong>Open source: contribute or customize</strong> above.
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
