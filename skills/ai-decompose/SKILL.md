---
name: ai-decompose
user-invocable: false
description: Use when turning a milestone or a triaged request into task files. Covers sizing limits, context contracts, forbidden lists, and dependency ordering. Runs just-in-time against real code, never ahead of time.
---

# Decomposition

Turns one milestone into task files. Runs **immediately before that milestone executes**,
never during vision.

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

1. Read `.agent/map.md` and the milestone's scope and acceptance.
2. Use `ai-serena` to look at the actual symbols the milestone touches. Overview
   and signatures — not bodies, unless a specific decision depends on one.
3. Confirm no `open` decision blocks this milestone. If one does, stop and surface it.

## Cutting rules

**Vertical, not horizontal.** Cut through the layers, not across them. "Token rotation
end to end" is a task. "All the interfaces, then all the implementations, then all the
tests" is three tasks of which none can be verified alone. Every task must be
independently checkable the moment it lands.

**Size ceiling: 5 files, one subsystem, one verifiable outcome.** If it needs more, it is
two tasks.

**Independence over elegance.** Two slightly redundant tasks that can run in either order
beat one clever task that couples them. Redundancy costs tokens; coupling costs
correctness.

**Each task ends with a check that did not exist before.** If you cannot state what that
check is, the task is not well-formed yet.

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

Number tasks in the order you would naturally do them. When several are eligible, the
parent picks lowest id first, so numbering carries your intent without imposing it.

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
- Does it state a test, and what "must fail before" looks like?

Then write them per `ai-taskfmt` and register them in the ledger via
`ai-ledger`.

## Re-decomposition after drift

When drift invalidates downstream tasks, do not patch them individually. Re-read the
drift record, re-read the code as it now is, and re-cut the remainder of the milestone.
Patched task files accumulate contradictions between their original spec and their
amendments until nobody can tell which parts are still true.

Keep completed tasks. Replace the rest.
