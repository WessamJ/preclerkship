# Rebuilding the portal

**This page is PoM 2's.** The portal now carries four courses, and each keeps
its own extractors beside its own sources:

| Course | Extractors | Reads |
|---|---|---|
| PoM 2 | `tools/*.py` (this page) | an Obsidian vault of lecture notes |
| FoM | `tools/fom/` | the block question-bank PDFs and the workbook |
| PoM 1 | `tools/pom1/` | the block bank PDFs, the workbook, and upper-year study notes |
| T2C | none | its questions arrived as JSON |

**The FoM and PoM 1 notes are now hand-curated.** On 2026-09-27 every written
lecture in `fom/data/notes/b1..b4.json` and `pom1/data/notes/{cardio,gi,resp}.json`
was cleaned by hand on top of what the extractors produced: split sentences
rejoined, phantom tables rebuilt, exploded equations rewritten, stray diagram
labels removed, misfiled sections moved to the lecture they belong to, a
framing and keypoints written for each, and 240 mermaid flowcharts added. Each
of those files carries a top-level `curated` key saying so. Re-running
`tools/fom/parse_summative.py` or `tools/pom1/notes_from_pdf.py` would overwrite
all of that, so they are kept for reference and for any block that has no
notes yet (ENT, GU); do not run them over a curated block.

The three *builders* below - `build_pages.py`, `build_index.py`,
`build_hub.py` - are shared: each runs over every course in
[`portal.py`](portal.py)'s roster, so a course is a dictionary, a directory and
some JSON rather than a fork of the engine. Two repair passes are shared too:
`question_figures.py`, which moves an inlined picture out into a file, and
`roman_items.py`, which puts a roman-numeral item list back in the stem it was
parsed out of. Both run after the extractors and both are idempotent.

Three more shared modules serve the two PDF extractors, because FoM's and
PoM 1's notes are the same kind of document and were getting the same things
wrong in two places:

| Module | What it does |
|---|---|
| [`tables.py`](tables.py) | reads a **ruled** table off a page, keeping the bold, and repairs what the finder gets wrong: a wrapped heading folded back, a phantom column merged away, a chart title lifted off the top row, and one ruled box split into the tables actually stacked inside it |
| [`diagrams.py`](diagrams.py) | rasterises artwork the PDF *draws* rather than embeds, so a labelled figure arrives as a figure instead of its labels arriving as loose paragraphs. A cluster has to be made of curve and line segments to qualify - a dashed box round a callout is rectangles only, and its text is already being read as text |
| [`coverage.py`](coverage.py) | titles a note with every lecture it covers, so a chart that runs two lectures together names both instead of leaving one showing as a gap |

**Reader reports.** Every question in the bank has a Report button, and two
pieces here carry a report from that button to a pull request:

| Piece | What it does |
|---|---|
| [`report-worker/`](report-worker/) | the relay, a Cloudflare Worker that checks the report, rate-limits it and opens a GitHub issue labelled `report` with a fenced block naming the question |
| [`report_to_pr.py`](report_to_pr.py) | the Action's script: reads that block, appends a `report` flag to the question's JSON, rebuilds the pages and opens the pull request |

The one-time setup, a token and a deploy, is in
[`report-worker/README.md`](report-worker/README.md).

**Why the tables are read off the ruling lines.** Both extractors used to infer
a table from its typography and both got it wrong: PoM 1 had no table
recovery at all and emitted every cell as its own paragraph, and FoM's x-anchor
clustering merged the two tables on the ADHD page into one and promoted the
bold sentence above them to a column heading - which, at 143 characters against
a `white-space: nowrap` rule, set that column thousands of pixels wide and
pushed the criteria off the side of the page. These documents do rule their
tables, so the rules are what to read.

---

Four scripts, run from the repo root, in this order. Python 3, no dependencies.

```bash
python tools/rosters_from_vault.py    # every lecture in the block, written up or not
python tools/charts_from_vault.py     # folds the notes that exist on top
python tools/build_pages.py           # the five block pages
python tools/build_index.py           # the landing page and its counts
```

The first two read an Obsidian vault of lecture notes. The last two read only
`data/` and the pages already in the repo, so they run anywhere.

If any chart embeds a figure, `figures.py` goes between the first two:

```bash
python tools/figures.py               # encodes chart figures into assets/figures/
```

It is separate because it needs Pillow, and keeping it out of the four above is
what lets them stay dependency-free. It is also skippable: a chart with no
`![[picture.png]]` in it needs nothing from it.

**After writing a new note, run the first two and then the last two.** The block
pages and the index both print counts, so they go stale otherwise.

## Pointing them at your vault

`rosters_from_vault.py` and `charts_from_vault.py` default to the author's vault
path. Set `POM2_VAULT` to your own:

```bash
export POM2_VAULT="/path/to/vault/01 - Lectures/99 - PoM 2"   # bash
$env:POM2_VAULT = "C:\path\to\vault\01 - Lectures\99 - PoM 2" # PowerShell
```

Inside that folder the scripts expect one directory per block (`01 - Endocrinology`,
`02 - Repro`, `03 - MSK`, `04 - Neuro`, `05 - Psych`), each holding `Week N`
folders of `.md` files named `NN - Lecture title.md`. The block list and its week
numbers live in `BLOCKS` at the top of both scripts. Edit that and the portal
follows a different course.

## What each one does

**`rosters_from_vault.py`** lists every lecture note in each block's week folders
and writes `data/notes/<slug>.json` with `"hasNote": false` throughout. The roster
is the point: a lecture with no note still appears, so the notes tab reads as a
coverage map. Week headings are borrowed from `data/questions/<slug>.json` so both
tabs name a week the same way.

**A word on vocabulary.** The vault calls these *charts*, since the region at the
top of each lecture note opens `# Overview chart:`, and the site calls them
*notes*. The extractor keeps the vault's word because that is what it reads.
Everything on the site side uses the site's.

**`charts_from_vault.py`** lifts the chart out of the top of each lecture note,
meaning the region between the frontmatter and the first `---`, and folds it into
the roster. It keeps the parts in source order in a `blocks` array, because the
sentence above a table is the reason the table is there. Markdown becomes inline
HTML: `**bold**`, `<u>`, `<br>`, `[[wikilinks]]` as `<span class="wl">`,
`[text](url)` as a real link, and mermaid fences as `{"t": "pathway"}`.

An Obsidian embed **alone on its line** becomes `{"t": "figure"}`; one with prose
around it is left as text, because that is a sentence mentioning a picture rather
than a block. The pipe is read the way the vault already writes it: a number is a
width (`![[adrenal crisis card.png|300]]`), anything else is a caption
(`![[hpg axis.png|The hypothalamic-pituitary-gonadal axis]]`). A figure whose file
`figures.py` has not encoded is reported by name and skipped, so a missing picture
is a line on stderr rather than a silent hole in the page.

**`figures.py`** reads the same chart regions, resolves each embed against the
vault's `Attachments`, re-compresses it to a JPEG under 220 KB and at most 900px
wide (the note's column width), and writes it to `assets/figures/<hash>.jpg` plus
the `data/figures.json` manifest that `charts_from_vault.py` reads. Naming a file
after its own bytes means re-runs are free and duplicates collapse. It prints
every newly-encoded picture, because a new image should never be added unseen -
it cannot tell a cadaveric image from a clinical photograph and does not try.

**`build_pages.py`** regenerates the five block pages. Only the name, blurb, accent
and two counts differ between them, so they are generated rather than copied. The
blurb and accent are read back out of the page being replaced, so edit those in the
HTML and they survive the next run.

**`build_index.py`** regenerates `index.html`, taking every count from the data
rather than from prose, so the cards cannot drift.

## Editing by hand

Prose in the block pages and the index is safe to edit **only in the templates**
inside `build_pages.py` and `build_index.py`. The next run overwrites the HTML. The
two exceptions are the per-block blurb (`<p class="lead">`) and the accent trio in
each page's inline `:root`, which are read back out before the page is rewritten.

`base.css`, `pom2.css`, `quiz.js`, `notes.js` and `pom2.js` are hand-maintained and
never generated. **After editing one of them, re-run `build_pages.py` and
`build_index.py` anyway.** The pages link these assets as `base.css?v=<hash of its
contents>`, and the hash is read off the file at build time. GitHub Pages serves
them with `Cache-Control: max-age=600`, so without a fresh hash a browser will keep
last deploy's stylesheet for ten minutes and paint the new markup with the old
rules. Skipping the rebuild is not harmful, since the server ignores the query
string, but it stops the cache from being busted.

Two constants at the top of `build_pages.py` and `build_index.py` are deliberately
empty: `CF`, for an analytics snippet, and `PILLNAV`, for a nav bar back to a
parent site. Fill either in and every generated page picks it up.

## Not regenerated

`data/questions/*.json` is not produced by anything here. If you are bringing your
own questions, write that JSON yourself. One object per question, in a flat list.
The fields the front end reads are documented in the main [README](../README.md).

## Publishing an Anki deck

One more script off to the side. It needs **Anki running** with the
[AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on on
`127.0.0.1:8765`, so unlike the four above it only runs on a machine holding the
collection.

```bash
python tools/build_anki.py pom2 endo "PoM2::Block 1"
```

It writes two things: `pom2/anki/endo.apkg`, the deck itself, and
`pom2/data/anki/endo.json`, the manifest of per-week and per-lecture card counts
that `build_pages.py` renders the Anki tab from. **Run `build_pages.py` after
it**, the way you would after editing a stylesheet - the counts on the tab come
from the manifest at build time.

A block with no manifest keeps the empty state on its Anki tab, which is what
every block but endo still shows. That is the whole switch: no manifest, no
deck, and the tab says so rather than offering a download that 404s.

**Scheduling is stripped on the way out** (`includeSched=False`). The due dates
in the collection are one person's review history; what gets published is the
cards. Anyone importing starts their own scheduling, and re-importing a later
export updates the cards without resetting their progress.

The deck is a **binary in a git repo** and endo's is 35 MB, most of it the 442
media files behind the image-occlusion cards. Each re-export commits another
copy, and git keeps every one of them forever. That is affordable a few times a
year and not affordable weekly, so re-export when the deck has meaningfully
changed rather than on every card edit.

AnkiConnect writes the `.apkg` itself, so the path it is handed is a path on the
machine **Anki** runs on. Under WSL that is a Windows path, and the script copies
the result back across `/mnt/c`. The two constants at the top of the script are
the two spellings of that one temporary file.

## Pulling a weekly quiz out of Elentra

Two more scripts, off to the side of the four above. They do not touch `data/`
and are not part of the rebuild. They exist to shorten the trip from a weekly
quiz sat in Elentra to a question note in the vault, which is where the four
scripts pick the work up again.

```bash
python tools/make_bookmarklet.py     # once, then open build/elentra-grab.bookmarklet.html
                                     # and drag the button onto the bookmarks bar
python tools/elentra_quiz.py ~/Downloads/elentra-3007-*.json \
    --topic endo --note "C:/Users/nsims/medwiki/00 - Practice Questions/Weekly Quizzes - Endocrinology.md"
```

**`tools/elentra_grab.js`** is the readable source of the bookmarklet.
`make_bookmarklet.py` strips its comments, percent-encodes it and writes the
`javascript:` URL into `build/`, along with a one-link page to drag from.

Sit the quiz, submit it, then open the **feedback** view,
`exams?section=feedback&progress_id=<n>`, the one showing the correct answers,
and click the bookmark. A panel appears bottom right saying
what it found. If the review paginates, click it on every page: captures
accumulate in `localStorage` under the one exam id and **Download JSON** writes
the merge. Nothing is fetched, clicked or submitted on your behalf, so it cannot
disturb an attempt.

**Probe page first.** The Rise grab in the bookmarks bar never reads a page: Rise
ships a whole course, keys included, as one `runtime-data.js`, so that bookmarklet
just fetches it and `rise_to_bank.py` decodes it. If Elentra's exam player has
anything of that kind, scraping the DOM is the wrong approach. The **Probe page**
button writes a file listing what the page fetched, what globals it is holding and
any inline JSON island, and answers that in one click. It reports; it opens and
fetches nothing.

Failing that, the DOM, read two ways. `elentraScan` knows the shape Schulich's
Elentra renders and reads it exactly: `.exam-question` per question,
`tr.question-answer-view` per option carrying `answer-correct`, and a
`.feedback-report` of `Points` / `Correct Answer` / `Rationale` lines. The key is
stated twice there and the prose line wins, since a class name is a theme's
business and can be restyled out from under this.

Anything that shape misses falls through to a structural reader: a group of radios
or checkboxes sharing a `name` is one question, its container is the smallest
ancestor holding that group alone, and the answer is guessed from surrounding
classes and icons. Both paths write every signal they saw into the file beside the
verdict, and keep each question's own `outerHTML`. That is not decoration. The
first version of this was pure guesswork, and one real capture showed that
matching `right` in a class name also matches Bootstrap's `space-right`, which
marked every option correct on all ten questions. The signals are what turned that
into a one-line fix. `--inspect` prints them. A page that parses to nothing has its
whole body kept in the file for the same reason.

**`tools/embed_image.py`** resolves a vault image, re-compresses it and prints the
`<img>` tag to paste into a question. Pictures ship *inside* the question as a
`data:` URI in the stem HTML. There is no image field and no assets directory,
because `quiz.js` renders the stem as HTML and the browser does the rest.

```bash
python tools/embed_image.py '![[incretin effect - oral vs IV glucose.png|600]]'
# incretin effect - oral vs IV glucose.png -> 78.1 KB encoded, 900px wide, q75
# <img loading="lazy" src="data:image/jpeg;base64,...">
```

It takes a bare filename, a whole `![[embed|600]]`, or a path, and looks in the
vault's `Attachments/` (override with `POM2_ATTACHMENTS`). It spends JPEG quality
before it drops pixels, since a keyed radiology or anatomy image is often keyed on
detail, and it walks both down until the encoded bytes fit `--max-kb` (100 by
default). A picture that will not fit warns rather than shipping quietly: the
question's stem still reads as though the image were there, so a picture too big is
the one failure that hides itself. Unlike the four rebuild scripts this one needs
**Pillow**.

**`tools/elentra_quiz.py`** turns that JSON into house-format markdown in
`build/`: a `#### <lecture>` group of `# N` questions with their answer callouts,
sized and numbered to drop into the week's section of
`Weekly Quizzes - <topic>.md`. Pass `--note` and the numbering continues from the
highest `# N` already in the real note, so nothing renumbers.

It writes a fragment rather than the note because the note is a vault file other
sessions edit, and its `## Week N` sections and Coverage callout are hand-kept.
Two things it will not decide on its own:

- **A question with no detected key** gets the `> [!red] No official answer key`
  scaffold rather than a guess.
- **Select-all and short-answer questions** come through in their original shape
  with the rewrite flagged, since the house rule that every banked question is
  MCQ or true/false is a writing job, not a parsing one.

Both are reported on stdout at the end of a run, with the qid range the fragment
claims.

**`tools/onenote_local.py`** reads OneNote pages off this laptop, with no Graph
API and no login — the ms365 route has been refused since 2026-09-07 with
`AADSTS50158`, a Duo challenge on a stale token. It drives the installed OneNote
desktop app over COM, which is already signed in and holds the same notebooks.

```bash
python tools/onenote_local.py list "Principles of Medicine 2"
python tools/onenote_local.py page --find "hypothyroidism" --slides
```

`list` prints `path :: title :: id` for every page; `page` takes an id, or
`--find <title fragment>` and resolves it. It prints her typed notes first,
which are what a vault note is actually built from, and adds the slide printouts
under `--slides`. Those slides come through as **text**: OneNote has already run
OCR over every image, so the words on the slides need no download and no image
read, which is the one thing the Graph route made expensive.

Two notes on where it runs. It needs `powershell.exe` and Office 16, so it is a
laptop tool, not a server one. And if COM is ever unavailable, OneNote's own
automatic backups under
`%LOCALAPPDATA%/Microsoft/OneNote/16.0/Backup` hold the same text —
`strings -el` on a `.one` section file reaches it without any app at all, but
flattens the page, losing the split between her notes and the lecturer's slides.

---

## Infographics without NotebookLM

`infographic.py` is the NotebookLM "Infographic" button with the login taken
out: it reads one lecture note, cleans the Obsidian syntax off it, and asks
Gemini's image model for a portrait study poster, which lands in the vault's
`Attachments/` as `<note> (generated infographic).png`. It needs `requests`
and a `GEMINI_API_KEY` in the environment (make one at aistudio.google.com;
it can only call the Gemini API and is revoked on the same page). It never
reads browser cookies.

```bash
python tools/infographic.py "pathology of 1st trimester" --dry-run   # see the prompt
python tools/infographic.py "pathology of 1st trimester"             # write the PNG
python tools/infographic.py "pathology of 1st trimester" --embed     # and link it under the chart
```

Slides are the gold standard. The picture is drawn by an image model and image
models garble small text, so check every number on it against the slides; the
filename says "generated infographic" so it is never mistaken for one. Tests:
`python -m pytest tools/tests -v`.
