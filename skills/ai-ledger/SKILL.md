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

schema: 2
vision: complete
current_milestone: M-03
oracle: npm test
main: green

## Tasks

| id | milestone | title | status | blocked_by | worktree | attempts | failures | latest_finding | blocker | resume_at | replaced_by |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T-011 | M-03 | TokenStore interface | done | — | merged | d0/e1/v1/l1 | 0 | — | — | — | — |
| T-013 | M-03 | Diagnose refresh regression | diagnosing | — | /workspace/acme/.rune/worktrees/T-013 | d1/e0/v0/l0 | 0 | — | — | plan:M-03/R-002 | — |
| T-014 | M-03 | Rotate refresh tokens | in_progress | — | /workspace/acme/.rune/worktrees/T-014 | d0/e2/v1/l0 | 1 | .rune/notes/T-014.verify.md#attempt-1 | — | recover | — |
| T-015 | M-03 | Refresh endpoint | pending | T-014 | — | d0/e0/v0/l0 | 0 | — | — | fresh | — |
| T-016 | M-03 | Session restart persistence | retired | — | discarded | d0/e1/v0/l0 | 0 | .rune/drift/DRF-003.md | — | — | T-020,T-021 |
| T-017 | M-03 | Expiry sweep | blocked | — | /workspace/acme/.rune/worktrees/T-017 | d0/e1/v0/l0 | 0 | .rune/notes/T-017.md | external:registry-unreachable | step:2 | — |
| T-020 | M-03 | Persist sessions through restart | pending | T-014 | — | d0/e0/v0/l0 | 0 | — | — | fresh | — |
| T-021 | M-03 | Restore persisted sessions | pending | T-020 | — | d0/e0/v0/l0 | 0 | — | — | fresh | — |

## Drift
- DRF-003 (from T-016) retired: T-016 — replacements: T-020, T-021

## Findings
- FND-007 (from T-014/e2) confirmed: purge sweeps permanent sessions when the flag is on
- FND-008 (from T-014/e2) refuted: the retry loop is bounded by maxAttempts three frames up

## Dispatches
| phase       | followed      | work              | outcome                         |
|-------------|---------------|-------------------|---------------------------------|
| plan-graph  | ai-decompose  | vision/graph      | graph: /workspace/acme/.rune/milestones.md |
| survey      | ai-survey     | survey            | map.md written                  |
| commands    | ai-oracle     | init/commands     | oracle: npm test                |
| diagnose    | ai-bug        | T-013             | reproduced @ b7a03d4           |
| plan-draft  | ai-decompose  | M-03/R-002/P-01   | draft: P-01.md                  |
| plan-draft  | ai-decompose  | M-03/R-002/P-02   | draft: P-02.md                  |
| reconcile   | ai-decompose  | M-03/R-002        | T-014..T-017 written            |
| report-slot | ai-drift      | T-014             | unused DRF-006                  |
| report-slot | ai-drift      | T-016             | recorded DRF-003: /workspace/acme/.rune/drift/DRF-003.md |
| report-slot | ai-investigate| INV-004           | recorded INV-004: /workspace/acme/.rune/notes/INV-004.md |
| find-check  | ai-verify-finding | FND-007       | confirmed FND-007: /workspace/acme/.rune/findings/FND-007.md |
| execute     | ai-execute    | T-014             | done @ 4a91c02                  |
| verify      | ai-verify     | T-014             | pass @ 4a91c02                  |
| land        | ai-land       | T-014             | landed @ 4a91c02                |
```

`schema: 2` is mandatory. Schema 1 is the recognized predecessor without `replaced_by`;
a ledger with no schema marker is legacy schema 0. `continue` migrates either one before
any normal lifecycle dispatch. The sole exception is its assigned record-only worker when
an amended legacy contract requires drift evidence for the migration candidate. An
unknown schema is a hard stop, never a best-effort parse.

### Vision phase

The top-level `vision` field is the **only authoritative vision phase**. Its exact enum is
`absent | drafting | complete`; the existence, headings, or apparent prose completeness
of `vision.md` never override it. The sole writer is the parent role identified by
`ai-taskfmt`, including while that parent follows `init`, `vision`, or `continue`.

| From | To | Persisted boundary |
|---|---|---|
| `absent` | `drafting` | before the first interview question or any vision/decision write |
| `drafting` | `drafting` | after each settled answer is first written to `vision.md` and any related decision is written to `decisions.md` |
| `drafting` | `complete` | after the final answer is durable, all required topics are represented, and every behaviour/scope choice has a decision record |

No reverse transition exists. `complete` does not mean every decision is decided; open
records may still block the milestone graph. Milestone generation requires
`vision: complete` and no blocking open decision in either decision location.

The ordering makes crashes deterministic. Before the first transition, recovery starts a
new interview. While `drafting`, recovery reads durable sections and decisions and resumes
at the first unanswered topic. If the final answer is durable but the phase write was
interrupted, `continue` validates `ai-taskfmt`'s exact Vision-document checklist and may perform only the
missing `drafting -> complete` replacement without re-asking a settled question. After
`complete`, recovery never resumes interviewing: it presents open decisions or generates
the missing milestone graph. A missing/invalid field or a graph present while the phase is
not `complete` is a stop condition.

For an empty project that runs vision before init, `oracle: —` is valid only while
`rune.yml` is absent, Tasks is empty, and Dispatches is empty or contains only these exact
coordination-only pre-init rows: `plan-graph | ai-decompose | vision/graph | graph: <absolute
milestones path>`, `survey | ai-survey | survey | map.md written`, and
`commands | ai-oracle | init/commands | oracle: <command>`. `vision` creates that canonical bootstrap
and logs its graph worker as `plan-graph`; `init` may then log survey/command
discovery before it replaces only `oracle` and `main` from ground truth, preserving the
vision phase and all rows. No diagnose, plan-draft, reconcile, execute, verify, land, or
other task-bound/report dispatch may start while the oracle is `—`.

The crash-safe post-init/pre-manifest state has `rune.yml` absent, `oracle != —`, no Tasks,
and the same restricted coordination-only Dispatches. It means init persisted the ledger
first and died before atomically installing `rune.yml`. Only `init` may recover it: rerun
its idempotent discovery, preserve vision/history, persist any refreshed ledger result
first, then install the complete `rune.yml`. `rune.yml` present with `oracle: —`, or either
missing-manifest state with a task/report dispatch, is invalid and stops.

Schema 1 has the same ordered columns through `resume_at`. Migration appends
`replaced_by` to the header and `—` to every existing row, then changes the marker to 2 in
the same validated replacement. Before that replacement, `continue` scans unfinished
task files for a nonempty legacy `## Amendments` footer. If it finds one, the
migration-specific record-only protocol below must create a causal drift record and the
candidate drift-blocks the complete unfinished dependency closure; it never promotes the
amended prose into a schema-2 contract. Existing drift-blocked rows remain blocked, and
migration never guesses future replacement ids. Schema 0 is mapped directly to schema 2
by `continue` using its durable artifacts and the same legacy-amendment preflight.

There is one `## Tasks` table for the whole ledger. Milestone membership is a field rather
than a heading so every task has one self-contained state record. The columns are exact and
ordered; adding an ad-hoc column creates a new schema version rather than an optional fact
that some readers ignore.

### Task fields

- `id`, `milestone`, `title`, `status`, and `blocked_by` identify the immutable task and
  its dependency state. `blocked_by` is `—` or a comma-separated list of `T-nnn` ids.
  Table values may not contain `|`; longer wording belongs in the task or note artifact.
- `replaced_by` is `—` for every live or completed task. A `retired` row lists one or more
  comma-separated task ids that immediately replace its obsolete contract, or the literal
  `none` when the replan proves no new work is required. These are lineage edges, not
  dependencies: replacement tasks declare their real execution order in `blocked_by`.
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

Immutable classification stays in `tasks/T-nnn.md` rather than becoming another mutable
ledger column. Before registering a reconciled batch, and whenever recovery validates its
rows, join each row to that task's canonical `type`, `remediation`, and
`root_cause_followup` fields. A mitigation link is valid only when the target is a
different task in the same milestone with `type: bug`, `remediation: root_cause`, and no
further follow-up. The target must exist in both the task set and ledger; registering one
side without the other is invalid.

Ledger-backed reports render that join explicitly as
`mitigation T-nnn → root-cause T-mmm` and report the root-cause row's current status. A
landed mitigation never makes its linked task `done`, removes it from the queue, or counts
as milestone completion. This keeps mutable routing in one table while making temporary
risk visible without duplicating immutable task metadata.

For pre-field immutable tasks, use `ai-taskfmt`'s deterministic reader normalization.
Legacy `kind: mitigation` without a durable follow-up is recovery work: unfinished
closures enter drift re-decomposition. A completed mitigation is valid only through
`ai-taskfmt`'s repair overlay: exactly one `mitigation-repair` dispatch row must be
in one of its parsed pending, linked, or blocked shapes. Every shape retains the fresh run,
legacy id, reserved root id, and exact protocol, task, and repair paths. The ids and paths
must be unique across all task files, protocols, and repair rows; each reservation is
permanently burned. A linked row's immutable repair artifact and registered target must
agree and satisfy the same different-id, same-milestone, root-cause constraints. That
joined relationship supplies the normalized old task's follow-up without adding mutable
classification columns or editing its bytes. Pending and blocked repairs prevent milestone
completion and ordinary task dispatch. Blocked also requires lowercase `blocker`, stable
`detail`, and objective `unblocks_when`, and remains unchanged until that condition is
observed. A missing, duplicate, or mismatched repair stops validation. Never silently
normalize that marker to `root_cause`.

Every live task worktree value is an absolute path. The parent allocates
`<main_root>/.rune/worktrees/T-nnn`, writes it into the row before dispatching the first
task-bound worker, and keeps that value unchanged through diagnosis, retries, verification,
recovery, and landing. `discarded` and `merged` may replace it only when the path no longer
contains live task state.

`## Drift` is also routing state. A live entry has the exact form
`- DRF-nnn (from T-nnn) quiescing: T-nnn,... — closure: N of M unfinished`; that frozen
set suppresses every new
task-bound dispatch even while an already-running row still has an active status. The set
is the complete unfinished dependency closure and may shrink only when an in-flight
lander proves its commit already reached green main, making that task `done`. The atomic
replacement transaction changes the entry to `retired: ... — replacements: ...` only
after every remaining frozen row is inactive and its worktree is `discarded`. A crash
therefore cannot erase the fact that a late worker return must be quarantined.

`## Findings` is the opposite kind of section: a record, never routing state. An entry has
the exact form `- FND-nnn (from T-nnn/eN) confirmed | refuted | inconclusive: <one line>`,
and it appears only once the verified record has been promoted to `findings/FND-nnn.md`.
An unverified claim under `findings/open/` has no entry here, because it is not yet
anything.

Findings block nothing. They do not freeze rows, gate milestone completion, or make a task
dispatchable or undispatchable, and a `confirmed` entry is not a task — it becomes one
only if the user asks for it and decomposition writes it. `refuted` entries stay
permanently: the value of the section is as much in the claims that turned out to be
wrong as the ones that did not.

`N` is the number of frozen ids in that entry and `M` the milestone's unfinished tasks
measured before the freeze. Both are written once, by the same update that creates the
entry, and are never recomputed afterwards: they are the durable evidence for `work`'s
stop rule, so a later session reads the original measurement rather than re-deriving one
from a tree that has since moved. `N` falls only when a lander removes an id from the set,
and `M` never changes.

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
| `retired` | worktree `discarded`; finding points at the causal drift record; blocker and resume `—`; `replaced_by` names immediate replacements or explicitly says `none` |

Every task id is unique, every dependency names another task in the table, no task depends
on itself, counters are non-negative, and `failures <= v`. Only `retired` rows may have a
`replaced_by` value other than `—`; every named replacement exists in the same milestone
and has a higher, never-before-used task id. `none` is valid only for `retired`.
Replacement edges are acyclic. No non-retired task may
depend on a retired task: re-decomposition must retire that dependent contract too or give
its replacement a valid dependency. These rules are data validity, not guidance: a route
that reads an invalid ledger stops before dispatch and reports the first exact violation.

## Atomic transition updates

The parent is the only writer, but single-writer does not make a multi-step update safe.
For every transition it follows this order:

1. Re-read and validate the complete ledger at its declared schema.
2. Produce one candidate replacement containing the new status, worktree, counters,
   finding, blocker, resume token, replacement lineage, and returned dispatch row together.
3. Validate the candidate, then replace `ledger.md` in one write.
4. Only after that write succeeds may the next worker be dispatched.

Before a diagnosis, execution, verification, or landing dispatch, the same replacement
claims the phase and increments `d`, `e`, `v`, or `l`. On return, one replacement consumes
the outcome and records the dispatch. Never write `status` first and fill in its required
fields later; a crash between those edits would create a state no fresh session can route.
Ordinary lifecycle transitions preserve `replaced_by: —`; only the completed drift-replan
transaction may populate it while moving an old row to `retired`.

Every route applies the structural checklist in this skill before each read and candidate
write. Validation is an agent obligation at the `ai-ledger` interface; Rune does not ship
an executable validator or a second implementation that could drift from these rules.

## Log every dispatch

**Every subagent you dispatch gets a row in `## Dispatches`.** Ordinarily the line is
written when it returns. Every `DRF-`, `INV-`, or `RES-` report reservation is the
deliberate exception: before dispatch, write a `report-slot` row that binds the globally
unused id to both its absolute `open/` staging path and final path. This reservation is
the allocator's durable claim and makes concurrent workers use different sole-writer
destinations.

The third column is exactly `work`, and its value equals the canonical dispatch
envelope's `work` token and the worker's echoed return. New rows never use a `for` header,
`task` field, `—` stand-in, or an attempt-suffixed substitute. Schema-0/1 and early
schema-2 ledgers may have the historical `for` header; `continue` deterministically
renames only that header and maps the three coordination-only stand-ins to
`vision/graph`, `survey`, and `init/commands` during its one validated migration.

Use one of these exact outcome shapes:

```text
pending DRF-007: <absolute staging> -> <absolute final>
recorded DRF-007: <absolute final>
unused DRF-007
blocked DRF-007: <absolute staging> -> <absolute final>; <reason>
```

`INV-` and `RES-` use the same shapes. A worker return never appends a second assignment;
the parent replaces only the matching pending outcome after atomic promotion, marks it
unused when the reserved report was not needed, or marks it blocked while retaining both
paths. A pending or unused row burns its id just as surely as a file does. A blocked row
does too. Allocation scans final files, staging files, and every report-slot row before
choosing the next number.

Report promotion is deliberately ordered outside the ledger replacement: validate the
complete assigned staging file, atomically promote it with no-replace semantics to the
assigned final path, then replace `pending` with `recorded` in the same candidate that
consumes the worker's outcome. A crash after the promotion leaves `pending` plus a
complete final file, which `continue` can finish. A crash before it leaves either a
complete staging file or no file.
The final path is therefore never a partial report and no retry receives a new id.

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

drifted or drift-blocked ─atomic replan with new ids─> retired (terminal; replacements linked)
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
- `retired` — the immutable task contract was invalidated before completion and removed
  from the current plan. It is permanent history, never eligible, and names its immediate
  replacement ids or explicitly says that no replacement was needed

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

Before any outcome mapping, validate `ai-taskfmt`'s common return envelope. `work` must
equal the dispatch row's assigned token, `summary` and the worker-specific outcome are
present, and `worktree` plus `worktree_path` agree. Historical `task` is normalized only
under the explicit one-field compatibility rule; a return with both ids or neither is
malformed and cannot transition the row.

An executor return maps `in_progress -> blocked` only when its `work` and `attempt` match
the claimed row and it supplies a lowercase blocker slug, schema-safe `resume_at`, absolute
handoff pointer, and valid `worktree: kept | discarded` disposition. The handoff must
contain both `blocker_reason` and observable `unblocks_when`. In one validated replacement,
store `external:<slug>`, point `latest_finding` at that handoff, apply the worktree
disposition, preserve the existing `e` counter, and append the dispatch row.

A malformed blocked return cannot produce a schema-2 `blocked` row. Fail closed: preserve
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

Pick the lowest-id `pending` task whose `blocked_by` are all `done`. A `retired` task is
terminal history, not resolved work, so validation rejects any live task that still names
one as a dependency.

Claiming is one atomic update: allocate or preserve the absolute worktree, set
`in_progress`, increment `e`, set `resume_at: recover`, reserve a fresh `DRF-` report
slot with its exact staging and final paths, validate, and persist. Dispatch only
afterward and pass the recorded `e` value as `attempt` plus that report assignment.
Every executor attempt gets its own slot. A non-drift return burns it as `unused`; a
retry never inherits an earlier attempt's slot.

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

Validate its conditional oracle evidence at the canonical enum seam first: `landed`
requires `passing | none`, `reverted` requires `failing`, and `none` is permitted only for
a manifest with no configured oracle. Stored and transient verdicts are never translated
through `pass`, `fail`, or `ok`.

| `ai-land` returned | Row |
|---|---|
| `landed` | `done`, worktree removed or cleanup `pending` as returned |
| `refused` | `pending`, worktree kept, finding points at the landing block, resume `publish` |
| `conflict` or `reverted` | `pending`, worktree kept, finding points at the landing block, resume `fresh` |
| `stuck` | `blocked`, blocker `main:red`, finding points at the landing block, and set `main: red` at the top of the file |

`not_landed` is accepted only from `ai-land` `drift-observe` for a task already named in a
`quiescing` drift entry. It never maps to `pending`: preserve the landing finding while an
`ai-drift` quiesce dispatch discards the registered worktree, then move the row to the
causal `drifted` state. A `landed` result for that frozen task still maps to `done` and
removes the id from the retirement set before re-decomposition.

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

A recovery `discard` with `premise_drift: true` is the exception to its table row. Reserve
a fresh DRF report slot, dispatch `ai-drift` record-only from the task and recovery
handoff, promote the assigned staging record, and apply the normal drift freeze. Recovery
never writes a report itself and never inherits the dead executor attempt's DRF slot.

**A row left at `landing` is the dangerous one.** A dead lander may have merged and never
rolled back, so the main tree is in a state nobody recorded. Re-dispatch `ai-land` on that
task rather than looking: it reads the durable `verified_commit`, detects whether that
exact SHA is already an ancestor of main, and runs the oracle instead of creating an empty
merge. First increment `l`, persist the complete `landing` row, and pass that attempt. That
is the same artifact and the same gate the live case uses.

If the task is named by a `quiescing` drift entry, that recovery dispatch must use
`drift-observe`; it may recognize an already-landed artifact but may not start a merge.

**No row may remain `in_progress` or `landing`** when reconciliation ends. A `blocked` row
may remain only when its schema fields are complete and `latest_finding` points at the
durable reason and unblock condition. A `diagnosing` row may remain only when its durable
outcome is reproduced and planning is next, or when a recorded diagnosis blocker prevents
re-dispatch. That is the invariant this section guarantees.

## Drift invalidation and replacement

When a drift record lands, the parent first freezes the affected contracts without
pretending replacements exist:

1. Record `DRF-nnn` in `## Drift`, including the originating task and every task it
   invalidates, plus the full unfinished reverse-dependency closure. Write it as a
   `quiescing` freeze before consuming another result. The originating task belongs in the
   set. Stop every new dispatch for every frozen id, regardless of the row's current
   status.
2. In the same update, set inactive affected rows to `drifted` with
   `blocker: drift:DRF-nnn`, point `latest_finding` at the drift record, and set
   `resume_at: replan`. Normalize `worktree: —` to `discarded`. An absolute worktree stays
   registered until an `ai-drift` quiesce dispatch proves it was discarded.
3. Drain active rows without using their normal successor transitions. A returned
   diagnosis, execution, or verification may add evidence but never starts planning,
   verification, retry, or landing; quiesce its unpublished registered worktree and then
   move it to the same complete `drifted` row. For `landing`, consume the live lander's
   result. If that return was lost, `ai-land` in `drift-observe` mode may only recognize an
   artifact already reachable from main; it must not merge a new one. Green already-landed
   work becomes `done` and leaves the retirement set. A not-landed artifact is quiesced;
   red or ambiguous main state stops all work. No `in_progress`, `verifying`, `landing`,
   `diagnosing`, or live-worktree row can be retired.

Re-decomposition writes new immutable task files under globally unused `T-nnn` ids. It
never overwrites, renames, deletes, or appends to an existing task file. Once every
replacement file exists and every affected old row is inactive with `worktree: discarded`,
the parent applies **one schema-2 ledger replacement** that:

- appends the replacement rows as ordinary `pending` tasks with fresh counters and
  `replaced_by: —`, or finalizes a fresh reproduced `diagnosing` bug reservation while
  preserving its diagnosis counter, commit evidence, and new worktree;
- changes each affected old row to `retired`, preserves its id, title, milestone,
  dependencies, counters, and historical files, points `latest_finding` at the causal
  drift, clears `blocker` and `resume_at`, and records its immediate successors in
  `replaced_by` or records `none` when the replan demonstrates that its outcome is already
  satisfied or deliberately removed from the milestone;
- includes every non-done task that depended directly or transitively on a retired task,
  so no live row keeps a dependency on historical work; and
- validates the whole candidate, including replacement existence, same-milestone lineage,
  increasing ids, and acyclicity, before replacing `ledger.md` once.

A replacement may itself be retired later. Its row then points to the next immediate
successors; readers follow the chain to the current leaves. `done` and `retired` rows are
never rewritten into each other, and retired rows never count as completed milestone work.
A milestone is complete only when every non-retired leaf task is `done`.

Crash order is fail-closed. Task files and `replacements.md` are written first, then the
one ledger transaction. If the parent dies before that transaction, the old rows remain
drift-blocked and no replacement is executable. `continue` may finish the transaction only
when the immutable replacement map is complete, every mapped new task file validates, and
the old rows still match the exact frozen retirement set. Otherwise all unregistered ids
stay burned and a fresh decomposition run uses new ones. If the ledger write succeeds, old
and new rows become visible together. There is no state in which an old task is retired
without an explicit replacement disposition.

Do not silently delete invalidated tasks or their files. The drift record, immutable old
contract, attempt history, terminal row, and replacement edges are the evidence that the
milestone decomposition was wrong.

## Reporting

`rune:continue` and `rune:work` read the ledger to answer: what is done, what is
available, what is blocked and on what, and whether anything needs a human decision.

Read it from disk each time. Never carry ledger state in context across dispatches — a
stale in-memory copy is exactly how the parent ends up dispatching a task someone else
already finished.
