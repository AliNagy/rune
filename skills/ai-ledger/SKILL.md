---
name: ai-ledger
user-invocable: false
description: Use when reading or updating .agent/ledger.md, or resuming work whose prior session ended unexpectedly. Covers status transitions, task claiming, drift-driven invalidation, and crash reconciliation.
---

# Ledger operations

`.agent/ledger.md` holds **all** mutable state. One writer: the parent / dispatcher.
Executors never touch it — they report, the parent records.

## Shape

```markdown
# Ledger

vision: complete            # absent | drafting | complete
current_milestone: M-03
oracle: npm test            # or: none (degraded)

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
| phase       | followed      | for   | outcome            |
|-------------|---------------|-------|--------------------|
| survey      | ai-survey     | —     | map.md written     |
| commands    | ai-oracle     | —     | oracle: npm test   |
| decompose   | ai-decompose ×3| M-03 | 4 tasks, cut agreed|
| execute     | ai-execute    | T-014 | done               |
| verify      | ai-verify     | T-014 | pass               |
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

- `decompose` with no `ai-decompose` row → the parent wrote the task files.
- `commands` with no `ai-oracle` row → the parent ran the suite.
- `survey` with no `ai-survey` row → the parent read the codebase.

Each of those was a real defect in Rune before this table existed. Keep the rows short;
detail belongs in the notes the subagents themselves write.

## Status transitions

```
pending ──claim──> in_progress ──report──> verifying ──pass──> done
                        │                      │
                        │                      └──fail──> pending (attempt++)
                        ├──drift────> drifted
                        ├──budget───> pending (handoff written)
                        └──question─> awaiting (open decision recorded)
```

- `pending` — available, provided `blocked_by` is empty or all resolved
- `in_progress` — an executor holds it. Records which, and its worktree path
- `verifying` — executor reported success; awaiting an independent check
- `done` — verified by a *different* agent in a clean context. Never self-declared
- `drifted` — the plan was wrong; a drift record exists; downstream may be invalid
- `awaiting` — blocked on a user decision. Names the `DEC-nnn`; worktree kept
- `blocked` — cannot proceed for an external reason, stated in the row

Only the parent writes these. A task is never `done` because the executor said so —
only because `ai-verify` confirmed it.

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

Merge completed tasks **one at a time**, and re-run the project checks after each. Disjoint
file lists rule out textual conflicts but not semantic ones — one task can rename something
another calls without either touching the other's files.

A task whose merge conflicts or breaks the checks goes back to `pending` with a note that
the ground moved. Already-applied merges stay; do not unwind a whole batch for one.

## Crash reconciliation

A task marked `in_progress` with no live executor is a lie. Nobody is working on it.
This is the most common way a ledger stops describing reality, and `rune:continue`
must repair it rather than merely report it.

For each `in_progress` row:

1. **Is there a handoff note?** (`notes/T-nnn.md`) If yes, the executor stopped
   deliberately — follow its `worktree: kept|discarded` instruction and set the status
   it implies (`pending` for budget stops, `drifted` for drift).
2. **No handoff?** The session died mid-flight. Inspect the worktree:
   - `git diff` empty → discard the worktree, set `pending`. Nothing was lost.
   - `git diff` non-empty → the work is real but unexplained. Default to **discard and
     reset to `pending`**; a fresh attempt from a clean base is cheaper and safer than
     asking the next executor to reverse-engineer an abandoned edit. Keep it only if the
     diff is large and coherent, and say so in the row.
3. **Never leave a row `in_progress`** at the end of reconciliation.

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
