# Pre-clerkship portal

A static study portal for the pre-clerkship years at Schulich. One directory per
course. Each **block** gets a page with two tabs: **notes**, a coverage map of
every lecture in the block whether or not it has been written up, and **Anki**,
the deck for those weeks. Each **course** gets one more page, the **question
bank**, which holds every question in the course at once.

The bank reads as one scrolling stream and answers on the spot. Five filters
narrow it - block, question set, week, topic, and whether you got it right - a
**View** switch takes it one question at a time, an **Order** switch shuffles
it, and a **Mode** switch turns whatever you have filtered to into a sat paper
of however many questions you ask for, optionally against a clock, marked only
once you submit. Every explanation closes by naming the block, the week and,
where the set knows it, the lecture the question came from, so the next step
after getting one wrong is on the card rather than in a filter.

The notes tab carries a **search** above the week chips. It reads the whole
note, not just the lecture title, narrows the stream and the lecture index
together, and highlights what it found. Every word of the query must appear
somewhere in the note, in any order, which is the bank's rule too: the two
searches share one rule and one highlighter, kept in `portal.js`.

**A block is a filter value, not a page.** That is the whole reason the bank is
one page: the things people want near an exam - every question they have got
wrong, a hundred questions across the term, weeks 7 to 11 - cannot be said on a
page whose scope is one block. Each block page's third tab is a link into the
bank, pre-filtered to that block, and the address carries the filter
(`qbank.html#block=msk`) so it can be sent to someone.

No build step, no framework, no server. HTML, three JS files, two stylesheets and
a folder of JSON per course. Serve the folder and it works.

By the **Open-Source Medicine Club** and the **AI in Medicine Club**.

Live at **<https://schulichmed.github.io/preclerkship/>**.
Questions, corrections and contributions: <schulichmedfriends@gmail.com>.

## The four courses

| Course | Year | State |
| --- | --- | --- |
| [Foundations of Medicine](fom/) | 1 | 4 blocks, weeks 1–15, 2,084 questions |
| [Principles of Medicine 1](pom1/) | 1 | 5 blocks, weeks 1–17, 2,302 questions |
| [Principles of Medicine 2](pom2/) | 2 | 5 blocks, weeks 1–20, 1,898 questions |
| [Transition to Clerkship](t2c/) | 2 | 6 blocks, weeks 1–13, 214 questions |

A course with nothing behind it keeps a card on the hub, greyed and unlinked,
and that is deliberate: it is the same habit the rest of the portal keeps. A
lecture with no note still renders on the notes tab, a question set with nothing
in it still renders in the filter bar, and PoM 1's ENT and Nephrology blocks
carry a full page of placeholders because no one has handed in notes for them.
Showing the shape of the whole thing, gaps included, is more useful than showing
only the parts that happen to be done.

## How a week gets built

Every week of a course is assembled by the same run, and the pipeline below is
what it does. One reservoir of content, three exposures to it, one repo out the
front.

![How a week of the course is built: a weekly run keeps a content reservoir
current - the Obsidian vault of inherited upper-year notes, this year's slides
pulled through the OneNote MCP server, and review slides. From that reservoir
come three exposures to the same material - charts to understand, Anki to
remember, and a question bank to apply - and all three feed this repo, which in
turn feeds class workshops and the public site.](docs/pipeline.svg)

The run itself is a Claude Code skill, [`skills/pom2-week/`](skills/pom2-week/),
which is published here rather than kept local because it is the recipe, not
just the output: its `SKILL.md` is the stage-by-stage order, and
[`pipeline.html`](skills/pom2-week/pipeline.html) is the same diagram with
screenshots of each stage.

Read it as one group's working recipe rather than something that runs anywhere
as-is. It names absolute paths on the machine it was written on, and it assumes
an Obsidian vault laid out a particular way.

## Layout

```
index.html         the hub, one card per course
base.css           design tokens, the reset, the page frame   ) the engine,
portal.css         everything the portal draws                ) shared by
portal.js          tab strip, the note renderer, the search   ) every
notes.js           the notes tab, including the PDF printing  ) course
quiz.js            the question runner and the progress store )

fom/               one course: its pages, its data, its README
pom1/              the same
pom2/              the same
t2c/               the same

tools/portal.py       the course roster: blocks, families, accents, store keys
tools/roman_items.py  a repair pass: item lists read as options, put back in the stem
tools/build_pages.py  every course's block pages AND its question bank
tools/build_index.py  every course's landing page
tools/build_hub.py    the front door
tools/build_anki.py   a block's deck out of Anki, plus the manifest its tab reads
tools/question_figures.py  question pictures out of the JSON and into assets/figures/
tools/vault_backup.py      the portal back into the medwiki vault: charts and question notes
tools/                PoM 2's extractors (an Obsidian vault in)
tools/fom/            FoM's extractors (the question-bank PDFs in)
tools/pom1/           PoM 1's extractors (the bank PDFs, the workbook, the study notes)
```

### What makes a course a course

Only three things, and all of them are data in
[`tools/portal.py`](tools/portal.py): its **block list**, its **question-set
families**, and the **localStorage prefix** its progress is kept under. The
engine reads all three off `window.QUIZ_BLOCK`, which the builders write into
each page. Adding a fifth course is a dictionary, a directory and some JSON.

That matters because the alternative was a copy of `quiz.js` per course, and
those copies diverge. When Foundations was first built as its own site, its copy
of the engine had already drifted in three places within a day.

The same engine runs the block-scoped view and the whole-course bank: a page
hands `quiz.js` a list of blocks, and a list of one behaves exactly as a block
page did. Progress is stored per block either way, one `localStorage` key each,
so an answer given in the bank is already there on the block page and there is
no second copy of it to disagree.

### Pictures are files, not base64

A question's pictures live in `<course>/assets/figures/`, named after the hash
of their own bytes, and the bank holds a path. They used to be inlined as
`data:` URIs, which cost 3.1 MB across PoM 2 and FoM for 1.9 MB of actual
picture, made a bank uncacheable and un-deltaable, and gave four questions
sharing one figure four copies of it. `tools/question_figures.py` is the
backfill and the check; the three places that could put one back -
`tools/embed_image.py` and FoM's two PDF parsers - write files now.

## Run it

```bash
python -m http.server 8000
```

Then open <http://localhost:8000>. A plain `file://` open works too, except that
browsers block `fetch` of local JSON, so the tabs come up empty. Use the server.

## Rebuilding

Always from the repo root. The three builders read only what is already in the
repo, so they run anywhere; each course's extractors read sources outside it and
take their paths from the environment.

```bash
python tools/fom/parse_qbank.py          # the question-bank PDFs -> fom/data/questions/
python tools/fom/rosters_from_vault.py   # the vault              -> fom/data/notes/
python tools/pom1/parse_qbank.py         # the bank PDFs + workbook -> pom1/data/questions/
python tools/pom1/rosters_from_vault.py  # the vault              -> pom1/data/notes/
python tools/pom1/notes_from_pdf.py      # the study notes        -> pom1/data/notes/
python tools/rosters_from_vault.py       # the vault              -> pom2/data/notes/
python tools/charts_from_vault.py        # folds written notes on top

python tools/roman_items.py              # item lists read as options -> back in the stem
python tools/question_figures.py         # any newly-inlined picture -> assets/figures/
python tools/review_lectures.py --derive # every question -> the lecture it tests

python tools/build_pages.py             # every course's block pages + question bank
python tools/build_index.py             # every course's landing page
python tools/build_hub.py               # the hub and its totals

python tools/vault_backup.py charts      # FoM/PoM 1 curated notes -> vault charts (new ones only)
python tools/vault_backup.py questions   # every bank the vault lacks -> 00 - Practice Questions
```

Run the last three after editing any CSS or JS as well, because they stamp each
asset's content hash into its URL and the stamp goes stale otherwise.

### Which lecture a question came from

`review_lectures.py` is the one script that writes `data/questions/*.json`, and
it writes exactly one field: `review`, the vault lecture note or notes whose
material the question tests. That is what the `Review` line under each answer
reads, and it is why the line can name a lecture rather than restating the week
the filter already told you.

Four of its five routes are lookups: the workbook notes state which lectures
each group of questions tests, and the module and new-question notes head each
group with the lecture's own name. Those cover PoM 2 and nothing else, because
no other course's inherited bank recorded a lecture at all. The fifth route
matches the question's own text against the lecture notes, and it is the only
one that infers anything. It is measured rather than trusted:
`--validate` scores it against the questions the four lookup routes already
answered, and it abstains rather than guess. **A question that resolves to
nothing keeps the week-only line** - a wrong lecture is worse than no lecture,
because it sends you to the wrong reading with the portal's name on it.

T2C resolves to nothing at all: the vault holds no T2C lectures to point at.

Each course's README covers its own sources and its own quirks:
[fom/README.md](fom/README.md), [pom1/README.md](pom1/README.md),
[pom2/README.md](pom2/README.md).

## Progress stays on the device

Answers, stars and per-lecture accuracy are written to the browser's
`localStorage`, under a **separate prefix per course**, so the four never read or
overwrite each other even though they share an origin. Nothing is sent anywhere
and there is no backend.

The flip side is that it does not follow you, so each course's questions tab has
**Download all my progress** and **Restore from a file**, which move a JSON file
by hand. One file holds every block of that course, and a restore only adds and
updates, so an out of date file cannot overwrite newer answers.

## Open source

The beauty of open source is that anyone can access the work, improve it or
customize it to their needs. It is crowdsourced expertise that creates
user-vetted products.

**To customize it.** Anything here can change, from the courses it covers to the
wording and the layout. Paste this into Claude Code:

```
Clone this repo and read the README so you understand how the portal is built. I want to
make it mine: [what you want changed, for example: cut it down to the course I am on,
import my own lecture notes and questions, restyle the pages, or build an Anki deck from
only the questions I got wrong]. Work out which files that touches, make the change, and
rebuild with the scripts in tools/.
```

You can also just take the material out. The questions and the notes are plain
JSON under each course's `data/`, so you can extract either into whatever you
already study from. They are updated week by week, so what you pull is a snapshot.

**To improve it.** Suggest a feature, fix an answer you think is wrong, or send in
questions of your own. Corrections and questions are the two most useful things
to send.
Every question in the bank has a **Report this question** button. Until the
relay in `tools/report-worker/` is deployed it opens an email; once it is, the
report becomes a public GitHub issue and a pull request that flags the question
for review, with no account needed.

## Licence and content

The code is MIT, see [LICENSE](LICENSE).

The study content under each course's `data/` came out of shared course material
that students already pass between years: class question banks, the
Pre-Clerkship Workbook, Elentra module knowledge checks, weekly quizzes, slide
concept checks and questions written from the case and small-group sessions.

**They are here on purpose.** Putting them somewhere public is the reason this
repository exists, not an accident of packaging. Where a question came out of a
peer-written bank, its errors and gaps are flagged on the question itself rather
than quietly patched, so you can see what you are trusting before you trust it.
