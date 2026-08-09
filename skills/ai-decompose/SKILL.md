---
name: ai-decompose
user-invocable: false
description: Use when turning a milestone or a triaged request into independent planner drafts and reconciled task files. Covers sizing limits, context contracts, forbidden lists, and dependency ordering. Runs just-in-time against real code, never ahead of time.
---

# Decomposition

Turns one milestone into independent draft cuts and then reconciled task files. Runs
**immediately before that milestone executes**, never during vision.

The dispatch includes absolute `main_root` and absolute coordination pointers. Resolve
every `.agent/...` read or write against `main_root`; never use the worker's starting
directory or a harness-created worktree as the coordination checkout.

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

1. Read `<main_root>/.agent/map.md` and the milestone's scope and acceptance.
2. Use `ai-serena` to look at the actual symbols the milestone touches. Overview
   and signatures — not bodies, unless a specific decision depends on one.
3. Confirm no `open` decision blocks this milestone. If one does, stop and surface it.

## Which job you were given

You are dispatched for one of three jobs, and never more than one at a time. The assigned
work id and pointers say which job it is; conversation context is never an input.

**Milestone graph** (from `rune:vision`) — read `vision.md`, `decisions.md`, and where they
exist `map.md` and the survey digest. Write `<main_root>/.agent/milestones.md` per
`ai-taskfmt`.
Everything you need is on disk; the dispatcher's conversation is not available to you and
is not supposed to be. If something the graph obviously needs is missing from those files,
say so and stop rather than inventing it — a gap on disk is a real finding. Return
`plan: graph` and `artifact: <main_root>/.agent/milestones.md`.

**Planner draft** (from `rune:work`) — the work id names one assigned slot such as
`M-03/R-002/P-01`, and a pointer names the exact
`<main_root>/.agent/drafts/M-03/R-002/P-01.md` destination. Decompose the milestone
against real code and write one complete candidate cut there per `ai-taskfmt`. Use only
local `D-nnn` ids. Do not create a final `T-nnn`, write under
`<main_root>/.agent/tasks/`, inspect or update `<main_root>/.agent/ledger.md`, or write any
path other than the assigned draft. If the assigned path already exists, return
`plan: blocked`; never overwrite an artifact whose writer may still be alive.

**Reconcile** (from `rune:work`) — the work id names one run such as `M-03/R-002`, and you
are given pointers to two or three completed draft artifacts from distinct planner slots
under that exact run. First fail closed if a pointer is missing, duplicated, outside the
run, or lacks any part of the planner-draft schema. Then pick the strongest cut, graft
anything better from the others, allocate the next unused final `T-nnn` ids, translate all
local dependency edges, and write the final task files. Say which cut you took as the base
and what you moved. Where the cuts disagreed, that seam is the part of the milestone that
is genuinely hard to divide; treat it as the thing to get right, not a tie to break
quickly. You are the only worker in the run allowed to write
`<main_root>/.agent/tasks/`, and you still never write `<main_root>/.agent/ledger.md`.

Every return is ≤200 tokens:

```
plan: drafted | reconciled | blocked | graph
task: M-03/R-002/P-01       # planner; M-03/R-002 for reconciler
artifact: /workspace/acme/.agent/drafts/M-03/R-002/P-01.md # milestones.md for graph
artifacts: <main_root>/.agent/tasks/T-021.md, <main_root>/.agent/tasks/T-022.md
summary: ids, one-line titles, and dependency edges; or the blocking pointer
```

Nothing longer belongs in the return — the complete cuts and final contracts are on disk.

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

Before writing files, check each task against:

- Could a stranger execute this with no knowledge of its siblings?
- Is there exactly one outcome, and is it checkable?
- Does the change surface fit in five files?
- Is there a `forbidden` list, and does it have reasons?
- Do `type` and `verification` form one allowed pair from `ai-taskfmt`?
- Does the check name an executable command, assertion, and mode-specific before/after result?
- For `red_then_green`, does it say why the check fails before the change?
- For `green_baseline`, are tests and fixtures absent from the change surface?
- For `characterization`, is production source absent from the change surface?

Then finish only the job you were assigned:

- **Planner:** write one complete, immutable artifact at the exact assigned draft pointer
  and return that path.
- **Reconciler:** validate every draft pointer, write the reconciled final task files, and
  return their paths, titles, and dependency edges.

**Never register tasks in the ledger.** The parent is its sole writer and registers the
reconciler's returned final tasks only after every file has been written successfully.

## Re-decomposition after drift

When drift invalidates downstream tasks, do not patch them individually. Re-read the
drift record, re-read the code as it now is, and re-cut the remainder of the milestone.
Patched task files accumulate contradictions between their original spec and their
amendments until nobody can tell which parts are still true.

Run the same fan-out through a fresh, never-reused `R-nnn` directory. Keep completed tasks.
Replace the rest.
