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

- **Read** `.agent/` coordination files.
- **Write** `ledger.md`, repairing the rows a dead session left behind.
- **Delete** `.agent/PAUSED` when the user confirms a resume. You never create it — that
  is `pause`.
- **Talk to the user** — the status report, and the question if one is owed.
- **Dispatch subagents**, naming the skill each one must follow. The dispatch table in
  `ai-taskfmt` says which skill does which job.

**Anything not on that list is a dispatch** — above all reading a torn worktree's diff,
which is the single most expensive thing you could do here and the reason `ai-recover`
exists. You are the session that everything resumes from; arriving already full defeats
the purpose of having resumed at all.

## 1. Read state

```
.agent/PAUSED       · paused? when, why, was the tree left clean?
.agent/sessions/    · newest session handoff — context the ledger does not carry
.agent/rune.yml     · initialized? stale? oracle?
.agent/vision.md     · exists? complete?
.agent/decisions.md  · any status: open?
.agent/milestones.md · exists? which is current?
.agent/ledger.md     · task statuses, drift records
.agent/notes/        · handoff notes
```

Cheap reads, all of them. Do not read source. Do not read task files unless you are about
to act on one.

## 2. Reconcile

Per `ai-ledger`. The critical step, and the one that is easy to skip because
everything *looks* fine.

**Every `in_progress` row is a lie** — no executor is holding it; they died with the
session. For each:

1. **Valid complete publication present?** The executor committed the task and appended
   `base_commit` plus `artifact_commit` to its progress file, the task branch still points
   to that artifact, and its worktree is clean. It died after publication but before its
   short return reached the parent. Set the row to `verifying` and dispatch `ai-verify`;
   its artifact preflight proves the remaining invariants. Do not discard it because the
   uncommitted diff is empty — a completed artifact should have an empty diff.
2. **Handoff note present?** The executor stopped deliberately. Follow its
   `worktree: kept|discarded` instruction and set the status it implies — `pending` for a
   budget stop, `drifted` for drift.
3. **No handoff?** The session died mid-flight. Check only whether the worktree's diff is
   empty and whether the task branch is ahead of its merge base with main — both are
   bounded state probes, not source reads:
   - empty diff, branch ahead → keep it and set `pending`. The executor may have died
     between `git commit` and writing the publication block; a fresh executor inspects the
     committed range and either publishes that `HEAD` or resumes the task.
   - empty diff, branch not ahead → discard, set `pending`. Nothing lost.
   - non-empty → work exists but is unexplained. **Dispatch `ai-recover`** as a subagent.
     It maps the diff onto the task's declared steps, decides whether the work is
     salvageable, names the resume point, and writes the handoff the dead executor never
     did. Apply its verdict — `salvage`, `discard`, or `partial` — and record it.

   Do not inspect the diff yourself. Reading it is exactly the code-reading the dispatcher
   is forbidden, and a torn worktree is expensive to read.
4. **No row may remain `in_progress`** when you are done.

Also check:

- orphaned worktrees with no ledger row → remove; if their task commit is already in main,
  delete the merged task branch too
- `verifying` rows whose verifier never returned → re-dispatch
- drift records not yet reflected in the ledger's blocked list
- **`decisions/open/` files with no `awaiting` row** → a worker asked something and the
  session died before it reached the user. Assign the `DEC-nnn`, move it into
  `decisions.md`, set the task `awaiting`, and surface it. This is the self-healing path
  and it is the whole reason those files exist.

## 3. Determine phase and route

| State on disk | Phase | Resume with |
|---|---|---|
| `.agent/PAUSED` present | deliberately stopped | **ask first** — see below |
| no `.agent/` | nothing started | `rune:init`, then `rune:vision` |
| `rune.yml` only | ground mapped, no plan | `rune:vision` |
| `vision.md` partial | interview interrupted | `rune:vision` — from the last settled section |
| vision done, decisions `open` | blocked on the user | present the open decisions |
| decisions done, no milestones | vision unfinished | `rune:vision` — generate milestones |
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

Resume only on a clear yes, and delete `.agent/PAUSED` when you do. If the pause file says
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

**Do not start work in this skill.** Reconcile, report, and hand to `rune:work` or
`rune:vision`. Continue answers *where are we*; the other skills answer *what next*.
