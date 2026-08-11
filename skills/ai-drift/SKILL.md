---
name: ai-drift
user-invocable: false
description: Use when reality contradicts a task spec, or when stopping work before completion for any reason. Covers the in-scope tripwire, drift records, handoff notes written for a stranger, and safe worktree disposition.
---

# When the plan is wrong

On any real codebase this is the common path, not an edge case. Task specs are written
from a survey, and surveys are optimistic about what is finished.

Drift handled well is information. Drift handled badly is a ledger that stops describing
reality.

This skill always receives absolute `main_root`. Detect and quiesce also receive the
ledger's exact `worktree_path`; record-only has no source checkout. Any mode that writes a
new record receives a parent-assigned unused `DRF-nnn` plus exact absolute `staging` and
`final` paths. All coordination writes resolve against `main_root`, and every source or
diff check targets only the supplied task worktree. Never infer either root, id, or output
path from the current directory or by scanning `.rune/`.

## Modes

The ordinary mode is **detect**: the task worker discovered drift, writes the causal
record to its assigned staging path plus the handoff below, and discards its own worktree.
Every executor attempt receives a fresh report reservation before it starts. If no drift
is found, the parent marks that slot unused; the worker never repurposes it.

Four bounded modes reuse the same ownership rules without claiming to have discovered new
source facts:

- **record-only** receives the same assigned id, staging and final paths, one or more
  immutable task pointers, and durable evidence pointers. It is used when an
  `ai-verify` verdict says the task's evidence or acceptance contract is not checkable, or
  when migration finds a nonempty legacy `## Amendments` section. Read only those
  coordination artifacts and the ledger dependency graph, write exactly the assigned
  staging record, and return it. The finding is the record's evidence; never rewrite the
  verifier record or interpret legacy amendment prose into a new contract. Do not read or
  change source, write a task handoff, or touch a worktree.
- **quiesce** receives an existing causal drift pointer, task id, and the ledger's exact
  absolute `worktree_path`. Wait until the task's prior worker is confirmed stopped, then
  discard that worktree and task branch without copying or landing their source state.
  Write no new drift record. Preserve every coordination artifact and return
  `status: quiesced`, the task id, causal drift id, and `worktree: discarded`. If the task
  commit is reachable from main, or cleanup cannot prove the source is unpublished, stop
  and return `status: refused`; a `landing` task must be reconciled by `ai-land` instead.
- **abandon** receives a task id and the ledger's exact absolute `worktree_path` after
  `pause` has confirmed the active worker stopped and the user accepted the loss. Prove
  the path is the registered task checkout and its tip is not reachable from main, then
  discard only that worktree and task branch. Write no drift record or handoff and return
  `status: abandoned`, the task id, and `worktree: discarded`. A reachable commit,
  mismatched path, or failed cleanup is `status: refused`; never delete landed work.
- **discard-empty** receives a task id, the exact registered `worktree_path` and task
  branch, plus `main_root`, after `continue` found a dead executor with an empty diff and
  no commits ahead of main. Re-prove that the worker is stopped, the path and branch match
  the task, `git status --porcelain` is empty, and the branch has zero commits after its
  merge-base with current main. Then remove only that worktree and use safe `branch -d`.
  Return `status: discarded`, `worktree: discarded`, and
  `cleanup: complete | branch-pending`. Any failed precondition or failed worktree removal
  is `status: refused` and leaves the registered path intact. This mode writes no report or
  handoff and never accepts a non-empty or ahead checkout.

Each mode is one dispatch and one sole writer. A record writer first validates a complete
collision-resistant sibling candidate, then atomically installs it at the exact staging
path with no-replace semantics. The operation must fail if staging already exists, and the
worker also refuses an existing final path; the parent promotes a complete staging file
instead of re-dispatching. A retry after a crash receives the same assigned paths or the same
registered worktree; it never allocates another drift id or guesses a nearby checkout.

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

**1. Write the drift record** — only the assigned
`<main_root>/.rune/drift/open/DRF-nnn.md` staging path. The parent already chose the id;
the final `<main_root>/.rune/drift/DRF-nnn.md` path must remain absent until promotion:

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

**2. Write the handoff note** — `<main_root>/.rune/notes/T-nnn.md`, per `ai-taskfmt`.

Written for a stranger with an empty context. No "as discussed", no pronouns aimed at a
conversation that will not exist. State what exists on disk now, what surprised you, and
what you would do next.

**3. Discard the worktree.**

A drifted task's immutable contract will be retired and any replacement receives a new id,
branch, worktree, and evidence chain. Source state must not cross that identity boundary.
Discard the task worktree even when one step appears independently useful; name that step
in the handoff so replanning can account for it, but require its replacement to implement
and verify the outcome under the new contract. Keeping or transferring the old diff would
make source written for T-016 appear under T-020 without a truthful publication history.

The task file, progress, handoff, and drift record remain under `<main_root>/.rune/` as
historical evidence. Only task source state is discarded.

Then return to the parent (≤200 tokens):

```
status: drifted
task: T-016
attempt: 2
drift: DRF-003
artifact: /workspace/acme/.rune/drift/open/DRF-003.md
worktree: discarded
worktree_path: /workspace/acme/.rune/worktrees/T-016
summary: handle() has two call sites; T-016 assumed one. T-018/T-019 also affected.
```

The parent accepts only the assigned id and staging pointer, validates the record, then
atomically promotes staging to the assigned final path with no-replace semantics before
writing any ledger pointer or drift freeze. You never write, overwrite, or edit the final
file.

A separate record-only dispatch returns the same interface with its own outcome:

```yaml
status: recorded
task: T-016
drift: DRF-003
artifact: /workspace/acme/.rune/drift/open/DRF-003.md
summary: immutable task evidence requires replanning
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
same gate already blocks on it. Write it to **`<main_root>/.rune/decisions/open/T-nnn.md`** and
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
