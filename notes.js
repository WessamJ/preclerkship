/* The notes half of a PoM 2 block page.

   data/notes/<slug>.json carries the block's whole lecture roster, taken from
   the vault folders, not only the lectures that have a note. A lecture with
   "hasNote": false renders as a dashed gap, so this view doubles as a map of
   what is still left to write - the same reasoning that keeps an empty question
   set visible on the other tab.

   The rail carries an index of every lecture in the block. A block runs to 36
   notes of a page or more each, so the week chips narrow the stream but cannot
   get you to a named lecture; the index is the way in, and it marks the note
   you are reading as you scroll.

   Any note can be sent to PDF on its own, or a whole week at once, so it can be
   annotated by hand afterwards. That runs through the browser's own print
   dialogue: the page marks what should survive, prints, and unmarks.

   Mermaid is only fetched if some lecture in this block actually has a pathway,
   and any pathway can be opened full size in its own tab - inside the stream a
   wide diagram is squeezed into the column and its labels shrink with it. */

(function () {
  "use strict";

  var BLOCK = window.QUIZ_BLOCK;

  var WEEKS = [];
  var WK = Object.create(null);   // lecture id -> week key
  var week = "all";
  var booted = false;

  var IDX = Object.create(null);  // lecture id -> its row in the index
  var AT = Object.create(null);   // lecture id -> its place in the stream
  var CURRENT = null;             // the note the index is pointing at
  var PENDING = null;             // a clicked note whose scroll is still running

  var query = "";                 // the search box, lowercased and trimmed
  var WORDS = [];                 // the query split by the rule in portal.js
  // the painting rule, its floor and its budget, is portal.js's as well
  var HITS = [];                  // every <mark> on the page, in reading order
  var AT_HIT = -1;                // which one the reader is standing on
  var HAY = Object.create(null);  // lecture id -> everything in it, lowercased
  var MARKED = [];                // notes currently carrying highlights
  var QT = null;                  // the keystroke debounce

  function byId(id) { return document.getElementById(id); }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function html(tag, cls, markup) {
    var n = el(tag, cls);
    if (markup) n.innerHTML = markup;
    return n;
  }

  function lectures() {
    var out = [];
    WEEKS.forEach(function (w) {
      (w.lectures || []).forEach(function (l) { out.push(l); });
    });
    return out;
  }

  /* Two lectures in a roster can carry the same id - endo week 3 has such a
     pair - and a repeated element id makes the second note unreachable: the
     index, the filter and getElementById all find the first one. The roster is
     the thing to fix, but the page must not mis-navigate while it is wrong, so
     every lecture gets a key that is unique on this page and the rest of the
     file addresses notes by that. */
  function assignKeys() {
    var used = Object.create(null);
    lectures().forEach(function (lec) {
      var base = lec.id || "lec", k = base, n = 2;
      while (used[k]) { k = base + "--" + (n++); }
      used[k] = true;
      lec.key = k;
    });
  }

  /* ---------- printing ---------- */

  /* The browser's print dialogue is the only PDF writer a static page has, and
     it is the right one - it produces a normal PDF that any annotator can mark
     up. Everything not in scope is hidden for the duration of the print. */
  function printScope(nodes) {
    var marked = [];
    nodes.forEach(function (n) { n.classList.add("print-me"); marked.push(n); });
    document.body.dataset.printing = "notes";

    function clear() {
      marked.forEach(function (n) { n.classList.remove("print-me"); });
      delete document.body.dataset.printing;
      window.removeEventListener("afterprint", clear);
    }
    window.addEventListener("afterprint", clear);
    // afterprint does not fire everywhere, so do not rely on it alone
    setTimeout(clear, 60000);

    window.print();
  }

  function printNote(art) {
    printScope([art]);
  }

  function printWeek(weekbar) {
    var nodes = [weekbar], n = weekbar.nextElementSibling;
    while (n && !n.classList.contains("weekbar")) {
      if (n.classList.contains("note") && !n.classList.contains("is-gap")
          && !n.classList.contains("is-covered")) nodes.push(n);
      n = n.nextElementSibling;
    }
    printScope(nodes);
  }

  function printAll() {
    var nodes = [].slice.call(
      document.querySelectorAll(
        "#note-stream .weekbar, #note-stream .note:not(.is-gap):not(.is-covered)"));
    printScope(nodes);
  }

  /* The note renderer is portal.js's, shared with the bank's note dialog.
     Looked up when called rather than at load, because portal.js is the
     later script tag on the page. */
  function shared() { return window.PORTAL_NOTES; }
  function written(lec) { return shared().written(lec); }
  function pdfButton(label, title, onClick) { return shared().pdfButton(label, title, onClick); }

  /* The search rule and the highlighter are portal.js's too, shared with the
     bank so the two boxes mean the same thing by a query. Checked rather than
     assumed: a page without them keeps its stream and index, unnarrowed. */
  function search() { return window.PORTAL_SEARCH; }

  /* ---------- one note may carry several lectures ---------- */

  function buildCovered(lec) {
    var art = el("article", "note is-covered");
    art.id = "n-" + lec.key;
    art.dataset.id = lec.key;
    var head = el("div", "note-head");
    head.appendChild(el("span", "note-num", lec.num));
    head.appendChild(el("h4", null, lec.name));
    art.appendChild(head);

    var p = el("p", "covernote");
    p.appendChild(document.createTextNode("Written up with "));
    var a = el("button", "coverlink", lec.coveredBy.num + " · " + lec.coveredBy.name);
    a.type = "button";
    a.addEventListener("click", function () { goTo(lec.coveredBy.key); });
    p.appendChild(a);
    art.appendChild(p);
    return art;
  }

  function buildGap(lec) {
    var art = el("article", "note is-gap");
    art.id = "n-" + lec.key;
    art.dataset.id = lec.key;
    var head = el("div", "note-head");
    head.appendChild(el("span", "note-num", lec.num));
    head.appendChild(el("h4", null, lec.name));
    art.appendChild(head);
    art.appendChild(el("span", "gapnote", "no note yet"));
    return art;
  }

  /* ---------- the lecture index ---------- */

  function buildIndex() {
    var box = byId("note-index");
    /* a page cached from before the index shipped still has to work */
    if (!box) return;
    var frag = document.createDocumentFragment();

    WEEKS.forEach(function (w) {
      var k = weekKey(w);
      var g = el("p", "lecgroup", k === "off" ? "Unscheduled" : "Week " + k);
      g.dataset.k = k;
      frag.appendChild(g);

      (w.lectures || []).forEach(function (lec) {
        var row = el("button", "lecrow"
          + (lec.hasNote === true ? "" : lec.coveredBy ? " is-covered" : " is-gap"));
        row.type = "button";
        row.dataset.id = lec.key;
        row.dataset.k = k;
        row.setAttribute("aria-current", "false");
        row.appendChild(el("span", "ln", lec.num));
        row.appendChild(el("span", "lt", lec.name));
        // the row clips, so the whole name has to be reachable some other way
        row.title = lec.num + " \u00b7 " + lec.name;
        row.addEventListener("click", function () { goTo(lec.key); });
        IDX[lec.key] = row;
        frag.appendChild(row);
      });
    });

    box.appendChild(frag);
  }

  /* the same scroll the questions tab does, so a jump from the rail and a jump
     from the position bar put a note in the same place */
  function goTo(id) {
    var art = byId("n-" + id);
    if (!art) return;
    PENDING = id;
    mark(id);
    var top = art.getBoundingClientRect().top + window.pageYOffset - 16;
    var still = window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    try { window.scrollTo({ top: top, behavior: still ? "auto" : "smooth" }); }
    catch (e) { window.scrollTo(0, top); }
  }

  function mark(id) {
    if (CURRENT === id) return;
    if (CURRENT && IDX[CURRENT]) IDX[CURRENT].setAttribute("aria-current", "false");
    CURRENT = id;

    var row = IDX[id], box = byId("note-index");
    if (!row || !box) return;
    row.setAttribute("aria-current", "true");

    /* the index scrolls in its own right once it outgrows the rail, so the
       marked row has to be brought back into view - scrollIntoView would take
       the page with it, which is the one thing it must not do here */
    var top = row.offsetTop, bot = top + row.offsetHeight;
    if (top < box.scrollTop) box.scrollTop = top - 4;
    else if (bot > box.scrollTop + box.clientHeight) {
      box.scrollTop = bot - box.clientHeight + 4;
    }
  }

  /* Position is read from an IntersectionObserver for the reasons the questions
     tab gives: asking every note where it is on each scroll event costs frames,
     and a hidden note never intersects, so the week filter falls out of it for
     free. The sight line is the top fifth of the viewport.

     A browser without IntersectionObserver keeps a working index - you can
     still jump from it, it just does not follow you. */
  function initSpy() {
    if (!window.IntersectionObserver) return;
    var inView = Object.create(null);
    var notes = [].slice.call(document.querySelectorAll("#note-stream .note"));

    AT = Object.create(null);
    notes.forEach(function (a, i) { AT[a.dataset.id] = i; });

    var obs = new window.IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        var id = e.target.dataset.id;
        if (e.isIntersecting) inView[id] = true;
        else delete inView[id];
      });

      /* At the top of the page the answer is always the first lecture listed,
         so it is not worth asking. Worth saying out loud, because the observer
         delivers its first batch before the web fonts and any diagrams have
         settled - at that moment the masthead has no height and half the block
         is briefly up at the sight line, which is enough to mark a lecture two
         weeks away and leave it there. */
      if (window.pageYOffset < 8) {
        var top = document.querySelector("#note-index .lecrow:not([hidden])");
        if (top) mark(top.dataset.id);
        return;
      }

      /* The questions tab takes the FIRST note crossing the line, because a
         question is a paragraph and the one above you is the one you are on.
         A note is pages long, so the same rule marks the lecture you have just
         left: if the next heading has reached the top of the screen, you have
         arrived at it. Hence the last one crossing, not the first. */
      var best = null, bestAt = -1;
      Object.keys(inView).forEach(function (id) {
        if (AT[id] !== undefined && AT[id] > bestAt) { bestAt = AT[id]; best = id; }
      });
      if (!best) return;

      /* A click owns the mark until its scroll actually arrives, or the index
         strobes through every note the page travels past on the way. Waiting
         for the arrival rather than running a timer matters here: the stream is
         90,000 pixels tall, and a smooth scroll across two weeks takes longer
         than any interval worth guessing at. */
      if (PENDING) {
        if (best !== PENDING) return;
        PENDING = null;
      }
      mark(best);
    }, { rootMargin: "0px 0px -80% 0px" });

    notes.forEach(function (a) { obs.observe(a); });

    /* ...unless the reader takes the wheel before it gets there, in which case
       they have changed their mind and the index should follow them, not the
       jump they walked away from */
    ["wheel", "touchstart", "keydown"].forEach(function (ev) {
      window.addEventListener(ev, function () { PENDING = null; }, { passive: true });
    });
  }

  /* ---------- search ---------- */

  /* What gets searched is the note as it was rendered, read back off the page
     rather than re-derived from the JSON. A note is a title, a framing
     paragraph, tables, callouts and key points in whatever order they were
     written, and textContent already carries all of it. Re-walking the blocks
     here would be a second parser that could disagree with the first.

     A lecture with no note still has its number and name in the haystack, so
     searching for one finds the gap where it will go rather than nothing. */
  function indexText() {
    lectures().forEach(function (lec) {
      var art = byId("n-" + lec.key);
      HAY[lec.key] = (lec.num + " " + lec.name + " " +
                      (art ? art.textContent : "")).toLowerCase();
    });
  }

  /* every word of the query, in any order, somewhere in the note: the bank's
     rule, and now this tab's */
  function hit(id) {
    var s = search();
    return !WORDS.length || !!(s && s.hit(HAY[id] || "", WORDS));
  }

  function unmark() {
    if (search()) search().unmark(MARKED);
    MARKED = [];
  }

  /* .pathway is skipped because mermaid parses that element's own text, and a
     <mark> inside it is a syntax error rather than a highlight. */
  function markHits(art, words, budget) {
    var s = search();
    if (!s) return 0;
    var made = s.mark(art, words, budget, ".pathway");
    if (made) MARKED.push(art);
    return made;
  }

  /* Filtering tells you WHICH notes hold the word; this walks you to the word
     itself, which is what Ctrl+F does and what the filter alone did not. The
     hits are collected in document order after a pass, so Next runs down the
     page rather than through the notes in roster order.

     The browser's own Ctrl+F is not a substitute: a note the filter has hidden
     is `hidden`, and find-in-page will not see inside it. */
  function collectHits() {
    HITS = [].slice.call(document.querySelectorAll("#note-stream mark.hit"));
    AT_HIT = -1;
    paintNav();
  }

  function paintNav() {
    var bar = byId("note-nav");
    if (!bar) return;
    bar.hidden = !query || !HITS.length;
    var pos = byId("note-nav-pos");
    if (pos) {
      var n = HITS.length + (capped() ? "+" : "");
      // before the first step there is no position to report, only a total
      pos.textContent = !HITS.length ? ""
        : AT_HIT < 0 ? n + (HITS.length === 1 ? " match" : " matches")
        : (AT_HIT + 1) + " of " + n;
    }
  }

  /* The budget stops painting part-way through a very common word, so the
     count has to say it is a floor rather than a total. */
  function capped() {
    var s = search();
    return !!s && HITS.length >= s.MARK_BUDGET;
  }

  function goHit(step) {
    if (!HITS.length) return;
    if (AT_HIT >= 0 && HITS[AT_HIT]) HITS[AT_HIT].classList.remove("on");
    AT_HIT = (AT_HIT + step + HITS.length) % HITS.length;
    var m = HITS[AT_HIT];
    m.classList.add("on");

    /* Centred rather than put at the top: a hit is a word inside a paragraph
       and the sentence around it is the reason you are looking at it. */
    var box = m.getBoundingClientRect();
    var mid = box.top + window.pageYOffset - (window.innerHeight / 2) + (box.height / 2);
    var still = window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    try { window.scrollTo({ top: Math.max(0, mid), behavior: still ? "auto" : "smooth" }); }
    catch (e) { window.scrollTo(0, Math.max(0, mid)); }

    // the rail should follow the reader to the note they have landed in
    var art = m.closest && m.closest(".note");
    if (art && art.dataset.id) {
      PENDING = art.dataset.id;
      mark(art.dataset.id);
    }
    paintNav();
  }

  function setQuery(v) {
    var next = (v || "").replace(/^\s+|\s+$/g, "").toLowerCase();
    if (next === query) return;
    query = next;
    WORDS = search() ? search().words(query) : [];
    var clear = byId("note-q-clear");
    if (clear) clear.hidden = !query;
    applyFilter();
  }

  /* ---------- filter ---------- */

  /* Week numbers run across the whole year, not from 1 inside each block - msk
     starts at 7 - so the chip is labelled with the number the roster carries.
     The number, not w.label: those are long enough to be headings, not chips. */
  function weekKey(w) { return (w && w.n != null) ? String(w.n) : "off"; }

  function weekDefs() {
    var defs = [{ k: "all", label: "All", n: lectures().length }];
    WEEKS.forEach(function (w) {
      var k = weekKey(w);
      defs.push({
        k: k,
        label: k === "off" ? "Unscheduled" : "Week " + k,
        n: (w.lectures || []).length
      });
    });
    return defs;
  }

  function matches(lec) {
    return (week === "all" || WK[lec.key] === week) && hit(lec.key);
  }

  function applyFilter() {
    var shown = 0;
    /* every highlight from the last query comes off before this one goes on,
       and a note that is about to be hidden is left clean rather than carrying
       marks nobody can see */
    unmark();
    var s = search();
    var paint = s ? s.paintWords(WORDS) : [];
    var budget = paint.length ? s.MARK_BUDGET : 0;
    lectures().forEach(function (lec) {
      var art = byId("n-" + lec.key);
      if (!art) return;
      var ok = matches(lec);
      art.hidden = !ok;
      if (ok && budget > 0) budget -= markHits(art, paint, budget);
      if (ok) shown++;
    });

    // a week heading survives only while a lecture under it is still visible
    [].forEach.call(document.querySelectorAll("#note-stream .weekbar"), function (h) {
      var any = false, n = h.nextElementSibling;
      while (n && !n.classList.contains("weekbar")) {
        if (n.classList.contains("note") && !n.hidden) { any = true; break; }
        n = n.nextElementSibling;
      }
      h.hidden = !any;
    });

    /* the index carries the same filter as the stream, read off the rows rather
       than from a lookup, so a roster that repeats an id cannot leave a row
       behind that never hides */
    [].forEach.call(document.querySelectorAll("#note-index .lecrow"), function (row) {
      row.hidden = !((week === "all" || row.dataset.k === week) &&
                     hit(row.dataset.id));
    });

    /* the week headings inside the index earn their line only on All, where the
       numbering restarts at 01 once per week and would otherwise be unreadable.
       A search thins the rows under them, so a heading left with nothing beneath
       it goes too - otherwise the rail reads as a list of empty weeks. */
    [].forEach.call(document.querySelectorAll("#note-index .lecgroup"), function (g) {
      if (week !== "all") { g.hidden = true; return; }
      var any = false, n = g.nextElementSibling;
      while (n && !n.classList.contains("lecgroup")) {
        if (n.classList.contains("lecrow") && !n.hidden) { any = true; break; }
        n = n.nextElementSibling;
      }
      g.hidden = !any;
    });

    /* Nothing is marked before the first scroll, because at the top of the page
       no note has reached the sight line yet - and the note the index was
       pointing at may have just been filtered away. Either way, fall back to the
       first lecture still listed; the observer corrects it to wherever the
       reader actually is as soon as one fires. */
    if (!CURRENT || (IDX[CURRENT] && IDX[CURRENT].hidden)) {
      if (CURRENT && IDX[CURRENT]) IDX[CURRENT].setAttribute("aria-current", "false");
      CURRENT = null;
      var first = document.querySelector("#note-index .lecrow:not([hidden])");
      if (first) mark(first.dataset.id);
    }

    byId("note-empty").hidden = shown > 0;
    collectHits();
    paintHits(shown);
    paintChips();
  }

  function paintHits(shown) {
    var line = byId("note-q-count");
    if (!line) return;
    // a query with no word past the floor narrows nothing, so it has no count
    line.hidden = !WORDS.length;
    line.textContent = shown === 1 ? "1 lecture matches"
                                   : shown + " lectures match";
  }

  function counts() {
    var all = lectures();
    return { all: all.length, written: all.filter(written).length };
  }

  function paintChips() {
    [].forEach.call(document.querySelectorAll("#note-week-chips .chip"), function (b) {
      b.setAttribute("aria-pressed", week === b.dataset.k ? "true" : "false");
    });
  }

  function paintCoverage() {
    var c = counts();
    var weeksWith = WEEKS.filter(function (w) {
      return (w.lectures || []).some(written);
    }).length;

    byId("cv-notes").textContent = c.written;
    byId("cv-of").textContent = "/" + c.all;
    byId("cv-weeks").textContent = weeksWith;
    byId("cv-weeks-of").textContent = "/" + WEEKS.length;

    var tc = byId("tc-notes");
    if (tc) tc.textContent = c.written + "/" + c.all;

    byId("print-all").disabled = c.written === 0;
  }

  /* ---------- boot ---------- */

  function buildRail() {
    /* a page cached from before the week filter shipped still has to work */
    var box = byId("note-week-chips");
    if (box) {
      weekDefs().forEach(function (d) {
        var b = el("button", "chip");
        b.type = "button";
        b.dataset.k = d.k;
        b.setAttribute("aria-pressed", d.k === "all" ? "true" : "false");
        b.appendChild(document.createTextNode(d.label));
        b.appendChild(el("span", "n", String(d.n)));
        b.addEventListener("click", function () { week = d.k; applyFilter(); });
        box.appendChild(b);
      });
    }

    buildSearch();
    buildIndex();
    byId("print-all").addEventListener("click", printAll);
  }

  function buildSearch() {
    /* a page cached from before the search shipped still has to work */
    var box = byId("note-q");
    if (!box) return;

    /* Debounced, because every keystroke re-filters the stream and re-walks
       the text nodes of whatever still matches. 150ms is below the gap between
       two typed characters and above the cost of one pass. */
    box.addEventListener("input", function () {
      if (QT) window.clearTimeout(QT);
      QT = window.setTimeout(function () { setQuery(box.value); }, 150);
    });
    box.addEventListener("keydown", function (e) {
      if (e.key === "Escape" || e.keyCode === 27) {
        box.value = "";
        setQuery("");
        return;
      }
      if (e.key === "Enter" || e.keyCode === 13) {
        /* Enter would submit if this box were ever wrapped in a form, and the
           debounce may not have run yet on a fast typist's last keystroke. */
        e.preventDefault();
        if (QT) { window.clearTimeout(QT); QT = null; setQuery(box.value); }
        goHit(e.shiftKey ? -1 : 1);
      }
    });

    var clear = byId("note-q-clear");
    if (clear) {
      clear.addEventListener("click", function () {
        box.value = "";
        setQuery("");
        box.focus();
      });
    }

    var prev = byId("note-nav-prev"), next = byId("note-nav-next");
    if (prev) prev.addEventListener("click", function () { goHit(-1); });
    if (next) next.addEventListener("click", function () { goHit(1); });

    document.addEventListener("keydown", function (e) {
      /* "/" jumps to the box, the way it does in the bank and on GitHub. Only
         while the notes are the visible panel, no dialog has the keyboard and
         the key was not typed into some other field; checked before the
         modifier guard because on many European layouts "/" IS shifted. The
         text is selected so the next keystroke replaces the old query. */
      if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey) {
        var panel = byId("panel-notes");
        if (panel && panel.hidden) return;
        if (document.querySelector("dialog[open]")) return;
        var t = e.target;
        if (t && (t.isContentEditable ||
                  /^(input|textarea|select)$/i.test(t.tagName || ""))) return;
        e.preventDefault();
        box.focus();
        box.select();
        return;
      }

      /* F3 and ctrl/cmd-G are the find-again keys every browser already uses,
         and here they should walk THIS search rather than open the browser's,
         which cannot see inside a filtered-out note. */
      if (!query || !HITS.length) return;
      var again = (e.key === "F3" || e.keyCode === 114) ||
                  ((e.ctrlKey || e.metaKey) && (e.key === "g" || e.key === "G"));
      if (!again) return;
      e.preventDefault();
      goHit(e.shiftKey ? -1 : 1);
    });
  }

  function buildStream() {
    var stream = byId("note-stream"), frag = document.createDocumentFragment();

    /* the same head the questions tab gives each source family, so the notes
       open by saying what they are rather than dropping straight into week 1 */
    var c = counts();
    var head = el("div", "fam-head");
    head.appendChild(el("p", "fam-meta",
      c.written ? c.written + " of " + c.all + " lectures" : "nothing written yet"));
    head.appendChild(el("h2", null, "Lecture notes"));
    head.appendChild(el("p", null,
      "Bolded + gold star = high-yield = showed up in modules, in-class, and Qbank"));
    frag.appendChild(head);

    WEEKS.forEach(function (w) {
      var wb = el("div", "weekbar");
      wb.appendChild(el("h3", null, w.label || ("Week " + w.n)));
      if ((w.lectures || []).some(written)) {
        wb.appendChild(pdfButton("Save week as PDF",
          "Save every note in this week as one PDF",
          function () { printWeek(wb); }));
      }
      frag.appendChild(wb);
      (w.lectures || []).forEach(function (lec) {
        frag.appendChild(lec.hasNote === true ? shared().build(lec, { block: BLOCK.name, onPrint: printNote })
                         : lec.coveredBy ? buildCovered(lec) : buildGap(lec));
      });
    });

    var empty = el("div", "empty", "Nothing matches that filter.");
    empty.id = "note-empty";
    empty.hidden = true;
    frag.appendChild(empty);

    stream.innerHTML = "";
    stream.appendChild(frag);
  }

  /* the notes are long enough that scrolling back by hand is a chore, so the
     tab carries the same pill the questions tab does, with only the way to the
     top on it. It is inside the notes panel, so switching tabs takes it away. */
  function initTop() {
    var bar = byId("notebar");
    if (!bar) return;
    var queued = false;

    byId("nb-top").addEventListener("click", function () {
      var still = window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      try { window.scrollTo({ top: 0, behavior: still ? "auto" : "smooth" }); }
      catch (e) { window.scrollTo(0, 0); }
    });

    function paint() { bar.hidden = window.pageYOffset <= 400; }
    window.addEventListener("scroll", function () {
      if (queued) return;
      queued = true;
      window.requestAnimationFrame(function () { queued = false; paint(); });
    }, { passive: true });
    paint();
  }

  /* ---------- a link straight to one note ---------- */

  /* b1.html#n-b1-w1-02 lands on that lecture. Read once the stream is built,
     again once the pathways have drawn because drawing swaps text for taller
     diagrams and moves everything below them, and again on every hashchange,
     because a same-document hash change never reloads the page and boot runs
     only once. A hash naming a note the roster lacks does nothing, which is
     better than a scroll to nowhere. */
  function wantedNote() {
    var h = window.location.hash || "";
    return h.indexOf("#n-") === 0 ? h.slice(3) : null;
  }

  function goToWanted() {
    var id = wantedNote();
    var art = id ? byId("n-" + id) : null;
    if (!art) return;
    /* 16 is the offset goTo aims for; already there means the earlier scroll
       landed, and scrolling again would only restart it */
    if (Math.abs(art.getBoundingClientRect().top - 16) < 2) return;
    goTo(id);
  }

  function start(data) {
    WEEKS = (data && data.weeks) || [];
    assignKeys();
    WEEKS.forEach(function (w) {
      (w.lectures || []).forEach(function (l) { WK[l.key] = weekKey(w); });
    });
    buildRail();
    buildStream();
    indexText();
    paintCoverage();
    applyFilter();
    initSpy();
    initTop();
    goToWanted();
    shared().drawPathways(byId("note-stream")).then(goToWanted);
    window.addEventListener("hashchange", goToWanted);
  }

  window.POM2_NOTES = {
    boot: function () {
      if (booted) return;
      booted = true;
      fetch("data/notes/" + BLOCK.slug + ".json" +
            /* build_pages.py stamps the file's content hash here. Without it this
               one fetch was the only thing on the page with no cache busting, so a
               browser could keep serving the previous deploy's bank however hard
               you refreshed. Older pages carry no hash and simply go without. */
            (BLOCK.nv ? "?v=" + BLOCK.nv : ""))
        .then(function (r) {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        })
        .then(start)
        .catch(function () {
          var stream = byId("note-stream");
          stream.innerHTML = "";
          stream.appendChild(el("div", "empty",
            "The notes could not be loaded. If you are opening this file straight from disk, serve the folder over HTTP instead - browsers block local fetches."));
        });
    }
  };
})();
