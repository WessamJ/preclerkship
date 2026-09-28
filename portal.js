/* Tab strip for a course block page, and the boot for the question bank.

   Notes and Anki are two views of the same week and share a page. Questions
   are not: they live on the course's one qbank.html, where a block is a filter
   value rather than a page, so the third tab is a link out rather than a panel.
   It carries the block in its hash, so arriving there lands pre-filtered.

   The tab lives in the hash, so a link can point straight at the notes and the
   back button steps between them. An old #questions link still works: it is
   redirected to the qbank, filtered to this block. */

(function () {
  "use strict";

  var BLOCK = window.QUIZ_BLOCK;

  var TABS = {
    notes: {
      tab: "tab-notes",
      panel: "panel-notes",
      board: "sb-notes",
      boot: function () { if (window.POM2_NOTES) window.POM2_NOTES.boot(); }
    },
    anki: {
      tab: "tab-anki",
      panel: "panel-anki",
      board: null,          /* the scoreboard counts answers; a deck has none */
      boot: function () {}
    }
  };

  /* Where this block's questions went. One place builds it, so the link in the
     tab strip and the redirect below cannot drift apart. */
  function qbankUrl() {
    return "qbank.html#block=" + BLOCK.slug;
  }

  /* A bookmark or an old link pointing at this block's questions still means
     something; it just means somewhere else now. Replace rather than assign,
     so Back goes where the reader came from instead of bouncing off a redirect.

     Checked on load AND on hashchange, because #questions arriving from a link
     on the page is a same-document navigation: nothing reloads, init never
     runs again, and a load-time check alone would sit there doing nothing. */
  function leftForQbank() {
    if ((window.location.hash || "") !== "#questions") return false;
    window.location.replace(qbankUrl());
    return true;
  }

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

  /* ---------- one note, rendered the same everywhere ---------- */

  /* A lecture's note is shown in two places: the block page's notes tab and
     the bank's note dialog, opened from a question's review line. They have
     to look the same, so the renderer lives here, in the file both pages load,
     and each caller hands in the two things that differ: the block's name, for
     the tabs a figure or pathway opens into, and what a PDF button should do
     - nothing, in the dialog, where printing would take the bank with it. */

  var MERMAID_SRC = "https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js";
  var HEAD_WRAP = 24;             // a table heading longer than this wraps
  var MERMAID = null;             // the one load of the diagram library


  function esc(t) {
    return String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function pdfButton(label, title, onClick) {
    var b = el("button", "pdf-btn", label);
    b.type = "button";
    b.title = title;
    b.addEventListener("click", function (e) {
      e.preventDefault();
      onClick();
    });
    return b;
  }

  function buildTable(spec) {
    var wrap = el("div", "ct-wrap");
    var t = el("table", "ct");
    if (spec.cols && spec.cols.length) {
      var thead = el("thead"), tr = el("tr");
      /* Headings are set on one line, which is right for "Mechanism of Action"
         and wrong for anything the extractor mistook for one: a sentence in a
         th sets the column's width by itself, and the first column is sticky,
         so it then covers the table while the content scrolls off to the
         right. Past a short measure the heading wraps instead. */
      spec.cols.forEach(function (c) {
        var th = html("th", null, c);
        if ((th.textContent || "").trim().length > HEAD_WRAP) th.className = "wide";
        tr.appendChild(th);
      });
      thead.appendChild(tr);
      t.appendChild(thead);
    }
    var tb = el("tbody");
    /* a blank first cell means the row belongs to the group named above it, so
       that label spans down the group instead of repeating. First column only:
       anywhere else a blank cell is just a blank cell. */
    var label = null;
    (spec.rows || []).forEach(function (row) {
      var r = el("tr");
      row.forEach(function (cell, i) {
        if (i !== 0) { r.appendChild(html("td", null, cell)); return; }
        if (label && !cell.trim()) { label.rowSpan += 1; return; }
        label = html("td", "rowlab", cell);
        r.appendChild(label);
      });
      tb.appendChild(r);
    });
    t.appendChild(tb);
    wrap.appendChild(t);
    return wrap;
  }

  /* the parts arrive in the order they were written, because the sentence above
     a table is the reason the table is there - splitting them into separate
     fields would have shuffled the argument */
  function buildBlock(b, lec, ctx) {
    if (b.t === "pathway") {
      var box = el("div", "pwblock");
      var p = el("div", "pathway");
      // mermaid parses the element's own text, so this must not be innerHTML
      p.textContent = b.mermaid;
      box.appendChild(p);

      /* the button sits outside .pathway: mermaid reads that element's text and
         would swallow anything else put inside it */
      var open = el("button", "pw-open", "Open full size");
      open.type = "button";
      // nothing to open until mermaid has drawn; revealed in drawPathways
      open.hidden = true;
      open.title = "Open this pathway in its own tab, big enough to read";
      open.addEventListener("click", function () { openPathway(p, lec, ctx); });
      box.appendChild(open);

      // the diagram is the obvious thing to click, so let it be
      p.addEventListener("click", function () { openPathway(p, lec, ctx); });

      return box;
    }
    if (b.t === "figure") {
      // openable the moment it is built, unlike a pathway, which has to wait
      // for mermaid to draw before there is anything to open
      var fbox = el("div", "figblock is-openable");
      var fig = el("figure", "fig");

      var img = el("img");
      // properties, never markup: a filename is not HTML and must not be parsed
      img.src = b.src;
      img.alt = b.alt || "";
      img.loading = "lazy";
      img.decoding = "async";
      /* the intrinsic size reserves the space, so a figure arriving late does
         not shunt the chart down the page under someone already reading it */
      if (b.w) img.width = b.w;
      if (b.h) img.height = b.h;
      if (b.width) img.style.maxWidth = b.width + "px";
      fig.appendChild(img);

      if (b.cap) fig.appendChild(html("figcaption", null, b.cap));
      fbox.appendChild(fig);

      var fopen = el("button", "fig-open", "Open full size");
      fopen.type = "button";
      fopen.title = "Open this figure in its own tab, big enough to read";
      fopen.addEventListener("click", function () { openFigure(b, lec, ctx); });
      fbox.appendChild(fopen);

      // the picture is the obvious thing to click, so let it be
      img.addEventListener("click", function () { openFigure(b, lec, ctx); });

      return fbox;
    }
    if (b.t === "table") {
      var box = el("div", "tblock");
      if (b.lead) box.appendChild(html("div", "tlead", b.lead));
      box.appendChild(buildTable(b));
      return box;
    }
    if (b.t === "callout") {
      var c = el("div", "callout k-" + (/^[a-z]+$/.test(b.kind || "") ? b.kind : "note"));
      c.appendChild(el("span", "ct", b.title || "Note"));
      c.appendChild(html("div", null, b.html));
      return c;
    }
    if (b.t === "list") return html("div", "clist", b.html);
    return html("div", "cnote", b.html);
  }

  /* A lecture is "covered" when the material is written up, but under a
     neighbouring lecture's heading - the upper-year notes chart "Esophagus
     Pathologies" or "Small Bowel Obstruction" across two or three of the
     course's lectures at once. Counting those as gaps understated the
     coverage and, worse, sent you looking for a note that is already there. */

  function written(lec) {
    return lec.hasNote === true || !!lec.coveredBy;
  }

  function coveredTitle(lec) {
    var names = [lec.name];
    (lec.covers || []).forEach(function (c) { names.push(c.name); });
    return names.join(" + ");
  }

  function buildNote(lec, opts) {
    opts = opts || {};
    var art = el("article", "note");
    /* the block page addresses notes by key; the dialog holds one note and
       needs no id, and must not plant one that could collide with the page */
    if (lec.key) {
      art.id = "n-" + lec.key;
      art.dataset.id = lec.key;
    }

    var head = el("div", "note-head");
    head.appendChild(el("span", "note-num", lec.num));
    /* These notes are not written one per lecture: one chart carries two or
       three of them. The note is titled with every lecture it covers, rather
       than being filed under one and leaving the rest reading as unwritten. */
    head.appendChild(el("h4", null, coveredTitle(lec)));
    if (typeof opts.onPrint === "function") {
      head.appendChild(el("span", "spacer"));
      head.appendChild(pdfButton("PDF", "Save this note as a PDF",
        function () { opts.onPrint(art); }));
    }
    art.appendChild(head);

    if (lec.title) art.appendChild(el("p", "note-title", lec.title));
    if (lec.framing) art.appendChild(html("div", "framing", lec.framing));

    (lec.blocks || []).forEach(function (b) { art.appendChild(buildBlock(b, lec, opts)); });

    if (lec.keypoints) {
      var kp = el("div", "keypoints");
      kp.appendChild(el("span", "kt", "High-yield discriminators"));
      kp.appendChild(html("div", null, lec.keypoints));
      art.appendChild(kp);
    }

    return art;
  }

  /* Inside the stream a pathway is capped at the column width, so a wide one is
     scaled down and its labels go with it. This hands the diagram to a tab of
     its own, where it has the whole window.

     It goes as SVG, which is what mermaid has already drawn: it stays sharp at
     any zoom the browser offers, costs the repo no image files and no build
     step, and works offline. A PNG would be a fixed grid of pixels and would
     blur at exactly the moment you leaned in, which is the problem being fixed.

     document.write into a blank tab rather than a blob URL: blobs inherit an
     opaque origin that some browsers refuse to render as a document, and this
     page has no server to fetch a real one from. */
  function openPathway(host, lec, ctx) {
    var svg = host.querySelector("svg");
    if (!svg) return;            // mermaid never drew it; the source is on screen

    var copy = svg.cloneNode(true);
    copy.removeAttribute("style");        // mermaid pins a max-width here
    copy.setAttribute("width", "100%");
    copy.removeAttribute("height");
    if (!copy.getAttribute("xmlns")) {
      copy.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    }

    var w = window.open("", "_blank");
    if (!w) return;                       // a blocked popup is not worth a dialog

    var title = (lec && lec.name) || "Pathway";
    var block = (ctx && ctx.block) || (BLOCK && BLOCK.name) || "PoM 2";
    var num = (lec && lec.num) ? lec.num + " \u00b7 " : "";

    w.document.open();
    w.document.write([
      "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">",
      "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
      "<title>", esc(num + title), " \u00b7 ", esc(block), "</title>",
      "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">",
      "<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>",
      "<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?",
      "family=Fraunces:opsz,wght@9..144,600&family=Inter:wght@400;600&display=swap\">",
      "<style>",
      "*{margin:0;padding:0;box-sizing:border-box}",
      "body{background:#faf7f7;color:#27060f;",
      "font:16px/1.7 Inter,-apple-system,BlinkMacSystemFont,sans-serif;",
      /* the diagram fills the width and scrolls, which is how a flowchart is
         read anyway and keeps the labels as large as they can be - but not
         past a comfortable measure on a very wide screen */
      "max-width:1500px;margin:auto;padding:22px clamp(16px,4vw,40px) 40px}",
      "p.eyebrow{font-size:.72rem;font-weight:600;letter-spacing:.08em;",
      "text-transform:uppercase;color:#8a7a7d;margin-bottom:6px}",
      "h1{font-family:Fraunces,Georgia,serif;font-size:clamp(1.3rem,3vw,1.9rem);",
      "font-weight:600;line-height:1.2;text-wrap:balance;margin-bottom:18px}",
      /* the whole point: the diagram gets the window, not a 900px column */
      "figure{background:#fff;border:1px solid #ecdfe1;border-radius:8px;",
      "padding:clamp(14px,3vw,30px);overflow-x:auto}",
      "svg{width:100%;height:auto;display:block}",
      "footer{margin-top:16px;font-size:.8rem;color:#8a7a7d}",
      "@media print{body{padding:0;background:#fff}",
      "figure{border:0;padding:0}footer{display:none}}",
      "</style></head><body>",
      "<p class=\"eyebrow\">", esc(block), "</p>",
      "<h1>", esc(num + title), "</h1>",
      "<figure>", new XMLSerializer().serializeToString(copy), "</figure>",
      "<footer>Zoom with your browser, or print this page to keep it. ",
      "The diagram is drawn, not photographed, so it stays sharp at any size.</footer>",
      "</body></html>"
    ].join(""));
    w.document.close();
  }

  /* The pathway's problem, and the same answer: inside the stream a figure is
     capped at the note's column, and the labels printed inside an axis diagram
     go down with it. This hands it a tab of its own.

     The picture is a file, not an inline SVG, so the new document just points
     at the same asset the browser has already cached - nothing is re-encoded
     and nothing is copied across.

     The img is built with DOM calls after the write rather than concatenated
     into the markup, because esc() escapes &<> but NOT quotes, and a src is an
     attribute. Nothing here would break on the hashed filenames we generate;
     building it this way means nothing later can. */
  function openFigure(b, lec, ctx) {
    var w = window.open("", "_blank");
    if (!w) return;                       // a blocked popup is not worth a dialog

    var title = (lec && lec.name) || "Figure";
    var block = (ctx && ctx.block) || (BLOCK && BLOCK.name) || "PoM 2";
    var num = (lec && lec.num) ? lec.num + " · " : "";

    w.document.open();
    w.document.write([
      "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">",
      "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
      "<title>", esc(num + title), " · ", esc(block), "</title>",
      "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">",
      "<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>",
      "<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?",
      "family=Fraunces:opsz,wght@9..144,600&family=Inter:wght@400;600&display=swap\">",
      "<style>",
      "*{margin:0;padding:0;box-sizing:border-box}",
      "body{background:#faf7f7;color:#27060f;",
      "font:16px/1.7 Inter,-apple-system,BlinkMacSystemFont,sans-serif;",
      "max-width:1500px;margin:auto;padding:22px clamp(16px,4vw,40px) 40px}",
      "p.eyebrow{font-size:.72rem;font-weight:600;letter-spacing:.08em;",
      "text-transform:uppercase;color:#8a7a7d;margin-bottom:6px}",
      "h1{font-family:Fraunces,Georgia,serif;font-size:clamp(1.3rem,3vw,1.9rem);",
      "font-weight:600;line-height:1.2;text-wrap:balance;margin-bottom:18px}",
      "figure{background:#fff;border:1px solid #ecdfe1;border-radius:8px;",
      "padding:clamp(14px,3vw,30px)}",
      "img{width:100%;height:auto;display:block;margin:auto}",
      "figcaption{margin-top:12px;font-size:.8rem;color:#8a7a7d;text-align:center}",
      "footer{margin-top:16px;font-size:.8rem;color:#8a7a7d}",
      "@media print{body{padding:0;background:#fff}",
      "figure{border:0;padding:0}footer{display:none}}",
      "</style></head><body>",
      "<p class=\"eyebrow\">", esc(block), "</p>",
      "<h1>", esc(num + title), "</h1>",
      "<figure id=\"fig\"></figure>",
      "<footer>Zoom with your browser, or print this page to keep it.</footer>",
      "</body></html>"
    ].join(""));
    w.document.close();

    var host = w.document.getElementById("fig");
    if (!host) return;
    var big = w.document.createElement("img");
    big.src = new URL(b.src, location.href).href;   // the popup has no base url
    big.alt = b.alt || "";
    host.appendChild(big);
    if (b.cap) {
      var cap = w.document.createElement("figcaption");
      cap.innerHTML = b.cap;
      host.appendChild(cap);
    }
  }

  /* One diagram failing to parse should not take the others' buttons with it, so
     this asks each block on its own whether it has a drawing to show. */
  function revealOpen(root) {
    [].forEach.call(root.querySelectorAll(".pwblock"), function (box) {
      var drawn = !!box.querySelector(".pathway svg");
      box.classList.toggle("is-openable", drawn);
      var btn = box.querySelector(".pw-open");
      if (btn) btn.hidden = !drawn;
    });
  }

  function themeVars() {
    var cs = getComputedStyle(document.documentElement);
    function v(name, fallback) {
      var got = cs.getPropertyValue(name).trim();
      return got || fallback;
    }
    return {
      background: v("--card-bg", "#ffffff"),
      primaryColor: v("--q-accent-soft", "#eeeeee"),
      primaryTextColor: v("--text", "#27060f"),
      primaryBorderColor: v("--q-accent", "#84223b"),
      lineColor: v("--muted", "#8a7a7d"),
      secondaryColor: v("--bg", "#faf7f7"),
      tertiaryColor: v("--bg", "#faf7f7"),
      fontFamily: v("--sans", "Inter, sans-serif"),
      fontSize: "13px"
    };
  }

  /* The library is fetched once per page, the first time any note on it
     needs a diagram, and every later call waits on that same load. */
  function loadMermaid() {
    if (MERMAID) return MERMAID;
    MERMAID = new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = MERMAID_SRC;
      s.async = true;
      s.onload = function () {
        if (!window.mermaid) { resolve(null); return; }
        window.mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "base",
          themeVariables: themeVars(),
          flowchart: { htmlLabels: true, useMaxWidth: true }
        });
        resolve(window.mermaid);
      };
      s.onerror = function () { reject(new Error("mermaid did not load")); };
      document.head.appendChild(s);
    });
    return MERMAID;
  }

  /* Returns a promise that settles once every diagram is drawn or has fallen
     back to text. Drawing swaps source text for a taller SVG, which moves
     everything below it, so a caller that scrolled to a note must re-aim
     afterwards. */
  function drawPathways(root) {
    if (!root) return Promise.resolve();
    var nodes = [].slice.call(root.querySelectorAll(".pathway"));
    if (!nodes.length) return Promise.resolve();

    return loadMermaid().then(function (mermaid) {
      if (!mermaid) return;       // loaded but exposed nothing; the source stays on screen
      function done() { revealOpen(root); }
      try {
        var run = mermaid.run({ nodes: nodes });
        if (run && run.then) return run.then(done, done);
        done();
      } catch (e) {
        // a diagram that will not parse should cost the page nothing; the
        // source text stays on screen and the rest of the note is unaffected
        done();
      }
    }, function () {
      nodes.forEach(function (n) {
        n.textContent = "";
        n.appendChild(el("p", null, "The diagram library could not be loaded, so this pathway is not drawn."));
      });
    });
  }

  window.PORTAL_NOTES = {
    written: written,
    coveredTitle: coveredTitle,
    pdfButton: pdfButton,
    build: buildNote,
    drawPathways: drawPathways
  };

  /* Notes come first when there are any - they are what you read before you
     test yourself. A block with none of them written yet would otherwise open
     on a page of nothing but gaps, so it falls through to the questions. */
  function fallback() {
    var tc = byId("tc-notes");
    var written = tc ? parseInt(tc.textContent, 10) : 0;
    /* Notes first where any are written - they are what you read before you
       test yourself. A block with none of them falls through to Anki rather
       than to questions, which are no longer on this page at all. */
    return written > 0 ? "notes" : "anki";
  }

  function wanted() {
    var h = (window.location.hash || "").replace("#", "");
    /* #n-<lecture id> names one note, the way the bank's note dialog links
       back here. The tab is implied by the note. */
    if (h.indexOf("n-") === 0) return "notes";
    return TABS[h] ? h : fallback();
  }

  /* How many of this block's questions have been answered, read straight out
     of the store. The bank itself is 44 to 269 KB and lives on another page;
     the answer to "how far in am I" is already here, in a record per question
     carrying its own status, so it costs one localStorage read and no fetch. */
  function answeredHere() {
    var raw = null;
    try { raw = window.localStorage.getItem((BLOCK.store || "nsq.v1.") + BLOCK.slug); }
    catch (e) { return 0; }
    if (!raw) return 0;
    var parsed;
    try { parsed = JSON.parse(raw); }
    catch (e) { return 0; }
    if (!parsed || typeof parsed !== "object") return 0;
    var n = 0;
    Object.keys(parsed).forEach(function (qid) {
      var r = parsed[qid];
      if (r && (r.status === "correct" || r.status === "wrong")) n++;
    });
    return n;
  }

  function paintDone() {
    var el = byId("qb-done"), n = answeredHere();
    if (!el) return;
    el.hidden = n === 0;
    el.textContent = n + " done";
  }

  function show(key) {
    /* the stylesheet reads this: the questions tab is a working view and drops
       the block's blurb from the masthead, where the notes tab keeps it */
    document.body.dataset.tab = key;
    Object.keys(TABS).forEach(function (k) {
      var t = TABS[k], on = k === key;
      byId(t.tab).setAttribute("aria-selected", on ? "true" : "false");
      byId(t.panel).hidden = !on;
      if (t.board) byId(t.board).hidden = !on;
    });
    if (!TABS[key].board) {
      Object.keys(TABS).forEach(function (k) {
        if (TABS[k].board) byId(TABS[k].board).hidden = true;
      });
    }
    TABS[key].boot();
  }

  function init() {
    /* The question bank has one panel and therefore no tab strip. It says its
       own eyebrow in QUIZ_BLOCK, because "Block 3 · Weeks 7–11" is not a true
       thing to say about a page that is every block at once. */
    if (BLOCK.blocks && BLOCK.blocks.length) {
      byId("m-eyebrow").textContent =
        "Schulich " + (BLOCK.course || "PoM 2") + " · " +
        (BLOCK.eyebrow || "Every block");
      /* not "questions": that value hides the masthead blurb, which the block
         pages can afford because their notes tab carries it and this page,
         having no other tab, cannot */
      document.body.dataset.tab = "qbank";
      if (window.POM2_QUIZ) window.POM2_QUIZ.boot();
      return;
    }

    /* quiz.js used to write this, but it only runs once questions are booted -
       landing on the notes tab would have left the masthead blank */
    byId("m-eyebrow").textContent =
      "Schulich " + (BLOCK.course || "PoM 2") + " · Block " + BLOCK.n +
      " · Weeks " + BLOCK.weeks;

    if (leftForQbank()) return;

    Object.keys(TABS).forEach(function (k) {
      byId(TABS[k].tab).addEventListener("click", function () {
        if (wanted() === k) { show(k); return; }
        window.location.hash = k;   // hashchange does the rest, and history keeps it
      });
    });

    paintDone();
    window.addEventListener("hashchange", function () {
      if (leftForQbank()) return;
      show(wanted());
    });
    show(wanted());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
