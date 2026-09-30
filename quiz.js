/* The questions half of a course block page.
   Each block page sets window.QUIZ_BLOCK and calls POM2_QUIZ.boot() when the
   Questions tab is first opened - the block JSON runs to hundreds of kilobytes,
   so nothing is fetched until it is asked for.

   This file is shared by every course in the portal, so the two things that
   differ between them arrive in QUIZ_BLOCK rather than being written here:

     store     the localStorage prefix, so one course cannot read or overwrite
               another's progress even though they are served from one origin
     families  the question sets shown in the rail, in the order they appear

   Both fall back to the PoM 2 values, which is what the pages carried before
   the portal held more than one course. */

(function () {
  "use strict";

  var BLOCK = window.QUIZ_BLOCK;
  var STORE_PREFIX = BLOCK.store || "nsq.v1.";

  /* One page, one block or all of them. A block page names itself; the term
     page names every block the course has and pools them into one bank. Every
     line below works off BLOCKS, so the pooled page is this engine with a
     longer list rather than a second copy of it - which is the whole reason
     the portal has one quiz.js and not four. */
  var BLOCKS = (BLOCK.blocks && BLOCK.blocks.length)
    ? BLOCK.blocks
    : [{ slug: BLOCK.slug, n: BLOCK.n, name: BLOCK.name,
         weeks: BLOCK.weeks, qv: BLOCK.qv }];
  var TERM = BLOCKS.length > 1;
  var BLOCK_NAME = Object.create(null);
  BLOCKS.forEach(function (b) { BLOCK_NAME[b.slug] = b.name; });

  /* Headings shift down one level on the pooled page, because the block name
     becomes the h2 that the question set used to be. */
  function hTag(level) { return "h" + (TERM ? level + 1 : level); }

  /* every family the course has is listed, empty ones included: an empty family
     is a visible gap in coverage, which is the point. */
  var FAMILIES = BLOCK.families || [
    {
      key: "module",
      name: "Course modules",
      blurb: "The Elentra module knowledge checks and the concept checks on the lecture slides. Cases live under Meds 2029 instead, wherever they came from."
    },
    {
      key: "weekly",
      name: "Weekly quizzes",
      blurb: "The weekly quizzes, both the Microsoft Forms ones and the ones sat in Elentra. Kept whole as their own set, so a week's quiz can be drilled the way it was written."
    },
    {
      key: "workbook",
      name: "Pre-Clerkship Workbook",
      blurb: "The Pre-Clerkship Workbook (2023 edition), the student bank passed down through the Schulich classes of 2015-2025. It has a written key, but the key is peer-written and contains real errors. Every one found is flagged on the question."
    },
    {
      key: "meds2029",
      name: "Meds 2029",
      blurb: "Questions built from patient cases in the modules, DSSGs and in-class lectures, since exams tend to recycle similar cases."
    },
    {
      key: "reviews",
      name: "Schulich Reviews",
      blurb: "The Schulich Reviews sessions, both their practice questions and their summary content. TBD."
    }
  ];

  var QUESTIONS = [];
  var QMAP = Object.create(null);
  var progress = Object.create(null);
  /* Every facet holds a LIST of picked keys, and an empty list means "all" -
     not a key called "all". Week 1 and week 2 is a question people actually
     ask, and a single-valued filter cannot answer it. Empty-means-all is what
     keeps the "All weeks" row a clear button rather than a fifth checkbox
     that has to be kept mutually exclusive with the other four. */
  /* search is the one facet whose value is typed rather than picked, so it is
     a string, and the empty string is its "all" */
  var filters = { status: [], block: [], family: [], week: [], tag: [], search: "" };

  function isOn(name, k) { return filters[name].indexOf(k) !== -1; }

  function anyFilter() {
    return filters.status.length > 0 || filters.block.length > 0 ||
           filters.family.length > 0 || filters.week.length > 0 ||
           filters.tag.length > 0 || searchOn();
  }

  /* View and Mode are two axes, deliberately independent. VIEW is how the
     questions are laid out; MODE is when the answer is allowed to appear. The
     pair that matters is paged + test - a block with a boundary and a submit -
     but neither implies the other: browsing one at a time and scrolling a
     tutor stream are both things people actually do. */
  var VIEW = "stream";          /* "stream" | "paged" */
  var MODE = "tutor";           /* "tutor"  | "test"  */
  var pageIdx = 0;

  /* A third axis, and bank order is the default for a reason: the stream reads
     week by week, which is the order the material was taught in. Shuffling is
     the other thing worth practising against - an exam does not ask five
     thyroid questions in a row, and knowing which lecture a question came
     from is half of some answers. So it sits beside View and Mode rather than
     being folded into Test, which draws WHICH questions and now leaves WHAT
     ORDER to this. */
  var ORDER = "bank";           /* "bank" | "shuffle" */
  var SHUFFLE = null;           /* qid -> its place in the shuffled deck */

  function shuffling() { return ORDER === "shuffle" && !!SHUFFLE; }

  /* A sat block is a lifecycle, not a toggle: drawn, sat, submitted, reviewed.
     Its answers stage HERE and are only written to the store on submit, so
     abandoning a block half-done leaves no trace - which is right, because you
     did not answer those questions. Drawing a block never erases what you
     already had. */
  var TEST = { size: 20, ids: null, picks: Object.create(null),
               submitted: false, poolN: 0, asked: 0,
               /* minutes asked for, and the wall-clock instant that becomes.
                  Off by default: a sat block is worth practising under time,
                  but imposing one on someone drilling twenty questions is not
                  what they asked for. */
               limit: 0, deadline: null };

  var TICK = null;

  function stopTick() {
    if (TICK) { clearInterval(TICK); TICK = null; }
  }

  function clockText(ms) {
    var s = Math.max(0, Math.round(ms / 1000));
    return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2);
  }

  /* label and total lookups, filled in by buildBar: the applied-filter line
     needs a filter's human name, and a family's block total is what tells an
     empty coverage gap ("none") apart from one the filters emptied ("0"). */
  var FAM_TOTAL = Object.create(null);
  var FAM_NAME = Object.create(null);
  var WEEK_LABEL = Object.create(null);
  var TAG_LABEL = Object.create(null);
  var STATUS_LABEL = Object.create(null);
  var RESET_SHOWN_IDLE = null;
  var storeWritable = true;

  /* every section's children in the order buildStream made them, which is how
     a shuffled stream gets put back without rebuilding a card */
  var HOME = [];

  function byId(id) { return document.getElementById(id); }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  /* ---------- the store ---------- */

  function sanitize(qid, data) {
    var q = QMAP[qid];
    if (!q || !data || typeof data !== "object") return null;
    return {
      qid: qid,
      source: q.source,
      family: q.family,
      lecture: q.lecture,
      week: q.week === null ? 0 : q.week,
      status: (data.status === "correct" || data.status === "wrong") ? data.status : null,
      flagged: data.flagged === true,
      firstTryCorrect: typeof data.firstTryCorrect === "boolean" ? data.firstTryCorrect : null,
      attempts: Array.isArray(data.attempts)
        ? data.attempts.filter(function (a) { return a && typeof a === "object"; }).slice(-50)
        : [],
      lastTs: typeof data.lastTs === "number" ? data.lastTs : 0
    };
  }

  /* Progress stays keyed per BLOCK, one localStorage entry each, and the
     pooled page reads and writes those same entries rather than a sixth of
     its own. Answer a question on the term page and the block page already
     has it: there is nothing to migrate, nothing to merge, and no second
     copy of an answer that could disagree with the first. */
  function storeKey(slug) { return STORE_PREFIX + slug; }

  function load() {
    BLOCKS.forEach(function (b) {
      var raw = null;
      try { raw = window.localStorage.getItem(storeKey(b.slug)); }
      catch (e) { storeWritable = false; return; }
      if (!raw) return;
      var parsed;
      try { parsed = JSON.parse(raw); }
      catch (e) { return; }
      if (!parsed || typeof parsed !== "object") return;
      Object.keys(parsed).forEach(function (qid) {
        var rec = sanitize(qid, parsed[qid]);
        if (rec) progress[qid] = rec;
      });
    });
  }

  /* Given a slug, writes that one block. Without one, all of them - which is
     what a restore needs and what a single answer must not do, or every tick
     on the term page would re-serialise fifteen hundred records five times. */
  function save(slug) {
    if (!storeWritable) return;
    var want = slug ? [slug] : BLOCKS.map(function (b) { return b.slug; });
    want.forEach(function (s) {
      var mine = Object.create(null);
      Object.keys(progress).forEach(function (qid) {
        var q = QMAP[qid];
        if (q && q.block === s) mine[qid] = progress[qid];
      });
      try { window.localStorage.setItem(storeKey(s), JSON.stringify(mine)); }
      catch (e) {
        storeWritable = false;
        note("Progress could not be saved - the browser refused to write to local storage. Every question still works, but nothing is being kept.");
      }
    });
  }

  function note(text) {
    var n = byId("storenote");
    n.hidden = false;
    n.textContent = text;
  }

  /* ---------- progress model ---------- */

  function rec(qid) { return progress[qid] || null; }

  function stateOf(qid) {
    var r = rec(qid);
    if (!r || (r.status !== "correct" && r.status !== "wrong")) return "unseen";
    return r.status;
  }

  function isStarred(qid) { var r = rec(qid); return !!(r && r.flagged === true); }

  function attemptsOf(qid) {
    var r = rec(qid);
    return (r && Array.isArray(r.attempts)) ? r.attempts : [];
  }

  function chosenOf(qid) {
    var a = attemptsOf(qid);
    if (!a.length) return null;
    var c = a[a.length - 1].chosen;
    return typeof c === "string" ? c.split("+").filter(Boolean) : null;
  }

  function persist(qid, patch) {
    var prev = progress[qid] || {}, q = QMAP[qid];
    var next = {
      qid: qid,
      source: q.source,
      family: q.family,
      lecture: q.lecture,
      week: q.week === null ? 0 : q.week,
      status: patch.status !== undefined ? patch.status : (prev.status || null),
      flagged: patch.flagged !== undefined ? patch.flagged : (prev.flagged === true),
      firstTryCorrect: (typeof prev.firstTryCorrect === "boolean") ? prev.firstTryCorrect : null,
      attempts: Array.isArray(prev.attempts) ? prev.attempts.slice(-49) : [],
      lastTs: Date.now()
    };
    if (patch.attempt) {
      if (next.firstTryCorrect === null) next.firstTryCorrect = patch.attempt.correct;
      next.attempts = next.attempts.concat([patch.attempt]);
    }
    progress[qid] = next;
    save(q.block);
    paintQuestion(qid);
    paintStats();
    setAnchor(qid);
  }

  function forget(qid) { forgetMany([qid]); }

  /* One pass, one write per block touched. Clearing what is shown on the
     pooled page can mean a thousand questions, and the old one-at-a-time
     forget wrote the whole store back on every single one of them. */
  function forgetMany(ids) {
    if (!ids.length) return;
    var touched = Object.create(null);
    ids.forEach(function (qid) {
      var q = QMAP[qid];
      if (q) touched[q.block] = 1;
      delete progress[qid];
    });
    Object.keys(touched).forEach(function (slug) { save(slug); });
    ids.forEach(paintQuestion);
    paintStats();
    if (ANCHOR && ids.indexOf(ANCHOR) !== -1) {
      ANCHOR = null; RESUMING = false; paintPos();
    }
  }

  /* ---------- mode helpers ---------- */

  /* The single gate on showing an answer. In tutor mode an answered question
     reveals at once - that is the whole value of the written rationales. In a
     sat block the pick is held and nothing is shown until submit; revealing
     early would make it a tutor stream with extra steps. */
  function revealOk() { return MODE !== "test" || TEST.submitted; }

  /* 155 of the questions in the banks cannot be auto-marked: free text,
     matching, and the ones whose source gives no defensible key. They are
     fine in a tutor stream, where you mark yourself. A sat block that
     silently fails to score a fifth of itself is not a score, so blocks are
     drawn from the gradable ones only. */
  function gradable(q) {
    if (q.unscorable) return false;
    /* a pairing carries its key in pairs.items, not in correct[] */
    if (q.kind === "pairing") return !!(q.pairs && q.pairs.items && q.pairs.items.length);
    return !q.free && Array.isArray(q.correct) && q.correct.length > 0;
  }

  /* ---------- pairing ---------- */

  /* The right-hand choices, deterministically shuffled by qid. Deterministic
     because a fresh shuffle on every repaint would move the options under the
     cursor; shuffled because presenting them in answer order gives the whole
     thing away. */
  function pairChoices(q) {
    var seen = Object.create(null), out = [];
    q.pairs.items.forEach(function (it) {
      if (!seen[it.right]) { seen[it.right] = 1; out.push(it.right); }
    });
    var h = 2166136261;
    for (var i = 0; i < q.qid.length; i++) {
      h ^= q.qid.charCodeAt(i);
      h = (h * 16777619) >>> 0;
    }
    for (var j = out.length - 1; j > 0; j--) {
      h = (h * 1103515245 + 12345) >>> 0;
      var k = h % (j + 1), t = out[j];
      out[j] = out[k]; out[k] = t;
    }
    return out;
  }

  /* the choice index each row should be carrying */
  function pairKey(q) {
    var choices = pairChoices(q);
    return q.pairs.items.map(function (it) { return choices.indexOf(it.right); });
  }

  function pairIsRight(q, picks) {
    var want = pairKey(q);
    return picks.length === want.length && want.every(function (v, i) { return picks[i] === v; });
  }

  /* picks restored from the store; -1 is a row left alone */
  function pairStored(qid) {
    var q = QMAP[qid];
    if (!q || q.kind !== "pairing") return null;
    var a = attemptsOf(qid);
    if (!a.length) return null;
    var c = a[a.length - 1].chosen;
    if (typeof c !== "string") return null;
    return c.split("|").map(function (x) { var n = parseInt(x, 10); return isNaN(n) ? -1 : n; });
  }

  function pairReadRows(art) {
    return [].map.call(art.querySelectorAll("select.ps"), function (sel) {
      return sel.value === "" ? -1 : parseInt(sel.value, 10);
    });
  }

  function buildPairing(q, art) {
    var choices = pairChoices(q);
    var wrap = el("div", "pairing");

    var head = el("div", "pair-row pair-head");
    head.appendChild(el("span", "pl", q.pairs.leftLabel || "Item"));
    head.appendChild(el("span", "pr", q.pairs.rightLabel || "Match"));
    wrap.appendChild(head);

    q.pairs.items.forEach(function (it, i) {
      var row = el("div", "pair-row");
      row.dataset.i = String(i);
      row.appendChild(el("span", "pl", it.left));
      var right = el("span", "pr");
      var sel = document.createElement("select");
      sel.className = "ps";
      sel.dataset.i = String(i);
      sel.setAttribute("aria-label", "Match for " + it.left);
      var blank = document.createElement("option");
      blank.value = "";
      blank.textContent = "Choose\u2026";
      sel.appendChild(blank);
      choices.forEach(function (c, ci) {
        var o = document.createElement("option");
        o.value = String(ci);
        o.textContent = c;
        sel.appendChild(o);
      });
      sel.addEventListener("change", function () { onPairChange(q, art); });
      right.appendChild(sel);
      right.appendChild(el("span", "pmark"));
      row.appendChild(right);
      wrap.appendChild(row);
    });
    return wrap;
  }

  /* While a block is being sat the rows stage like any other pick. In tutor
     mode nothing is graded until Check, so a half-filled grid is not an
     answer and does not get written through. */
  function onPairChange(q, art) {
    var picks = pairReadRows(art);
    if (staging()) {
      TEST.picks[q.qid] = picks;
      paintTest();
    }
    var check = art.querySelector('[data-role="check"]');
    if (check) check.disabled = picks.indexOf(-1) !== -1;
  }

  function submitPairing(q, art) {
    if (staging()) return;
    var picks = pairReadRows(art);
    if (picks.indexOf(-1) !== -1) return;
    var right = pairIsRight(q, picks);
    persist(q.qid, {
      status: right ? "correct" : "wrong",
      attempt: { ts: Date.now(), chosen: picks.join("|"), correct: right }
    });
  }

  function testChosen(qid) {
    var v = TEST.picks[qid];
    return Array.isArray(v) ? v : [];
  }

  function staging() { return MODE === "test" && !TEST.submitted; }

  /* ---------- build one question ---------- */

  var KIND_LABEL = { matching: "matching", pairing: "matching", short: "short answer", broken: "unscorable" };

  /* ---------- where a question came from ---------- */

  /* Not every set knows its lecture. The FoM and PoM 1 banks file by week, so
     each of their questions carries the SET's name where a lecture would go,
     and a HippoNotes chapter covers a whole week and names that week. Printing
     either back as "the lecture to review" would be a promise the data cannot
     keep.

     A lecture earns its place on the line only when it says something the week
     heading has not already said. What makes a set's label detectable without a
     hand-kept list is that every question in that block and set carries it: a
     real lecture name never does. */
  var LABEL = null;

  function setLabels() {
    if (LABEL) return LABEL;
    LABEL = Object.create(null);
    var only = Object.create(null);
    QUESTIONS.forEach(function (q) {
      var k = q.block + "\u0000" + q.family;
      if (only[k] === undefined) only[k] = q.lecture;
      else if (only[k] !== q.lecture) only[k] = null;
    });
    Object.keys(only).forEach(function (k) { if (only[k]) LABEL[only[k]] = true; });
    return LABEL;
  }

  /* A review entry names a week and a lecture number but not a block. Weeks
     are numbered once across a course and the bank already carries each
     block's span, so the block follows from the week. That is also what joins
     a question filed under one block to a lecture taught in another - the
     Infection & Immunity questions on vaccines review a week 4 lecture, and
     week 4 is Principles & Development. */
  function blockForWeek(w) {
    var n = parseInt(w, 10);
    if (isNaN(n)) return null;
    for (var i = 0; i < BLOCKS.length; i++) {
      /* "1–4" with an en dash as the builder writes it, or "9" for a block
         one week long; a plain hyphen is accepted so a hand-edited config
         cannot silently break the join */
      var span = String(BLOCKS[i].weeks || "").split(/[–—-]/);
      var lo = parseInt(span[0], 10), hi = parseInt(span[span.length - 1], 10);
      if (isNaN(hi)) hi = lo;
      if (!isNaN(lo) && n >= lo && n <= hi) return BLOCKS[i].slug;
    }
    return null;
  }

  /* The id the notes file gives the lecture: <block>-w<week>-<number>. An
     in-class session carries no number and resolves to nothing; the line
     still names it, it just cannot be opened. */
  function noteIdFor(r) {
    if (!r || !/^\d+$/.test(String(r.n || ""))) return null;
    var slug = blockForWeek(r.w);
    return slug ? slug + "-w" + r.w + "-" + r.n : null;
  }

  /* The lectures tools/review_lectures.py resolved this question to, as the
     place to go rather than the place it was filed. Where those disagree the
     LECTURE's week wins: a question filed under week 5 whose material is
     taught in week 4 should send you to week 4, and several hundred of them
     do exactly that.

     The shape is one run per week, each run the lectures that share it, so
     the common case - one lecture, or two from the same week - reads as one
     location: "Week 13 · 05 - X, 06 - Y". The text and the buttons are
     both built from this, so they cannot disagree. */
  function reviewParts(q) {
    var runs = [], last = null;
    (q.review || []).forEach(function (r) {
      var id = noteIdFor(r);
      var item = { n: r.n, t: r.t, name: (r.n ? r.n + " - " : "") + r.t,
                   id: id, slug: id ? blockForWeek(r.w) : null };
      if (r.w !== last) {
        runs.push({ w: r.w, items: [item] });
        last = r.w;
      } else {
        runs[runs.length - 1].items.push(item);
      }
    });
    return runs;
  }

  /* Nothing resolved: the week is all there is, and saying so plainly beats
     naming a lecture the data does not actually know. Used only when the
     question has no review entries; those are drawn by buildWhere. */
  function whereFrom(q) {
    var parts = [];
    if (TERM) parts.push(BLOCK_NAME[q.block] || q.block);
    parts.push(q.weekLabel ||
      (q.week === null ? "Off-curriculum" : "Week " + q.week));
    var lec = q.lecture;
    if (lec && !setLabels()[lec] && lec !== BLOCK_NAME[q.block] &&
        parts.join(" ").toLowerCase().indexOf(lec.toLowerCase()) === -1) {
      parts.push(lec);
    }
    return parts.join(" \u00b7 ");
  }

  /* Each lecture on the line opens its note, so the line is built from the
     same runs the text was, with a button where a lecture resolved and plain
     text where it did not. A browser with no <dialog> gets a link to the
     note on its block page instead: the same note, one page over. */
  var DIALOG_OK = !!window.HTMLDialogElement;

  function noteUrl(it) { return it.slug + ".html#n-" + it.id; }

  function lectureLink(it, w) {
    if (!DIALOG_OK) {
      var a = el("a", "sw-lec", it.name);
      a.href = noteUrl(it);
      return a;
    }
    var b = el("button", "sw-lec", it.name);
    b.type = "button";
    b.title = "Open this lecture's note";
    b.addEventListener("click", function () { openNote(it, w, b); });
    return b;
  }

  function buildWhere(q) {
    var sw = el("span", "sw");
    var runs = reviewParts(q);
    if (!runs.length) {
      sw.textContent = whereFrom(q);
      return sw;
    }
    if (TERM) sw.appendChild(document.createTextNode((BLOCK_NAME[q.block] || q.block) + " \u00b7 "));
    runs.forEach(function (run, i) {
      if (i) sw.appendChild(document.createTextNode("  +  "));
      sw.appendChild(document.createTextNode("Week " + run.w + " \u00b7 "));
      run.items.forEach(function (it, j) {
        if (j) sw.appendChild(document.createTextNode(", "));
        sw.appendChild(it.id ? lectureLink(it, run.w) : document.createTextNode(it.name));
      });
    });
    return sw;
  }

  /* ---------- the note dialog ---------- */

  /* One lecture's note, read without leaving the question. The dialog is
     built by script on first use rather than by the page template, so a page
     cached from before it shipped gets it too, and a browser that lacks
     <dialog> never builds it - its review lines are links instead. */
  var DLG = null;
  var NOTES = Object.create(null);   // block slug -> promise of {lecture id -> lecture}
  var OPENING = 0;                   // which click the load in flight belongs to
  /* the button that opened the dialog, kept so focus can be handed back
     explicitly: the native restore only works if the button held focus, and
     Safari never focuses a button on click */
  var OPENER = null;

  function ensureDialog() {
    if (DLG) return DLG;
    var d = el("dialog", "notedlg");
    d.setAttribute("aria-labelledby", "notedlg-title");

    var head = el("div", "notedlg-head");
    var text = el("div", "notedlg-text");
    text.appendChild(el("p", "eyebrow notedlg-where"));
    var h = el("h2");
    h.id = "notedlg-title";
    text.appendChild(h);
    text.appendChild(el("a", "notedlg-full", "Open on the block page"));
    head.appendChild(text);
    var x = el("button", "notedlg-close", "\u00d7");
    x.type = "button";
    x.title = "Close (Esc)";
    x.setAttribute("aria-label", "Close");
    x.addEventListener("click", function () { d.close(); });
    head.appendChild(x);
    d.appendChild(head);
    d.appendChild(el("div", "notedlg-body"));

    /* the backdrop is the dialog's own box outside its children, so a click
       whose target is the dialog itself is a click on the backdrop */
    d.addEventListener("click", function (e) { if (e.target === d) d.close(); });
    d.addEventListener("close", function () {
      document.body.classList.remove("has-dialog");
      d.querySelector(".notedlg-body").innerHTML = "";
      if (OPENER && OPENER.focus) OPENER.focus();
      OPENER = null;
    });
    document.body.appendChild(d);
    DLG = d;
    return d;
  }

  /* One request per block per page, kept for the session. A failed load is
     forgotten, so the next click tries again rather than repeating the error. */
  function fetchNotes(slug) {
    if (NOTES[slug]) return NOTES[slug];
    var b = null;
    BLOCKS.forEach(function (x) { if (x.slug === slug) b = x; });
    var p = fetch("data/notes/" + slug + ".json" + (b && b.nv ? "?v=" + b.nv : ""))
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        var map = Object.create(null);
        ((data && data.weeks) || []).forEach(function (w) {
          (w.lectures || []).forEach(function (l) {
            // a roster can repeat an id; the first one is the one the block page shows too
            if (l.id && !map[l.id]) map[l.id] = l;
          });
        });
        return map;
      });
    p.then(null, function () { delete NOTES[slug]; });
    NOTES[slug] = p;
    return p;
  }

  function fillState(body, text, it) {
    body.innerHTML = "";
    var p = el("p", "notedlg-state", text + " ");
    var a = el("a", null, "Open the block page");
    a.href = noteUrl(it);
    p.appendChild(a);
    body.appendChild(p);
  }

  function openNote(it, w, from) {
    var d = ensureDialog();
    var where = d.querySelector(".notedlg-where"), title = byId("notedlg-title"),
        full = d.querySelector(".notedlg-full"), body = d.querySelector(".notedlg-body");
    var token = ++OPENING;
    OPENER = from || null;

    where.textContent = (BLOCK_NAME[it.slug] || it.slug) + " \u00b7 Week " + w;
    title.textContent = it.name;
    full.href = noteUrl(it);
    body.innerHTML = "";
    body.appendChild(el("p", "notedlg-state", "Loading\u2026"));
    document.body.classList.add("has-dialog");
    if (!d.open) d.showModal();
    body.scrollTop = 0;

    fetchNotes(it.slug).then(function (map) {
      if (token !== OPENING) return;      // a later click owns the dialog now
      var lec = map[it.id];
      if (!lec) { fillState(body, "This lecture is not in the block's roster.", it); return; }
      /* written up under a neighbour's heading: show that note, under its title */
      var target = lec.coveredBy ? map[lec.coveredBy.key] : lec;
      var shared = window.PORTAL_NOTES;
      if (!shared || !target || target.hasNote !== true) {
        fillState(body, "No note yet for this lecture.", it);
        return;
      }
      title.textContent = (target.num ? target.num + " \u00b7 " : "") + shared.coveredTitle(target);
      body.innerHTML = "";
      body.appendChild(shared.build(target, { block: BLOCK_NAME[it.slug] || it.slug, slug: it.slug, onPrint: null }));
      shared.drawPathways(body);
      body.scrollTop = 0;
    }, function () {
      if (token !== OPENING) return;
      fillState(body, "The note could not be loaded.", it);
    });
  }

  /* ---------- the report button ---------- */

  /* The dialog is portal.js's, shared with the notes; a question hands it
     the fields that name it and its stem to show. */
  function reportButton(q) {
    return window.PORTAL_REPORT.button({
      kind: "question",
      id: q.qid,
      where: (BLOCK.course ? BLOCK.course + " \u00b7 " : "") +
             (BLOCK_NAME[q.block] || BLOCK.name) + " \u00b7 " + q.qid,
      preview: plainText(q.stem || ""),
      fields: {
        course: BLOCK.dir || "", block: q.block || BLOCK.slug,
        qid: q.qid, num: String(q.num), family: q.family || ""
      }
    });
  }

  function buildQuestion(q) {
    var art = el("article", "q");
    art.id = "q-" + q.qid;
    art.dataset.qid = q.qid;
    art.dataset.kind = q.kind;

    var head = el("div", "qhead");
    head.appendChild(el("span", "qnum", "Q" + q.num));
    head.appendChild(el("span", "tag", q.sourceLabel));
    if (!q.keyed) head.appendChild(el("span", "tag reasoned", "no official key"));
    if (KIND_LABEL[q.kind]) head.appendChild(el("span", "tag kind", KIND_LABEL[q.kind]));
    if (q.multi) head.appendChild(el("span", "tag multi", "select " + q.correct.length));
    if (q.retired) head.appendChild(el("span", "tag retired", "retired"));
    var hasErr = (q.flags || []).some(function (f) {
      return f.type === "bug" || f.type === "red" ||
             (f.type === "warning" && f.title !== "No explanation in the module");
    });
    if (hasErr) head.appendChild(el("span", "tag errflag", "source error flagged"));
    head.appendChild(el("span", "spacer"));

    var star = el("button", "star-btn", "★");
    star.type = "button";
    star.title = "Star for review";
    star.setAttribute("aria-label", "Star question " + q.num);
    star.setAttribute("aria-pressed", "false");
    star.addEventListener("click", function () {
      persist(q.qid, { flagged: !isStarred(q.qid) });
    });
    head.appendChild(star);
    art.appendChild(head);

    /* Shown only in a shuffled stream, where the week and lecture headings are
       gone. In bank order the heading three lines up already says this, and
       repeating it on every card is noise. */
    art.appendChild(el("p", "qwhere",
      (TERM ? (BLOCK_NAME[q.block] || q.block) + " \u00b7 " : "") +
      (q.week === null ? "Off-curriculum" : "Week " + q.week) + " \u00b7 " + q.lecture));

    if (q.preamble) {
      var pre = el("div", "preamble");
      pre.appendChild(el("span", "pt", q.preamble.title || "Instructions"));
      var pb = el("div");
      pb.innerHTML = q.preamble.html;
      pre.appendChild(pb);
      art.appendChild(pre);
    }

    var stem = el("div", "stem");
    stem.innerHTML = q.stem;
    art.appendChild(stem);

    if (q.options.length) {
      var list = el("ul", "opts");
      q.options.forEach(function (o) {
        var li = document.createElement("li");
        var b = el("button", "opt");
        b.type = "button";
        b.dataset.letter = o.letter;
        b.appendChild(el("span", "L", o.letter));
        var t = el("span", "t");
        t.innerHTML = o.html;
        b.appendChild(t);
        b.appendChild(el("span", "verdict"));
        if (q.unscorable) b.disabled = true;
        else b.addEventListener("click", function () { pick(q, art, o.letter); });
        li.appendChild(b);
        list.appendChild(li);
      });
      art.appendChild(list);
    }

    if (q.kind === "pairing" && q.pairs && q.pairs.items) {
      art.appendChild(buildPairing(q, art));
    }

    if (q.unscorable) {
      var bn = el("div", "banner pre");
      bn.appendChild(el("b", null, "Not scored"));
      bn.appendChild(document.createTextNode(
        "The source gives no defensible answer for this one, so it is left out of the accuracy figures. Read why, then move on."));
      art.appendChild(bn);
      var a1 = el("div", "actions");
      var sh = el("button", "btn ghost", "Show the problem");
      sh.type = "button";
      sh.addEventListener("click", function () { art.classList.add("revealed"); });
      a1.appendChild(sh);
      art.appendChild(a1);
    } else if (q.kind === "pairing" && q.pairs && q.pairs.items) {
      var a4 = el("div", "actions");
      var pc = el("button", "btn", "Check answer");
      pc.type = "button";
      pc.dataset.role = "check";
      pc.disabled = true;
      pc.addEventListener("click", function () { submitPairing(q, art); });
      a4.appendChild(pc);
      a4.appendChild(el("span", "hint", "fill every row, then check"));
      art.appendChild(a4);
    } else if (q.free) {
      var a2 = el("div", "actions");
      var show = el("button", "btn", "Show answer");
      show.type = "button";
      show.addEventListener("click", function () { art.classList.add("revealed"); });
      var got = el("button", "btn ghost", "I had it");
      got.type = "button";
      got.addEventListener("click", function () {
        art.classList.add("revealed");
        persist(q.qid, {
          status: "correct",
          attempt: { ts: Date.now(), chosen: "self", correct: true }
        });
      });
      var mis = el("button", "btn ghost", "I missed it");
      mis.type = "button";
      mis.addEventListener("click", function () {
        art.classList.add("revealed");
        persist(q.qid, {
          status: "wrong",
          attempt: { ts: Date.now(), chosen: "self", correct: false }
        });
      });
      a2.appendChild(show);
      a2.appendChild(got);
      a2.appendChild(mis);
      art.appendChild(a2);
    } else if (q.multi) {
      var a3 = el("div", "actions");
      var check = el("button", "btn", "Check answer");
      check.type = "button";
      check.dataset.role = "check";
      check.disabled = true;
      check.addEventListener("click", function () { submitMulti(q, art); });
      a3.appendChild(check);
      a3.appendChild(el("span", "hint", "select " + q.correct.length + ", then check"));
      art.appendChild(a3);
    }

    var ans = el("div", "answer");
    if (!q.keyed) {
      var nk = el("div", "banner");
      nk.appendChild(el("b", null, "No official answer key"));
      nk.appendChild(document.createTextNode(
        "Reasoned from the lecture content, not transcribed from a key. Verify before relying on it."));
      ans.appendChild(nk);
    }
    ans.appendChild(el("p", "ans-h", q.keyed ? (q.answerTitle || "Answer") : "Reasoned answer"));
    var ab = el("div", "ans-body");
    ab.innerHTML = q.answer;
    ans.appendChild(ab);
    (q.flags || []).forEach(function (f) {
      var c = el("div", "callout k-" + (/^[a-z]+$/.test(f.type) ? f.type : "note"));
      c.appendChild(el("span", "ct", f.title || "Note"));
      var cb = el("div");
      cb.innerHTML = f.html;
      c.appendChild(cb);
      ans.appendChild(c);
    });

    /* The lecture to go back to, at the FOOT of the explanation rather than the
       head of the card. It is the next thing wanted after reading why an answer
       was wrong, and before answering it is a hint. */
    var src = el("p", "ans-src");
    src.appendChild(el("span", "sl", "Review"));
    src.appendChild(buildWhere(q));
    ans.appendChild(src);

    art.appendChild(ans);

    var foot = el("div", "qfoot");
    foot.appendChild(el("span", "qid", q.qid));
    foot.appendChild(el("span", "qid attempts"));
    var rst = el("button", "reset-q", "reset");
    rst.type = "button";
    rst.hidden = true;
    rst.addEventListener("click", function () { forget(q.qid); });
    foot.appendChild(rst);
    foot.appendChild(reportButton(q));
    art.appendChild(foot);
    return art;
  }

  function pick(q, art, letter) {
    /* While a block is being sat, a pick is held in memory rather than
       written through: nothing reaches localStorage until submit. */
    if (staging()) {
      var cur = testChosen(q.qid);
      if (q.multi) {
        var at = cur.indexOf(letter);
        if (at === -1) cur = cur.concat([letter]);
        else cur = cur.slice(0, at).concat(cur.slice(at + 1));
      } else {
        cur = (cur.length === 1 && cur[0] === letter) ? [] : [letter];
      }
      TEST.picks[q.qid] = cur;
      paintQuestion(q.qid);
      paintTest();
      return;
    }
    if (q.multi) {
      if (art.classList.contains("revealed")) return;
      var btn = art.querySelector('.opt[data-letter="' + letter + '"]');
      btn.dataset.pick = btn.dataset.pick === "on" ? "" : "on";
      art.querySelector('[data-role="check"]').disabled =
        art.querySelectorAll('.opt[data-pick="on"]').length === 0;
      return;
    }
    var correct = q.correct.indexOf(letter) !== -1;
    persist(q.qid, {
      status: correct ? "correct" : "wrong",
      attempt: { ts: Date.now(), chosen: letter, correct: correct }
    });
  }

  function submitMulti(q, art) {
    if (staging()) return;
    var picked = [].slice.call(art.querySelectorAll('.opt[data-pick="on"]'))
      .map(function (b) { return b.dataset.letter; })
      .sort();
    var correct = picked.join("+") === q.correct.slice().sort().join("+");
    persist(q.qid, {
      status: correct ? "correct" : "wrong",
      attempt: { ts: Date.now(), chosen: picked.join("+"), correct: correct }
    });
  }

  function paintPairing(art, q, qid, reveal) {
    var picks = staging() ? (TEST.picks[qid] || null) : pairStored(qid);
    var key = pairKey(q);
    [].forEach.call(art.querySelectorAll("select.ps"), function (sel) {
      var i = parseInt(sel.dataset.i, 10);
      var v = (picks && picks[i] !== undefined) ? picks[i] : -1;
      sel.value = v === -1 ? "" : String(v);
      sel.disabled = reveal;
      var row = sel.parentNode.parentNode, mark = row.querySelector(".pmark");
      mark.textContent = "";
      row.dataset.mark = "";
      if (!reveal) return;
      if (v === key[i]) { row.dataset.mark = "hit"; mark.textContent = "correct"; }
      else {
        row.dataset.mark = "miss";
        mark.textContent = (v === -1 ? "left blank \u00b7 " : "\u2192 ") + q.pairs.items[i].right;
      }
    });
    var chk = art.querySelector('[data-role="check"]');
    if (chk && !reveal) chk.disabled = pairReadRows(art).indexOf(-1) !== -1;
  }

  function paintQuestion(qid) {
    var art = byId("q-" + qid);
    if (!art) return;
    var q = QMAP[qid], st = stateOf(qid), done = st !== "unseen";

    /* A staged block answers from TEST.picks, not from the store, and reveals
       nothing: no verdict, no state stripe, options still live so the answer
       can be changed right up to the submit. */
    var chosen, reveal;
    if (staging()) {
      chosen = testChosen(qid);
      done = chosen.length > 0;
      reveal = false;
    } else {
      chosen = chosenOf(qid) || [];
      reveal = done && revealOk();
    }

    art.dataset.state = reveal ? st : "unseen";
    if (!q.unscorable) art.classList.toggle("revealed", reveal);
    art.querySelector(".star-btn").setAttribute("aria-pressed", isStarred(qid) ? "true" : "false");

    [].forEach.call(art.querySelectorAll(".opt"), function (b) {
      if (q.unscorable) return;
      var L = b.dataset.letter;
      b.disabled = reveal;
      b.dataset.pick = (!reveal && chosen.indexOf(L) !== -1) ? "on" : "";
      var v = b.querySelector(".verdict");
      v.textContent = "";
      b.dataset.mark = "";
      if (!reveal) return;
      var isKey = q.correct.indexOf(L) !== -1, wasPicked = chosen.indexOf(L) !== -1;
      if (wasPicked && isKey) { b.dataset.mark = "hit"; v.textContent = "your pick · correct"; }
      else if (wasPicked) { b.dataset.mark = "miss"; v.textContent = "your pick"; }
      else if (isKey) { b.dataset.mark = "key"; v.textContent = "correct"; }
    });

    if (q.kind === "pairing" && q.pairs && q.pairs.items) paintPairing(art, q, qid, reveal);

    /* nothing to "check" while staging - the pick IS the answer until submit */
    var check = art.querySelector('[data-role="check"]');
    if (check) check.hidden = reveal || staging();

    var atts = attemptsOf(qid);
    art.querySelector(".attempts").textContent = atts.length > 1 ? atts.length + " attempts" : "";
    art.querySelector(".reset-q").hidden = staging() || (!reveal && !isStarred(qid));
  }

  /* ---------- filters ---------- */

  /* One predicate per filter group rather than one combined test: a facet's
     own count has to honour the other two groups and ignore itself, which is
     what makes "Week 3" read as "3 of the questions you are looking at". */
  /* Within a group the picks are an OR - week 1 or week 2 - and the four
     groups are ANDed together. That is the only reading that makes a second
     pick widen the stream rather than empty it. */
  /* The block a question came from. On a block page every question shares
     one, so the group is hidden and this is always true; on the term page it
     is the first cut most people want. */
  function blockOk(q) { return !filters.block.length || isOn("block", q.block); }

  function famOk(q) { return !filters.family.length || isOn("family", q.family); }

  function weekOk(q) { return !filters.week.length || isOn("week", weekKey(q)); }

  /* Tags cut across the other three: the anatomy strand is taught in one block
     but its questions arrive as modules and as workbook chapters, so neither
     the family row nor the week chip can gather them. A question carries none
     unless it was tagged, and most carry none. */
  function tagsOf(q) { return Array.isArray(q.tags) ? q.tags : []; }

  function tagOk(q) {
    if (!filters.tag.length) return true;
    var t = tagsOf(q);
    return filters.tag.some(function (k) { return t.indexOf(k) !== -1; });
  }

  /* Starred is not a state the other three can be in - a starred question is
     also unseen or wrong or correct - so picking Wrong and Starred asks for
     the union of two overlapping sets, not for their intersection. */
  function statusIs(q, k) {
    var st = stateOf(q.qid);
    switch (k) {
      case "unseen":  return st === "unseen";
      case "wrong":   return st === "wrong";
      case "correct": return st === "correct";
      case "starred": return isStarred(q.qid);
      default:        return true;
    }
  }

  function statusOk(q) {
    if (!filters.status.length) return true;
    return filters.status.some(function (k) { return statusIs(q, k); });
  }

  /* ---------- search ---------- */

  /* markup to words: block-level tags end a word and inline ones do not, so
     two paragraphs stay two words and a bolded half of one word stays one */
  function plainText(html) {
    return (html || "")
      .replace(/<\/?(?:p|div|li|ol|ul|br|tr|td|th|h[1-6]|blockquote|table)\b[^>]*>/gi, " ")
      .replace(/<[^>]+>/g, "")
      .replace(/&nbsp;/gi, " ")
      .replace(/&amp;/gi, "&")
      .replace(/&lt;/gi, "<")
      .replace(/&gt;/gi, ">")
      .replace(/&quot;/gi, "\"")
      .replace(/&#39;/g, "'");
  }

  /* The sixth facet. Its value is a typed query, and every word of it has to
     appear somewhere in the question - preamble, stem, options, review line -
     in any order: a stem is a long clinical vignette, and "warfarin bleeding"
     is the question people mean even when the two words sit a sentence apart.
     The notes tab searches by the same rule. The rule and the highlighter
     live in portal.js, on window.PORTAL_SEARCH, and this file keeps only what
     is the bank's own: which text a question is searched by, and where the
     marks may go.

     The answer and its explanation are never read. A search for "metformin"
     that surfaced every question whose ANSWER is metformin would hand out the
     key before the question was attempted. */
  function searchText(q) {
    var parts = [q.stem];
    /* a preamble is usually {title, html}; two in the banks are bare strings */
    if (q.preamble && typeof q.preamble === "object") parts.push(q.preamble.title, q.preamble.html);
    else parts.push(q.preamble);
    (q.options || []).forEach(function (o) { parts.push(o.html); });
    /* a pairing's choices are its options, they just live in pairs.items */
    if (q.pairs && q.pairs.items) {
      q.pairs.items.forEach(function (it) { parts.push(it.left, it.right); });
    }
    /* the review line as the reader sees it: the week, the lecture the set
       named, and any lecture review_lectures.py resolved the question to */
    parts.push(q.weekLabel, q.lecture);
    (q.review || []).forEach(function (r) { parts.push(r.t); });
    return plainText(parts.join(" ")).toLowerCase();
  }

  /* Looked up when called rather than at load, because portal.js is the
     later script tag on the page. */
  function search() { return window.PORTAL_SEARCH; }

  function searchWords(query) {
    return search() ? search().words(query) : [];
  }

  function searchHit(hay, words) {
    return search() ? search().hit(hay, words) : true;
  }

  /* The pure form: one question, one query, no state. It is what the test
     script exercises. */
  function searchMatches(q, query) {
    return searchHit(searchText(q), searchWords(query));
  }

  /* The haystack is stripped once per question rather than on every keystroke
     - the facet counts and the stream each ask about every question per pass */
  var SEARCH_HAY = Object.create(null);

  /* the word list is split once per query, not once per question per pass */
  var SEARCH_WORDS = { query: null, words: [] };

  function currentWords() {
    if (SEARCH_WORDS.query !== filters.search) {
      SEARCH_WORDS = { query: filters.search, words: searchWords(filters.search) };
    }
    return SEARCH_WORDS.words;
  }

  function searchOn() { return currentWords().length > 0; }

  function searchOk(q) {
    var words = currentWords();
    if (!words.length) return true;
    var hay = SEARCH_HAY[q.qid];
    if (hay === undefined) hay = SEARCH_HAY[q.qid] = searchText(q);
    return searchHit(hay, words);
  }

  function setSearch(v) {
    var next = v || "";
    if (next === filters.search) return;
    filters.search = next;
    syncSearchBox();
    afterFilterChange();
  }

  /* the box, the chip and the Clear-all button can each change the query, so
     the input is made to agree with the facet rather than the other way round */
  function syncSearchBox() {
    var box = byId("bank-q"), clear = byId("bank-q-clear");
    if (box && box.value !== filters.search) box.value = filters.search;
    if (clear) clear.hidden = !searchOn();
  }

  /* ---------- search highlights ---------- */

  /* portal.js's walker paints the marks, by its painting rule: the floor a
     word must reach to be painted and the budget one pass stops at are its.
     Marks go into the parts of the question the search read - preamble,
     stem, options - and never into the answer, which it did not. */
  var SEARCH_MARKED = [];

  function unmarkSearch() {
    if (search()) search().unmark(SEARCH_MARKED);
    SEARCH_MARKED = [];
  }

  function paintSearchMarks(live) {
    var s = search();
    unmarkSearch();
    if (!s) return;
    var words = s.paintWords(currentWords());
    if (!words.length) return;
    var budget = s.MARK_BUDGET;
    QUESTIONS.forEach(function (q) {
      if (budget <= 0 || !live[q.qid]) return;
      var art = byId("q-" + q.qid);
      if (!art) return;
      var made = 0;
      [].forEach.call(art.querySelectorAll(".preamble, .stem, .opts .t"), function (part) {
        made += s.mark(part, words, budget - made);
      });
      if (made) { SEARCH_MARKED.push(art); budget -= made; }
    });
  }

  function matches(qid) {
    var q = QMAP[qid];
    return blockOk(q) && famOk(q) && weekOk(q) && tagOk(q) && statusOk(q) && searchOk(q);
  }

  // qids currently passing the filters that actually have something to clear
  function shownWithProgress() {
    return QUESTIONS.filter(function (q) { return progress[q.qid] && matches(q.qid); })
                    .map(function (q) { return q.qid; });
  }

  /* The qids in play, in bank order. In a sat block that is the block; in a
     tutor stream it is whatever the filters match. Bank order either way -
     the draw decides WHICH questions, never what order you meet them in, so
     a block still reads week by week. */
  function inPlayIds() {
    if (MODE === "test" && TEST.ids) {
      var set = Object.create(null);
      TEST.ids.forEach(function (id) { set[id] = 1; });
      return inDeckOrder(QUESTIONS.filter(function (q) { return set[q.qid]; })
                                  .map(function (q) { return q.qid; }));
    }
    return inDeckOrder(QUESTIONS.filter(function (q) { return matches(q.qid); })
                                .map(function (q) { return q.qid; }));
  }

  /* Paging is the filter trick with a narrower predicate: the stream already
     builds every question once and hides what is out of play, so one at a
     time is "hide all but one" and every other part of the engine - progress,
     stars, the keyboard steps, the resume point - carries over untouched. */
  function applyFilters() {
    var ids = inPlayIds(), live = Object.create(null);
    if (VIEW === "paged" && ids.length) {
      if (pageIdx >= ids.length) pageIdx = ids.length - 1;
      if (pageIdx < 0) pageIdx = 0;
      live[ids[pageIdx]] = 1;
    } else {
      ids.forEach(function (id) { live[id] = 1; });
    }

    var shown = 0;
    QUESTIONS.forEach(function (q) {
      var art = byId("q-" + q.qid);
      /* buildStream only renders questions whose family is declared on the
         block, so a bank carrying a family portal.py does not list yet has
         no node here. Before this guard that was a null dereference that
         took the whole questions tab down - one stray family, blank page. */
      if (!art) return;
      var ok = !!live[q.qid];
      art.hidden = !ok;
      if (ok) shown++;
    });
    // a heading survives only while a question under it is still visible
    [].forEach.call(document.querySelectorAll(".lecbar"), function (h) {
      var any = false, n = h.nextElementSibling;
      while (n && n.classList.contains("q")) {
        if (!n.hidden) { any = true; break; }
        n = n.nextElementSibling;
      }
      h.hidden = !any;
    });
    [].forEach.call(document.querySelectorAll(".weekbar"), function (h) {
      var any = false, n = h.nextElementSibling;
      while (n && !n.classList.contains("weekbar")) {
        if (n.classList.contains("q") && !n.hidden) { any = true; break; }
        n = n.nextElementSibling;
      }
      h.hidden = !any;
    });

    var narrowed = filters.status.length > 0 || filters.week.length > 0 ||
                   filters.tag.length > 0 || filters.block.length > 0 || searchOn();
    [].forEach.call(document.querySelectorAll(".family"), function (f) {
      if (filters.family.length && !isOn("family", f.dataset.family)) { f.hidden = true; return; }
      /* a coverage gap is worth showing where the stream is grouped by set,
         and means nothing in a shuffled list that is not grouped at all */
      if (f.dataset.count === "0") { f.hidden = shuffling() || !!narrowed; return; }
      f.hidden = !f.querySelector(".q:not([hidden])");
    });
    [].forEach.call(document.querySelectorAll(".fam-gap"), function (g) {
      g.hidden = shuffling() || !!narrowed;
    });
    /* after the sets, because it asks which of them are left standing */
    [].forEach.call(document.querySelectorAll(".blockgroup"), function (g) {
      g.hidden = !g.querySelector(".family:not([hidden])");
    });
    paintSearchMarks(live);
    /* the empty state belongs to the filters, not to the page you are on */
    byId("empty").hidden = ids.length > 0;
    indexVisible();
    paintPos();
    paintBar();
    paintTest();
    paintPagebar(ids);
  }

  /* Changing a filter while a block is being sat draws a new block. The
     alternative - quietly editing the block under you - would make the score
     mean nothing. */
  function afterFilterChange() {
    pageIdx = 0;
    if (MODE === "test") { redrawBlock(); return; }
    applyFilters();
  }

  function setFacet(name, keys) {
    filters[name] = keys;
    if (name === "block") writeHash();
    afterFilterChange();
  }

  /* ---------- the block in the address bar ---------- */

  /* A block page used to BE the link to a block's questions. Now the block is
     one value of one filter, so the filter has to be linkable or that address
     is lost - it is what every block page's third tab points at, and what
     someone sends when they say "these are the ones to do".

     Only the block, and only on the pooled page: the other four facets are
     things you try and drop within a session, where the block is where you
     started. replaceState rather than the hash, so dragging the filter does
     not fill the Back button with every combination passed through. */
  function readHash() {
    if (!TERM) return;
    var m = /(?:^|[#&])block=([a-z0-9_,-]+)/i.exec(window.location.hash || "");
    if (!m) return;
    var want = m[1].split(",").filter(function (k) {
      return BLOCK_NAME[k] !== undefined;
    });
    if (want.length) filters.block = want;
  }

  function writeHash() {
    if (!TERM || !window.history || !window.history.replaceState) return;
    var h = filters.block.length ? "#block=" + filters.block.join(",") : "";
    try {
      window.history.replaceState(null, "",
        window.location.pathname + window.location.search + h);
    } catch (e) { /* a file:// page refuses this; the filter still works */ }
  }

  function clearFilters() {
    filters.block = [];
    filters.family = [];
    filters.week = [];
    filters.tag = [];
    filters.status = [];
    filters.search = "";
    syncSearchBox();
  }

  /* ---------- order ---------- */

  /* Fisher-Yates, in place. Sorting on Math.random() is the usual shortcut and
     it is not a uniform shuffle; with 611 questions that shows. */
  function shuffleInto(list) {
    for (var i = list.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1)), t = list[i];
      list[i] = list[j]; list[j] = t;
    }
    return list;
  }

  /* One deck for the whole bank, not one per filter. Drawing a fresh order
     every time the filters move would reshuffle the questions under someone
     who only wanted to drop a week, and in one-at-a-time that means losing
     your place. The deck changes when you ask it to and at no other time. */
  function reshuffle() {
    var deck = shuffleInto(QUESTIONS.map(function (q) { return q.qid; }));
    SHUFFLE = Object.create(null);
    deck.forEach(function (qid, i) { SHUFFLE[qid] = i; });
  }

  function inDeckOrder(ids) {
    if (!shuffling()) return ids;
    return ids.slice().sort(function (a, b) { return SHUFFLE[a] - SHUFFLE[b]; });
  }

  /* One at a time needs nothing here - it shows whichever card inPlayIds hands
     it. The continuous stream does: its cards are built inside their family,
     week and lecture headings, so a shuffled stream cannot be made by hiding
     things, the cards have to move. They move into one flat container and come
     back by re-appending each section's children in the order they were built,
     which is exact and cheaper than rebuilding 611 cards. */
  function applyStreamOrder(force) {
    var flat = byId("shuffled");
    if (!flat) return;                 /* a page cached from before this shipped */
    var want = shuffling(), on = flat.dataset.on === "1";
    if (want === on && !force) return;

    if (want) {
      var frag = document.createDocumentFragment();
      QUESTIONS.slice().sort(function (a, b) {
        return SHUFFLE[a.qid] - SHUFFLE[b.qid];
      }).forEach(function (q) {
        var art = byId("q-" + q.qid);
        if (art) frag.appendChild(art);
      });
      flat.appendChild(frag);
      flat.hidden = false;
      flat.dataset.on = "1";
    } else if (on) {
      HOME.forEach(function (h) {
        h.kids.forEach(function (n) { h.sec.appendChild(n); });
      });
      flat.hidden = true;
      flat.dataset.on = "";
    }
    if (byId("stream")) byId("stream").dataset.order = want ? "shuffle" : "bank";
  }

  /* Picking Shuffled while already shuffled deals again - the segment is the
     only place to ask for a new order, and wanting another one is the whole
     reason to press it twice. */
  function setOrder(o) {
    if (o !== "bank" && o !== "shuffle") return;
    if (o === ORDER && o === "bank") return;
    ORDER = o;
    if (o === "shuffle") reshuffle();
    applyStreamOrder(true);
    pageIdx = 0;
    syncSegs();
    /* not afterFilterChange: the order a sat block is presented in is not a
       different block, so changing it must not redraw one */
    applyFilters();
    toTop();
  }

  /* ---------- view + mode ---------- */

  function syncSegs() {
    [].forEach.call(document.querySelectorAll("#view-seg button"), function (b) {
      b.setAttribute("aria-pressed", b.dataset.view === VIEW ? "true" : "false");
    });
    [].forEach.call(document.querySelectorAll("#order-seg button"), function (b) {
      b.setAttribute("aria-pressed", b.dataset.order === ORDER ? "true" : "false");
    });
    [].forEach.call(document.querySelectorAll("#mode-seg button"), function (b) {
      b.setAttribute("aria-pressed", b.dataset.mode === MODE ? "true" : "false");
    });
  }

  function setView(v) {
    if ((v !== "stream" && v !== "paged") || VIEW === v) return;
    VIEW = v;
    if (v === "paged") {
      /* land on the question you were already looking at rather than the top
         of the bank - the anchor is what the resume point is built on */
      var ids = inPlayIds(), at = ANCHOR ? ids.indexOf(ANCHOR) : -1;
      pageIdx = at === -1 ? 0 : at;
    }
    syncSegs();
    applyFilters();
    if (v === "paged") toTop();
  }

  function setMode(m) {
    if ((m !== "tutor" && m !== "test") || MODE === m) return;
    MODE = m;
    if (m === "test") {
      drawTest();
    } else {
      TEST.ids = null;
      TEST.picks = Object.create(null);
      TEST.submitted = false;
      TEST.deadline = null;
      stopTick();
      pageIdx = 0;
    }
    syncSegs();
    applyFilters();
    /* reveal is a global condition, so every card has to be repainted */
    QUESTIONS.forEach(function (q) { paintQuestion(q.qid); });
    toTop();
  }

  /* ---------- the sat block ---------- */

  function drawTest() {
    var pool = QUESTIONS.filter(function (q) {
      return matches(q.qid) && gradable(q);
    }).map(function (q) { return q.qid; });

    /* Drawn in bank order, a block would be the same block every time, and the
       first twenty questions of week 1 are not a rehearsal. This picks WHICH
       questions; the Order segment decides what order they arrive in. */
    shuffleInto(pool);
    TEST.poolN = pool.length;
    TEST.asked = TEST.size;
    TEST.ids = pool.slice(0, Math.min(TEST.size, pool.length));
    TEST.picks = Object.create(null);
    TEST.submitted = false;
    TEST.deadline = TEST.limit ? Date.now() + TEST.limit * 60000 : null;
    pageIdx = 0;
  }

  function submitTest() {
    if (!TEST.ids || TEST.submitted) return;
    /* flipped before the writes so persist() paints a revealed card, not a
       staged one */
    TEST.submitted = true;
    TEST.deadline = null;
    stopTick();
    TEST.ids.forEach(function (qid) {
      var q = QMAP[qid], picked = testChosen(qid);
      if (!picked.length) return;         /* left blank stays left blank */
      var correct, chosen;
      if (q.kind === "pairing") {
        correct = pairIsRight(q, picked);
        chosen = picked.join("|");
      } else {
        correct = picked.slice().sort().join("+") === q.correct.slice().sort().join("+");
        chosen = picked.join("+");
      }
      persist(qid, {
        status: correct ? "correct" : "wrong",
        /* tagged, so "what is my accuracy when nothing tells me I am right"
           stays an answerable question later */
        attempt: { ts: Date.now(), chosen: chosen, correct: correct, mode: "test" }
      });
    });
    pageIdx = 0;
    applyFilters();
    TEST.ids.forEach(paintQuestion);
    toTop();
  }

  /* Repaint only the cards that changed hands. This runs on every keystroke
     in the block-size field, and a blanket repaint of a 581-question bank
     there is a visible stutter for no gain. */
  function redrawBlock() {
    var before = TEST.ids || [];
    drawTest();
    applyFilters();
    var touched = Object.create(null);
    before.concat(TEST.ids || []).forEach(function (id) { touched[id] = 1; });
    Object.keys(touched).forEach(paintQuestion);
  }

  function clearResult() {
    var r = byId("tb-result");
    if (r && r.parentNode) r.parentNode.removeChild(r);
  }

  /* The one number a sat block exists to produce, and the grouping that a
     tutor stream structurally cannot show you: which SOURCE you are losing
     marks to, visible only because forty were marked at once. */
  function paintResult() {
    clearResult();
    if (MODE !== "test" || !TEST.submitted || !TEST.ids) return;
    var n = TEST.ids.length, right = 0, blank = 0, missed = [];
    TEST.ids.forEach(function (qid) {
      if (!testChosen(qid).length) { blank++; return; }
      if (stateOf(qid) === "correct") right++; else missed.push(QMAP[qid]);
    });

    var box = el("div", "tb-result");
    box.id = "tb-result";
    box.appendChild(el("h3", null, "Block submitted"));
    box.appendChild(el("div", "big", right + " / " + n));
    box.appendChild(el("p", null,
      (n ? Math.round(right / n * 100) : 0) + "% on this block" +
      (blank ? " \u00b7 " + blank + " left blank" : "") + "."));

    /* The grouping a tutor stream structurally cannot show you, and on a
       pooled paper the block is the cut that changes what you revise next -
       "eleven of your fourteen misses were neurology" is the whole reason to
       sit one paper across the term instead of five papers one at a time. */
    function breakdown(label, keyOf) {
      var by = Object.create(null), order = [];
      missed.forEach(function (q) {
        var k = keyOf(q);
        if (by[k] === undefined) { by[k] = 0; order.push(k); }
        by[k]++;
      });
      if (label) box.appendChild(el("p", "tb-cut", label));
      var ul = document.createElement("ul");
      order.forEach(function (k) {
        ul.appendChild(el("li", null, by[k] + " missed from " + k));
      });
      box.appendChild(ul);
    }

    if (missed.length) {
      if (TERM) {
        breakdown("By block", function (q) { return BLOCK_NAME[q.block] || q.block; });
        breakdown("By question set", function (q) { return q.sourceLabel; });
      } else {
        breakdown(null, function (q) { return q.sourceLabel; });
      }
    }
    var stream = byId("stream");
    stream.parentNode.insertBefore(box, stream);
  }

  function paintTest() {
    var shell = byId("panel-questions");
    if (shell) {
      shell.dataset.view = VIEW;
      shell.dataset.mode = MODE;
      shell.dataset.submitted = TEST.submitted ? "true" : "false";
    }
    var bar = byId("testbar");
    if (!bar) return;
    bar.textContent = "";
    if (MODE !== "test") { bar.hidden = true; clearResult(); return; }
    bar.hidden = false;

    var ids = TEST.ids || [];
    var answered = ids.filter(function (id) { return testChosen(id).length; }).length;

    var head = el("span");
    head.appendChild(el("b", null, "Block of " + ids.length));
    head.appendChild(document.createTextNode(TEST.submitted
      ? " \u00b7 submitted \u00b7 reviewing"
      : " \u00b7 " + answered + " of " + ids.length +
        " answered \u00b7 no feedback until you submit"));
    bar.appendChild(head);

    stopTick();
    if (!TEST.submitted && TEST.limit && TEST.deadline) {
      var cEl = el("span", "tb-clock", clockText(TEST.deadline - Date.now()));
      bar.appendChild(cEl);
      TICK = setInterval(function () {
        if (!TEST.deadline || TEST.submitted) { stopTick(); return; }
        var left = TEST.deadline - Date.now();
        cEl.textContent = clockText(left);
        cEl.dataset.low = left < 60000 ? "1" : "";
        /* Time up marks the paper where it stands. Blanks stay blank, which
           is what an unanswered question on a real paper is. */
        if (left <= 0) { stopTick(); submitTest(); }
      }, 1000);
    }

    if (!TEST.submitted) {
      /* Typed, not chosen from a list, for the same reason the block length is:
         the list offered eight lengths and the paper you are actually sitting
         is 100 minutes or 25. Empty means no limit, which is the default and
         has to stay reachable by clearing the field. */
      var tf = el("div", "tb-time");
      var tlab = document.createElement("label");
      tlab.setAttribute("for", "tb-limit");
      tlab.textContent = "Time";
      var tin = document.createElement("input");
      tin.type = "number";
      tin.id = "tb-limit";
      tin.min = "1";
      tin.step = "1";
      tin.placeholder = "No limit";
      tin.value = TEST.limit ? String(TEST.limit) : "";
      tin.addEventListener("input", function () {
        var v = parseInt(tin.value, 10);
        TEST.limit = (isNaN(v) || v < 1) ? 0 : v;
        /* the clock restarts from now rather than back-dating itself onto a
           block you are already part-way through */
        TEST.deadline = TEST.limit ? Date.now() + TEST.limit * 60000 : null;
        paintTest();
        /* repainting the bar rebuilds this field, so the caret has to be put
           back or it jumps out on every keystroke */
        var back = byId("tb-limit");
        if (back) {
          back.focus();
          try { back.setSelectionRange(back.value.length, back.value.length); }
          catch (e) { /* number inputs refuse this in some browsers */ }
        }
      });
      tf.appendChild(tlab);
      tf.appendChild(tin);
      tf.appendChild(el("span", "tb-unit", "min"));
      bar.appendChild(tf);
    }

    var sf = el("div", "tb-size");
    var lab = document.createElement("label");
    lab.setAttribute("for", "tb-count");
    lab.textContent = "How many?";
    var inp = document.createElement("input");
    inp.type = "number";
    inp.id = "tb-count";
    inp.min = "1";
    inp.step = "1";
    inp.value = String(TEST.size);
    /* repainting the bar rebuilds this field, so the caret has to be put back
       or it jumps out on every keystroke */
    inp.addEventListener("input", function () {
      var v = parseInt(inp.value, 10);
      if (isNaN(v) || v < 1) return;
      TEST.size = v;
      redrawBlock();
      var back = byId("tb-count");
      if (back) {
        back.focus();
        try { back.setSelectionRange(back.value.length, back.value.length); }
        catch (e) { /* number inputs refuse this in some browsers */ }
      }
    });
    sf.appendChild(lab);
    sf.appendChild(inp);
    bar.appendChild(sf);

    var btn = el("button", "tb-btn", TEST.submitted ? "New block" : "Submit block");
    btn.type = "button";
    btn.addEventListener("click", function () {
      if (TEST.submitted) { redrawBlock(); toTop(); } else submitTest();
    });
    bar.appendChild(btn);

    /* A block shrunk to fit the pool says so, here, beside the count. Clamping
       in silence is indistinguishable from a control that does nothing. */
    if (TEST.asked > ids.length) {
      bar.appendChild(el("span", "tb-note",
        "You asked for " + TEST.asked + ". These filters match " + TEST.poolN +
        " auto-markable question" + (TEST.poolN === 1 ? "" : "s") +
        ", so the block is " + ids.length + ". Widen the filters for a longer one."));
    }
    paintResult();
  }

  function paintPagebar(ids) {
    var bar = byId("pagebar");
    if (!bar) return;
    bar.textContent = "";
    if (VIEW !== "paged" || !ids.length) { bar.hidden = true; return; }
    bar.hidden = false;
    /* the position bar and the pager say the same thing; one of them goes */
    var pb = byId("posbar");
    if (pb) pb.hidden = true;

    var prev = el("button", "pg-btn", "\u2190 Previous");
    prev.type = "button";
    prev.disabled = pageIdx === 0;
    prev.addEventListener("click", function () { pageIdx--; applyFilters(); showPage(); });
    bar.appendChild(prev);

    bar.appendChild(el("span", "pg-pos", (pageIdx + 1) + " of " + ids.length));

    var atEnd = pageIdx === ids.length - 1;
    if (MODE === "test" && !TEST.submitted && atEnd) {
      var sub = el("button", "pg-btn primary", "Submit block");
      sub.type = "button";
      sub.addEventListener("click", submitTest);
      bar.appendChild(sub);
    } else {
      var next = el("button", "pg-btn", "Next \u2192");
      next.type = "button";
      next.disabled = atEnd;
      next.addEventListener("click", function () { pageIdx++; applyFilters(); showPage(); });
      bar.appendChild(next);
    }
  }

  /* ---------- where you are in the stream ---------- */

  /* The stream runs from the first question to the last in one scroll - 279 of
     them in endo - so the bar pinned to the bottom of the viewport is the only
     thing that says where you are, and the only way back to the question you
     were on before you scrolled off to check something.

     Position is read from an IntersectionObserver rather than measured on
     scroll. Asking this many nodes where they are on every scroll event costs
     frames, and a hidden question is not rendered and so never intersects,
     which means the filters fall out of it for free. */

  var VISIBLE = [];                  // qids passing the filters, in stream order
  var VINDEX = Object.create(null);  // qid -> its place in VISIBLE
  var inView = Object.create(null);  // qids currently crossing the sight line
  var CURRENT = null;                // the question at the top of the viewport
  var ANCHOR = null;                 // the question to offer a way back to
  var RESUMING = false;              // showing the reopen offer, not the marker
  var posReady = false;
  var scrollQueued = false;

  /* read off the DOM, not off QUESTIONS: the stream is built family by family,
     so its order is not the order the JSON happens to arrive in */
  function indexVisible() {
    VISIBLE = [];
    VINDEX = Object.create(null);
    [].forEach.call(document.querySelectorAll("#stream .q"), function (art) {
      if (art.hidden) return;
      VINDEX[art.dataset.qid] = VISIBLE.length;
      VISIBLE.push(art.dataset.qid);
    });
  }

  function topmostInView() {
    var best = null, bestAt = Infinity;
    Object.keys(inView).forEach(function (qid) {
      var i = VINDEX[qid];
      if (i !== undefined && i < bestAt) { bestAt = i; best = qid; }
    });
    return best;
  }

  function onIntersect(entries) {
    entries.forEach(function (e) {
      var qid = e.target.dataset.qid;
      if (e.isIntersecting) inView[qid] = true;
      else delete inView[qid];
    });
    var top = topmostInView();
    if (top) CURRENT = top;   // between two questions, the last one still holds
    paintPos();
  }

  /* the stream runs to hundreds of questions, so the bar owes you the way
     out of it as well as the way around it. It hides itself once you land. */
  function scrollToY(y) {
    var still = window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    try { window.scrollTo({ top: y, behavior: still ? "auto" : "smooth" }); }
    catch (e) { window.scrollTo(0, y); }
  }

  function toTop() { scrollToY(0); }

  /* Paging used to call toTop, which threw the whole document to 0 on every
     single Next - up past the masthead, the tabs, the how-to and the toolbar.
     In this view the stream is one question tall, so there was never anything
     up there worth being sent to, and the jump was the loudest thing on the
     page.

     Two changes. It scrolls to the QUESTION - taking the week and lecture
     headings above it when they are showing, since those are its label - and
     it does nothing at all when the question's top is already on screen,
     which after a short stem is most of the time. Answering a question and
     pressing Next should leave the page where it is. */
  function showPage() {
    var ids = inPlayIds(), art = ids.length ? byId("q-" + ids[pageIdx]) : null;
    if (!art) return;

    var target = art, p = art.previousElementSibling;
    while (p && !p.hidden &&
           (p.classList.contains("lecbar") || p.classList.contains("weekbar"))) {
      target = p;
      p = p.previousElementSibling;
    }

    var r = target.getBoundingClientRect();
    if (r.top >= 0 && r.top <= window.innerHeight * 0.5) return;
    scrollToY(r.top + window.pageYOffset - 16);
  }

  function goTo(qid) {
    var art = byId("q-" + qid);
    if (!art) return;
    scrollToY(art.getBoundingClientRect().top + window.pageYOffset - 16);
    CURRENT = qid;
    paintPos();
  }

  function step(delta) {
    if (!VISIBLE.length) return;
    var i = (CURRENT && VINDEX[CURRENT] !== undefined) ? VINDEX[CURRENT] : 0;
    var j = i + delta;
    if (j < 0 || j >= VISIBLE.length) return;
    goTo(VISIBLE[j]);
  }

  function setAnchor(qid) {
    ANCHOR = qid;
    RESUMING = false;
    paintPos();
  }

  /* lastTs has been written on every answer all along and read by nothing, so
     the question you last touched costs no new storage and already rides along
     in the JSON backup */
  function resumePoint() {
    var best = null, bestTs = 0;
    Object.keys(progress).forEach(function (qid) {
      if (QMAP[qid] && progress[qid].lastTs > bestTs) {
        bestTs = progress[qid].lastTs;
        best = qid;
      }
    });
    return best;
  }

  function paintMark(at) {
    var mk = byId("pb-mark");
    if (RESUMING && ANCHOR && QMAP[ANCHOR]) {
      mk.hidden = false;
      mk.textContent = "Resume at Q" + QMAP[ANCHOR].num +
                       " \u00b7 " + QMAP[ANCHOR].lecture;
      return;
    }
    // no anchor, filtered away, or near enough that a button would be noise
    if (!ANCHOR || VINDEX[ANCHOR] === undefined || at === null) {
      mk.hidden = true;
      return;
    }
    var away = VINDEX[ANCHOR] - at;
    if (Math.abs(away) < 2) { mk.hidden = true; return; }
    mk.hidden = false;
    mk.textContent = (away < 0 ? "\u2191" : "\u2193") +
                     " back to Q" + QMAP[ANCHOR].num;
  }

  function paintPos() {
    if (!posReady) return;
    var bar = byId("posbar");
    /* out of the way until you are actually into the stream, except when there
       is a spot to reopen at - that offer has to be visible from the top */
    if (!VISIBLE.length || !(RESUMING || window.pageYOffset > 400)) {
      bar.hidden = true;
      return;
    }
    bar.hidden = false;

    if (!CURRENT || VINDEX[CURRENT] === undefined) {
      CURRENT = topmostInView() || VISIBLE[0];
    }
    var at = VINDEX[CURRENT] === undefined ? null : VINDEX[CURRENT];
    var q = QMAP[CURRENT];

    byId("pb-where").textContent = q ? (q.weekLabel + " \u00b7 " + q.lecture) : "";
    byId("pb-count").textContent = (at === null ? "\u2013" : String(at + 1)) +
      " / " + VISIBLE.length +
      (anyFilter() ? " shown" : "");
    byId("pb-prev").disabled = at === null || at === 0;
    byId("pb-next").disabled = at === null || at === VISIBLE.length - 1;
    paintMark(at);
  }

  function onScroll() {
    if (scrollQueued) return;
    scrollQueued = true;
    window.requestAnimationFrame(function () {
      scrollQueued = false;
      // scrolling in is answer enough: the offer gives way to the live marker
      if (RESUMING && window.pageYOffset > 240) RESUMING = false;
      paintPos();
    });
  }

  function onKey(e) {
    if (document.querySelector("dialog[open]")) return;   // a dialog has the keyboard
    /* "/" jumps to the search box; portal.js holds the guards, and it is
       asked first because it takes shift where the letters below do not */
    if (search() && search().jumpKey(e, byId("bank-q"), "panel-questions")) return;
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (byId("panel-questions").hidden) return;
    var t = e.target;
    if (t && (t.isContentEditable ||
              /^(input|textarea|select)$/i.test(t.tagName || ""))) return;
    if (e.shiftKey) return;
    if (e.key === "j") { e.preventDefault(); step(1); }
    else if (e.key === "k") { e.preventDefault(); step(-1); }
    else if (e.key === "b" && ANCHOR) {
      e.preventDefault();
      RESUMING = false;
      goTo(ANCHOR);
    }
  }

  /* a browser without IntersectionObserver gets the stream exactly as it was,
     which is better than a bar that cannot say where it is */
  function initPos() {
    if (!window.IntersectionObserver) return;
    posReady = true;

    // the sight line is the top fifth of the viewport
    var obs = new window.IntersectionObserver(onIntersect,
      { rootMargin: "0px 0px -80% 0px" });
    [].forEach.call(document.querySelectorAll("#stream .q"), function (art) {
      obs.observe(art);
    });

    byId("pb-top").addEventListener("click", toTop);
    byId("pb-prev").addEventListener("click", function () { step(-1); });
    byId("pb-next").addEventListener("click", function () { step(1); });
    byId("pb-mark").addEventListener("click", function () {
      if (!ANCHOR) return;
      RESUMING = false;
      goTo(ANCHOR);
    });
    window.addEventListener("scroll", onScroll, { passive: true });
    document.addEventListener("keydown", onKey);

    var r = resumePoint();
    if (r && matches(r)) { ANCHOR = r; RESUMING = true; }
    paintPos();
  }

  /* ---------- rail ---------- */

  var STATUS_DEFS = [
    { k: "all", label: "All" },
    { k: "unseen", label: "Unseen" },
    { k: "wrong", label: "Wrong", cls: "wrongish" },
    { k: "correct", label: "Correct" },
    { k: "starred", label: "Starred", cls: "starish" }
  ];

  /* Weeks come off the questions rather than off BLOCK.weeks: that is a
     display string ("1–3"), and a block can carry off-curriculum questions
     that belong to no week at all. Numbers, not labels - the same week is
     labelled differently by each family, so the labels would split it. */
  function weekKey(q) { return q.week === null ? "off" : String(q.week); }

  function weekDefs() {
    var n = Object.create(null), order = [];
    QUESTIONS.forEach(function (q) {
      var k = weekKey(q);
      if (n[k] === undefined) { n[k] = 0; order.push(k); }
      n[k]++;
    });
    order.sort(function (a, b) {
      if (a === "off") return 1;
      if (b === "off") return -1;
      return Number(a) - Number(b);
    });
    var defs = [{ k: "all", label: "All", n: QUESTIONS.length }];
    order.forEach(function (k) {
      defs.push({ k: k, label: k === "off" ? "Off-curriculum" : "Week " + k, n: n[k] });
    });
    return defs;
  }

  /* Spelled out here rather than derived from the tag, so a chip can be worded
     independently of the tag every question carries. An unknown tag still
     renders, capitalised. */
  var TAG_NAMES = { anatomy: "Anatomy" };

  function tagTitle(k) {
    return TAG_NAMES[k] || (k.charAt(0).toUpperCase() + k.slice(1));
  }

  /* Empty for a block with nothing tagged, which is what hides the group:
     endo has the anatomy strand, the other four have nothing yet. */
  function tagDefs() {
    var n = Object.create(null), order = [];
    QUESTIONS.forEach(function (q) {
      tagsOf(q).forEach(function (k) {
        if (n[k] === undefined) { n[k] = 0; order.push(k); }
        n[k]++;
      });
    });
    if (!order.length) return [];
    order.sort();
    var defs = [{ k: "all", label: "All", n: QUESTIONS.length }];
    order.forEach(function (k) { defs.push({ k: k, label: tagTitle(k), n: n[k] }); });
    return defs;
  }

  /* Every tally below skips its own group and applies the other three, in one
     pass. Before this, the numbers went wrong the moment a second filter was
     on: picking Wrong still offered "Week 1 195" when only a handful of those
     were wrong, and the week counts were written once at build and never
     repainted at all. */
  function facetCounts() {
    var blk = Object.create(null), fam = Object.create(null);
    var week = Object.create(null), tag = Object.create(null);
    var status = { all: 0, unseen: 0, wrong: 0, correct: 0, starred: 0 };
    var blkAll = 0, famAll = 0, weekAll = 0, tagAll = 0, shown = 0;
    QUESTIONS.forEach(function (q) {
      var b = blockOk(q), f = famOk(q), w = weekOk(q), t = tagOk(q);
      var sOk = statusOk(q), wk, st;
      /* the search narrows every count the same way the other facets do,
         and it has no dropdown of its own to count for */
      if (!searchOk(q)) return;
      if (f && w && t && sOk) {
        blk[q.block] = (blk[q.block] || 0) + 1;
        blkAll++;
      }
      if (b && w && t && sOk) {
        fam[q.family] = (fam[q.family] || 0) + 1;
        famAll++;
      }
      if (b && f && t && sOk) {
        wk = weekKey(q);
        week[wk] = (week[wk] || 0) + 1;
        weekAll++;
      }
      if (b && f && w && sOk) {
        /* a question with two tags counts under each, so these never sum to
           tagAll - the same way the week chips are a partition and these are
           not */
        tagsOf(q).forEach(function (k) { tag[k] = (tag[k] || 0) + 1; });
        tagAll++;
      }
      if (b && f && w && t) {
        st = stateOf(q.qid);
        status.all++;
        if (st === "unseen") status.unseen++;
        else if (st === "wrong") status.wrong++;
        else status.correct++;
        if (isStarred(q.qid)) status.starred++;
      }
      if (b && f && w && t && sOk) shown++;
    });
    return {
      blk: blk, blkAll: blkAll,
      fam: fam, famAll: famAll,
      week: week, weekAll: weekAll,
      tag: tag, tagAll: tagAll,
      status: status, shown: shown
    };
  }

  /* Four independent filters and, without this, nothing anywhere saying which
     of them emptied the stream - the answer had to be hunted across all four
     groups. It matters more now than it did in the rail: a closed dropdown
     hides its count, so this row is the only thing standing between you and a
     filtered view that looks unfiltered. */
  function paintApplied(shown) {
    var box = byId("applied");
    if (!box) return;          // a page cached from before this shipped

    var live = [];

    /* One chip per PICKED value, not one per group. Two weeks means two
       chips, each of which drops only itself - the collapsed button can only
       say "2 weeks", so this row is where the second week is named and where
       it can be taken back off without reopening anything. */
    function chips(name, labelFor) {
      filters[name].forEach(function (k) {
        live.push({
          label: labelFor(k),
          clear: function () {
            filters[name] = filters[name].filter(function (x) { return x !== k; });
          }
        });
      });
    }

    chips("block", function (k) { return BLOCK_NAME[k] || k; });
    chips("family", function (k) { return FAM_NAME[k] || k; });
    chips("week", function (k) { return WEEK_LABEL[k] || ("Week " + k); });
    chips("tag", function (k) { return TAG_LABEL[k] || k; });
    chips("status", function (k) { return STATUS_LABEL[k] || k; });
    if (searchOn()) {
      live.push({
        label: "\u201c" + filters.search.replace(/^\s+|\s+$/g, "") + "\u201d",
        clear: function () { filters.search = ""; syncSearchBox(); }
      });
    }

    box.hidden = live.length === 0;
    box.textContent = "";
    if (!live.length) return;

    var head = el("div", "applied-h");
    head.appendChild(el("span", null, "Active filters"));
    head.appendChild(el("span", "res", shown + (shown === 1 ? " question" : " questions")));
    box.appendChild(head);

    var list = el("div", "applied-list");
    live.forEach(function (item) {
      var b = el("button", "fchip");
      b.type = "button";
      b.setAttribute("aria-label", "Remove the " + item.label + " filter");
      b.appendChild(el("span", null, item.label));
      b.appendChild(el("span", "x", "\u00d7"));
      b.addEventListener("click", function () { item.clear(); applyFilters(); });
      list.appendChild(b);
    });

    var ca = el("button", "clear-all", "Clear all");
    ca.type = "button";
    ca.addEventListener("click", function () {
      clearFilters();
      writeHash();
      applyFilters();
    });
    list.appendChild(ca);

    box.appendChild(list);
  }

  /* An option worth zero is disabled rather than left live, which is what the
     family rows have always done and the chips never did. The one exception is
     an option already ticked: disabling that would trap you in it.

     The collapsed button prints c.shown for every facet, and that is not a
     shortcut - "the questions passing the other three groups AND this one" IS
     the whole filtered stream, whichever facet you ask from. Summing the
     ticked options would be wrong the moment two of them overlap, which is
     exactly what Wrong + Starred does. */
  function paintBar() {
    var c = facetCounts();

    paintMulti("f-block", c.shown, c.blkAll,
               function (k) { return c.blk[k] || 0; }, null);
    paintMulti("f-family", c.shown, c.famAll,
               function (k) { return c.fam[k] || 0; },
               function (k) { return FAM_TOTAL[k] === 0; });
    paintMulti("f-week", c.shown, c.weekAll,
               function (k) { return c.week[k] || 0; }, null);
    paintMulti("f-tag", c.shown, c.tagAll,
               function (k) { return c.tag[k] || 0; }, null);
    paintMulti("f-status", c.shown, c.status.all,
               function (k) { return c.status[k] || 0; }, null);

    paintApplied(c.shown);
    if (RESET_SHOWN_IDLE) RESET_SHOWN_IDLE();
  }

  function paintStats() {
    var attempted = 0, wrong = 0, starred = 0, ok = 0;
    QUESTIONS.forEach(function (q) {
      var st = stateOf(q.qid);
      if (st !== "unseen") {
        attempted++;
        if (st === "wrong") wrong++; else ok++;
      }
      if (isStarred(q.qid)) starred++;
    });
    byId("sc-done").textContent = attempted;
    byId("sc-first").textContent = attempted ? Math.round(ok / attempted * 100) + "%" : "–";
    byId("sc-wrong").textContent = wrong;
    byId("sc-star").textContent = starred;
    paintBar();
  }

  /* ---------- boot ---------- */

  /* the eyebrow is written by pom2.js instead - it has to be right even when
     the page opens on the notes tab and none of this has run */
  function buildMasthead() {
    byId("sc-of").textContent = "/" + QUESTIONS.length;
  }

  /* ---------- the facet dropdowns ---------- */

  /* One control per facet, options built once, their live counts rewritten by
     paintBar - so a count still rides on the option the way it used to ride on
     the chip, which is the one real thing a collapsed dropdown hides.

     These were <select>s until weeks 1 AND 2 turned out to be a thing people
     ask for. A native <select multiple> can do it, but it is a scrolling list
     box that wants ctrl-click and eats half the toolbar's height, so each
     facet is now a button that opens a panel of checkboxes. The button still
     reads like the select it replaces - one ticked option prints its own name
     - and only falls back to "2 weeks" when the names would not fit. The
     applied chips underneath are where they get named and dropped one at a
     time.

     Nothing ticked means everything, so the "All ..." row at the top clears
     rather than being a fifth checkbox to keep mutually exclusive. */
  var MSEL = Object.create(null);
  var OPEN_MSEL = null;
  var MSEL_DOC = false;

  function closeMsel(refocus) {
    if (!OPEN_MSEL) return;
    var m = OPEN_MSEL;
    OPEN_MSEL = null;
    m.pop.hidden = true;
    m.btn.setAttribute("aria-expanded", "false");
    if (refocus) m.btn.focus();
  }

  function toggleMsel(m) {
    if (OPEN_MSEL === m) { closeMsel(false); return; }
    closeMsel(false);
    OPEN_MSEL = m;
    m.pop.hidden = false;
    m.btn.setAttribute("aria-expanded", "true");
  }

  /* One panel open at a time; a click anywhere else, or escape, closes it.
     Registered once for the whole bar rather than once per facet. */
  function mselDocHandlers() {
    if (MSEL_DOC) return;
    MSEL_DOC = true;
    document.addEventListener("click", function (e) {
      if (OPEN_MSEL && !OPEN_MSEL.wrap.contains(e.target)) closeMsel(false);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeMsel(true);
    });
  }

  function buildMulti(id, name, noun, defs) {
    var wrap = byId(id + "-wrap"), btn = byId(id), pop = byId(id + "-pop");
    if (!wrap || !btn || !pop || !defs.length) return null;

    var m = { name: name, noun: noun, wrap: wrap, btn: btn, pop: pop,
              val: byId(id + "-val"), order: [], rows: Object.create(null),
              allLabel: defs[0].label, allRow: null, allN: null };

    var all = el("button", "msel-opt msel-any");
    all.type = "button";
    all.appendChild(el("span", "t", m.allLabel));
    m.allN = el("span", "n");
    all.appendChild(m.allN);
    all.addEventListener("click", function () { setFacet(name, []); });
    pop.appendChild(all);
    m.allRow = all;

    defs.slice(1).forEach(function (d) {
      var row = el("label", "msel-opt"), cnt = el("span", "n");
      var cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = d.k;
      row.appendChild(cb);
      row.appendChild(el("span", "t", d.label));
      row.appendChild(cnt);
      /* read back off the boxes in def order rather than pushed and spliced,
         so the picks stay in panel order however they were ticked */
      cb.addEventListener("change", function () {
        setFacet(name, m.order.filter(function (k) { return m.rows[k].cb.checked; }));
      });
      pop.appendChild(row);
      m.order.push(d.k);
      m.rows[d.k] = { cb: cb, row: row, n: cnt, label: d.label };
    });

    btn.addEventListener("click", function () { toggleMsel(m); });
    MSEL[id] = m;
    mselDocHandlers();
    return m;
  }

  function paintMulti(id, shown, allCount, countFor, gapFor) {
    var m = MSEL[id];
    if (!m) return;
    var picked = filters[m.name], only = null;

    m.order.forEach(function (k) {
      var r = m.rows[k], n = countFor(k), on = picked.indexOf(k) !== -1;
      r.cb.checked = on;
      r.cb.disabled = n === 0 && !on;
      r.n.textContent = (gapFor && gapFor(k)) ? "none" : String(n);
      r.row.dataset.on = on ? "1" : "";
      r.row.dataset.off = r.cb.disabled ? "1" : "";
      if (on && only === null) only = r.label;
    });

    m.allRow.dataset.on = picked.length ? "" : "1";
    m.allN.textContent = String(allCount);

    m.val.textContent = (picked.length === 0 ? m.allLabel
                      : picked.length === 1 ? only
                      : picked.length + " " + m.noun) + " · " + shown;
  }

  function buildBar() {
    /* Only where there is more than one block to choose between. A block page
       ships the same markup and leaves it hidden, so the two pages stay one
       template. */
    if (TERM) {
      var blkCount = {};
      QUESTIONS.forEach(function (q) { blkCount[q.block] = (blkCount[q.block] || 0) + 1; });
      var blkDefs = [{ k: "all", label: "All blocks" }];
      BLOCKS.forEach(function (b) {
        blkDefs.push({ k: b.slug, label: b.n + " \u00b7 " + b.name });
      });
      buildMulti("f-block", "block", "blocks", blkDefs);
      if (byId("f-block-wrap")) byId("f-block-wrap").hidden = false;
    }

    var famCount = {};
    QUESTIONS.forEach(function (q) { famCount[q.family] = (famCount[q.family] || 0) + 1; });

    var famDefs = [{ k: "all", label: "All question sets" }];
    FAMILIES.forEach(function (f) {
      FAM_TOTAL[f.key] = famCount[f.key] || 0;
      FAM_NAME[f.key] = f.name;
      famDefs.push({ k: f.key, label: f.name });
    });
    STATUS_DEFS.forEach(function (d) { STATUS_LABEL[d.k] = d.label; });

    buildMulti("f-family", "family", "question sets", famDefs);

    var wd = weekDefs();
    wd.forEach(function (d) { WEEK_LABEL[d.k] = d.label; });
    buildMulti("f-week", "week", "weeks", wd.map(function (d) {
      return { k: d.k, label: d.k === "all" ? "All weeks" : d.label };
    }));

    /* The topic group only earns its slot where something is tagged, so the
       dropdown ships hidden and the block's own data is what reveals it. */
    var td = tagDefs();
    if (td.length) {
      td.forEach(function (d) { TAG_LABEL[d.k] = d.label; });
      buildMulti("f-tag", "tag", "topics", td.map(function (d) {
        return { k: d.k, label: d.k === "all" ? "All topics" : d.label };
      }));
      if (byId("f-tag-wrap")) byId("f-tag-wrap").hidden = false;
    }

    buildMulti("f-status", "status", "statuses", STATUS_DEFS.map(function (d) {
      return { k: d.k, label: d.k === "all" ? "Any status" : d.label };
    }));

    /* The search box. Guarded, because a page cached from before it shipped
       has no box and must keep working. Debounced like the notes tab's: every
       keystroke re-filters the stream and re-walks the text of what is left. */
    var qbox = byId("bank-q"), QT = null;
    if (qbox) {
      qbox.addEventListener("input", function () {
        if (QT) window.clearTimeout(QT);
        QT = window.setTimeout(function () { QT = null; setSearch(qbox.value); }, 150);
      });
      qbox.addEventListener("keydown", function (e) {
        if (e.key === "Escape" || e.keyCode === 27) {
          if (QT) { window.clearTimeout(QT); QT = null; }
          setSearch("");
          return;
        }
        if (e.key === "Enter" || e.keyCode === 13) {
          /* Enter would submit if this box were ever wrapped in a form, and
             the debounce may not have run yet on a fast typist's last key */
          e.preventDefault();
          if (QT) { window.clearTimeout(QT); QT = null; }
          setSearch(qbox.value);
        }
      });
      var qclear = byId("bank-q-clear");
      if (qclear) {
        qclear.addEventListener("click", function () {
          setSearch("");
          qbox.focus();
        });
      }
      /* Whatever is already in the box counts: a query typed while the bank
         was still loading, or one a browser put back on reload. Adopted here
         and applied by start()'s own applyFilters, since the stream does not
         exist yet at this point. */
      if (qbox.value) { filters.search = qbox.value; syncSearchBox(); }
    }

    [].forEach.call(document.querySelectorAll("#view-seg button"), function (b) {
      b.addEventListener("click", function () { setView(b.dataset.view); });
    });
    [].forEach.call(document.querySelectorAll("#order-seg button"), function (b) {
      b.addEventListener("click", function () { setOrder(b.dataset.order); });
    });
    [].forEach.call(document.querySelectorAll("#mode-seg button"), function (b) {
      b.addEventListener("click", function () { setMode(b.dataset.mode); });
    });
    syncSegs();

    // reset only what is on screen right now
    var rs = byId("reset-shown"), rsArmed = false, rsTimer = null;
    function rsIdle() {
      rsArmed = false;
      rs.classList.remove("armed");
      rs.textContent = "Reset the questions shown (" + shownWithProgress().length + ")";
      rs.disabled = shownWithProgress().length === 0;
    }
    rs.addEventListener("click", function () {
      var hit = shownWithProgress();
      if (!hit.length) return;
      if (!rsArmed) {
        rsArmed = true;
        rs.classList.add("armed");
        rs.textContent = "Clear these " + hit.length + ", click to confirm";
        rsTimer = setTimeout(rsIdle, 5000);
        return;
      }
      clearTimeout(rsTimer);
      forgetMany(hit);
      rsIdle();
    });
    RESET_SHOWN_IDLE = rsIdle;

    var ra = byId("reset-all"), armed = false, timer = null;
    function raIdle() {
      armed = false;
      ra.classList.remove("armed");
      ra.textContent = "Reset all progress";
    }
    ra.addEventListener("click", function () {
      if (!armed) {
        armed = true;
        ra.classList.add("armed");
        ra.textContent = TERM
          ? "Erase every answer in all " + BLOCKS.length + " blocks, click to confirm"
          : "Erase every answer in " + BLOCK.name + ", click to confirm";
        timer = setTimeout(raIdle, 5000);
        return;
      }
      clearTimeout(timer);
      raIdle();
      forgetMany(Object.keys(progress).slice());
    });

    buildBackup();
  }

  /* localStorage is per-browser and the browser can clear it, so the progress
     has to be liftable out of here by hand. One file carries every block: the
     browser keeps all of them under the same key prefix, and a page that can
     read its own key can read its neighbours' just as well. */

  var SLUG_OK = /^[a-z0-9][a-z0-9_-]*$/i;

  function readStored(slug) {
    var raw = null;
    try { raw = window.localStorage.getItem(STORE_PREFIX + slug); }
    catch (e) { return null; }
    if (!raw) return null;
    var parsed;
    try { parsed = JSON.parse(raw); }
    catch (e) { return null; }
    return (parsed && typeof parsed === "object") ? parsed : null;
  }

  /* every block this browser has answered anything in, read off the keys rather
     than a list - the block list stays in tools/, and five stays unspecial */
  function everyBlock() {
    var out = {}, i, key, slug, data;
    try {
      for (i = 0; i < window.localStorage.length; i++) {
        key = window.localStorage.key(i);
        if (!key || key.indexOf(STORE_PREFIX) !== 0) continue;
        slug = key.slice(STORE_PREFIX.length);
        data = readStored(slug);
        if (data) out[slug] = data;
      }
    } catch (e) { /* the scan was refused; the open block still lands below */ }
    out[BLOCK.slug] = progress;   // what is in memory is at least as new
    return out;
  }

  /* a restore adds and advances, it never erases: a record older than the one
     already here loses. That is what makes restoring a stale file safe, and
     what makes it safe to restore onto a machine already part way through. */
  function newer(have, inc) {
    var a = (have && typeof have.lastTs === "number") ? have.lastTs : -1;
    var b = (inc && typeof inc.lastTs === "number") ? inc.lastTs : 0;
    return b > a;
  }

  function buildBackup() {
    byId("export-progress").addEventListener("click", function () {
      var payload = {
        store: "nsq",
        version: 2,
        exported: new Date().toISOString(),
        blocks: everyBlock()
      };
      var url = URL.createObjectURL(
        new Blob([JSON.stringify(payload, null, 1)], { type: "application/json" }));
      var a = document.createElement("a");
      a.href = url;
      /* dated, because the browser otherwise stacks these up as (1), (2) and
         there is no telling them apart from the outside */
      a.download = (BLOCK.course || "pom2").toLowerCase().replace(/[^a-z0-9]+/g, "-") + "-progress-" + new Date().toISOString().slice(0, 10) + ".json";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    });

    var file = byId("import-file");
    byId("import-progress").addEventListener("click", function () { file.click(); });
    file.addEventListener("change", function () {
      var f = file.files && file.files[0];
      if (!f) return;
      var reader = new FileReader();
      reader.onload = function () { restore(String(reader.result)); };
      reader.readAsText(f);
      file.value = "";
    });
  }

  /* a v2 file holds every block at once. A v1 file held one, named beside it -
     those still restore, they just restore the one. */
  function blocksInFile(parsed) {
    if (!parsed || typeof parsed !== "object") return null;
    if (parsed.blocks && typeof parsed.blocks === "object") return parsed.blocks;
    if (parsed.progress && typeof parsed.progress === "object") {
      var one = {};
      one[typeof parsed.block === "string" ? parsed.block : BLOCK.slug] = parsed.progress;
      return one;
    }
    return null;
  }

  function restore(text) {
    var parsed;
    try { parsed = JSON.parse(text); }
    catch (e) { note("That file is not valid JSON, so nothing was imported."); return; }

    var incoming = blocksInFile(parsed);
    if (!incoming) { note("No progress records found in that file."); return; }

    var here = 0, away = 0, elsewhere = [];

    Object.keys(incoming).forEach(function (slug) {
      var set = incoming[slug];
      if (!SLUG_OK.test(slug) || !set || typeof set !== "object") return;

      /* every block this page holds in memory is restored into memory. The
         pooled page is BLOCK.slug "term", which no record carries, and routing
         its blocks through storage instead let the save() below overwrite
         them with the empty copy still in memory. */
      if (BLOCKS.some(function (b) { return b.slug === slug; })) {
        Object.keys(set).forEach(function (qid) {
          var r = sanitize(qid, set[qid]);
          if (r && newer(progress[qid], r)) { progress[qid] = r; here++; }
        });
        return;
      }

      /* another block's records go to storage unchecked. Its own page sanitizes
         everything it loads against its own question list, so nothing
         unrecognised can reach the screen, and this page has no list to check
         them against without fetching a second question file. */
      var store = readStored(slug) || {}, n = 0;
      Object.keys(set).forEach(function (qid) {
        var inc = set[qid];
        if (!inc || typeof inc !== "object") return;
        if (newer(store[qid], inc)) { store[qid] = inc; n++; }
      });
      if (!n) return;
      try { window.localStorage.setItem(STORE_PREFIX + slug, JSON.stringify(store)); }
      catch (e) { return; }
      away += n;
      elsewhere.push(slug);
    });

    if (!here && !away) {
      note("Nothing in that file was newer than what is already here, so nothing changed.");
      return;
    }

    save();
    QUESTIONS.forEach(function (q) { paintQuestion(q.qid); });
    paintStats();
    applyFilters();

    var msg = here + " question" + (here === 1 ? "" : "s") + " restored in " + BLOCK.name + ".";
    if (away) {
      msg += " Another " + away + " in " + elsewhere.join(", ") +
             ", which appear when you open those blocks.";
    }
    note(msg);
  }

  function buildStream() {
    var stream = byId("stream"), frag = document.createDocumentFragment();
    BLOCKS.forEach(function (b) {
      /* On the pooled page each block gets a group and the question sets nest
         inside it, so the stream still reads the way the term was taught -
         block by block, week by week - instead of interleaving five blocks
         under one heading called "Pre-Clerkship Workbook". One block means no
         wrapper, and the markup is then exactly what it has always been. */
      var host = frag, gaps = [];
      if (TERM) {
        var grp = el("section", "blockgroup");
        grp.dataset.block = b.slug;
        var bh = el("div", "blockbar");
        bh.appendChild(el("p", "block-n",
          "Block " + b.n + " \u00b7 Weeks " + b.weeks));
        bh.appendChild(el("h2", null, b.name));
        grp.appendChild(bh);
        frag.appendChild(grp);
        host = grp;
      }

      FAMILIES.forEach(function (f) {
        var mine = QUESTIONS.filter(function (q) {
          return q.block === b.slug && q.family === f.key;
        });

        /* A set with nothing in it is a coverage gap, and the block page is
           where that is worth a panel of its own. Five blocks times six sets
           would put sixteen of those panels on one page, so here the gap is
           collected into one line at the foot of the block instead. */
        if (TERM && !mine.length) { gaps.push(f.name); return; }

        var sec = el("section", "family");
        sec.dataset.family = f.key;
        sec.dataset.count = String(mine.length);

        var head = el("div", "fam-head");
        head.appendChild(el("p", "fam-meta",
          mine.length ? mine.length + " questions" : "nothing transcribed yet"));
        head.appendChild(el(hTag(2), null, f.name));
        /* f.blurb still describes each set in portal.py and is worth keeping
           there, but on the page it is a paragraph of preamble sitting between
           you and the first question, re-read every time you scroll past. The
           count and the name say enough. */
        sec.appendChild(head);

        if (!mine.length) {
          sec.appendChild(el("p", "fam-empty",
            "No " + f.name.toLowerCase() + " questions exist for this block yet. When they are written, they appear here."));
        }

        var lastWeek = null, lastLecture = null;
        mine.forEach(function (q) {
          if (q.weekLabel !== lastWeek) {
            lastWeek = q.weekLabel;
            lastLecture = null;
            var wb = el("div", "weekbar");
            wb.appendChild(el(hTag(3), null, q.weekLabel));
            sec.appendChild(wb);
          }
          if (q.lecture !== lastLecture) {
            lastLecture = q.lecture;
            var lb = el("div", "lecbar");
            lb.appendChild(el(hTag(4), null, q.lecture));
            /* lectureMeta is provenance - which deck, which pages, keyed or
               reasoned - and it stays in the bank and in the vault note. It is
               not shown here: on the page it sat between the lecture name and
               the first question as a paragraph of housekeeping, which is not
               what you are there to read. */
            sec.appendChild(lb);
          }
          sec.appendChild(buildQuestion(q));
        });
        HOME.push({ sec: sec, kids: [].slice.call(sec.childNodes) });
        host.appendChild(sec);
      });

      if (gaps.length) {
        host.appendChild(el("p", "fam-gap",
          "Nothing transcribed yet from: " + gaps.join(", ") + "."));
      }
    });

    /* where the cards go when the order is shuffled: one flat list, no
       headings, because there is nothing left for a heading to group */
    var flat = el("div", "shuffled");
    flat.id = "shuffled";
    flat.hidden = true;
    flat.appendChild(el("p", "shuffle-note",
      "Shuffled order. Each card says which week and lecture it came from; pick Shuffled again to deal a new order."));
    frag.appendChild(flat);

    var empty = el("div", "empty", "Nothing matches that filter.");
    empty.id = "empty";
    empty.hidden = true;
    frag.appendChild(empty);
    stream.innerHTML = "";
    stream.appendChild(frag);
  }

  function start(data) {
    QUESTIONS = data;
    QUESTIONS.forEach(function (q) { QMAP[q.qid] = q; });
    load();
    readHash();
    buildMasthead();
    buildBar();
    buildStream();
    paintStats();
    applyFilters();
    QUESTIONS.forEach(function (q) { paintQuestion(q.qid); });
    initPos();
    if (!storeWritable) {
      note("This browser will not let the page use local storage, so answers cannot be saved. Every question still works.");
    }
  }

  /* the tab strip calls this the first time Questions is opened; a second call
     is a no-op so switching tabs never refetches or rebuilds the stream */
  var booted = false;

  window.POM2_QUIZ = {
    searchMatches: searchMatches,
    blockForWeek: blockForWeek,
    noteIdFor: noteIdFor,
    reviewParts: reviewParts,
    boot: function () {
      if (booted) return;
      booted = true;
      /* One request per block, in parallel, concatenated in block order -
         which is why the pooled stream reads week 1 to week 20 without
         anything having to sort it. Each question is stamped with the block
         it came from on the way in; that stamp is what the block filter
         reads and what tells save() which store to write. */
      Promise.all(BLOCKS.map(function (b) {
        return fetch("data/questions/" + b.slug + ".json" +
              /* build_pages.py stamps the file's content hash here. Without it this
                 one fetch was the only thing on the page with no cache busting, so a
                 browser could keep serving the previous deploy's bank however hard
                 you refreshed. Older pages carry no hash and simply go without. */
              (b.qv ? "?v=" + b.qv : ""))
          .then(function (r) {
            if (!r.ok) throw new Error("HTTP " + r.status);
            return r.json();
          })
          .then(function (rows) {
            rows.forEach(function (q) { q.block = b.slug; });
            return rows;
          });
      }))
        .then(function (lists) {
          return lists.reduce(function (all, rows) { return all.concat(rows); }, []);
        })
        .then(start)
        .catch(function () {
          byId("stream").innerHTML = "";
          var e = el("div", "empty",
            "The question set could not be loaded. If you are opening this file straight from disk, serve the folder over HTTP instead - browsers block local fetches.");
          byId("stream").appendChild(e);
        });
    }
  };
})();
