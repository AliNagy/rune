---
name: ai-drift
user-invocable: false
description: Use when reality contradicts a task spec, or when stopping work before completion for any reason. Covers the in-scope tripwire, drift records, handoff notes written for a stranger, and worktree keep-or-discard.
---

# When the plan is wrong

On any real codebase this is the common path, not an edge case. Task specs are written
from a survey, and surveys are optimistic about what is finished.

Drift handled well is information. Drift handled badly is a ledger that stops describing
reality.

This skill inherits absolute `main_root` and `worktree_path` from `ai-execute`. All
coordination writes resolve against `main_root`; all source and diff checks target the
exact supplied task worktree. Never infer either from the current directory.

## The tripwire

**Adapt freely inside your declared change surface. Stop the moment the fix requires a
file the task did not name.**

That boundary is mechanical, so it cannot be rationalised away under pressure:

- The signature differs from what the spec assumed, but the file is yours → **adapt**,
  note it, continue.
- A helper you expected does not exist and you can add it inside your surface →
  **adapt**, note it, continue.
- The fix requires editing a file outside your change surface → **stop**.
- The fix requires reading something on the `forbidden` list → **stop**.
- The task's premise is simply false — the thing it modifies does not exist, or already
  works → **stop**.

"I had to leave my sandbox" is exactly the signal that the *plan* needs revisiting, not
just this task. That is why the boundary is drawn at files rather than at judgement.

Adaptations inside the surface still get recorded in the progress file. Silent
adaptation is how plans rot while every row stays green.

## Stopping properly

Three things, in this order.

**1. Write the drift record** — `<main_root>/.agent/drift/DRF-nnn.md`:

```markdown
# DRF-003
from_task: T-016
kind: false_premise      # false_premise | out_of_scope | blocked | wrong_shape
found: handle() is called from two places — src/server.ts and src/ws/upgrade.ts.
       The task assumed one call site and its acceptance only covers the HTTP path.
evidence: find_referencing_symbols SessionMiddleware/handle -> 2 results
invalidates: T-018, T-019    # they assume a single entry path
suggests: split the websocket path into its own task, or widen T-016's surface
```

`invalidates` is the load-bearing field. You are the only agent who has seen this. Name
every downstream task whose premise this breaks — the parent will block them.

**2. Write the handoff note** — `<main_root>/.agent/notes/T-nnn.md`, per `ai-taskfmt`.

Written for a stranger with an empty context. No "as discussed", no pronouns aimed at a
conversation that will not exist. State what exists on disk now, what surprised you, and
what you would do next.

**3. Decide the worktree.**

First matching rule wins:

1. Any change built on the false premise → **discard**.
2. Any change outside the declared change surface → **discard**.
3. A declared step is fully applied, passes on its own, and does not depend on the false
   premise → **keep**, and name that step in the handoff.
4. Otherwise → **discard**.

Discard is the default because it is the safe direction, and rule 3 is deliberately narrow
— "a step that is finished and independent" is checkable, where "substantial work" is
not.

You do not need to journal what you changed. `git diff` in the worktree is the record; it
is atomic with the edit and cannot desync. Say whether to trust it, not what it contains.

Then return to the parent (≤200 tokens):

```
status: drifted
drift: DRF-003
worktree: discarded
summary: handle() has two call sites; T-016 assumed one. T-018/T-019 also affected.
```

## Stopping for budget

Same shape, different reason. At roughly 60% of context, stop taking new ground: finish
the step in flight, write the handoff, keep the worktree, return `status: budget`.

The task returns to `pending` and a fresh executor resumes from the handoff and the diff.
This is a normal outcome, not a failure. Running to exhaustion — producing a truncated
result and no handoff — is the failure, because it forces the next attempt to start from
nothing.

If a task drifts or exhausts budget repeatedly, that is a decomposition problem. Say so
in the drift record. A task that keeps bouncing was cut too large, and that is
information about the planner.

## Stopping to ask the user something

You cannot talk to the user. The dispatcher can. So when you hit a choice you have no
authority to make, end your run and hand the question up.

**The tripwire: ask only when the answer changes behaviour the user would notice, and the
task spec does not settle it.**

- A technical choice inside your change surface — helper name, loop or map, where a
  private function lives → **decide it yourself**, note it, continue.
- A choice the user would notice and might disagree with — what happens to expired data,
  whether an error is silent or loud, what a default value is → **ask**.
- The task spec already answers it → **do not ask**. Re-read it.
- The code already answers it — an existing convention, a pattern used everywhere else →
  **do not ask**. Follow the convention and say you did.

An agent that asks about things it could have determined is worse than one that guesses,
because it spends the user's attention, which is the scarcest thing in the system.

When you do ask, write an open decision record rather than inventing a new artifact — the
same gate already blocks on it. Write it to **`<main_root>/.agent/decisions/open/T-nnn.md`** and
**do not assign an id**: three executors run at once, so a shared file races and two
workers would both reach for `DEC-012`. The parent assigns the number and moves it into
`decisions.md`.

```markdown
## Expired session rows
status: open
raised_by: T-017
options:
  - Delete the row - simpler, no cleanup job
  - Keep it flagged - supports "you were logged out at 4pm", needs a sweep
recommendation: keep flagged
decided: -
rationale: -
```

Then write your handoff, **keep** the worktree — the work so far is usually fine, it is
just blocked — and return:

```
status: question
task: T-017
worktree: kept
decision: DEC-012
summary: expired sessions - delete or flag? blocked until decided
```

Give a recommendation every time. "I don't know, you decide" wastes the round trip; the
user wants your read, they just want the final call.

## What not to do

**Do not widen scope to be helpful.** Fixing an unrelated bug you noticed inside another
module is not a favour — it lands unreviewed, unverified, and outside every acceptance
criterion in the ledger. Record it in the drift record as an observation and leave it.

**Do not fabricate a passing state.** If the test will not go green, report that. A
`drifted` row is cheap. A `done` row over broken code costs the whole system its
credibility, because everything downstream assumes done means done.

**Do not resume by reconstructing memory.** Read the handoff and the diff. If they do not
explain the state, discard the worktree and start clean — that is cheaper and safer than
inferring intent from an abandoned edit.
