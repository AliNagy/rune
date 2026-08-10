---
name: ai-ledger
user-invocable: false
description: Use when reading or updating .rune/ledger.md, or resuming work whose prior session ended unexpectedly. Covers status transitions, task claiming, drift-driven invalidation, and crash reconciliation.
---

# Ledger operations

`.rune/ledger.md` holds **all authoritative mutable routing state**. Detailed worker
evidence lives in sole-writer note files, but the counters and pointers that determine the
next action live here. One writer: the parent — the same parent across every route, per
`ai-taskfmt`. Workers never touch it; they report, the parent records.

**This skill owns what the statuses mean and what the file looks like. The routes own the
procedures.** Recovery belongs to `continue`, the landing loop to `work`, and the merge
itself to `ai-land`. Where this file used to
restate them, it had already drifted out of step with both — so it now states the mapping
and points at the owner.

## Shape

```markdown
# Ledger

schema: 1
vision: complete
current_milestone: M-03
oracle: npm test
main: green

## Tasks

| id | milestone | title | status | blocked_by | worktree | attempts | failures | latest_finding | blocker | resume_at |
|---|---|---|---|---|---|---|---|---|---|---|
| T-011 | M-03 | TokenStore interface | done | — | merged | d0/e1/v1/l1 | 0 | — | — | — |
| T-013 | M-03 | Diagnose refresh regression | diagnosing | — | /workspace/acme/.rune/worktrees/T-013 | d1/e0/v0/l0 | 0 | — | — | plan:M-03/R-002 |
| T-014 | M-03 | Rotate refresh tokens | in_progress | — | /workspace/acme/.rune/worktrees/T-014 | d0/e2/v1/l0 | 1 | .rune/notes/T-014.verify.md#attempt-1 | — | recover |
| T-015 | M-03 | Refresh endpoint | pending | T-014 | — | d0/e0/v0/l0 | 0 | — | — | fresh |
| T-016 | M-03 | Session restart persistence | blocked | — | discarded | d0/e1/v0/l0 | 0 | .rune/drift/DRF-003.md | drift:DRF-003 | replan |
| T-017 | M-03 | Expiry sweep | blocked | — | /workspace/acme/.rune/worktrees/T-017 | d0/e1/v0/l0 | 0 | .rune/notes/T-017.md | external:registry-unreachable | step:2 |

## Drift
- DRF-003 (from T-016) invalidates: T-018, T-019 — awaiting re-plan

## Dispatches
| phase       | followed      | for               | outcome                         |
|-------------|---------------|-------------------|---------------------------------|
| survey      | ai-survey     | —                 | map.md written                  |
| commands    | ai-oracle     | —                 | oracle: npm test                |
| diagnose    | ai-bug        | T-013             | reproduced @ b7a03d4           |
| plan-draft  | ai-decompose  | M-03/R-002/P-01   | draft: P-01.md                  |
| plan-draft  | ai-decompose  | M-03/R-002/P-02   | draft: P-02.md                  |
| reconcile   | ai-decompose  | M-03/R-002        | T-014..T-017 written            |
| execute     | ai-execute    | T-014             | done @ 4a91c02                  |
| verify      | ai-verify     | T-014             | pass @ 4a91c02                  |
| land        | ai-land       | T-014             | landed @ 4a91c02                |
```

`schema: 1` is mandatory. A ledger with no schema marker is legacy schema 0; `continue`
migrates it before any route dispatches work. An unknown schema is a hard stop, never a
best-effort parse.

There is one `## Tasks` table for the whole ledger. Milestone membership is a field rather
than a heading so every task has one self-contained state record. The columns are exact and
ordered; adding an ad-hoc column creates a new schema version rather than an optional fact
that some readers ignore.

### Task fields

- `id`, `milestone`, `title`, `status`, and `blocked_by` identify the immutable task and
  its dependency state. `blocked_by` is `—` or a comma-separated list of `T-nnn` ids.
  Table values may not contain `|`; longer wording belongs in the task or note artifact.
- `worktree` is `—`, an absolute path, `discarded`, or `merged`. A live worktree is always
  recorded by path; `kept` is a worker return value, never a ledger value.
- `attempts` is `dN/eN/vN/lN`: diagnosis, executor, verifier, and lander dispatches. The
  parent increments the relevant counter in the same update that claims the phase, before
  dispatch. A dead worker therefore still consumed an attempt and is visible after a crash.
- `failures` counts verifier `fail` verdicts only. This is the durable input to the
  two-failure stop rule; `unverified`, landing failures, and dead dispatches do not increase
  it.
- `latest_finding` is `—` or a coordination-relative pointer such as
  `.rune/notes/T-014.verify.md#attempt-1`. The detail remains in its sole-writer artifact;
  the ledger carries the pointer needed to find it without duplicating prose.
- `blocker` is `—`, `decision:DEC-nnn`, `drift:DRF-nnn`, `external:<slug>`, or `main:red`.
  Dependency ids stay in `blocked_by`; this field is only for a task's live non-dependency
  blocker. An external blocker requires `latest_finding` to point at a handoff containing
  both `blocker_reason` and `unblocks_when`.
- `resume_at` is the next durable action: `—`, `diagnose`, `plan:M-nn/R-nnn`, `fresh`,
  `recover`, `step:N`, `evidence:<mode>`, `publish`, `verify`, `land`, or `replan`.
  Details belong in the artifact named by `latest_finding`; this field stays a stable token.

Every live task worktree value is an absolute path. The parent allocates
`<main_root>/.rune/worktrees/T-nnn`, writes it into the row before dispatching the first
task-bound worker, and keeps that value unchanged through diagnosis, retries, verification,
recovery, and landing. `discarded` and `merged` may replace it only when the path no longer
contains live task state.

## Required fields by status

| status | Required state |
|---|---|
| `diagnosing` | absolute worktree; `d >= 1`; resume is `diagnose` or the bound `plan:M-nn/R-nnn`; blocker is `—` or `external:*` |
| `pending` | blocker `—`; resume is `fresh`, `step:N`, `evidence:<mode>`, or `publish`; a missing worktree is valid only with `fresh`; partial step/evidence resumes require a finding pointer |
| `in_progress` | absolute worktree; `e >= 1`; blocker `—`; resume `recover` |
| `verifying` | absolute worktree; `e >= 1`, `v >= 1`; blocker `—`; resume `verify` |
| `landing` | absolute worktree; `v >= 1`, `l >= 1`; blocker `—`; resume `land` |
| `done` | worktree `merged` or an absolute cleanup-pending path; blocker `—`; resume `—` |
| `drifted` | blocker `drift:DRF-nnn`; finding points at that record; resume `replan` |
| `awaiting` | absolute worktree; blocker `decision:DEC-nnn`; finding points at the decision; resume is a pending resume token |
| `blocked` | a nonempty `external:*`, `drift:*`, or `main:red` blocker; finding points at its durable detail; an external block without a live worktree resumes `fresh` |

Every task id is unique, every dependency names another task in the table, no task depends
on itself, counters are non-negative, and `failures <= v`. These rules are data validity,
not guidance: a route that reads an invalid ledger stops before dispatch and reports the
first exact violation.

## Atomic transition updates

The parent is the only writer, but single-writer does not make a multi-step update safe.
For every transition it follows this order:

1. Re-read and validate the complete ledger at its declared schema.
2. Produce one candidate replacement containing the new status, worktree, counters,
   finding, blocker, resume token, and returned dispatch row together.
3. Validate the candidate, then replace `ledger.md` in one write.
4. Only after that write succeeds may the next worker be dispatched.

Before a diagnosis, execution, verification, or landing dispatch, the same replacement
claims the phase and increments `d`, `e`, `v`, or `l`. On return, one replacement consumes
the outcome and records the dispatch. Never write `status` first and fill in its required
fields later; a crash between those edits would create a state no fresh session can route.

Every route applies the structural checklist in this skill before each read and candidate
write. Validation is an agent obligation at the `ai-ledger` interface; Rune does not ship
an executable validator or a second implementation that could drift from these rules.

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
diagnosing ─reproduced + reconciled─> pending
     ├─not reproduced───────────────> reservation removed; id burned
     ├─reclassified─────────────────> reservation removed; id burned; fresh run
     └─blocked──────────────────────> diagnosing (blocker recorded)

pending ─claim; e++─> in_progress ─done; v++─> verifying ─pass; l++─> landing ─landed─> done
                      │                    │                │
                      │                    │                └─refused───> pending
                      │                    │                  conflict     (worktree kept)
                      │                    │                  reverted
                      │                    └─fail──────────> pending (failures++)
                      ├─drift────────────> drifted
                      ├─budget───────────> pending (handoff written)
                      ├─blocked──────────> blocked (handoff + unblock condition + worktree disposition)
                      └─question─────────> awaiting (open decision recorded)

external block ─unblocks_when observed─> pending (preserve recorded resume/worktree state)
```

- `diagnosing` — a bug id and worktree are reserved, but its immutable task spec does not
  exist yet. Only `ai-bug` may hold it; it is never executable.
- `pending` — available, provided `blocked_by` is empty or all resolved. `resume_at` tells
  the next executor whether to start fresh or consume durable partial state
- `in_progress` — an executor holds it. Its worktree is absolute and `resume_at: recover`
  tells a dead-session reader not to invent progress from the row
- `verifying` — executor published a commit; awaiting an independent check of that artifact.
  The `v` counter already names the dispatched attempt
- `landing` — the published commit was independently verified; a lander is merging that
  exact SHA into the main tree. Worktree kept
- `done` — verified by a *different* agent **and** landed without breaking the main tree.
  Never self-declared, and never set straight off a `pass`
- `drifted` — the plan was wrong; a drift record exists; downstream may be invalid
- `awaiting` — blocked on a user decision. Names the `DEC-nnn`; worktree kept
- `blocked` — cannot proceed for an external, drift, or main-tree reason. The row names the
  kind, the finding points at detail, and an external detail states what clears it

`landing` exists because passing verification and surviving the merge are two separate
claims, and there was previously no state between them — so a task that had landed and
broken the build was indistinguishable from one that had never been tried.

Only the parent writes these. A task is never `done` because the executor said so — it is
done only after `ai-verify` names the published commit and `ai-land` lands that same SHA.

`awaiting` returns to `pending` the moment its decision is marked `decided`. Clear
`blocker`, preserve its `resume_at`, and increment `e` only when the fresh executor is
actually claimed. It picks up with the handoff, the worktree diff, and the resolved
decision.

An externally `blocked` task returns to `pending` only after the parent can observe the
handoff's `unblocks_when` condition. Clear `blocker`, preserve `latest_finding` as history
and the compatible `resume_at`, validate, and persist. Do not poll or redispatch merely
because time passed.

### Blocked executor returns

An executor return maps `in_progress -> blocked` only when its `task` and `attempt` match
the claimed row and it supplies a lowercase blocker slug, schema-safe `resume_at`, absolute
handoff pointer, and valid `worktree: kept | discarded` disposition. The handoff must
contain both `blocker_reason` and observable `unblocks_when`. In one validated replacement,
store `external:<slug>`, point `latest_finding` at that handoff, apply the worktree
disposition, preserve the existing `e` counter, and append the dispatch row.

A malformed blocked return cannot produce a schema-1 `blocked` row. Fail closed: preserve
the already-valid claimed row and recorded worktree, append the incomplete dispatch outcome,
stop the normal route, and enter `continue` reconciliation before reporting. Do not invent
missing fields, discard source state, or immediately redispatch the task; reconciliation
must remove the now-stale `in_progress` claim.

Unblocking is one validated ledger write after the parent observes `unblocks_when` through
an already-permitted bounded probe, durable coordination state, or explicit user
confirmation. Clear `blocker`, retain the finding as history, preserve compatible
`resume_at` and any live worktree, and set `pending`. If none of those can prove the
condition, report it and wait. A new session, elapsed time, or an optimistic retry is not
proof. User decisions use `awaiting`, not this transition.

`diagnosing` is deliberately earlier than `pending`. A reproduced bug remains there while
its planners consume `diagnosis_commit`; only successful reconciliation creates the task
spec and moves the existing row to `pending`. If diagnosis fails or reclassifies, remove
the provisional row but retain its protocol and progress artifacts. The id remains used
forever, so a late worker cannot attach its result to a different task.

## Claiming

Pick the lowest-id `pending` task whose `blocked_by` are all `done`.

Claiming is one atomic update: allocate or preserve the absolute worktree, set
`in_progress`, increment `e`, set `resume_at: recover`, validate, and persist. Dispatch
only afterward and pass the recorded `e` value as `attempt`.

### Claiming several at once

Multiple tasks may run concurrently, each in its own worktree, when **their change
surfaces share no files**. That is the whole condition, and it is checkable — every task
declares its surface, so compare the lists.

- Cap concurrent executors at **3**. Beyond that, merge and cost overhead outweighs the
  wall-clock win.
- Allocate and record every absolute `worktree_path` before dispatch. Two rows may be
  `in_progress` at once; each names its own stable worktree.
- If all eligible tasks overlap, run one. Serial is the fallback, not a failure.

**The landing procedure lives in `work`; the merge itself lives in `ai-land`.** Here, only
what a landing does to a row:

| `ai-land` returned | Row |
|---|---|
| `landed` | `done`, worktree removed or cleanup `pending` as returned |
| `refused` | `pending`, worktree kept, finding points at the landing block, resume `publish` |
| `conflict` or `reverted` | `pending`, worktree kept, finding points at the landing block, resume `fresh` |
| `stuck` | `blocked`, blocker `main:red`, finding points at the landing block, and set `main: red` at the top of the file |

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

Every reconciliation dispatch uses the absolute worktree path already recorded in the
row. Never replace it with the current directory or ask the harness to create a fresh
checkout; the uncommitted diff may exist only at the recorded path.

A `diagnosing` row is reconciled separately because no task specification exists for
`ai-recover` to read:

| Durable diagnosis state | Parent action |
|---|---|
| `diagnosis: reproduced` with valid commit ids | keep row and worktree; resume the same decomposition run |
| `diagnosis: not_reproduced` or `reclassified` | remove row; keep protocol/progress; id stays burned |
| `diagnosis: blocked` | keep row and worktree; report the blocker; retry only after it clears |
| no terminal diagnosis block | re-dispatch `ai-bug` with the same task, protocol, progress, and worktree pointers |

Never send a diagnosing reservation to `ai-execute` or `ai-recover`. The former requires
an immutable task contract; the latter cannot map a diff onto steps that do not exist yet.

Your job is the mapping:

| What comes back | Status | Worktree |
|---|---|---|
| valid complete publication, executor return missing | `verifying`, increment `v`, resume `verify` | kept; persist, then dispatch that verifier attempt |
| handoff note says `budget` | `pending` | kept |
| handoff note says `drift` | `drifted` | per the note |
| handoff note says `blocked` and includes slug, `blocker_reason`, `unblocks_when`, and resume token | `blocked`, `external:<slug>`, finding pointer, and returned resume token | kept or dropped exactly as recorded |
| `ai-recover` → `salvage` | `pending`, returned `step:N`, finding points at handoff | kept |
| `ai-recover` → `partial` | `pending`, returned `evidence:<mode>`, finding points at handoff | kept |
| `ai-recover` → `discard` | `pending`, resume `fresh`, finding points at handoff | dropped |
| empty diff, branch ahead, no publication | `pending`, resume `publish` | kept; executor recovers the committed range |
| empty diff, branch not ahead, no note | `pending`, resume `fresh` | dropped |

**A row left at `landing` is the dangerous one.** A dead lander may have merged and never
rolled back, so the main tree is in a state nobody recorded. Re-dispatch `ai-land` on that
task rather than looking: it reads the durable `verified_commit`, detects whether that
exact SHA is already an ancestor of main, and runs the oracle instead of creating an empty
merge. First increment `l`, persist the complete `landing` row, and pass that attempt. That
is the same artifact and the same gate the live case uses.

**No row may remain `in_progress` or `landing`** when reconciliation ends. A `blocked` row
may remain only when its schema fields are complete and `latest_finding` points at the
durable reason and unblock condition. A `diagnosing` row may remain only when its durable
outcome is reproduced and planning is next, or when a recorded diagnosis blocker prevents
re-dispatch. That is the invariant this section guarantees.

## Drift invalidation

When a drift record lands, downstream tasks may now be wrong. The parent must:

1. Record `DRF-nnn` in the ledger with the tasks it names as invalidated.
2. Set those tasks to `blocked`, `blocker: drift:DRF-nnn`, point `latest_finding` at the
   drift record, and set `resume_at: replan`.
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
