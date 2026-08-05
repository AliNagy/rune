---
name: continue
description: Use when returning to a project in a fresh session, after a crash, or after a cleared context, and you need to know where things stand. Reconciles stale state left by a dead session before reporting anything.
---

# rune:continue

Works out where things stand and resumes. Everything comes from disk; nothing is
remembered.

**Reconcile before reporting.** A ledger left by a dead session contains claims that are
no longer true, and reporting them as status propagates the lie. Repair first.

## 1. Read state

```
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

1. **Handoff note present?** The executor stopped deliberately. Follow its
   `worktree: kept|discarded` instruction and set the status it implies — `pending` for a
   budget stop, `drifted` for drift.
2. **No handoff?** The session died mid-flight. Inspect the worktree:
   - empty `git diff` → discard, set `pending`. Nothing lost.
   - non-empty → work exists but is unexplained. **Default to discard and reset to
     `pending`.** A fresh attempt from a clean base is cheaper and safer than asking the
     next executor to reverse-engineer an abandoned edit. Keep only if the diff is large
     and coherent — and say so.
3. **No row may remain `in_progress`** when you are done.

Also check: orphaned worktrees with no ledger row (remove), `verifying` rows whose
verifier never returned (back to `verifying`, re-dispatch), and drift records not yet
reflected in the ledger's blocked list.

## 3. Determine phase and route

| State on disk | Phase | Resume with |
|---|---|---|
| no `.agent/` | nothing started | `rune:init`, then `rune:vision` |
| `rune.yml` only | ground mapped, no plan | `rune:vision` |
| `vision.md` partial | interview interrupted | `rune:vision` — from the last settled section |
| vision done, decisions `open` | blocked on the user | present the open decisions |
| decisions done, no milestones | vision unfinished | `rune:vision` — generate milestones |
| milestones, none decomposed | ready to work | `rune:work` — decompose M-01 |
| tasks pending | mid-milestone | `rune:work` — next available task |
| tasks `blocked` by drift | plan needs repair | `rune:work` — re-decompose remainder |
| all milestones done | v1 reached | report; ask what is next |

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
