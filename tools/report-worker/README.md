# The report relay

Every question in the bank carries a **Report this question** button. The
portal is static and a reader without a GitHub account cannot open an issue,
so the button posts the report here instead: a small Cloudflare Worker that
checks the report, refuses more than five a minute from one address, and opens
an issue labelled `report` on the repository with a token that can write
issues there and nothing else. The Action in
`.github/workflows/report-to-pr.yml` then turns that issue into a pull request
that flags the question, so the maintainer reviews a change rather than an
email.

The whole relay is `worker.js`, one file with no dependencies, and
`wrangler.toml` beside it. Until it is deployed the button opens an email to
the address in `tools/portal.py` with the same fields, so nothing is lost by
leaving this step for later.

## Set it up once

1. In GitHub, under Settings > Developer settings > Personal access tokens >
   Fine-grained tokens, create a new token. Repository access: only
   `schulichmed/preclerkship`. Permissions: Issues, Read and write, and
   nothing else. Set the expiry as long as GitHub allows; the relay stops
   working when it lapses and the button falls back to email.
2. `cd tools/report-worker && npx wrangler login` and sign in to the
   Cloudflare account that will own the worker. The free plan is enough.
3. `npx wrangler secret put GITHUB_TOKEN` and paste the token when asked. It
   is stored by Cloudflare, never in this folder.
4. `npx wrangler deploy`. Copy the URL it prints, of the form
   `https://preclerkship-report.<account>.workers.dev`.
5. Put that URL in `REPORT_URL` in `tools/portal.py`, run the three builders
   (`build_pages.py`, `build_index.py`, `build_hub.py`) and commit. Every bank
   page now knows where to post.
6. In the repository's Settings > Actions > General, under Workflow
   permissions, tick "Allow GitHub Actions to create and approve pull
   requests". Without it the Action can flag the question but cannot open the
   pull request.

## Try it

One request from the command line, with the origin the worker allows:

```bash
curl -s -X POST https://preclerkship-report.<account>.workers.dev/ \
  -H 'origin: https://schulichmed.github.io' -H 'content-type: application/json' \
  -d '{"site":"preclerkship","course":"fom","block":"b1","qid":"b1-w1-module-q1-1","num":"1","family":"module","reason":"other","note":"Testing the relay.","page":"","hp":""}'
```

The answer is `{"url": "https://github.com/schulichmed/preclerkship/issues/N"}`
and, a minute later, a pull request against that issue. Close both once you
have seen them arrive.

## Spam, and turning it off

Two things stand between the button and a flood: the rate limit above, and a
hidden field in the dialog that a person never fills but a form-filling bot
does, which the worker refuses silently. Reports are public issues, and the
dialog says so, so there is no contact field to harvest. If spam appears
anyway, Cloudflare Turnstile is the next step: one widget in the dialog and
one check in `worker.js`.

To turn the relay off, set `REPORT_URL` back to `""` in `tools/portal.py`,
run the builders and commit. The button emails instead, and the worker can be
deleted with `npx wrangler delete` at leisure.
