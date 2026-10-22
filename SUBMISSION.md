<!-- Suggested title: Pick Up Here: Stop Relearning Your Own Repositories -->
<!-- Tags to review before publishing: devchallenge, hf26challenge -->

This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19).

## What I Built

**Pick Up Here** is a local repository restart assistant for the moment when
you open an old project and think, “Where was I?”

Choose a Git repository and optionally a topic. The app collects bounded facts,
then local Gemma chooses one inspection supported by that evidence. You can open
the exact source text before deciding whether the suggestion helps.

The effort I want to save is repeated context gathering: reading the same notes,
finding the same script, and reconstructing the same entrypoint. Early suggestions
were too generic. A real Mac trial helped somewhat but still pointed at introductory
README text. That pushed the build toward static entrypoint discovery, including
one named Python re-export hop to an implementation declaration.

It also remembers responsibly. Save a brief, reopen it later, and collect fresh
facts for a deterministic comparison. A compact summary distinguishes changed
retained text, identical excerpts, one-sided observations, and comparison limits.
Export both evidence sets with the results, then reopen that package in a separate
read-only historical viewer that checks integrity and recomputes the comparison.

## Demo

[Watch the captioned RC.7 demo](https://raw.githubusercontent.com/zacharymplace/pick-up-here/main/demo/rc7-demo-captioned.mp4).

The accompanying RC.7 recording uses a synthetic Workshop repository and a real
local Gemma call. It shows facts → supported proposal → save brief → reload and
reopen → collect and compare → export comparison → reload and review historical
evidence. The demo harness appends a README line to represent a later session;
the application does not edit the project. No private project source is shown.
The captioned edit shortens the real inference wait by 33.5 seconds and labels
that cut; the unedited 61.84-second recording is retained with the evidence.

## Code

[Source code on GitHub](https://github.com/zacharymplace/pick-up-here).

Candidate **0.1.0-rc.7** uses Python's standard library and plain HTML/CSS/JavaScript.
Run it locally with Python and Git. Ollama with `gemma3:4b` supplies optional local
interpretation; facts, exports, reopening, and comparison do not need AI.

## How I Built It

Repository facts are deterministic. The collector records Git metadata, tracked
filenames, an explicit inventory of four note paths, bounded source excerpts,
and supported static script/import leads. Missing notes remain missing; notes
and unchecked tasks do not become proof of completion. No project script, test,
import, or export is executed.

Gemma selects allowed action/evidence IDs. A validator rejects unsupported
choices, and code renders the final wording. The model cannot introduce a new
filename, command, or completion claim. Comparison uses retained literal text
without a model, and current comparison requires verified local Git ancestry.

The candidate passed 98 Python tests and 62 Linux Chrome browser checks, including
three synthetic boundary checks. The refreshed demo is a supplementary run,
separate from the earlier seven-input RC.1 live qualification. That qualification
preserved an original 6/7 report and a corrected 7/7 assessment after a citation-check
bug in the harness; it did not change the model responses. These are bounded
technical checks, not proof of general usefulness. The Mac save/reopen/compare/
export/reopen workflow subsequently passed an operator-run no-change test.
A fresh usefulness judgment remains pending, and empty source-list bullets in
copied output remain unresolved. I have not measured time saved.

## Why Does Open Innovation Matter?

Gemma's open weights let the interpretation step run locally through Ollama.
Once installed, it has no hosted inference dependency, API credential, or hosted
fallback. Repository excerpts can stay on the computer running the app.

The collector and validator are inspectable source, so the boundary between
observation and interpretation can be reviewed and maintained. Local weights
make an offline workflow possible without replacing that evidence boundary with
trust in generated prose.

The application is MIT licensed. Gemma is open-weight under its own terms;
model weights are not included or relicensed by the project.

## Prize Categories

**Best Use of Gemma** — Gemma 3 4B performs the local prioritization step by
selecting an evidence-supported inspection. Deterministic code supplies the
candidates, validates the selection, and renders the result.
