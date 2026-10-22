This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19).

## What I Built

Every time I return to an unfinished repository, I pay the same context tax: rereading notes and finding the code I meant to inspect. **Pick Up Here** gathers bounded repository evidence and asks local Gemma to choose one supported inspection. I can check its sources before deciding what to do next.

Choose a Git repository and optionally a topic. Early suggestions were too generic; a Mac trial pushed the build toward static entrypoint discovery, including one named Python re-export hop to an implementation declaration.

Save a brief, reopen it later, and collect fresh facts for a deterministic comparison. A compact summary distinguishes changed retained text, identical excerpts, one-sided observations, and comparison limits. Export both evidence sets with the results, then reopen that package in a separate read-only historical viewer that checks integrity and recomputes the comparison.

## Demo

<video controls preload="metadata" src="https://github.com/zacharymplace/pick-up-here/raw/refs/heads/main/demo/rc7-demo-captioned.mp4"></video>

[Download the captioned RC.7 demo](https://github.com/zacharymplace/pick-up-here/blob/main/demo/rc7-demo-captioned.mp4) using **Download raw file**.

The accompanying RC.7 recording uses a synthetic Workshop repository and a real local Gemma call. It shows facts → supported proposal → save brief → reload and reopen → collect and compare → export comparison → reload and review historical evidence. The demo harness appends a README line to represent a later session; the application does not edit the project. No private project source is shown. The captioned edit shortens the real inference wait by 33.5 seconds and labels that cut; the unedited 61.84-second recording is retained with the evidence.

## Code

[Source code on GitHub](https://github.com/zacharymplace/pick-up-here).

Candidate **0.1.0-rc.7** uses Python's standard library and plain HTML/CSS/JavaScript. Run it locally with Python and Git. Ollama with `gemma3:4b` supplies optional local interpretation; facts, exports, reopening, and comparison do not need AI.

## How I Built It

Repository facts are deterministic. The collector records Git metadata, tracked filenames, an explicit inventory of four note paths, bounded source excerpts, and supported static script/import leads. Missing notes remain missing; notes and unchecked tasks do not become proof of completion. No project script, test, import, or export is executed.

Gemma selects allowed action/evidence IDs. A validator rejects unsupported choices, and code renders the final wording. The model cannot introduce a new filename, command, or completion claim. Comparison uses retained literal text without a model, and current comparison requires verified local Git ancestry.

RC.7 passed 98 Python tests and 62 Linux Chrome browser checks; an operator-run Mac test also completed the save → reopen → compare → export → reopen workflow without repository changes. These are bounded technical checks, not proof of general usefulness. The [validation notes](https://github.com/zacharymplace/pick-up-here/blob/main/RELEASE-STATUS.md) preserve the earlier live-qualification harness correction and remaining gaps, including unresolved empty bullets in copied output. Fresh usefulness review is pending; time saved has not been measured.

## Why Does Open Innovation Matter?

Gemma's open weights let the interpretation step run locally through Ollama. Once installed, it has no hosted inference dependency, API credential, or hosted fallback. Repository excerpts can stay on the computer running the app.

The collector and validator are inspectable source, so the boundary between observation and interpretation can be reviewed and maintained. Local weights make an offline workflow possible without replacing that evidence boundary with trust in generated prose.

The application is MIT licensed. Gemma is open-weight under its own terms; model weights are not included or relicensed by the project.

## Prize Categories

**Best Use of Gemma** — Gemma 3 4B performs the local prioritization step by selecting an evidence-supported inspection. Deterministic code supplies the candidates, validates the selection, and renders the result.
