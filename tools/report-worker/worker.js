/* The report relay.

   The portal is static and a browser cannot open a GitHub issue without an
   account, so the bank's Report button posts here instead. This Worker checks
   the report, refuses more than a few a minute from one address, and opens a
   labelled issue with a token that can write issues on this one repository
   and nothing else. The Action in .github/workflows/report-to-pr.yml then
   turns the issue into a pull request. The fenced block at the top of the
   issue body is what that Action parses, so its shape is fixed here and
   read there. COURSES and REASONS are repeated in quiz.js and
   tools/report_to_pr.py, which run elsewhere and cannot import them: change
   all three together. */

const COURSES = ["fom", "pom1", "pom2", "t2c"];
const REASONS = ["wrong-key", "explanation", "typo", "misfiled", "other"];

export function validate(r) {
  if (!r || typeof r !== "object") return "not a report";
  if (r.site !== "preclerkship") return "wrong site";
  if (!COURSES.includes(r.course)) return "unknown course";
  if (!/^[a-z0-9]{1,12}$/.test(r.block || "")) return "bad block";
  if (!/^[A-Za-z0-9-]{3,80}$/.test(r.qid || "")) return "bad qid";
  if (!REASONS.includes(r.reason)) return "unknown reason";
  const note = typeof r.note === "string" ? r.note.trim() : "";
  if (note.length < 3) return "note too short";
  if (note.length > 2000) return "note too long";
  if (typeof r.page !== "string" || r.page.length > 300) return "bad page";
  // the honeypot field, which only a bot fills
  if (r.hp) return "refused";
  return null;
}

/* Three backticks inside the note would end the fenced block early, and a
   crafted note could open a second report block for the Action to read. A
   zero-width space between the backticks keeps the text readable and the
   fence whole. The issue is opened under the token owner's account, so an
   @name in the note would ping that person as if the owner had written it;
   the same space after the @ turns it into plain text. */
function defuse(s) {
  return s.replace(/```/g, "`\u200b`\u200b`").replace(/@(?=[A-Za-z0-9])/g, "@\u200b");
}

export function issueBody(r) {
  return [
    "```report",
    "course: " + r.course,
    "block: " + r.block,
    "qid: " + r.qid,
    "reason: " + r.reason,
    "page: " + r.page,
    "```",
    "",
    "### What is wrong",
    defuse(r.note.trim()),
    "",
    "_Sent from the Report button on the question. The Action opens a pull request that flags the question with this note._",
  ].join("\n");
}

export function corsHeaders(origin, allowed) {
  const list = (allowed || "").split(",").map(s => s.trim()).filter(Boolean);
  if (!origin || !list.includes(origin)) return null;
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "content-type",
    "Vary": "Origin",
  };
}

function reply(status, body, cors) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", ...(cors || {}) },
  });
}

export default {
  async fetch(request, env) {
    const cors = corsHeaders(request.headers.get("origin"), env.ALLOWED_ORIGINS);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: cors ? 204 : 403, headers: cors || {} });
    }
    if (request.method !== "POST" || new URL(request.url).pathname !== "/") {
      return reply(404, { error: "not found" }, cors);
    }
    if (!cors) return reply(403, { error: "origin not allowed" }, null);

    let report;
    try { report = await request.json(); } catch (e) { return reply(400, { error: "not json" }, cors); }
    const bad = validate(report);
    if (bad) return reply(400, { error: bad }, cors);

    const ip = request.headers.get("cf-connecting-ip") || "unknown";
    const { success } = await env.LIMIT.limit({ key: ip });
    if (!success) return reply(429, { error: "too many reports, try again in a minute" }, cors);

    const res = await fetch("https://api.github.com/repos/" + env.REPO + "/issues", {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + env.GITHUB_TOKEN,
        "Accept": "application/vnd.github+json",
        "User-Agent": "preclerkship-report",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        title: "Report: " + report.qid + " (" + report.reason + ")",
        body: issueBody(report),
        labels: ["report"],
      }),
    });
    if (!res.ok) return reply(502, { error: "github said " + res.status }, cors);
    const issue = await res.json();
    return reply(200, { url: issue.html_url }, cors);
  },
};
