---
name: pom2-week
description: Run a week of PoM 2 work end to end, in order - update the medwiki lecture notes from the current OneNote lectures, bank the week's questions from every source, chart them, then ship both to the pom2 repo as portal JSON, rebuild the site, and update Anki. Use for "do week 2", "catch up endo week 3", "run the weekly pipeline", or any request spanning more than one of med-chart / med-questions / med-anki.
---

# A week of PoM 2, end to end

This skill is the **order and the glue**. The four `med-*` skills own their own formats and
rules. Invoke them, do not restate or second-guess them here - and where one of them is wrong,
fix it in its own file rather than adding a correction to this one, or the fix only exists for
someone who came in through this skill.

**Read first:** `C:\Users\nsims\medwiki\CLAUDE.md` (vault conventions) and
`C:\Users\nsims\OneDrive\Desktop\projects\pom2\tools\README.md` (the rebuild order).

## The unit of work is one block-week

| Block | Vault folder | Weeks | Portal slug |
| --- | --- | --- | --- |
| 1 Endocrinology | `01 - Endocrinology` | 1-3 | `endo` |
| 2 Reproduction | `02 - Repro` | 4-6 | `repro` |
| 3 Musculoskeletal | `03 - MSK` | 7-11 | `msk` |
| 4 Neurology | `04 - Neuro` | 12-16 | `neuro` |
| 5 Psychiatry | `05 - Psych` | 17-20 | `psych` |

Lecture notes live at
`C:\Users\nsims\medwiki\01 - Lectures\99 - PoM 2\<block folder>\Week N\NN - <Lecture>.md`.
Week folders are numbered **across the year, not within the block**, so Repro's weeks are
`Week 4` / `Week 5` / `Week 6` inside `02 - Repro`. The week number in the request is the folder
name, verbatim.

If the request does not name a block and a week, ask once, then run the rest without check-ins
except at the gates below.

## The order, and why it is this order

```
0  inventory            what is here, and is OneNote actually assembled yet
1  notes  <- OneNote    the vault note is rewritten from this year's lecture
2  questions <- notes   every source banked into the vault question notes
3  charts <- questions  the chart is written knowing what gets tested
4  portal JSON <- both  the hand-authored hop, pictures included
5  rebuild             four scripts, then commit
6  Anki <- notes        the delta against CLim, prioritised by the chart
7  report
8  late arrivals        quiz, DSSG, in-class cases - optional, never blocking
```

The high-yield signal flows **downhill from the questions**: the questions tell the chart what
matters, the chart tells the Anki pass which of its gaps matter most. That is why questions come
before charts, and why neither can be written from the note alone.

## Where the work lands

**The repo is the destination. Charts and questions ship on the site, not as an Artifact.**

| What | Written to | Shipped by |
| --- | --- | --- |
| Chart | the top of the vault lecture note | `data/notes/<slug>.json`, then the block page's notes tab |
| Question | a `00 - Practice Questions/` note | `data/questions/<slug>.json`, then the block page's questions tab |

The site is <https://noorsimsam.com/pom2/>, and `quiz.js` is its own question runner with its own
progress store, keyed on the same `qid` and held in the browser's `localStorage`.

**Do not publish a quiz Artifact as part of a week.** The five per-block Artifact hubs that
`med-quiz` documents predate the portal's questions tab and duplicate it. They still exist and
still hold recorded attempts, which is why **qids stay append-only** and
`reorder_bank.py` stays unrun, but regenerating them is **not** a step in this pipeline. Invoke
`med-quiz` only when she asks for a hub by name, or to read progress back out of one.

## Stage 0 - inventory before touching anything

Report this before doing any work, because it decides which stages have anything to do:

- Which lectures are in the week folder, which have a note at all, and which already open with
  `Overview chart:`. **A note existing is not a note being current**, see Stage 1.
- Which lecture slides are available, as a PDF in `C:\Users\nsims\OneDrive\Documents\` or as a
  OneNote page, and which lectures have neither.
- Which question notes in `00 - Practice Questions/` already carry a `## Week N` section for
  this week, and the highest `# N` in each, since that is where new qids continue from.
- Which slide decks for these lectures are on disk. They land flat in `C:\Users\nsims\Downloads\`,
  named by lecturer or by lecture title, so match loosely and list what you found **and what you
  did not**. The Week 2 clinical decks and all of Week 3 endo were never on disk.
- Which Rise module captures are on disk, as `C:\Users\nsims\Downloads\rise-*.js`, and which
  lectures they cover.
- Whether any of the **Stage 8** sources exist yet: a grabbed capture of the week's Elentra quiz,
  notes from the DSSG, notes from the in-class CBL. **Note them, do not chase them.** All three
  are on the course's schedule, so "not there" is the normal state for most of a week and says
  nothing about whether she is behind. Do not ask whether she has sat the quiz or been to the
  session, do not tell her to go, and do not hold any other work for them.

### Is OneNote actually assembled yet

**This is a required-fail check, not an observation.** She assembles the week herself: she
downloads the slides, uploads them to OneNote, and grabs the Rise module in alongside them. Only
then does OneNote hold this year's lecture. Stage 1 rewrites the vault note from OneNote on the
authority that OneNote is current, so running it against a **half-assembled** section does the
one thing worse than leaving a stale note in place: it overwrites good content with last year's,
and reports the overwrite as an update.

So before Stage 1 touches anything, confirm the week's OneNote section holds a page per lecture
in the week folder, with this year's decks in them. **If pages are missing, name them and stop.**
Do not proceed on the assumption she will add them; do not treat a thin section as a lecture with
little content.

**Recount every total at the moment you need it.** Never quote a question count from a skill
file, a README, this file, or a memory. Use `len()` over `data/questions/<slug>.json`, and say
when the count was taken.

## Stage 1 - update the vault lecture notes from OneNote

**This is work, not a check, and it comes first.** OneNote holds the current lectures. The vault
lecture note is written from them, and everything downstream is written from the vault note. So
every run of this skill **updates the week's medwiki notes from the current OneNote lectures
before anything else happens**. Skipping straight to questions or charts is the single most
damaging thing this pipeline can do, because a chart, its questions, its cards and its portal
page are all only as current as the note underneath them, and **nothing downstream can detect a
stale note**.

For every lecture in the week, in this order:

1. **Pull the current lecture from OneNote** (routes below).
2. **Write or update
   `01 - Lectures\99 - PoM 2\<block>\Week N\NN - <Lecture>.md` from it.** A missing note gets
   written. An existing note gets brought up to the lecture as it now stands: sections the
   lecture added, content it changed, figures it introduced. Follow the note's transclusions
   before concluding a topic is absent, since a note's byte size understates its coverage.
3. **Only then bank its questions** (Stage 2), and chart it after that (Stage 3).

Updating the body is a separate act from charting. The chart sits above the `---`, and
everything from the `> [!check] Objectives` callout down is the note's own body, which is what
this stage writes.

### OneNote outranks what is already in the note

**Most pre-existing medwiki lecture content is an upper year's notes, "Maggie's notes", not
hers and not this year's course.** Nothing in the vault says so: there is no provenance line, no
frontmatter field, and `CLAUDE.md` does not mention it. A note that reads as authoritative and
complete may be entirely inherited.

So when OneNote and the existing note disagree, **OneNote wins and the note gets corrected**.
This is not a merge and not a both-sides note. Replace the conflicting content, do not append the
current version underneath the old one and do not soften it into "some sources say".

- **Conflicting** content is overwritten from OneNote.
- **Absent** content, in OneNote but not in the note, is added.
- **Extra** content, in the note but not in this year's lecture, is left alone unless it
  contradicts OneNote. An upper year's note going deeper than the lecture is not a conflict, it
  is context.

**Report every override**: the lecture, what the note said, what OneNote says. Correcting the
note silently is what makes an inherited error indistinguishable from taught material next time
anyone reads it. The report is the only record, since the note keeps no history of what it used
to say.

This ordering holds for anything derived downstream too. Where a chart, a question's reasoned
answer, or a card was built on inherited content that OneNote contradicts, it is wrong at the
source and gets rebuilt, not patched.

### Staleness has to be read, not detected

**There is no automated sync and no provenance line in the note.** A lecture note records nothing
about which slide version it came from, so staleness cannot be found by timestamp or diff. The
note has to be read against the lecture. Do not skip a note because it looks long or looks
finished, and especially not because it looks polished: inherited notes are the polished ones.

Report every lecture as **written**, **updated**, **already current**, or **not updatable** with
the reason, and list the overrides made under each. "Already current" is a claim about content,
so only make it after actually comparing, never because a note exists.

**Getting at the slides.** Two routes, in order of preference:

1. **The PDF export in `C:\Users\nsims\OneDrive\Documents\`.** Named either by the vault lecture
   name (`04 - Clinically Useful Endocrine Principles.pdf`) or by the OneNote page title
   (`UME P2 Endocrine Pharmacology (Pharmacology of T2DM).pdf`), so match on both.
2. **OneNote via the ms365 MCP.** Notebook `Principles of Medicine 2`
   (`1-cd3f58aa-2e1a-44d4-b871-e2f265fbdd36`), content in section groups such as `B1 Endo`
   (`1-d25acdea-e17e-438b-9361-032cfff576ed`), lecture pages under `Synch W<N>`.
   Cross-notebook page listing fails with Graph error 20266, so query per-section. The token
   expires often, and a failed call says so. Ask her to run `login` rather than working around
   it.

   **Read the page's own text before you touch the printout, every time.** A lecture page is
   one `<p>` or two of *her typed notes*, an `<object>` (the attached PDF), and 20-90 `<img>`
   slide printouts. The printout carries no extractable text - that part is true - but her
   typed notes come back as ordinary HTML in the page body, and they are the most valuable
   thing on the page, because they are her annotation rather than the lecturer's slide.
   **Incorporate them into the vault note alongside the slide content, never instead of
   checking for them.** Extract them from the `rawResponse` field of
   `get-onenote-page-content` and grep it before concluding a page is empty - a page reporting
   only a few hundred bytes of text is *not* proof it is title-only. This cost a wrong answer
   on 2026-09-07: her note on the Synch W2 hypothyroidism page was skipped on the assumption
   the body was image-only.

   **Slide text** is not in the HTML - it is pixels. Fetch the `src` resources with
   `download-bytes-to-file` and read the PNGs directly, which works fine at 1279x720 and is
   much cheaper tiled 4-up into contact sheets.

   **Handwritten ink** is retrievable, but it is **opt-in - never part of the weekly run.**
   Transcribing one lecture page costs ~40 image reads, so do it only when she asks for it by
   name. Verified 2026-09-07 against Asynch W1 `Pharmacology of glucose lowering drugs_edited`:
   1,429 strokes, 36 annotation clusters, spanning slides 11-53.

   - **Fetch.** `get-onenote-page-content` has no flag for it. Go around it with
     `download-bytes-to-file` and the raw relative path
     `/users/<userId>/onenote/pages/<pageId>/content?includeInkML=true`. The reply is
     `multipart/mixed`: an HTML part, then an `application/inkml+xml` part.
   - **Parse.** There is **no recognised text** - only strokes, so it must be drawn to be read.
     Each `<inkml:trace>` is comma-separated points of absolute `X Y F` integers in himetric;
     its `brushRef` resolves to an `<inkml:brush>` carrying colour and width.
   - **Split pen from highlighter by colour**, or broad highlighter swipes swamp the writing.
     Seen in this notebook: highlighter `#FFFC00 #00F900 #FFACD5 #A9D8FF #A2D762`; pen
     `#000000 #E71225 #FF8517 #008C3A`.
   - **Cluster, don't band.** The page is ~8 m tall in himetric, so uniform bands are useless
     (82 unreadable strips on the first attempt). Sort pen strokes by y, break where the gap
     exceeds ~4000 himetric, drop clusters under ~3 strokes, and render each tightly cropped
     with any overlapping highlighter drawn *underneath* for context.
   - **Tie each cluster to its slide.** The HTML part gives every `<img>` an absolute `top:` in
     CSS px and the slides sit ~828 px apart; ink is himetric, and **1 px = 26.46 himetric**
     (`25.4/96*100`). So `cluster_y / 26.46` → px → nearest image top → slide number. This is
     what makes the transcription usable rather than a pile of loose phrases.
   - **Flag what you guessed.** Her shorthand is genuinely ambiguous in places. List the words
     you are unsure of rather than smoothing them over, and separately flag anything that reads
     like a content slip (`Orthostatic HTN` for hypotension, `DDP4` for DPP-4) - she wants those
     caught before they reach a question bank.

   Two traps in the server's own setup, if it ever needs re-adding. It must be spawned from the
   installed binary (`~/.npm-global/bin/ms-365-mcp-server`), **not** `npx -y` - npx re-resolves
   the registry on every launch and blows the MCP startup window, so the server reports
   `Failed to connect - Request timed out`. And `--verify-login` returns
   `Graph API access failed: 403` even when everything works, because it probes `/v1.0/me`, which
   needs a `User.Read` the onenote preset does not request. Ignore it and test a real OneNote
   call instead.

   Section names repeat across section groups - there are two `Synch W1`s and two `Synch W2`s in
   this notebook alone. Resolve a section through its section group, never by name.

Reading OneNote needs no permission. *Posting* to OneNote is a gate further down, and since
2026-09-07 it is a **rule, not a flag** - the server runs `--preset onenote` with no
`--read-only`, so the create tools are live and nothing mechanical will stop you.

## Stage 2 - questions into the vault

**A patient is the discriminator.** A question that presents a patient and reasons through them
is a **case**, and every case belongs to `New Questions - <topic>.md` with
`family: "meds2029"`, `source: "module-case"` - **whatever source it came from**: an Elentra
module knowledge check, a lecture slide, a DSSG, an in-class case. A case goes to `meds2029`
even when it carries lettered options, and a check on understanding stays in the module set
even when it is a one-line vignette. **Options are not the discriminator, a patient is.**

This rule governs every source below, and belongs at the top of the stage. Nested inside the
slide-deck sweep it read as deck-only, which is what let 38 endo cases sit under the module
family until 2026-09-08.

**A case already banked in the wrong note is marked, not moved.** Moving one changes its `qid`,
which orphans the `med-quiz` progress and the Anki cards joined on it. Leave the block where it
is and emit the marker directly under its `# N` heading:

```
<!-- set: meds2029 | source: module-case | qid: module-endo-Q99 -->
```

**An export reads the marker, not the note it is sitting in**; an unmarked question belongs to
the note's own family. Before Stage 5, check that the markers in the vault and the `meds2029`
entries in `data/questions/<slug>.json` name the same set.

### Every question names the lecture it tests, not just the week

**The week is a given. The lecture is the thing she actually has to go back and read.** A
question that resolves only to "Week 4 - Gynecology: Contraception, STIs, Pelvic Pain &
Menopause" has told her nothing she did not already know from the filter she used to get there,
and a week of PoM 2 is sixteen lectures deep.

So **every question banked in the vault carries its lecture**, and it carries it in a form that
resolves against the vault rather than in prose:

- The `#### group` heading is **the lecture's own name as the vault spells it**, minus the
  number. `#### Contraception`, not `#### Contraceptive methods`, because
  `01 - Lectures/99 - PoM 2/02 - Repro/Week 4/03 - Contraception.md` is the note it has to find.
- Where the group's name cannot be the lecture's - a CBL, a DSSG, a HippoNotes chapter, a
  workbook group spanning three lectures - the group carries an explicit
  **`Tests [[NN - Lecture]]`** line naming every lecture it draws on, the way the workbook notes
  already do:

  ```
  #### Pelvic pain, endometriosis & PID
  *Workbook Q15, Q34-Q38, Q138. Tests [[11 - Clinical Approach to Acute Pelvic Pain]],
  [[12 - Clinical Approach to Chronic Pelvic Pain]], [[10 - Endometriosis]].*
  ```

- **The link has to resolve.** A `Tests [[...]]` naming a note that does not exist is worse than
  no line at all, because it reads as attribution and is not. `tools/review_lectures.py` reports
  every one it cannot resolve; a run that names any is not finished.

**Name the lecture that teaches the material, not the session that asked the question.** A DSSG
case on adrenal incidentalomas tests `[[01 - Clinical Presentation and Evaluation of Adrenal
Gland Disease]]`; "DSSG - Approach to Adrenal & Pituitary Issues" is where it was asked, which is
already in `lectureMeta` and is not a lecture.

**And the lecture decides the week, not the other way round.** Where a question's material is
taught in a different week from the one the source filed it under, the lecture link is still the
lecture that teaches it - do not move the link to fit the heading. The reproduction workbook has
nine groups filed under the wrong week for exactly this reason, and the portal now renders the
lecture's week rather than the filing week, so a correct link quietly corrects a wrong heading.

### Every option has to look like the answer

**The medicine is the only thing allowed to pick the key out of the set.** Anything else that
singles it out is a **tell**, and one tell turns a case into a formatting puzzle she can solve
without reading it. Three have shipped and been caught after the fact, each in a different
currency. Check all three before banking, and again before the Stage 4 export:

- **Length.** Write every option to roughly the length of the longest one. A key that is
  qualified - *"..., so they confirm she is thyrotoxic but are not specific to Graves; the
  Graves-specific findings are absent"* - sitting above three four-word distractors is readable
  across the room. ⭐ **The qualification belongs in the answer callout, not in the option**: the
  option states the claim, the callout does the reasoning. **Measure it, do not eyeball it** -
  `len()` every option and confirm the key is not the longest. *Observed 2026-09-09: the key was
  the longest option in 18 of 24 DSSG questions, up to 4.8x the mean distractor.*
- **Markup.** Options carry **none** - no `**bold**`, no ⭐ or ⚠, and ⭐ **no wikilinks**, which
  `pom2.css` paints in accent ink with a dotted underline while plain options stay black.
  Whatever markup one option carries, all of them carry. Stems and answer callouts keep their
  wikilinks; those give nothing away. `.opt .wl` is neutralised in `pom2.css` as a backstop, but
  it knows only that one class - a lone `<strong>` is the same tell in another colour. *Observed
  2026-09-08: 252 endo options carried a wikilink, and in 16 questions exactly one option was
  tinted and it was the key.*
- **Position.** Spread the key across A-D, and check the spread **over the batch**, not per
  question. *Observed 2026-09-09: a first pass keyed all 25 new questions to A.*

The vault note and the portal JSON both carry the option text, so a tell fixed in one is still
live in the other. **Fix it in the vault note and re-export.**

### Nothing enters a question that the material did not put there

**Ask the source's own question, verbatim.** A DSSG prompt, an Elentra stem, a deck's Concept
Check: copy it, do not improve it. Its typos, its missing punctuation and its wrong units are
copied too and flagged in a `> [!warning]`, ⭐ **never silently corrected**. **Verify the copy
mechanically** rather than by eye - normalise whitespace and case, then assert each stem is a
substring of the extracted source text. Eyeballing missed a dropped question mark and a
`mmol/L`-for-`pmol/L` on the same pass that felt careful.

**Bank the questions the source asks, and no others.** The count comes from the source: 24
prompts is 24 questions. A question the material never asks is out of scope however good it is,
and a plausible one is worse than an obvious one because nothing later flags it.

**Build options and answers from the block's own notes.** ⭐ **Grep the block before asserting a
clinical fact in an answer** - if the phrase is not there, it is not available, whatever you know
about the medicine. Where a case turns on something the notes genuinely lack, ⭐ **say so in the
answer and leave it open for the facilitator**; do not fill the gap from elsewhere and let it
read as taught material.

*Observed 2026-09-09, all four from one DSSG pass: a thyroid bruit, non-pitting edema, a pleural
effusion and a thyroiditis timeline in months were all reasoned into answers, and none of the
four appears anywhere in the endocrinology block.* The notes usually carry a **better**
discriminator than the one being reached for - goiter symmetry, the wide-versus-narrow pulse
pressure and the Woltman sign were all sitting in the same table.

Invoke **`med-questions`**. Two sources are available the moment the lecture is, and they never
merge across notes:

- **Elentra module knowledge checks** into `Module Questions - <topic>.md`. **Do not transcribe
  these by hand.** Rise ships a whole module, keys included, as one `runtime-data.js`, so the
  Rise grab in the bookmarks bar fetches it without reading the page, and it decodes with:

  ```
  python "C:\Users\nsims\medwiki\.scripts\rise_to_bank.py" "<bank note>.md" C:\Users\nsims\Downloads\rise-*.js
  ```

  It appends each module as its own `#### <module title>` section and continues the `# N`
  numbering from whatever is already in the bank. **Re-running with a module already present is
  a no-op**, so running it over the whole `Downloads` folder is safe and is usually the right
  call. It also records an image card's referenced filename and emits `![[filename]]`, which is
  where Stage 4's picture rule picks up.

  > `rise_to_bank.py` and `reorder_bank.py` sit in the same directory. You run the first one
  > every week. You never run the second - see the qid rule below.

- **Slide decks, split by what the slide is.** A comprehension check goes to
  `Module Questions - <topic>.md` under its own `#### Concept Checks - <Lecture>` heading. A
  **patient case** goes to `New Questions - <topic>.md`, `family: "meds2029"`,
  `source: "module-case"`. This is the routing rule, not a guideline. See the sweep below, which
  `med-questions` does not cover.

The **weekly quiz, the DSSG cases and the in-class CBL cases** are not here. They arrive on the
course's schedule rather than hers, so they are **Stage 8**, and a week is complete without any
of them.

**Watch for the same question arriving twice.** A module and its lecturer's deck are often the
same slides, so a knowledge check can come in through both the Rise grab and the sweep. **Grep
the existing banks for a distinctive stem phrase before transcribing** or the same question gets
banked twice under a second qid.

**qids are append-only.** New questions take the next number, removed ones are marked retired and
left in place. **Never run `medwiki\.scripts\reorder_bank.py`**: it renumbers the join key shared
by the vault notes, the five quiz artifact databases, `data/questions/*.json`, and roughly 5,500
Anki cards.

### Sweeping a slide deck

**An Elentra module with no knowledge checks does not mean the lecture has no questions.** Four
Week 1 endo lectures with confirmed-empty modules carry real questions in their decks.

Use **PyMuPDF, not `pdftotext`**, at
`C:\Users\nsims\.pyenv\pyenv-win\versions\3.9.13\python.exe` (it carries PyMuPDF 1.26.5). Write
sweep output to a UTF-8 file, since the console's `cp1252` dies on Wingdings arrows.

**Three shapes, not one.** Each miss below was a real one:

1. **Option-shaped lines.** `^\s*\(?([a-eA-E1-5])[.)]\s*\S` is right. Do **not** require
   whitespace after the marker: the `\s+` version misses `1.T2DM IS DIAGNOSED...`, which is how
   one deck writes every option, and it hid that slide through two separate sweeps.
2. **A case marker** (`NN-year-old`, `Case N`, `POP QUIZ`) **with an ask** (`What should...`,
   `Back to the cases`). This finds short-answer vignettes with no lettered options. Missing it
   lost the Glycemic Goals target-A1c cases and recorded that deck as having no questions.
3. **Any patient-shaped slide at all**, even with no question posed, which finds worked case
   illustrations. Missing it lost four more cases across three decks.

**Four answer-marking mechanisms.** Decks key answers by:

- (a) repeating the slide with the correct option **bolded** (`span["flags"] & 16`, which
  `pdftotext` discards);
- (b) an explicit `ANSWERS` slide a page or two later;
- (c) a **coloured highlight box drawn around the correct options in place**. This is a vector
  shape, invisible to `pdftotext` and to any span or bold read. Detect it with
  `page.get_drawings()`, match the fill colour, and test which lines' vertical midpoint falls
  inside the box. Missing this made three keyed questions look unkeyed and hid that one keys
  *two* correct options;
- (d) **✓ / ✗ glyphs per option** (U+2713 / U+2717). These are in the text layer, but they
  **extract in a different order than they appear**, so match each glyph to its option by
  vertical position, never by reading order.

Beware bold numbered diagram labels, which are false positives for (a).

**Routing every swept slide.** The two destinations are decided by what the slide *is*, and the
decks do not use one word for it. Observed labels include `Concept Check`,
`CHECK YOUR UNDERSTANDING` and `POP QUIZ`, so **read the slide, do not match the heading**:

| The slide is | Destination | Fields |
| --- | --- | --- |
| A check on understanding: a standalone question testing whether the last few slides landed | `Module Questions - <topic>.md`, under `#### Concept Checks - <Lecture>` | the note's usual `module` family |
| A **case**: a patient presented and reasoned through, whether or not a question is posed | `New Questions - <topic>.md` | `family: "meds2029"`, `source: "module-case"` |

The case rule at the top of this stage decides the row. Sweep shape 3 exists precisely because
some cases pose no question at all, and those are still cases.

Cases sit beside the CBL and DSSG questions in `New Questions` because that note is where
reasoned answers live, and a deck case is usually keyed by the lecturer's own worked reasoning
rather than by an answer letter.

## Stage 3 - charts

Invoke **`med-chart`** per lecture in the week whose note is current after Stage 1. One chart per
lecture, at the top of the lecture note itself.

**Apply the block's Schulich Reviews digest when one exists.** MSK, Neuro and Psych were
reviewed before they were taught, so their review points wait in
`<block folder>/Schulich Reviews - <Block>.md`, filed by week and lecture. When charting a lecture
listed there, **bold** each point the chart already carries, and put the rest in one
`> [!tip] Schulich Reviews` callout inside the chart region. **This year's lecture outranks the
review**: a point OneNote contradicts goes in as the lecture says it, or not at all, and is
reported. The review decides what is high yield, not what is true.

**The chart is written after the questions, and reads them.** By this point the week's questions
are banked, and they are the best available evidence of what the course actually tests. Open the
week's new questions for the lecture before charting it: what they turn on belongs on the chart,
and a discriminator three questions hinge on is not an optional row. This is the reason Stage 2
comes first, and charting a lecture whose questions have not been banked yet throws that away.

Bold marks the testable discriminator only. Stage 6 reads the bolded spans as its **priority
signal** - which of its gaps matter most - not as its list of cards; the note is the card source,
not the chart.

**A lecture whose note Stage 1 could not bring up to date does not get charted.** Report it as
skipped. A chart is the wrong place to discover the note was out of date.

## Stage 4 - the manual hop into the portal JSON

`data/questions/*.json` **has no extractor**. Every week it is re-authored by hand from the vault
notes. This is the one unautomated step in the chain, so budget for it.

- **Re-check the option sets as you export them** - length parity, no markup, key spread across
  A-D (see *Every option has to look like the answer*, Stage 2). The export is where a wikilink
  becomes a tinted option, because the vault note legitimately carries links the site must not.
- The shipped files are **compact** JSON (`json.dumps` default separators, UTF-8, LF, no trailing
  newline), unlike `data/notes/*.json` which is `indent=1`.
- The field list is in the repo `README.md`. `keyed: false`, `unscorable: true` and
  `retired: true` carry real meaning, do not flatten them.
- If `tools/questions_from_vault.py` exists by the time you read this, it replaces this stage and
  must run **before** `rosters_from_vault.py`, which borrows its week headings from the questions
  JSON.

### An option carries no markup the other options lack

`<span class="wl">` is how the vault's wikilinks render, and it is the easiest thing to paste in
by accident, because the vault note links the concept the answer names. In an option it tints
that one choice and dotted-underlines it while the rest stay plain, which reads as the key. Endo
shipped 252 of these; 16 questions had exactly one tinted option and it was the correct one.

- **Strip wikilink spans out of every option**, keeping the text. Stems and answer bodies may
  keep theirs - they give nothing away.
- The rule is wider than `.wl`: **whatever markup one option carries, all of them carry**. A lone
  `<strong>` or `<em>` is the same tell in a different colour. `pom2.css` neutralises `.opt .wl`
  as a backstop, but the backstop only knows about that one class.

### Questions with pictures

Some questions are answerable only from an image, and the module sometimes tests the image
itself. **The picture ships inside the question**, as a `data:` URI in the stem HTML - there is no
image field, no assets directory, and `quiz.js` needs no image handling because it renders the
stem as HTML. This is existing practice; it works; keep doing it:

- **Re-compress before embedding.** The vault original can be far larger than the site needs -
  one 3 MB PNG ships as a 75 KB JPEG. Convert to JPEG and keep each picture **under about
  100 KB**. `tools/embed_image.py` does the resolve-compress-encode step in one command.
- **One embed per distinct picture, reused.** Four endo questions share the cortisol figure and
  carry the same embed; do not paste four copies of a different encoding.
- **Report the count in Stage 7.** A dropped question is obvious; a dropped picture is not,
  because the stem still reads as though the image were there.

### Cadaveric images do not ship

Illustrations, radiology, endoscopy, gross pathology specimens and clinical photographs are all
fine and there is approved precedent for every one of them. **Cadaveric images are the exception**
and are covered by a separate protocol.

- **Recognise them by looking at the image, never by which module it came from.** Most anatomy
  module images are imaging or illustrations, and cadaveric images turn up in textbook figures
  too, so the module predicts badly in both directions.
- **Never include one initially.** Ship the question without it, flag the question so the missing
  image shows on its face, and list it for her - she approves case by case.
- **Flag and propose, never substitute.** Where an online alternative would work, name a
  candidate and wait. An anatomy question usually turns on one structure at one angle, and a
  plausible near-miss makes the question quietly wrong, which is worse than a question that says
  its picture is missing.

## Stage 5 - rebuild the portal

**Pull first.** Other sessions of hers commit to this repo, and this stage commits. Check
`git -C <repo> status` and pull before rebuilding - committing on top of a stale read of another
session's work is worse than a stale wikilink, because it is the shared history that ends up
wrong. During one recent session two commits landed mid-conversation from elsewhere.

From the repo root, in this order, with the absolute interpreter path, since `python` on PATH is
a pyenv shim that mangles multi-line `-c`:

```
C:\Users\nsims\.pyenv\pyenv-win\versions\3.9.13\python.exe tools/rosters_from_vault.py
C:\Users\nsims\.pyenv\pyenv-win\versions\3.9.13\python.exe tools/charts_from_vault.py
C:\Users\nsims\.pyenv\pyenv-win\versions\3.9.13\python.exe tools/review_lectures.py --derive
C:\Users\nsims\.pyenv\pyenv-win\versions\3.9.13\python.exe tools/build_pages.py
C:\Users\nsims\.pyenv\pyenv-win\versions\3.9.13\python.exe tools/build_index.py
```

`review_lectures.py` is the one script here that **does write** `data/questions/*.json`, and the
exception is narrow: it sets each question's `review` field and touches nothing else. Read its
run line. It prints how many questions resolved to a lecture and by which route, and
`--report` lists the ones that did not - a new week's questions showing up under `ambiguous`
means the `#### group` heading or the `Tests [[...]]` line did not resolve, which is a vault fix,
not a tool fix. Run `--validate` after any change to the matcher.

**This updates the portal, it does not rebuild the repo.** Worth knowing exactly what each script
touches, because the question bank is the irreplaceable part:

- **Only `review_lectures.py` writes `data/questions/*.json`, and only its `review` field.**
  The other four read the bank and never write it, so the hand-authored stems, options, keys and
  answer callouts cannot be clobbered by a rebuild. `review_lectures.py` rewrites each file
  wholesale to set that one field, which is why it is worth knowing it is the exception: if it is
  ever extended, that guarantee is the thing to protect.
- `data/notes/*.json` is regenerated from the vault, which is the point - the vault is the source
  of truth for notes and charts.
- The five block pages and `index.html` are **overwritten wholesale**, but `existing()` in
  `build_pages.py` reads the blurb, the meta description and the accent trio back out of the page
  it is replacing and writes them into the new one, so per-block identity survives.
- **Anything else hand-edited directly into the HTML is lost on the next rebuild.** That is why
  prose gets edited in the templates inside `build_pages.py` and `build_index.py`, not in the
  pages. It is not a style preference, it is the only place an edit survives.

Re-run the last two after editing any of `base.css`, `pom2.css`, `quiz.js`, `notes.js` or
`pom2.js`, because the asset cache-busting hash is read off the file at build time. The per-block
blurb and the accent trio are the two things read back out of the HTML and preserved.

**Any prose written for the portal keeps her voice and uses no em dashes.** Edit her existing
sentences and add to them, do not rewrite the passage in another register.

Commit at the end of this stage. Do not push unless asked.

## Stage 6 - Anki

Invoke **`med-anki`**.

**This is a delta, not a deck build.** The CLim endo deck already holds the breadth, so the job
is what changed: content the updated vault note has that CLim is **missing**, and content CLim
has that the note now **contradicts**. You are not starting from scratch and you are not choosing
a deck size.

- **There is no card-count target.** Some weeks the delta is three cards; after a substantially
  rewritten lecture it is forty. A number invites padding.
- **Outdated cannot be detected, only read.** CLim's cards carry no provenance, exactly as the
  lecture notes do not, so pull the lecture's cards out of CLim with `findNotes` / `notesInfo`
  and compare them against the note. There is no timestamp shortcut.
- **The chart sets priority, not scope.** The note is the source. Where the chart bolded
  something, that gap goes first and earns `#HighYield`.

High yield means facts that drive a clinical decision. Keep a number when it changes a decision,
drop it when it is a property of the molecule. The deck naming, the tag handling and the
AnkiConnect mechanics are `med-anki`'s to state, and it now does.

## Stage 7 - report

- Lecture notes written or updated from slides, questions banked per source with their qid
  ranges, lectures charted, cards added and corrected per lecture.
- **Any lecture whose note could not be brought up to date**, named, with what was missing. This
  is the one that quietly poisons everything downstream, so it goes near the top of the report.
- The recounted question total, per block and overall, with the time it was taken.
- **How many pictures were embedded**, and any question whose picture is missing because it is
  cadaveric or unresolved. A dropped picture is invisible otherwise.
- Everything skipped and why: decks not on disk, modules with no questions, and which of the
  **Stage 8** sources have not arrived. **Report a pending quiz, DSSG or CBL as a normal open
  item, not as an incomplete week.**
- Any source errors flagged rather than silently corrected.

## Stage 8 - the late arrivals (the bonus stage)

Three sources do not run on her schedule: the **weekly quiz**, the **DSSG cases** and the
**in-class CBL cases**. Everything in Stages 1 through 7 is available as soon as the lecture is;
these three are released, or held, by the course. So they are grouped here, after the report, and
they are **optional by construction**:

- **A week with none of them is a complete week.** Finish Stages 1 through 7 and report these as
  pending, never the week as unfinished.
- **Absent is expected, not merely normal.** The quiz opens at the **end** of the week, so for
  the first four days there is no judgement to make: not there is the correct state and says
  nothing about whether she is behind.
- **Never wait, and never chase.** Do not ask whether she has sat the quiz or been to the DSSG,
  and do not tell her to go.
- **Never hold Stages 1 through 7 for any of them.**

### All three land as MCQs

They arrive as prose, a discussion or a select-all, and the bank takes none of those. Each becomes
a **single-best-answer MCQ** in `kind: mcq` form, which is what all 71 case-derived endo questions
already are.

| Source | Destination | Fields | The rewrite |
| --- | --- | --- | --- |
| Weekly Elentra quiz | `Weekly Quizzes - <topic>.md` | the note's `weekly` family | mostly select-all, which the house rule forbids in a banked question, so each becomes a **combinations MCQ** |
| DSSG cases | `New Questions - <topic>.md` | `family: "meds2029"`, `source: "dssg"` | a discussed case becomes a stem with options, keyed to the group's reasoning |
| In-class CBL cases | `New Questions - <topic>.md` | `family: "meds2029"`, `source: "new"` | the same, from the case as it was worked in class |

#### A matching activity becomes a numbered-against-lettered MCQ

A matching activity has no single best answer and the bank cannot score it, so it converts to one
MCQ over the whole set rather than shipping `kind: "matching"` and `free: true`, which scores
nothing and reads as a gap.

- **Number the left column 1, 2, 3 and letter the right column A, B, C**, as a two-column table
  in the stem.
- ⚠ **Shuffle the lettered column.** Left in source order the two columns line up row by row and
  the question answers itself.
- **Each option is the whole set of pairings**, `1-F · 2-B · 3-E · …`, so the options are
  identical in length by construction and the Stage 2 parity rule is satisfied for free.
- **Distractors swap two or three pairs, never one.** A single swap is spotted by scanning one
  row; the swaps should be **the pairs that are genuinely confusable** - the two that both come
  from the same primordium, the two that both end as labia.
- Ship it `kind: "mcq"`, `free: false`, keyed to a letter.

`module-endo-Q156` is the worked example: nine primordial structures against nine terminal ones,
four options, the key spread away from the letters its neighbours use.

**Writing the options is where both Stage 2 rules bind hardest** - *Every option has to look
like the answer* and *Nothing enters a question that the material did not put there*. A source
that arrives as prose has no options at all, so every one is written from scratch, and the key
is the one you understand best: that is how it ends up longest, most qualified, and first.

**The rewrite is the work, not the extraction.** Capturing the quiz is one bookmarklet click;
turning ten select-alls into defensible combinations MCQs is the slow part, and a case discussed
for forty minutes has to be cut down to one decision worth asking about.

**Where the reasoning is yours, say so.** Elentra usually writes `Rationale: N/A`, and a DSSG or
CBL case is keyed by the discussion rather than by an answer letter. Write the reasoning and
**label it as yours** rather than passing it off as transcribed. Where the discussion genuinely
does not settle a single answer, ship it **`keyed: false`** rather than inventing a letter - three
module cases already do exactly this, and the portal states it on the question's face.

**The weekly quizzes carry no images**, so nothing in the picture rule applies to them.

### Re-entering for one late arrival

**Do not re-run the week.** Take the short path:

| | |
| --- | --- |
| Stage 8 | bank it into its own note, numbering continuing from that note |
| Stage 4 | add those questions to `data/questions/<slug>.json` |
| Stage 5 | rebuild the portal so the counts move |
| Stage 7 | report what it added, and what is still pending |

**Stages 1, 2, 3 and 6 do not re-run**: the notes, the module and deck questions, the charts and
the cards do not change because a quiz or a case session happened. **This holds even though
Stage 3 reads the questions** - a chart is not rewritten for a late arrival. The one exception is
a late question that **contradicts the lecture note**, which is a Stage 1 conflict and follows the
OneNote precedence rule, not a banking decision.

## Gates - stop and confirm

- **A cadaveric image she has not approved.** Flag, propose, and wait. Never ship one and never
  substitute one.
- **Deleting the CLim source deck.** Import, verify, then ask. Do not delete it for her, and run
  no Check Media purge before the import: 333 of the endo notes carry images that the deck owns.
- **Posting charts to OneNote.** The create tools are live and `Notes.Create` is consented, so
  this is held by nothing but this line. Her notebook is the year's lecture record - propose the
  page and wait for an explicit yes before creating or updating one, every time. `--read-only`
  used to enforce this; it no longer does.
- **Pushing to GitHub.** Committing is part of Stage 5, pushing is not.
- **Publishing any Artifact at all.** A week's work ships through the repo. If publishing one
  looks like the right answer, ask first, because it usually means the repo path was missed.

## Concurrency

Other sessions of hers work this vault **and this repo** at the same time, split by topic. A file
listing taken at the start of a stage is not trustworthy at the end.

- **Re-validate every wikilink as the last step of any vault stage**, and re-read a question note
  before appending to it rather than trusting an earlier read of its highest `# N`.
- **Re-check `git status` before the Stage 5 commit**, for the same reason. The repo drifts under
  you exactly as the vault does, and a commit is harder to unpick than an appended note.
