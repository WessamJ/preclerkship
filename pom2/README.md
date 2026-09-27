# Principles of Medicine 2

One course in the [pre-clerkship portal](../README.md). Its pages live in this
directory; the engine they run on (`base.css`, `portal.css`, `portal.js`,
`quiz.js`, `notes.js`) is shared and sits at the repo root.

A static study portal for a medical school course, built around one page per
block. Each page has two tabs: **notes**, a coverage map of every lecture in the
block whether or not it has been written up, and **practice questions**, a quiz
runner that keeps score.

No build step, no framework, no server. Six HTML files, three JS files, two
stylesheets and a folder of JSON. Open `index.html` and it works.

It was written for the five blocks of the second Principles of Medicine year at
Schulich (endocrinology, reproduction, MSK, neurology, psychiatry), but nothing
about the code knows that. Swap the JSON and it is your course.

Live at **<https://noorsimsam.com/pre-clerkship/pom2/>**.

## Open source

The portal is open source at <https://github.com/schulichmed/preclerkship>.

The beauty of open source is that anyone can access the work, improve it or
customize it to their needs. It is crowdsourced expertise that creates
user-vetted products.

### To customize it

Anything here can change, from the blocks it covers and the questions in them to
the wording, the layout and the tooling around it. Paste this into Claude Code:

```
Clone https://github.com/schulichmed/preclerkship and read the README so you understand how
the portal is built. I want to make it mine: [what you want changed, for example:
cut it down to the blocks I am on, import my own lecture notes and questions,
restyle the pages, or build an Anki deck from only the questions I got wrong].
Work out which files that touches, make the change, and rebuild the pages with
the scripts in tools/.
```

You can also just take the material out. The questions and the notes are both
plain JSON under `data/`, so you can extract either one into whatever you already
study from. Keep in mind they are being updated week by week, so what you pull is
a snapshot of that week.

### To improve it

Suggest a feature, fix an answer you think is wrong, or send in questions of your
own. You need a GitHub account; Claude Code can do the rest. Paste this into it:

```
Clone https://github.com/schulichmed/preclerkship and read the README so you understand how
the portal is built. I want to contribute: [what you are adding, for example: the
questions from the week 8 MSK module, a correction to an answer, or a feature].
Match the format the existing files use, rebuild the pages with the scripts in
tools/, then create a branch, commit, and open a pull request against
schulichmedfriend/preclerkship explaining what changed and why.
```

Corrections and questions are the two most useful things to send.

## Run it yourself

```bash
git clone https://github.com/schulichmed/preclerkship
cd preclerkship
python -m http.server 8000
```

Then open <http://localhost:8000>. A plain `file://` open works too, except that
browsers block `fetch` of local JSON, so the tabs come up empty. Use the server.

## What is in here

```
pom2/index.html              the landing page, five block cards
pom2/endo|repro|msk|neuro|psych.html    one page per block
pom2/data/notes/*.json       lecture rosters, with a written note folded in where one exists
pom2/data/questions/*.json   the question bank
pom2/assets/figures/         the pictures the notes embed

../base.css      design tokens, the reset, the page frame   (shared)
../portal.css    everything the portal draws                (shared)
../portal.js     tab switching, shared helpers              (shared)
../notes.js      the notes tab, including the PDF printing  (shared)
../quiz.js       the question runner and the progress store (shared)
../tools/        the scripts that regenerate all of the above
```

`tools/` is only needed if you keep your source material in an Obsidian vault and
want it extracted automatically. See [tools/README.md](tools/README.md). If you
are hand-writing the JSON, ignore the whole folder.

## Progress stays on the device

Answers, stars and per-lecture accuracy are written to the browser's
`localStorage`. Nothing is sent anywhere, there is no backend, and nobody running
a copy of this can see anyone else's progress. The flip side is that it does not
follow you between browsers or machines, so the questions tab has **Download all my
progress** and **Restore from a file** buttons that move a JSON file by hand. One file holds
every block and can be written or read from any of them, and a restore only adds and updates,
so an out of date file cannot overwrite newer answers.

## Bringing your own content

### Questions

`data/questions/<block>.json` is a flat list of question objects. Every question
carries the same fields:

| field | what it holds |
| --- | --- |
| `qid` | unique id, and the key progress is stored against |
| `num`, `week`, `weekLabel` | position in the course, used for grouping |
| `lecture`, `lectureMeta` | which lecture it hangs off, and a note about the source |
| `tags` | optional labels that cut across the other filters, shown as **Topic** |
| `source`, `sourceLabel`, `family` | which bank it came from, shown as a filter |
| `stem`, `preamble` | the question itself as HTML, and any shared setup above it |
| `kind` | `mcq`, `short`, `matching`, or `broken` |
| `options` | `[{"letter": "A", "html": "..."}]` |
| `correct`, `multi` | the answer letters, and whether more than one is expected |
| `answer`, `answerTitle` | the explanation shown after answering |
| `keyed`, `free`, `unscorable`, `retired` | whether it has a real key, is ungraded, cannot be scored, or is hidden |
| `flags` | `[{"type": "warning", "title": "...", "html": "..."}]`, printed on the question |

`keyed: false` and `unscorable: true` matter. Question banks handed down between
years are often missing an answer key or contain a question with no defensible
answer. Rather than inventing a letter, the portal says so on the question's face
and leaves it out of the score.

`tags` is the one filter that cuts across the others. The anatomy, histology and
embryology lectures are a strand of their own, but their questions arrive as
Elentra modules, as module cases and as workbook chapters, and they sit in more
than one week, so neither the question-set nor the week dropdown can gather
them. Tagging those questions `["anatomy"]` puts a **Topic** dropdown in the
toolbar that does. A block with nothing tagged shows no group at all, so the four blocks
that have no anatomy questions yet are unchanged. The tag is a list, so a
question can carry more than one, and the counts under Topic are the only ones in
the toolbar that do not add up to the total, because a question is counted under
each tag it carries.

### Notes

`data/notes/<block>.json` is one object per block, holding `weeks`, holding
`lectures`. A lecture with `hasNote: false` still renders, greyed, so the tab
reads as a coverage map rather than a list of what happens to be done. A lecture
with a note adds `title`, `framing`, `keypoints` and `blocks`, where `blocks` is
an ordered list of
`{"t": "table" | "note" | "callout" | "list" | "pathway" | "figure"}` parts.
Order is preserved on purpose, since the sentence above a table is usually the
reason the table is there.

A `figure` block carries `src`, `alt`, the intrinsic `w`/`h`, and an optional
`cap`. Unlike a question's picture, which is inlined as a `data:` URI, a figure
points at a real file under `assets/figures/` named after the hash of its own
bytes. The notes JSON is fetched whole when the tab opens and is regenerated on
every rebuild, so inlining it there would cost every reader on every load and
defeat git's delta compression besides; hashing the name means two lectures
embedding the same picture share one file.

## Making it yours

- **Colours.** The palette is nine custom properties at the top of `base.css`.
  Each block page then sets its own `--q-accent`, `--q-accent-soft` and
  `--q-accent-ink` in an inline `:root`, which is also what the landing page card
  reads for its `--hue`.
- **Blocks.** The block list lives in `BLOCKS` at the top of each script in
  `tools/`. Five is not special.
- **Fonts.** Fraunces and Inter, pulled from Google Fonts in each page head. Both
  have local fallbacks in `base.css`.
- **Search engines.** Every page ships with `<meta name="robots"
  content="noindex, nofollow">`, because the original is meant to be unlisted.
  Delete that line if you want yours found.
- **Analytics and the link out.** `CF` in `tools/portal.py` sits in the right
  spot in the template and ships empty; drop your own snippet in if you want it.
  There is no longer a nav bar out to a parent site. A block page has its block
  nav, and a course index page carries one plain link back to the hub, built by
  `portal.uplink()` and styled by `.uplink` in `base.css`.

## Licence and content

The code is MIT, see [LICENSE](LICENSE).

The study content under `data/` has its own history. The 700 practice questions
came out of shared course material: a student-written workbook handed down through
the Schulich classes of 2015 to 2025, Elentra module knowledge checks, weekly
quizzes, slide concept checks and questions written from the case and small-group
sessions.

**They are here on purpose.** These are resources students already pass between
years, and putting them somewhere public is the reason this
repository exists, not an accident of packaging. Use them, fork them, correct them,
add to them. Where a question came out of a peer-written bank its errors are flagged
on the question itself rather than quietly patched, so you can see what you are
trusting before you trust it.

A handful of questions carry a picture, embedded in the question itself. Those come
from the teaching material the question came from: course illustrations, radiology
and endoscopy stills, gross pathology specimens and clinical photographs of the kind
that circulate in every medical curriculum. Cadaveric images from the anatomy modules
are covered by a separate protocol and are **not** included, so a question that
needed one says on its face that its picture is missing.
