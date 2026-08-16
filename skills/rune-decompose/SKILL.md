---
name: rune-decompose
context: fork
allowed-tools: Skill, Read, Glob, Grep, Write, Edit, Bash, mcp__serena__get_symbols_overview, mcp__serena__find_symbol, mcp__serena__find_referencing_symbols
user-invocable: false
description: Use when turning a milestone or a triaged request into independent planner drafts and reconciled task files. Covers sizing limits, context contracts, forbidden lists, and dependency ordering. Runs just-in-time against real code, never ahead of time.
---

# Decomposition

Turns one milestone into independent draft cuts and then reconciled task files. Runs
**immediately before that milestone executes**, never during vision.

The dispatch includes absolute `main_root` and absolute coordination pointers. Resolve
every `.rune/...` read or write against `main_root`; never use the worker's starting
directory or a harness-created worktree as the coordination checkout.

## Bind the selected protocol

A planner or reconciler receives an absolute pointer to the run's
`<main_root>/.rune/drafts/M-nn/R-nnn/protocol.md`. Read it before source or draft work,
confirm its `run` matches the assigned work id, and accept only these pairs:

| type | protocol to load |
|---|---|
| `bug` | `rune-bug` |
| `feature` | `rune-feature` |
| `refactor` | `rune-refactor` |

Load that skill and follow it alongside this one. The record, not the request wording or
the milestone title, decides the protocol. A missing, relative, out-of-run, malformed, or
mismatched pointer is `plan: blocked` before any file is written. An investigation never
reaches this skill for task decomposition.

The protocol also contains `decisions: [...]`, including an explicit empty list. Read the
absolute `decisions.md` pointer supplied with the run, resolve every listed id there, and
require `status: decided`; these records are the durable settled inputs for every planner
and reconciler. A missing, duplicate, open, or unlisted record that constrains the
milestone/request blocks the run. Never substitute prompt text or conversation memory.

A bug protocol also requires `reserved_task: T-nnn`, the exact reserved
`worktree_path`, and an absolute diagnosis progress pointer. Confirm the progress file ends
in `diagnosis: reproduced`, its commit ids exist on `task/T-nnn`, and the worktree is the
registered checkout of that branch. Read bug source and the reproduction from that
worktree, not from `main_root`; do not modify it. A missing or mismatched reservation is
`plan: blocked`, never permission to allocate a replacement id or worktree.
For a drift replan, the reservation must be a fresh id outside the protocol's `retiring`
set, and the diagnosis pointer and branch must belong to that fresh id. The old task's
diagnosis is historical context only; reject any attempt to transfer it into a replacement.

The one exception is a completed-legacy-mitigation repair protocol. It declares
`repair: completed_legacy_mitigation`, `legacy_mitigation: T-nnn`,
`reserved_root_cause: T-mmm`, and the assigned absolute task and repair paths. It
deliberately omits `reserved_task`: the completed legacy task and its progress/verification
evidence are historical diagnosis input, while the parent has already allocated the new
root-cause identity. The reconciler must echo and use that id; it never allocates another.
Reject
this mode unless the supplied ledger shows that old task `done`, its immutable file has
`type: bug` and legacy `kind: mitigation`, and the pending `mitigation-repair` row binds
the exact run, old id, and artifact path.

Milestone-graph work from `rune-vision` is the only job here without a protocol pointer;
it creates milestones rather than executable tasks.

## Why just-in-time

A task must name real files and real symbols. For a milestone three steps out, those
files do not exist yet — they get created by the milestones in between. Anything written
now is fiction composed against imagined code, and every line of it drifts on contact.

Plan the whole road during vision. Pave one section at a time.

The exception is the first milestone, whose ground state is known and which may be
decomposed as soon as vision completes.

## Before decomposing

Read the real code. This is the step that most repays care: a bad cut produces tasks that
are not actually independent, and then every executor blows its budget rediscovering
shared context.

1. For planner or reconcile work, bind and load the protocol above.
2. Read `<main_root>/.rune/map.md` and the milestone's scope and acceptance. For a bug,
   also read the supplied diagnosis block and committed reproduction diff. For a drift
   replan, require the protocol's `rune-drift` and `retiring` fields plus absolute pointers to
   that drift record and every retiring task file; read them before cutting replacements.
3. Use `rune-serena` to look at the actual symbols the milestone touches in the correct
   source checkout: the reserved worktree for a bug, `main_root` otherwise. Overview
   and signatures — not bodies, unless a specific decision depends on one.
4. Confirm no `open` decision blocks this milestone and that every applicable decided id
   is listed in the protocol. If either check fails, stop and surface it.

## Which job you were given

You are dispatched for one of four jobs, and never more than one at a time. The assigned
work id and pointers say which job it is; conversation context is never an input.

**Milestone graph** (from `rune-vision`) — read `vision.md`, `decisions.md`, and where they
exist `map.md` and the survey digest. Write `<main_root>/.rune/milestones.md` per
`rune-taskfmt`.
Everything you need is on disk; the dispatcher's conversation is not available to you and
is not supposed to be. If something the graph obviously needs is missing from those files,
say so and stop rather than inventing it — a gap on disk is a real finding. Return
`plan: graph` and `artifact: <main_root>/.rune/milestones.md`.

You are the sole writer for that file. Build and validate the complete graph in a sibling
candidate, then atomically replace `milestones.md`; never ask the parent to compose, copy,
promote, or amend it. The parent dispatches at most one milestone-graph worker at a time
and must confirm an interrupted predecessor stopped before retrying, so two graph writers
can never be live concurrently.

**Planner draft** (from `rune-work`) — the work id names one assigned slot such as
`M-03/R-002/P-01`, and a pointer names the exact
`<main_root>/.rune/drafts/M-03/R-002/P-01.md` destination. A second pointer names that
run's `protocol.md`. Decompose the milestone against real code and the loaded protocol,
then write one complete candidate cut there per `rune-taskfmt`. Repeat the protocol `type`
and skill in the draft frontmatter and use only local `D-nnn` ids. Do not create a final
`T-nnn`, write under
`<main_root>/.rune/tasks/`, inspect or update `<main_root>/.rune/ledger.md`, or write any
path other than the assigned draft. If the assigned path already exists, return
`plan: blocked`; never overwrite an artifact whose writer may still be alive.
For a bug, mark exactly one proposed task `reservation: primary`; it must own the committed
reproduction check and root-cause fix.
For a drift replan, cover the current milestone outcome against the new code state rather
than editing the old contracts. The retiring files are evidence about the failed cut, not
templates. Use only local `D-nnn` ids and state in `Cut notes` which retiring outcomes each
proposed task replaces, including any old outcome that now needs no task.
Put only harmless, reversible internal choices under `assumptions`. Put every discovered
behaviour/scope ambiguity under `decision_candidates` with options and a recommendation;
do not silently choose it.

**Completed mitigation repair** (from `rune-continue`) — the work id names the fresh run
bound by the pending ledger assignment. Read the repair protocol, legacy task, its durable
evidence, and milestone acceptance. Write exactly one new immutable `type: bug`,
`remediation: root_cause`, `root_cause_followup: none` task in the same milestone and the
exact assigned `mitigation-repair.md` artifact from `rune-taskfmt`; never edit the old task.
Install the reserved task first and repair artifact second with atomic no-replace writes.
On a recovery dispatch, a valid existing reserved task is immutable input: do not overwrite
it; validate it and create only the missing repair artifact. An existing repair artifact
without the task, or either output with mismatched ids or pointers, returns blocked without
writing another output.
The new task must address the causal defect left open by the mitigation and carry its own
valid verification contract. Write both complete artifacts before returning
`plan: reconciled`; if the evidence cannot support a root-cause contract, return
`plan: blocked`, write neither task nor repair artifact, and return a lowercase `blocker`,
stable single-token-or-pointer `detail`, and objective `unblocks_when`. Do not read or write
the ledger, reuse or allocate a final id, create
a planner draft, or turn this relationship into replacement lineage.

**Reconcile** (from `rune-work`) — the work id names one run such as `M-03/R-002`, and you
are given the run's protocol pointer plus pointers to two or three completed draft
artifacts from distinct planner slots under that exact run. First fail closed if a pointer
is missing, duplicated, outside the run, lacks any part of the planner-draft schema, or
declares a different type or protocol. Then pick the strongest cut, graft anything better
from the others, run the protocol-specific sanity pass again on the proposed final cut,
allocate the next unused final `T-nnn` ids, translate all local dependency edges, and write
the final task files. An id is used if it appears anywhere under `.rune/`, including an
unregistered task file left by an interrupted run; never overwrite or reuse it. For a bug,
require exactly one `reservation: primary` in the final
cut and map it to the protocol's existing `reserved_task`; allocate ids only for additional
tasks. Confirm that primary task's check and change surface include the diagnosis commit's
reproduction files. Say which cut you took as the base and what you moved. Where the cuts
disagreed, that seam is the part of the milestone that is genuinely hard to divide; treat
it as the thing to get right, not a tie to break quickly. You are the only worker in the
run allowed to write
`<main_root>/.rune/tasks/`, and you still never write `<main_root>/.rune/ledger.md`.
Refuse reconciliation if any draft has a nonempty `decision_candidates` list or any
protocol decision is no longer decided. The parent must settle the choice and dispatch a
fresh run; final task files are never written from pre-decision drafts.
For a drift replan, also write the exact assigned `replacements.md` artifact per
`rune-taskfmt`. Map every protocol `retiring` id exactly once to `none` or one or more new
ids, require every new id to appear in the map, and fail closed if any non-retired
dependency would still name a retiring task. If every old task maps to `none`, return an
empty task-artifact list only after checking the milestone acceptance against current
code and recording that result in each disposition. Do not edit or delete an old task file.

Every return is ≤200 tokens:

```rune-return
work: M-03/R-002/P-01       # planner; M-03/R-002 for reconciler
summary: ids, one-line titles, and dependency edges; or the blocking pointer
plan: drafted | reconciled | blocked | graph
worktree: none
artifact: /workspace/acme/.rune/drafts/M-03/R-002/P-01.md # milestones.md for graph
artifacts: <main_root>/.rune/tasks/T-021.md, <main_root>/.rune/tasks/T-022.md
replacement_artifact: <main_root>/.rune/drafts/M-03/R-004/replacements.md # replan only
repair_artifact: <main_root>/.rune/drafts/M-03/R-005/mitigation-repair.md # repair only
```

Nothing longer belongs in the return — the complete cuts and final contracts are on disk.
Graph work and ordinary planning/reconciliation return `worktree: none`. A confirmed-bug
planner or reconciler that received the reserved diagnosis checkout instead returns
`worktree: kept` plus that exact `worktree_path`; it never discards diagnosis evidence.

## You may be one of several

Decomposition is the one job in Rune worth running two or three times in parallel and
reconciling, because a bad cut does not announce itself — it surfaces later as executors
colliding on files that were supposed to be disjoint, by which point tasks have been built
on it.

If you are one of several planners on the same milestone, **cut it independently.** Do not
hedge toward what you imagine the others will produce. Where independent cuts agree, the
milestone divided cleanly; where they disagree, that seam is the genuinely hard part, and
the disagreement is the only cheap signal anyone gets that it was hard. A planner that
hedges erases exactly the information the fan-out was dispatched to buy.

Each planner writes only the path for its assigned slot. A reconciling planner then reads
the returned artifact pointers, picks the strongest cut, grafts what is better from the
others, and writes the final task files. No planner return summary is accepted as a
substitute for a complete draft artifact.

## Cutting rules

These are generic defaults. The loaded protocol is authoritative wherever it gives a more
specific task shape. Never silently discard either instruction: if the protocol and a
generic rule cannot both be satisfied, return `plan: blocked` and name the exact conflict
instead of choosing whichever rule is more convenient.

Choose the task type and its required verification mode before choosing the cut. The
evidence contract determines what an independently checkable task looks like.

**Behavior-changing work is vertical.** A `feature`, `bug`, or `chore` uses
`verification: red_then_green`. Cut through the layers, not across them. "Token rotation
end to end" is a task. "All the interfaces, then all the implementations, then all the
tests" is three tasks of which none can demonstrate the behavior change alone. Each task
ends with one declared check observed failing before the change and passing afterward.

**Refactors are horizontal.** A `refactor` uses `verification: green_baseline`. Cut one
mechanical transformation per task: additive structure first, call-site migrations next,
deletion last. Every intermediate task must compile and preserve the same existing check
and oracle baseline. The check already exists; creating a new failing check would turn the
task into a behavior change.

**Characterization is a separate test-only task.** If a refactor has no adequate existing
check, first create a `characterization` task with `verification: characterization`. Its
change surface contains only tests and their fixtures, and its new check must pass against
unchanged production code. The refactor tasks depend on it and keep those tests unchanged.

**Size ceiling: 5 files, one subsystem, one verifiable outcome.** If it needs more, it is
two tasks.

**Independence over elegance.** Two slightly redundant tasks that can run in either order
beat one clever task that couples them. Redundancy costs tokens; coupling costs
correctness.

**Each task names one check and its before/after contract.** New behavior gets a new
red-then-green check. Refactors name the existing green check they preserve.
Characterization adds a new check over behavior that already exists.

## Context contracts

The `read` list is easy. The `forbidden` list is the one that matters and the one
planners skip.

Executors do not blow budgets reading what they need — they blow them exploring. You are
the only agent positioned to know that `src/api/**` is irrelevant to this task and would
cost 40k tokens if opened. The executor cannot know that; it will look, because looking
feels responsible.

Name, with a one-line reason:

- Large modules adjacent to the work but not part of it
- Anything scheduled for deletion or replacement in a later milestone
- Generated directories and vendored code
- Test fixtures large enough to matter

Give the reason. `src/legacy/** — being deleted in M-05` tells the executor it is not
missing something; a bare path makes it wonder.

## Dependencies

Set `blocked_by` only for **hard** dependencies — task B literally cannot compile or run
without task A. Do not encode preference or tidiness; every false dependency serialises
work that could have run in parallel and lengthens the whole milestone.

Number proposed tasks in the order you would naturally do them. A planner uses local
`D-nnn` ids; only the reconciler maps the chosen cut to final `T-nnn` ids. When several
final tasks are eligible, the parent picks lowest id first, so numbering carries your
intent without imposing it.

## Cutting for parallelism

Tasks run concurrently when their **change surfaces share no files**. You control that
directly, so cut with it in mind — it is the difference between a milestone that takes one
pass and one that takes four.

- Prefer cuts along module boundaries over cuts along layers. Two tasks in `auth/` and
  `worker/` can run together; "the interfaces" and "the implementations" cannot.
- When two tasks would both touch one shared file, ask whether that edit can be pulled
  into a single earlier task that both then depend on. One extra dependency often unlocks
  three parallel tasks.
- Be honest in the change surface. A task that quietly touches a file it did not declare
  will collide with whatever else is running, and the merge will be a mess nobody can
  attribute.

Do not contort a decomposition to manufacture parallelism. Correct and serial beats clever
and tangled — the context ceiling is the constraint that matters, not wall-clock.

## Sanity pass

Before writing files, check each task against the generic contract:

- Could a stranger execute this with no knowledge of its siblings?
- Is there exactly one outcome, and is it checkable?
- Does the change surface fit in five files?
- Is there a `forbidden` list, and does it have reasons?
- Do `type`, `remediation`, `root_cause_followup`, and `verification` form one allowed
  task contract from `rune-taskfmt`?
- Does the check name an executable command, assertion, and mode-specific before/after result?
- For `red_then_green`, does it say why the check fails before the change?
- For `green_baseline`, are tests and fixtures absent from the change surface?
- For `characterization`, is production source absent from the change surface?

Then run the loaded protocol's checks:

- **Bug / `rune-bug`:** the task is grounded in the already-observed reproduction; the
  reproduction becomes the regression test; boundary cases appear in acceptance; and a
  mitigation uses `remediation: mitigation` and links a local `root_cause_followup` whose
  target uses `remediation: root_cause`. The reconciler maps that local link to final ids
  and writes both immutable files before registering either. The exact diagnosis check and
  commit are supplied, exactly one proposed task is `reservation: primary`, and that task
  owns the check and root-cause fix. No confirmed reproduction means no task.
- **Feature / `rune-feature`:** the scope boundary and exclusions are present; every
  user-visible decision is settled; tasks are vertical slices; and each task names its
  integration point and failure behavior.
- **Refactor / `rune-refactor`:** the characterization net exists or is established first;
  tasks preserve behavior; the sequence is additive, then mechanical, then subtractive;
  and test files are not edited by the restructuring tasks.

The planner runs both passes before creating its draft. The reconciler runs both again on
the combined final cut before creating any `T-nnn` file. A failed check returns
`plan: blocked`; do not leave a partial draft or partial final task set behind.

## Protocol-shaped examples

These are shape checks, not substitutes for reading the protocol:

```text
bug + bug
  D-001 reservation: primary — keep the reproduced login redirect failure as a regression
        test, fix its cause, and assert the adjacent redirect cases from reproduction

feature + feature
  D-001 store one profile field end to end through the existing API, including its error
        path; later slices add read and edit behavior

refactor + refactor
  D-001 add characterization coverage if the affected entry points are not pinned
  D-002 add the new interface without moving callers
  D-003 migrate callers mechanically
  D-004 remove the old implementation last
```

A generic horizontal feature cut, an unreproduced bug task, or a refactor cut with changed
behavior must fail the sanity pass even if it satisfies the five-file ceiling.

Then finish only the job you were assigned:

- **Planner:** write one complete, immutable artifact at the exact assigned draft pointer
  and return that path.
- **Reconciler:** validate every draft pointer, write the reconciled final task files, and
  return their paths, titles, and dependency edges.

**Never register tasks in the ledger.** The parent is its sole writer and registers the
reconciler's returned final tasks only after every file has been written successfully.

## Re-decomposition after drift

When drift invalidates unfinished tasks, do not patch or overwrite them. Re-read the drift
record, the retiring task files, and the code as it now is, then re-cut the remainder of
the milestone through a fresh, never-reused `R-nnn` directory. Completed tasks remain
`done` and define the current code baseline.

The parent writes `drift: DRF-nnn` and the complete transitive `retiring: [...]` set into
the run's immutable protocol. Every planner gets absolute pointers to the same drift and
old-task artifacts. The reconciler allocates globally unused ids for every replacement,
writes only new task files, then writes `replacements.md`. It may map an old task to
`none` only when the milestone no longer needs that outcome or current code already
satisfies it; the disposition must say which.

Return the replacement artifact pointer with the new task paths. The parent validates it
and performs the one ledger transaction defined by `rune-ledger`: add the new rows and mark
the old rows `retired` with their immediate `replaced_by` values together. Until that
transaction succeeds, the old tasks remain drift-blocked and none of the new tasks is
dispatchable. A crash leaves immutable unregistered files whose ids are burned; the next
run starts fresh rather than guessing or overwriting them.
