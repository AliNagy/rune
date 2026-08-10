---
name: continue
description: Use when returning to a project in a fresh session, after a crash, or after a cleared context, and you need to know where things stand. Reconciles stale state left by a dead session before reporting anything.
---

# rune:continue

Works out where things stand and resumes. Everything comes from disk; nothing is
remembered.

**Reconcile before reporting.** A ledger left by a dead session contains claims that are
no longer true, and reporting them as status propagates the lie. Repair first.

## What you may do

**You work out where things stand and say so.** Everything you are allowed to do follows
from that, and this list is exhaustive:

- **Run** `git rev-parse --show-toplevel` as the one bounded identity probe.
- **Read** `<main_root>/.agent/` coordination files.
- **Write** `<main_root>/.agent/ledger.md`, repairing the rows a dead session left behind.
- **Delete** `<main_root>/.agent/PAUSED` when the user confirms a resume. You never create it — that
  is `pause`.
- **Talk to the user** — the status report, and the question if one is owed.
- **Dispatch subagents**, naming the skill each one must follow. The dispatch table in
  `ai-taskfmt` says which skill does which job.

Resolve `main_root` once with the bounded probe `git rev-parse --show-toplevel` before
reading state. Resolve every `.agent/...` path against it. Every recovery, verification,
or landing dispatch carries that `main_root`, the absolute `worktree_path` recorded in the
task's ledger row, and absolute coordination pointers.

**Anything not on that list is a dispatch** — above all reading a torn worktree's diff,
which is the single most expensive thing you could do here and the reason `ai-recover`
exists. You are the session that everything resumes from; arriving already full defeats
the purpose of having resumed at all.

## 1. Read state

```
<main_root>/.agent/PAUSED        · paused? when, why, was the tree left clean?
<main_root>/.agent/sessions/     · newest session handoff — context the ledger does not carry
<main_root>/.agent/rune.yml      · initialized? stale? oracle?
<main_root>/.agent/vision.md     · exists? complete?
<main_root>/.agent/decisions.md  · any status: open?
<main_root>/.agent/milestones.md · exists? which is current?
<main_root>/.agent/drafts/       · completed or interrupted decomposition runs?
<main_root>/.agent/ledger.md     · task statuses, drift records
<main_root>/.agent/notes/        · handoff notes
```

Cheap reads, all of them. Do not read source. Do not read task files unless you are about
to act on one.

### Validate or migrate the ledger first

Before treating any row as state, apply `ai-ledger`'s schema validation. `schema: 1` must
validate completely. An unknown schema stops here and is reported.

A ledger with no schema marker is legacy schema 0. Migrate it once, before reconciliation:

1. Read only coordination artifacts. Map each old milestone table row into the canonical
   schema-1 Tasks table; the enclosing milestone heading supplies `milestone`.
2. Derive `d/e/v/l` from durable dispatch rows and numbered diagnosis, verification, and
   landing blocks. Gaps remain counted when a dispatch row exists. Count verifier `fail`
   blocks into `failures`.
3. Point `latest_finding` at the last live verifier, landing, drift, decision, or handoff
   artifact. Derive `blocker` and `resume_at` from the old status plus that artifact.
4. If any required value has two plausible answers, stop and name the row; do not choose.
5. Validate the complete candidate and replace `ledger.md` once; never partially upgrade
   in place.

Only schema 0 has this path. Migration is idempotent because a successful replacement is
schema 1 and later runs validate it instead of migrating again.

## 2. Reconcile

Per `ai-ledger`. The critical step, and the one that is easy to skip because
everything *looks* fine.

**Reconcile `diagnosing` rows before executable tasks.** No immutable task file exists yet,
so never send one to `ai-execute` or `ai-recover`.

- A progress file ending in `diagnosis: reproduced` with valid diagnosis commit ids means
  diagnosis finished and the parent died before planning. Keep the exact worktree and row;
  route `work` back into the same decomposition run.
- `diagnosis: not_reproduced` or `reclassified` means the worker finished but the parent
  did not consume its result. Remove the provisional row, keep the protocol and progress
  artifacts so the id stays burned, and report or reroute as recorded.
- `diagnosis: blocked` keeps the row and worktree. Report the recorded condition and
  re-dispatch only after it has cleared.
- No terminal diagnosis block means the diagnosis worker died. Re-dispatch `ai-bug` with
  the same task id, protocol, progress, `main_root`, and exact `worktree_path`. First
  increment `d`, set `resume_at: diagnose`, validate, and persist; pass the new attempt.
  That skill owns recovery before a task contract exists.

**Every `in_progress` row is a lie** — no executor is holding it; they died with the
session. For each:

1. **Valid complete publication present?** The executor committed the task and appended
   `base_commit` plus `artifact_commit` to its progress file, the task branch still points
   to that artifact, and its worktree is clean. It died after publication but before its
   short return reached the parent. In one update set the row to `verifying`, increment
   `v`, and set `resume_at: verify`; then dispatch `ai-verify` with that attempt and the
   row's exact `worktree_path`. Its artifact preflight proves the remaining invariants. Do
   not discard it because the uncommitted diff is empty — a completed artifact should have
   an empty diff.
2. **Handoff note present?** The executor stopped deliberately. Follow its
   `worktree: kept|discarded` instruction and set the complete state it implies —
   `pending` plus its resume token for budget; `drifted`, drift blocker, and `replan` for
   drift; `blocked` plus its external blocker, finding pointer, and resume token for a
   recorded external condition.
3. **No handoff?** The session died mid-flight. At the ledger's exact absolute
   `worktree_path`, check only whether the worktree's diff is
   empty and whether the task branch is ahead of its merge base with main — both are
   bounded state probes, not source reads:
   - empty diff, branch ahead → keep it and set `pending`, `resume_at: publish`. The executor may have died
     between `git commit` and writing the publication block; a fresh executor inspects the
     committed range and either publishes that `HEAD` or resumes the task. For a diagnosed
     bug, `diagnosis_commit` alone is only the starting baseline and must never be published.
   - empty diff, branch not ahead → discard, set `pending`, `resume_at: fresh`. Nothing lost.
   - non-empty → work exists but is unexplained. **Dispatch `ai-recover`** with the same
     `main_root`, exact `worktree_path`, and absolute task/progress pointers.
     It maps the diff onto the task's declared steps, decides whether the work is
     salvageable, names the resume point, and writes the handoff the dead executor never
     did. Apply its verdict — `salvage`, `discard`, or `partial` — copy its schema token to
     `resume_at`, and point `latest_finding` at the handoff.

   Do not inspect the diff yourself. Reading it is exactly the code-reading the dispatcher
   is forbidden, and a torn worktree is expensive to read.
4. **No row may remain `in_progress`** when you are done.

Also check:

- orphaned worktrees with no ledger row → remove; if their task commit is already in main,
  delete the merged task branch too
- `verifying` rows whose verifier never returned → first check for a durable block matching
  the row's current `v`; consume it with the same complete mapping as `work` (including
  `failures++` only for `fail`, the finding pointer, and the returned dispatch row) if
  present. Otherwise increment `v`, persist, and
  re-dispatch that attempt against the row's exact `worktree_path`; never create a fresh
  verifier checkout
- `landing` rows whose lander never returned → first consume a durable block matching the
  current `l` with `work`'s complete outcome mapping when present. Otherwise, if `l` is
  below five, increment it, persist, and
  re-dispatch that attempt against the same verified artifact and exact worktree. At `l5`,
  stop and surface the exhausted landing ceiling rather than creating attempt six
- drift records not yet reflected in the ledger's blocked list
- decomposition runs with a protocol record or planner drafts but no registered tasks →
  keep the immutable artifacts, mark the attempt interrupted in the dispatch log, and
  route back to `work`. It allocates a fresh `R-nnn`; never resume into or reuse the
  interrupted run's paths. The exception is a reproduced `diagnosing` bug reservation:
  its protocol, diagnosis, and worktree are one bound input, so resume that same run.
- **`decisions/open/` files with no `awaiting` row** → a worker asked something and the
  session died before it reached the user. Assign the `DEC-nnn`, move it into
  `decisions.md`, set the task `awaiting`, store `decision:DEC-nnn`, point at the decision
  record, preserve the handoff's resume token, and surface it. This is the self-healing path
  and it is the whole reason those files exist.

## 3. Determine phase and route

| State on disk | Phase | Resume with |
|---|---|---|
| `<main_root>/.agent/PAUSED` present | deliberately stopped | **ask first** — see below |
| no `<main_root>/.agent/` | nothing started | `rune:init`, then `rune:vision` |
| `rune.yml` only | ground mapped, no plan | `rune:vision` |
| `vision.md` partial | interview interrupted | `rune:vision` — from the last settled section |
| vision done, decisions `open` | blocked on the user | present the open decisions |
| decisions done, no milestones | vision unfinished | `rune:vision` — generate milestones |
| task `diagnosing` | bug reproduction or planning interrupted | reconcile diagnosis, then `rune:work` |
| protocol record or planner drafts, no registered tasks | planning interrupted | `rune:work` — allocate a fresh draft run |
| milestones, none decomposed | ready to work | `rune:work` — decompose M-01 |
| tasks pending | mid-milestone | `rune:work` — next available task |
| tasks `blocked` by drift | plan needs repair | `rune:work` — re-decompose remainder |
| all milestones done | v1 reached | report; ask what is next |

### Resuming from a pause

A pause is a decision someone made. Never lift it as a side effect of being asked for
status.

Reconcile as normal, report where things stand, then state the pause and **ask**:

```
TL;DR
- Work is paused. You stopped it 3 days ago — "heading into a meeting".
- The tree was left clean: everything in flight merged before it stopped.
- 2 tasks still queued for M-03. Want me to pick them up?
```

Resume only on a clear yes, and delete `<main_root>/.agent/PAUSED` when you do. If the pause file says
the tree was left dirty, say what is dangling before asking — the user may want to deal
with it themselves rather than have an executor inherit it.

### Resuming a vision interview

Do not restart it. Read `vision.md` for what is settled and `decisions.md` for what is
open, then continue from the first unanswered topic. Re-asking questions the user already
answered is the fastest way to lose their patience with the system.

Summarise what was settled in two or three lines so they can correct you, then carry on.

## 4. Report

Follow `ai-report`. Say what was **repaired**, not just what exists — silent repair looks
like nothing happened, and the user needs to know work was thrown away.

```
TL;DR
- Back on M-03, session lifecycle. 2 of 4 tasks done.
- Cleaned up after the last session: T-016 died mid-edit, its work was discarded.
- Need you: the plan assumed one entry point into session handling, there are two.

Repaired
- T-016 was marked in progress with nobody working on it. 40 lines of unexplained
  changes, no notes — discarded, back in the queue.
- T-018 was missing that it depends on the same problem. Recorded.

Where things stand
  done       T-014 rotate tokens · T-015 refresh endpoint
  queued     T-016 restart persistence
  waiting    T-017, T-018

Tests pass. No decisions outstanding.

The problem: handle() is called from two places, not one. T-016 assumed one.
Re-split the rest of M-03, or retry T-016 as written?
```

## Rules

**Never guess at intent.** If the ledger and the worktrees disagree and no handoff
explains it, say so and ask. Inventing a plausible history is how a corrupted ledger
becomes permanent.

**Discard freely.** Under Serena, re-acquiring a working set is a handful of symbol
lookups. Partial work of unknown provenance is worth less than the clean base it is
occupying, and the task file — not the worktree — was always the durable state.
For a diagnosed bug, the committed reproduction and progress block are also durable state:
discard later implementation freely, but preserve `diagnosis_commit` as the task baseline.

**Do not start work in this skill.** Reconcile, report, and hand to `rune:work` or
`rune:vision`. Continue answers *where are we*; the other skills answer *what next*.
