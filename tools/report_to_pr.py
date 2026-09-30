# -*- coding: utf-8 -*-
"""Turn a reader's report issue into a pull request that flags the question
or note it names.

Purpose: the Report button on a bank question, or on a lecture's note, opens
         a GitHub issue (through tools/report-worker/) with a fenced block
         naming what was reported. This script, run by
         .github/workflows/report-to-pr.yml, finds it, appends a "report"
         flag carrying the reader's note, rebuilds the pages so the site
         fetches the new JSON, and opens the pull request for the maintainer
         to review. A note's flag goes in the lecture's own "flags" list,
         never among its chart blocks, which charts_from_vault.py rewrites.
Author:  Wessam Al Jawhri
Date:    2026-09-28
Input:   ISSUE_NUMBER and ISSUE_BODY in the environment, GH_TOKEN for gh
Output:  a branch report/<issue>, a pull request, a comment on the issue

Run from the repo root. Safe to run twice for one issue: the second run finds
the branch and stops. An issue without the block is not an error; a maintainer
may label a hand-written issue "report" and nothing should break.
"""

import html, io, json, os, re, subprocess, sys

COURSES = ("fom", "pom1", "pom2", "t2c")
REASON_LABEL = {
    "question": {
        "wrong-key": "The answer key is wrong",
        "explanation": "The explanation is wrong or missing",
        "typo": "A typo or formatting problem",
        "misfiled": "It belongs to a different week or lecture",
        "other": "Something else",
    },
    "note": {
        "wrong": "Something in the note is wrong",
        "missing": "Something important is missing",
        "typo": "A typo or formatting problem",
        "misfiled": "It belongs to a different week or lecture",
        "other": "Something else",
    },
}
# the first fenced report block only: the worker breaks any fence a reader
# typed, so a second block can only come from a hand-edited issue, and even
# then it is not the one read
BLOCK_RE = re.compile(r"```report\s*\n(.*?)\n```\s*\n?(.*)", re.S)


def parse_report(body):
    """The first fenced report block and the note under it, or None."""
    m = BLOCK_RE.search(body or "")
    if not m:
        return None
    fields = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        fields[k.strip()] = v.strip()
    if fields.get("course") not in COURSES:
        return None
    if not re.match(r"^[a-z0-9]{1,12}$", fields.get("block", "")):
        return None
    # an issue from before notes had the button names no kind
    kind = fields.setdefault("kind", "question")
    if kind not in REASON_LABEL:
        return None
    if kind == "question":
        if not re.match(r"^[A-Za-z0-9-]{3,80}$", fields.get("qid", "")):
            return None
    else:
        if not re.match(r"^[A-Za-z0-9.-]{3,80}$", fields.get("lecture", "")):
            return None
        fields["name"] = fields.get("name", "").replace(u"\u200b", "")
    if fields.get("reason") not in REASON_LABEL[kind]:
        return None
    rest = m.group(2)
    # the note is what follows the heading, up to the sign-off line if any
    note = rest.split("### What is wrong", 1)[-1]
    note = note.split("\n_Sent from the Report button", 1)[0].strip()
    # the worker put a zero-width space between any backticks; take it out
    fields["note"] = note.replace(u"\u200b", "")
    return fields


def flag_for(kind, reason, note):
    """The flag the question or note gains: the reason's label, then the note
    as escaped paragraphs, so nothing a reader typed is ever markup."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", note.strip()) if p.strip()]
    first = "<p><strong>%s.</strong> %s</p>" % (REASON_LABEL[kind][reason], html.escape(paras[0]) if paras else "")
    rest = "".join("<p>%s</p>" % html.escape(p) for p in paras[1:])
    return {"type": "report", "title": "Reader report", "html": first + rest}


def patch_file(path, qid, flag):
    """Append the flag to the one question; False if the qid is not there."""
    with io.open(path, encoding="utf-8") as f:
        rows = json.load(f)
    hit = [q for q in rows if q.get("qid") == qid]
    if not hit:
        return False
    hit[0].setdefault("flags", []).append(flag)
    # exactly the serialisation the files already use, or the diff is the file
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rows, ensure_ascii=False))
    return True


def patch_note(path, lecture, name, flag):
    """Append the flag to the one lecture; False if it is not there.

    Two lectures in a roster can share an id (fom b1 and pom1 gi each have a
    pair), so the name the page sent picks between them."""
    with io.open(path, encoding="utf-8") as f:
        raw = f.read()
    doc = json.loads(raw)
    hit = [l for w in doc.get("weeks", []) for l in w.get("lectures", []) if l.get("id") == lecture]
    if len(hit) > 1:
        hit = [l for l in hit if l.get("name") == name] or hit
    if not hit:
        return False
    hit[0].setdefault("flags", []).append(flag)
    # the vault builders write these indented and the t2c ones compact; keep
    # whichever the file already is, or the diff is the whole file
    out = json.dumps(doc, ensure_ascii=False, indent=1 if raw.startswith("{\n") else None)
    if raw.endswith("\n"):
        out += "\n"
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    return True


def target_of(r):
    """Where the report points: the file, the id, a word for it, and whether
    the flag went in."""
    flag = flag_for(r["kind"], r["reason"], r["note"])
    if r["kind"] == "note":
        path = os.path.join(r["course"], "data", "notes", "%s.json" % r["block"])
        ok = os.path.exists(path) and patch_note(path, r["lecture"], r["name"], flag)
        return path, r["lecture"], "note", ok
    path = os.path.join(r["course"], "data", "questions", "%s.json" % r["block"])
    ok = os.path.exists(path) and patch_file(path, r["qid"], flag)
    return path, r["qid"], "question", ok


def sh(*args, **kw):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kw).stdout.strip()


def main():
    n = os.environ.get("ISSUE_NUMBER", "").strip()
    body = os.environ.get("ISSUE_BODY", "")
    if not n:
        print("no ISSUE_NUMBER; nothing to do")
        return 0
    r = parse_report(body)
    if not r:
        print("issue #%s carries no report block; nothing to do" % n)
        return 0
    branch = "report/%s" % n
    if subprocess.run(["git", "ls-remote", "--exit-code", "--heads", "origin", branch],
                      capture_output=True).returncode == 0:
        print("branch %s exists; already handled" % branch)
        return 0
    path, ident, thing, ok = target_of(r)
    if not ok:
        sh("gh", "issue", "comment", n, "--body",
           "I could not find %s `%s` in `%s`, so no pull request was opened." % (thing, ident, path))
        return 0
    sh("python3", "tools/build_pages.py")
    sh("git", "config", "user.name", "github-actions[bot]")
    sh("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    sh("git", "checkout", "-b", branch)
    sh("git", "add", "-A")
    title = "Flag %s %s from reader report #%s" % (thing, ident, n)
    sh("git", "commit", "-m", title, "-m",
       "A reader reported this %s from the portal. This adds their note to the "
       "%s as a flag so the maintainer can review it, change the flag's type, "
       "correct the %s, or close the report." % (thing, thing, thing))
    sh("git", "push", "origin", branch)
    fix = ("fix the question itself" if thing == "question" else
           "fix the note in the vault and rebuild, which is where the note is written")
    pr_body = "Closes #%s.\n\n**%s.**\n\n%s\n\nEdit the flag in `%s`, change its `type` to `warning` to add the head tag, or %s before merging." % (
        n, REASON_LABEL[r["kind"]][r["reason"]], r["note"], path, fix)
    # the label may not exist yet, and a failed create after the push would
    # leave the issue with a branch and no pull request forever; --force
    # creates it or updates it and never fails on exists
    sh("gh", "label", "create", "report", "--color", "e4a11b", "--description",
       "A reader's report from the portal's Report button", "--force")
    url = sh("gh", "pr", "create", "--base", "main", "--head", branch, "--title", title,
             "--body", pr_body, "--label", "report")
    sh("gh", "issue", "comment", n, "--body", "Opened %s to flag the %s. Thank you." % (url, thing))
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
