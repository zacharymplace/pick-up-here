# Pick Up Here

A local repository restart assistant: collect bounded facts, ask local Gemma
for one supported inspection, and save enough context to return later.

Current application: **0.1.0-rc.7**, a prototype release candidate.
Evidence packet version 0.6; restart-brief format 1; return-comparison format 1.

## Run

Requires Python 3.10+, Git, and a browser. There are no pip dependencies.
Clone and start the app:

```bash
git clone https://github.com/zacharymplace/pick-up-here.git
cd pick-up-here
python3 app.py --open
```

If you downloaded an archive instead, extract it and run `python3 app.py --open`
from that folder; on macOS you can also open `Start.command`.

Keep Terminal open. Use the printed 127.0.0.1 address. If the port is occupied,
run `python3 app.py --port 8766 --open`. Enter a Git repository root, or use
the native Choose folder button on macOS. Other systems support pasted paths.

## First inspection and example output

1. Start the app with the command above and open the printed local URL.
2. Enter the absolute path to a Git repository you already have on disk. You can
   inspect this clone first; on macOS, **Choose folder** also works.
3. Collect facts and review the evidence before requesting any AI suggestion.
4. Download a restart brief, then reopen it with **Saved restart brief** to try
   the return flow below. No model or API key is needed for these steps.

Expected startup output at the default port:

```text
Pick Up Here 0.1.0-rc.7: http://127.0.0.1:8765
Keep this terminal open. Press Ctrl+C to stop.
```

Use the address actually printed if you selected another port. For a visual
walkthrough, see the [captioned RC.7 demo](demo/rc7-demo-captioned.mp4).
This is a prototype: collecting repository facts does not run its tests or
establish that its software works. Saved briefs can contain private source
excerpts; review them before sharing.

## Local AI

Install and start Ollama, then install the required open-weight model:

```bash
ollama pull gemma3:4b
```

Facts, saving, reopening, and comparison work without a model. The local model
list check does not test inference. AI proposals use local Gemma 3 4B, with no
hosted fallback or API credential. Model weights are not bundled.

## Complete return flow

1. Inspect a repository, optionally with a topic; review the observed facts.
2. Request one local AI inspection if wanted, then inspect its linked evidence.
3. Download a restart brief. Its excerpts may be private; review before sharing.
4. Return later and open that brief using Saved restart brief.
5. Select the repository folder and choose Collect fresh facts and compare.
6. Review the deterministic return summary and literal retained-text changes.
7. Save comparison and evidence to retain both evidence packets and the results.
8. Open that file in Review an exported comparison, even without collecting facts.

Comparison requires local Git ancestry and equal topics/collector versions.
Clones and forks may share ancestry; this is not authenticated ownership.
Missing or rewritten history may block comparison. No remote fetch is attempted.

The separate historical comparison viewer checks payload/packet hashes and
recomputes retained-text counts, lists, and diffs. It never checks out files,
runs Git, collects current facts, or calls AI. Its recorded ancestry remains a
file-supplied claim. Invalid files preserve existing views. Hashes detect
changes but do not authenticate authorship or establish that evidence is true.

## Boundaries

Deterministic collection includes Git metadata, tracked filenames, four note
paths with explicit missing states, bounded source excerpts, and supported
static entrypoint/import leads. Notes and unchecked tasks remain unverified.
The app does not execute repository scripts, tests, imports, or exports.

Gemma selects from allowed action/evidence IDs; validation rejects unsupported
choices and code renders the final wording. AI never supplies repository facts.
Comparison concerns retained excerpts, not all files, runtime behavior, tests,
or live connections. Clipped and one-sided observations stay explicit.

The app listens on loopback. Operations require the exact local origin and a
session token. Active facts and opened briefs are memory-only. Download files
deliberately to retain them; source excerpts can contain private information.

## Verify and status

```bash
cd /path/to/pick-up-here
python3 -m unittest discover -q
python3 app.py --version
```

RC.7: 98 Python tests and 62 Linux Chrome browser checks passed. Three browser
checks use explicitly synthetic boundary responses. Physical Mac acceptance,
full owner-checkout coffee-cad acceptance, and fresh human usefulness remain
pending. This package does not declare stable 0.1.0 or v1.0.

See [the captioned demo](demo/rc7-demo-captioned.mp4) and [submission draft](SUBMISSION.md).
The Mac save/reopen/compare/export/reopen workflow was subsequently confirmed
by the operator. Identical-source names are now always visible in live and
reopened comparison summaries. Browser clipboard checks on macOS confirmed
that plain-text copying retains the names without an expand-before-copy step.
The earlier literal empty-bullet report was not reproduced; other browsers
and paste destinations remain unverified.
MIT application code; Gemma remains subject to its own terms. See ATTRIBUTION.md.
