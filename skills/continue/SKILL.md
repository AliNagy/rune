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

- **Run** `git rev-parse --show-toplevel` and the bounded probes owned by `ai-root`.
- **Follow** `ai-root`; its narrowly scoped coordination migration is the sole write
  exception outside this route's reconciliation records.
- **Read** `<main_root>/.rune/` coordination files.
- **Write** `<main_root>/.rune/ledger.md`, repairing the rows a dead session left behind.
- **Promote** a complete worker-authored report from an assigned `open/` staging path to
  its exact final path with a same-filesystem atomic no-replace operation. You never
  compose or edit report content.
- **Delete** `<main_root>/.rune/PAUSED` when the user confirms a resume. You never create it — that
  is `pause`.
- **Talk to the user** — the status report, and the question if one is owed.
- **Dispatch subagents**, naming the skill each one must follow. The dispatch table in
  `ai-taskfmt` says which skill does which job.

## Coordination-root preflight

Resolve `main_root` once with the bounded probe `git rev-parse --show-toplevel` before
reading state. Then follow `ai-root` with that absolute root and `mode: resolve`; it
resumes an interrupted directory migration before ledger recovery. Stop and report any
failure it returns. Resolve every `.rune/...` path against the returned root. Every
recovery, verification, or landing dispatch carries `main_root`, the absolute
`worktree_path` recorded in the task's ledger row, and absolute coordination pointers.

**Anything not on that list is a dispatch** — above all reading a torn worktree's diff,
which is the single most expensive thing you could do here and the reason `ai-recover`
exists. You are the session that everything resumes from; arriving already full defeats
the purpose of having resumed at all.

## 1. Read state

```
<main_root>/.rune/PAUSED        · paused? when, why, was the tree left clean?
<main_root>/.rune/sessions/     · newest session handoff — context the ledger does not carry
<main_root>/.rune/rune.yml      · initialized? stale? oracle?
<main_root>/.rune/vision.md     · exists? complete?
<main_root>/.rune/decisions.md  · any status: open?
<main_root>/.rune/milestones.md · exists? which is current?
<main_root>/.rune/drafts/       · completed or interrupted decomposition runs?
<main_root>/.rune/ledger.md     · task statuses, drift records
<main_root>/.rune/notes/        · handoff notes
<main_root>/.rune/notes/open/   · assigned INV/RES reports awaiting promotion
<main_root>/.rune/drift/open/   · assigned DRF reports awaiting promotion
```

Cheap reads, all of them. Do not read source. Do not read task files unless you are about
to act on one.

### Validate or migrate the ledger first

Before treating any row as state, apply `ai-ledger`'s schema validation. `schema: 2` must
validate completely. An unknown schema stops here and is reported.

Schema 1 is the recognized predecessor. Migrate it once, before reconciliation: validate
its exact ordered table, run the legacy-amendment preflight below, append the
`replaced_by` header and `—` to every row, change the marker to 2, validate the complete
candidate, then replace `ledger.md` once. Do not infer replacement lineage for an
existing drift blocker; only a completed replan can do that.

A ledger with no schema marker is legacy schema 0. Migrate it directly to schema 2:

1. Read only coordination artifacts. Map each old milestone table row into the canonical
   schema-2 Tasks table; the enclosing milestone heading supplies `milestone`, and every
   row starts with `replaced_by: —`.
2. Derive `d/e/v/l` from durable dispatch rows and numbered diagnosis, verification, and
   landing blocks. Gaps remain counted when a dispatch row exists. Count verifier `fail`
   blocks into `failures`.
3. Point `latest_finding` at the last live verifier, landing, drift, decision, or handoff
   artifact. Derive `blocker` and `resume_at` from the old status plus that artifact.
4. If any required value has two plausible answers, stop and name the row; do not choose.
5. Validate the complete candidate and replace `ledger.md` once; never partially upgrade
   in place.

For either predecessor, inspect the task file for every mapped row before the final
replacement. A legacy `## Amendments` footer is nonempty when anything other than
whitespace or its old placeholder comment follows the heading.

- A `done` amended task remains `done`. Preserve the entire file byte-for-byte as the
  historical contract that was executed; no route reads it as a live schema-2 contract.
- Any unfinished amended task fails closed. Choose the lowest-id amended row as the
  record's `from_task`, put every other unfinished amended row in `invalidates`, compute
  their unioned unfinished reverse-dependency closure, and allocate one migration
  `DRF-nnn`. Before dispatching,
  append or recover the one pending `## Dispatches` assignment that binds that id to its
  exact staging and final paths, then dispatch `ai-drift` in record-only mode with the
  assignment, amended task pointers, and pre-migration ledger. The staging record names
  the selected origin, every other
  amended task and the closure, and all amended task files as evidence; it does not
  interpret amendment prose.
- If that worker or session dies, keep the predecessor ledger and its pending assignment;
  the next `continue` reuses the same id and paths. Once staging validates, atomically
  promote it to the assigned final path. The single schema-2 candidate then marks the slot
  recorded, adds its `quiescing` drift entry, and sets every inactive affected row to
  `drifted` with that DRF pointer and `resume_at: replan`, maps `worktree: —` to
  `discarded`, and preserves absolute worktrees for the quiescing pass. Active-looking
  rows are stale in a fresh session and are reconciled under the freeze, never resumed
  normally.

This is the only pre-migration worker dispatch. It creates evidence required by the
schema-2 candidate; no diagnosis, execution, verification, landing, or decomposition may
start against a predecessor ledger.

Only schemas 0 and 1 have migration paths. Migration is idempotent because a successful
replacement is schema 2 and later runs validate it instead of migrating again.

## 2. Reconcile

Per `ai-ledger`. The critical step, and the one that is easy to skip because
everything *looks* fine.

### Reconcile report assignments first

Before task status, reconcile every pending or blocked `DRF-`, `INV-`, and `RES-`
report-slot row. The row's id and exact staging/final paths are authoritative. A blocked
row keeps both paths and its reason; it remains burned and is surfaced rather than ignored.
Only after its objective unblock condition is proven may a standalone report job move
back to pending and reuse the same assignment. An executor's blocked slot never moves to
a later attempt, which receives a fresh id and paths.

For pending rows:

- complete staging exists and final is absent → validate the required report shape,
  atomically promote staging to final with no-replace semantics, then mark the row
  `recorded`
- final exists and staging is absent → validate final and mark the row `recorded`; the
  prior session died after promotion
- neither exists, but the paired worker has a durable non-report outcome → mark the slot
  `unused`
- neither exists and a standalone `ai-drift` record-only, `ai-investigate`, or
  `ai-research` dispatch can be reconstructed entirely from durable pointers → re-dispatch
  that report job with the same id and paths, never a new reservation
- neither exists for an executor attempt → settle that slot only while reconciling the
  stopped attempt below; never pass it to a new executor attempt, which gets a fresh slot
- both exist, an id or path differs, a report is malformed, or a staging/final file has no
  pending assignment → stop and report the first exact inconsistency; burn the id and do
  not guess which file wins

Reconcile paired investigation reports in dependency order. A complete INV report must
contain `research: RES-nnn`, `research: unused`, or `research: not-assigned`. When it names
RES, validate and record that exact companion before promoting INV. When it says `unused`,
mark the assigned RES slot unused only after both RES paths are absent. If RES is already
recorded while INV is still pending, re-dispatch the reconstructible investigation with
the same INV assignment and the RES final as read-only `research_evidence`; do not pass a
writable RES assignment or repeat the search. If the original question cannot be rebuilt
from durable pointers, mark INV blocked and surface the preserved RES instead of guessing.

For a recorded `INV-` or `RES-` report, finish the pending worker row and report its final
pointer; these reports never create task rows. For a recorded `DRF-`, consume the causal
record through the ordinary drift-freeze rules below. Report promotion is complete before
any ledger pointer names the final artifact.

Reconcile every `quiescing` entry under `## Drift` before the ordinary status rules below.
Its frozen ids must not resume their old lifecycle: consume durable worker returns only as
evidence, use `ai-drift` quiesce for unpublished registered worktrees, and use `ai-land`
`drift-observe` for a stale `landing` row whose prior return is missing. Already-reachable
green work becomes `done`; `not_landed` is discarded; ambiguous or red main state stops.
A row with no worktree becomes `discarded` without a cleanup dispatch. Resume the replan
only when every remaining frozen row is inactive and discarded.

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
   `pending` plus its resume token for budget; for drift, require that this attempt's
   assigned DRF staging file was promoted above, then set `drifted`, its final drift
   pointer, blocker, and `replan`; `blocked` plus its external blocker, finding pointer,
   and resume token for a recorded external condition. A blocked handoff must include the lowercase `blocker`
   slug, `blocker_reason`, observable `unblocks_when`, a schema-safe `resume_at`, and its
   worktree disposition. If any are missing, treat the handoff as unusable and continue
   through step 3; never write an invalid blocked row or optimistically set `pending`.
3. **No handoff?** The session died mid-flight. At the ledger's exact absolute
   `worktree_path`, check only whether the worktree's diff is
   empty and whether the task branch is ahead of its merge base with main — both are
   bounded state probes, not source reads:
   - empty diff, branch ahead → keep it and set `pending`, `resume_at: publish`. The
     executor may have died between `git commit` and writing the publication block; a fresh executor inspects the
     committed range and either publishes that `HEAD` or resumes the task. For a diagnosed
     bug, `diagnosis_commit` alone is only the starting baseline and must never be published.
   - empty diff, branch not ahead → discard, set `pending`, `resume_at: fresh`. Nothing lost.
   - non-empty → work exists but is unexplained. **Dispatch `ai-recover`** with the same
     `main_root`, exact `worktree_path`, and absolute task/progress pointers.
     It maps the diff onto the task's declared steps, decides whether the work is
     salvageable, names the resume point, and writes the handoff the dead executor never
     did. Before dispatch, mark the stopped executor attempt's absent DRF slot `unused`;
     recovery never inherits it. Apply its verdict — `salvage`, `discard`, or `partial` —
     copy its schema token to `resume_at`, and point `latest_finding` at the handoff. If a
     discard also returns `premise_drift: true`, instead reserve a fresh DRF report slot
     and dispatch `ai-drift` in record-only mode from the task and recovery handoff. Promote
     that report and apply the ordinary drift freeze before leaving `in_progress`.

   Do not inspect the diff yourself. Reading it is exactly the code-reading the dispatcher
   is forbidden, and a torn worktree is expensive to read.
4. **No row may remain `in_progress`** when you are done.

Also check:

- orphaned worktrees with no ledger row → remove; if their task commit is already in main,
  delete the merged task branch too
- `verifying` rows whose verifier never returned → first check for a durable block matching
  the row's current `v`. If it is `unverified` for `evidence` or `acceptance`, recover the
  pending record-only drift assignment: reconcile its assigned staging/final pair and
  apply the freeze transition, or re-dispatch `ai-drift` with the same id and paths when
  both files are absent. Never allocate a second DRF for the same verdict. Consume every
  other verdict with `work`'s complete mapping (including `failures++` only for `fail`, the finding
  pointer, and the returned dispatch row). If no verdict exists, increment `v`, persist,
  and re-dispatch that attempt against the row's exact `worktree_path`; never create a
  fresh verifier checkout
- `landing` rows whose lander never returned → first consume a durable block matching the
  current `l` with `work`'s complete outcome mapping when present. Otherwise, if `l` is
  below five, increment it, persist, and
  re-dispatch that attempt against the same verified artifact and exact worktree. At `l5`,
  stop and surface the exhausted landing ceiling rather than creating attempt six
- completed record-only drift records not yet reflected in `## Drift` → require their
  report-slot row to be `recorded`, validate the assigned task/finding inputs, then
  atomically add the exact quiescing closure and block inactive rows; a pending assignment
  with neither path is re-dispatched to the same id and paths
- `blocked` rows whose finding is missing, unreadable, or lacks the blocker reason and
  observable unblock condition → keep them blocked, report the damaged durable record,
  and do not redispatch; never infer that elapsed time cleared the condition
- decomposition runs with a protocol record or planner drafts but no registered tasks →
  keep the immutable artifacts, mark the attempt interrupted in the dispatch log, and
  route back to `work`. It allocates a fresh `R-nnn`; never resume into or reuse the
  interrupted run's paths. The exception is a reproduced `diagnosing` bug reservation:
  its protocol, diagnosis, and worktree are one bound input, so resume that same run.
- drift-replan runs with new task files or `replacements.md` but no atomic ledger
  transaction → if the immutable replacement map is complete, every mapped task file
  validates, every target id is new, the protocol and drift pointers match, and the old
  rows still equal the frozen retirement set with no live worktrees, finish the exact
  schema-2 transaction and record the recovered reconcile outcome. Otherwise keep every
  artifact and burn every file id, leave the old rows drift-blocked, and route `work`
  through a fresh `R-nnn`. Never register a partial map or infer lineage from task titles.
  If the schema-2 transaction is already present, validate the complete old-to-new map and
  treat the run as finished. A fresh reproduced bug reservation may be finalized only when
  its diagnosis evidence and replacement task file both validate for that same new id.
- `retired` rows → validate their drift pointer and explicit `replaced_by` disposition,
  but never recover, claim, or resurrect them. Follow replacement chains only to report
  the current leaf tasks.
- **`decisions/open/` files with no `awaiting` row** → a worker asked something and the
  session died before it reached the user. Assign the `DEC-nnn`, move it into
  `decisions.md`, set the task `awaiting`, store `decision:DEC-nnn`, point at the decision
  record, preserve the handoff's resume token, and surface it. This is the self-healing path
  and it is the whole reason those files exist.

## 3. Determine phase and route

| State on disk | Phase | Resume with |
|---|---|---|
| `<main_root>/.rune/PAUSED` present | deliberately stopped | **ask first** — see below |
| no `<main_root>/.rune/` | nothing started | `rune:init`, then `rune:vision` |
| `rune.yml` only | ground mapped, no plan | `rune:vision` |
| `vision.md` partial | interview interrupted | `rune:vision` — from the last settled section |
| vision done, decisions `open` | blocked on the user | present the open decisions |
| decisions done, no milestones | vision unfinished | `rune:vision` — generate milestones |
| task `diagnosing` | bug reproduction or planning interrupted | reconcile diagnosis, then `rune:work` |
| protocol record or planner drafts, no registered tasks | planning interrupted | `rune:work` — allocate a fresh draft run |
| milestones, none decomposed | ready to work | `rune:work` — decompose M-01 |
| tasks pending | mid-milestone | `rune:work` — next available task |
| tasks `drifted` or `blocked` by drift | plan needs repair | `rune:work` — re-decompose and atomically retire the obsolete contracts |
| task `blocked` by executor | executor condition unresolved | report the reason and exact unblock condition; route to `rune:work` only after it is proven cleared |
| every non-retired leaf task in all milestones is `done` | v1 reached | report; ask what is next |

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

Resume only on a clear yes, and delete `<main_root>/.rune/PAUSED` when you do. If the pause file says
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

A session restart never clears a blocker. If its objective condition is already proven by
coordination state or the user explicitly confirms it, clear the task's `blocker`, preserve
its finding history plus compatible resume/worktree state, and set it to `pending` in one
validated ledger write. Otherwise report what is blocked, why, and the fact that would
allow it to resume.

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
