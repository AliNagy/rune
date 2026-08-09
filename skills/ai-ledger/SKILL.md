---
name: ai-ledger
user-invocable: false
description: Use when reading or updating .agent/ledger.md, or resuming work whose prior session ended unexpectedly. Covers status transitions, task claiming, drift-driven invalidation, and crash reconciliation.
---

# Ledger operations

`.agent/ledger.md` holds **all** mutable state. One writer: the parent — the same parent
across every route, per `ai-taskfmt`. Workers never touch it; they report, the parent
records.

**This skill owns what the statuses mean and what the file looks like. The routes own the
procedures.** Recovery belongs to `continue`, the landing loop to `work`, and the merge
itself to `ai-land`. Where this file used to
restate them, it had already drifted out of step with both — so it now states the mapping
and points at the owner.

## Shape

```markdown
# Ledger

vision: complete            # absent | drafting | complete
current_milestone: M-03
oracle: npm test            # or: none (degraded)
main: green                 # green | red — red halts all dispatch. only ai-land sets it

## M-03 · Session lifecycle   [decomposed]

| id    | title                        | status      | blocked_by | worktree        |
|-------|------------------------------|-------------|------------|-----------------|
| T-011 | TokenStore interface         | done        | —          | merged          |
| T-014 | Rotate refresh tokens        | in_progress | —          | .wt/T-014       |
| T-015 | Refresh endpoint             | pending     | T-014      | —               |
| T-016 | Session restart persistence  | drifted     | —          | discarded       |

## Drift
- DRF-003 (from T-016) invalidates: T-018, T-019 — awaiting re-plan

## Dispatches
| phase       | followed      | for               | outcome                         |
|-------------|---------------|-------------------|---------------------------------|
| survey      | ai-survey     | —                 | map.md written                  |
| commands    | ai-oracle     | —                 | oracle: npm test                |
| plan-draft  | ai-decompose  | M-03/R-002/P-01   | draft: P-01.md                  |
| plan-draft  | ai-decompose  | M-03/R-002/P-02   | draft: P-02.md                  |
| reconcile   | ai-decompose  | M-03/R-002        | T-014..T-017 written            |
| execute     | ai-execute    | T-014             | done @ 4a91c02                  |
| verify      | ai-verify     | T-014             | pass @ 4a91c02                  |
| land        | ai-land       | T-014             | landed @ 4a91c02                |
```

## Log every dispatch

**Every subagent you dispatch gets a row in `## Dispatches`.** One line, written when it
returns.

The point is not the audit trail — it is that the absence becomes visible. Expensive work
done in the parent leaves no dispatch row, so a phase that completed with no rows against
it did that work in the context the whole system exists to protect. That is the failure
this section is built to expose, and it is otherwise almost impossible to notice: the
files all exist, the ledger looks healthy, and nothing anywhere says who wrote them.

Read it as a checklist with teeth:

- reconciled task files with no `ai-decompose` planner and reconciler rows → the parent
  skipped the durable fan-out or wrote the task files.
- `commands` with no `ai-oracle` row → the parent ran the suite.
- `survey` with no `ai-survey` row → the parent read the codebase.

Each of those was a real defect in Rune before this table existed. Keep the rows short;
detail belongs in the notes the subagents themselves write.

## Status transitions

```
pending ─claim─> in_progress ─report─> verifying ─pass─> landing ─landed─> done
                      │                    │                │
                      │                    │                └─refused───> pending
                      │                    │                  conflict     (worktree kept)
                      │                    │                  reverted
                      │                    └─fail──────────> pending (attempt++)
                      ├─drift────────────> drifted
                      ├─budget───────────> pending (handoff written)
                      └─question─────────> awaiting (open decision recorded)
```

- `pending` — available, provided `blocked_by` is empty or all resolved
- `in_progress` — an executor holds it. Records which, and its worktree path
- `verifying` — executor published a commit; awaiting an independent check of that artifact
- `landing` — the published commit was independently verified; a lander is merging that
  exact SHA into the main tree. Worktree kept
- `done` — verified by a *different* agent **and** landed without breaking the main tree.
  Never self-declared, and never set straight off a `pass`
- `drifted` — the plan was wrong; a drift record exists; downstream may be invalid
- `awaiting` — blocked on a user decision. Names the `DEC-nnn`; worktree kept
- `blocked` — cannot proceed for an external reason, stated in the row

`landing` exists because passing verification and surviving the merge are two separate
claims, and there was previously no state between them — so a task that had landed and
broken the build was indistinguishable from one that had never been tried.

Only the parent writes these. A task is never `done` because the executor said so — it is
done only after `ai-verify` names the published commit and `ai-land` lands that same SHA.

`awaiting` returns to `pending` the moment its decision is marked `decided`. A fresh
executor picks it up with the handoff, the worktree diff, and the resolved decision.

## Claiming

Pick the lowest-id `pending` task whose `blocked_by` are all `done`.

### Claiming several at once

Multiple tasks may run concurrently, each in its own worktree, when **their change
surfaces share no files**. That is the whole condition, and it is checkable — every task
declares its surface, so compare the lists.

- Cap concurrent executors at **3**. Beyond that, merge and cost overhead outweighs the
  wall-clock win.
- Record every holder in its row. Two rows may be `in_progress` at once; each names its
  own worktree.
- If all eligible tasks overlap, run one. Serial is the fallback, not a failure.

**The landing procedure lives in `work`; the merge itself lives in `ai-land`.** Here, only
what a landing does to a row:

| `ai-land` returned | Row |
|---|---|
| `landed` | `done`, worktree removed or cleanup `pending` as returned |
| `refused`, `conflict`, or `reverted` | `pending`, worktree **kept**, attempt++ |
| `stuck` | `blocked`, and set `main: red` at the top of the file |

Earlier landings that succeeded stay landed — one task that could not land is not a reason
to unwind the ones that did. What does **not** stay is the merge that failed: `ai-land`
rolls that one back before it returns, so `pending` here always means the main tree is
genuinely free of it.

That is the distinction the old rule got wrong. "Already-applied merges stay" is right for
a conflict, where nothing was applied — and wrong for a failed oracle, where the merge that
just broke the build *is* one of the already-applied merges.

**`main: red` halts dispatch.** No task is claimed, no batch starts, nothing lands while
that flag is set. It is cleared by a human, not by the next agent that finds it
inconvenient.

## Crash reconciliation — what the verdicts mean

A task marked `in_progress` with no live executor is a lie. Nobody is working on it.

**The procedure lives in `continue`.** It dispatches `ai-recover` and hands you a verdict.
You record it. **Never inspect a worktree diff yourself** — that is unbounded reading in
the one context that must stay small, and it is why the recovery dispatch exists.

Your job is the mapping:

| What comes back | Status | Worktree |
|---|---|---|
| valid complete publication, executor return missing | `verifying` | kept; dispatch `ai-verify` |
| handoff note says `budget` | `pending` | kept |
| handoff note says `drift` | `drifted` | per the note |
| `ai-recover` → `salvage` | `pending`, resume point in the row | kept |
| `ai-recover` → `partial` | `pending`, note that the test must be redone red-first | kept |
| `ai-recover` → `discard` | `pending` | dropped |
| empty diff, branch ahead, no publication | `pending` | kept; executor recovers the committed range |
| empty diff, branch not ahead, no note | `pending` | dropped |

**A row left at `landing` is the dangerous one.** A dead lander may have merged and never
rolled back, so the main tree is in a state nobody recorded. Re-dispatch `ai-land` on that
task rather than looking: it reads the durable `verified_commit`, detects whether that
exact SHA is already an ancestor of main, and runs the oracle instead of creating an empty
merge. That is the same artifact and the same gate the live case uses.

**No row may remain `in_progress` or `landing`** when reconciliation ends. That is the one
invariant this section guarantees.

## Drift invalidation

When a drift record lands, downstream tasks may now be wrong. The parent must:

1. Record `DRF-nnn` in the ledger with the tasks it names as invalidated.
2. Set those tasks to `blocked`, referencing the drift id.
3. Refuse to dispatch them until re-planned.

Do not silently delete invalidated tasks. The drift record plus the tasks it killed is
the evidence that the milestone decomposition was wrong, and that evidence is what
improves the next decomposition.

## Reporting

`rune:continue` and `rune:work` read the ledger to answer: what is done, what is
available, what is blocked and on what, and whether anything needs a human decision.

Read it from disk each time. Never carry ledger state in context across dispatches — a
stale in-memory copy is exactly how the parent ends up dispatching a task someone else
already finished.
