---
name: ai-investigate
user-invocable: false
description: Use when the request is a question rather than a change - why something is slow, whether an approach is feasible, diagnosis without a fix. Read-only, and terminates in a written answer rather than an implementation.
---

# Investigation protocol

**Governing rule: read-only, and it terminates in an answer.**

The dispatch includes absolute `main_root` plus a parent-assigned `INV-nnn` and exact
absolute staging and final paths. It may also include a reserved `RES-nnn` assignment for
outside evidence. A crash-recovery dispatch may instead include the already recorded RES
final path as a read-only evidence pointer. Investigate that checkout, not the worker's
starting directory, and resolve every coordination write against `main_root`. Never scan
for the next report id or derive an output path yourself.

Before reading source, require the investigation staging path to be
`<main_root>/.rune/notes/open/INV-nnn.md`, the final path to be
`<main_root>/.rune/notes/INV-nnn.md`, and both paths to use the assigned id and be absent.
A missing, relative, mismatched, or occupied assignment is `investigation: blocked`.

This protocol exists because a system that only knows how to make plans will turn "why is
this slow?" into an implementation plan. That is the failure mode it prevents.

## 1. Make the question answerable

Restate the request as a question with a shape that admits an answer.

- "Why is the dashboard slow" → "which operation dominates dashboard load time, and by
  how much"
- "Can we move to Postgres" → "what depends on Mongo-specific behaviour, and what would
  each one cost to change"
- "Is the auth secure" → too broad. Narrow it, or split it into several investigations.

State the question at the top of your output. If your answer does not address the
question you wrote down, you have drifted into something else.

## 2. Gather evidence, not impressions

Read-only. `ai-serena` applies with full force — this protocol is where exploration
sprawl is most likely, because there is no change surface bounding you.

If the question needs evidence from **outside** the repository — prior art, a spec
detail, whether a library is maintained, what other teams found — use exactly one of:

- the reserved `RES-nnn` id and paths: load `ai-research`, follow it for that part, and
  finish its staging report before creating the INV staging candidate
- a recovery `research_evidence` pointer to the already promoted assigned RES final:
  validate its id and report shape, then read it without loading or re-running
  `ai-research`

Do not improvise research or allocate an id yourself. A remembered fact presented as a
looked-up one is exactly the failure both protocols exist to prevent. If neither form was
supplied, return `investigation: blocked` and name that missing pointer before searching.

- Prefer measurement to reading. A profile, a timing, a query count, a row count beats an
  hour of reasoning about which code path looks expensive.
- Cite specifics. `src/api/dashboard.ts :: load — 4 sequential queries, no join` is
  evidence. "The data layer is inefficient" is an impression.
- Look for the thing that would disprove you. If you conclude the bottleneck is the
  database, find the measurement that would show otherwise and check it.

Set a budget before you start and stop when you reach it. Investigations expand to fill
whatever context they are given, and the answer rarely improves past the first solid
finding.

## 3. Running things is allowed. Changing them is not.

You may run the test suite, a profiler, a read-only query, a build. You may create
scratch files **outside** the repo — use the session scratchpad, never the working tree.

You may not: edit source, edit tests, install packages, run migrations, or "just try"
a fix to see if it helps. If a change is required to answer the question, that is a
finding to report — the experiment becomes a proposed task, not something you do.

No worktree. No diff. When you are done the tree is exactly as you found it.

## 4. The answer

Write the complete answer only to the assigned
`<main_root>/.rune/notes/open/INV-nnn.md` staging path. Validate it in a collision-resistant
sibling candidate and atomically install it at staging with no-replace semantics; the
operation must fail if staging exists, and the worker also refuses an existing final. The
parent validates and atomically promotes the unchanged staging file to
`<main_root>/.rune/notes/INV-nnn.md` after return.

```markdown
# INV-004 · Why is dashboard load slow
asked: 2026-08-04
research: RES-007

## Answer
Four sequential Postgres round trips in `src/api/dashboard.ts :: load`, each ~180ms on
the staging dataset. Total 740ms of the observed 900ms. The remaining 160ms is render.

## Evidence
- query log, staging, 50 samples: 4 queries per request, no joins
- dashboard.ts :: load — awaits each fetch in sequence (lines shown in diff below)
- disabling three of the four drops p50 to 210ms

## Confidence
High on the cause. Medium on the fix estimate — the join may be blocked by the tenant
scoping in `db/scope.ts`, which I did not fully trace.

## What I did not check
Production data volumes. Staging is ~1/20th the size; the shape should hold but the
constants will not.

## Proposed next steps  (NOT tasks — nothing is scheduled by this document)
- Collapse the four queries into one join      — likely 3-4x improvement
- Or parallelise them                          — smaller win, much smaller change
```

The `research` disposition is mandatory: use the assigned `RES-nnn`, `unused` when an
assigned companion slot was not needed, or `not-assigned` when none was reserved. An INV
report that names `RES-nnn` is complete only after that RES staging or final report
validates. Four sections are mandatory: **answer, evidence, confidence, what you did not
check.**

The last two are what make an investigation trustworthy. An investigation that reports
uniform certainty over a codebase it sampled is worse than one that names its blind spots
— because the reader cannot tell which parts to re-check.

## 5. Do not schedule work

Proposed next steps are proposals. They do not enter the ledger, do not become task
files, and do not get an id in the `T-` space.

If the user wants them built, that is a separate `rune:work` invocation which will
triage them properly — probably into `ai-feature` or `ai-refactor`, with the
scoping and decision records those protocols require.

The gap between "here is what I found" and "I have begun changing your codebase" is the
entire purpose of this protocol. Do not close it on your own initiative.

## Return (≤200 tokens)

```rune-return
work: INV-004
summary: dashboard load is dominated by four sequential database queries
investigation: answered | blocked
worktree: none
artifact: /workspace/acme/.rune/notes/open/INV-004.md # answered only
companion_research: answered | recorded | unused | blocked # companion slot only
research_task: RES-007                              # companion slot only
research_artifact: /workspace/acme/.rune/notes/open/RES-007.md # answered; final path when recorded
blocker: outside-evidence-unavailable                # blocked only
```

Report the investigation outcome and conditional `companion_research` result independently so the parent can
settle both reservations. `recorded` is only for recovery with a supplied RES final
pointer. If nested research blocks, return both outcomes as `blocked` and the same
objective blocker; if research succeeds but the investigation later blocks, return its RES
artifact as `answered` and only the INV outcome as `blocked`. Return only assigned ids and
paths. Never write a self-selected number or any final report path.
