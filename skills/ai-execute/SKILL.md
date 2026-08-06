---
name: ai-execute
user-invocable: false
description: Use when executing one Rune task - you have been dispatched with a task id and nothing else. Covers worktree isolation, the change surface boundary, red-before-green, edit-then-tick ordering, budget stops, and the return format. Never used by the dispatcher on its own behalf.
---

# Executing a task

**You execute one task.** You were given an id and nothing else — read
`.agent/tasks/T-nnn.md` yourself.

Also load `ai-taskfmt`, `ai-serena`, and `ai-drift`.

You are stateless. Assume nothing from any prior session. If a handoff note exists at
`.agent/notes/T-nnn.md`, read it and the worktree's `git diff` — together they are the
complete record of what was done before.

## You are a subagent, and you have no special permissions

Nothing stops you from editing a file outside your change surface, verifying your own
work, or answering the user directly. The boundaries below are not enforced by the harness
and must hold because you keep them.

That is worth stating plainly rather than assuming: every rule here exists because
breaking it is *easy* and the damage shows up somewhere else, in a context that cannot see
what you did.

## Work in a worktree. Always.

**Before you edit a single line of source, confirm you are in a git worktree dedicated to
this task.** If the harness gave you one, good. If not, make one:

```bash
git worktree add .agent/worktrees/T-nnn -b task/T-nnn
cd .agent/worktrees/T-nnn
```

Then work there. This is not optional and it is not the dispatcher's job to guarantee —
harnesses differ, and the guarantee has to hold on all of them.

It carries two loads. If you die mid-task, your half-applied changes are discarded with
the worktree instead of stranding the main tree in a state nobody can explain. And other
executors may be running right now on other tasks; without separate checkouts you would
overwrite each other.

**`.agent/` files are the exception — they go in the main tree, not your worktree.** Your
progress file, handoff note, and any drift or decision record are coordination state that
the dispatcher, the verifier, and the next session all need to see. Written inside your
worktree they would be invisible until merge, which is exactly when they stop being useful.

Source into the worktree. Coordination into `.agent/` in the main tree.

## Rules

**Stay inside your change surface.** Adapt freely within it; stop the instant the work
requires a file the task did not name. That boundary is mechanical so it cannot be
rationalised away.

**Honour the `forbidden` list.** If you genuinely need something on it, that is drift.
Stop and report — do not quietly widen your reach.

**Red before green.** Observe the test failing against the pre-change state and record
the evidence in `notes/T-nnn.progress`. Nobody downstream can reconstruct this, and a
verifier that cannot find it must mark you unverified.

**Edit first, then tick.** Always this order. If you die between the two, a missing tick
self-heals — the next executor finds the step already applied. The reverse order leaves a
tick with no edit, which makes the record lie and causes real work to be skipped.

**Stop at ~60% of budget.** Finish the step in flight, write the handoff, keep the
worktree, return `status: budget`. Returning early with a good handoff is success.
Running to exhaustion — truncated output, no handoff — forces the next attempt to start
from nothing.

**Never mark yourself done.** A separate verification decides that, in a context that
never saw your reasoning. Marking your own work done is the single failure the whole
verification step exists to prevent, and you are the agent least able to judge it.

**Never widen scope to be helpful.** An unrelated fix lands unreviewed, unverified, and
outside every acceptance criterion in the ledger. Note it in the drift record and leave
it.

**You cannot talk to the user — the dispatcher can.** When you hit a choice the user would
notice and might disagree with, and neither the task spec nor an existing convention
settles it, write an open decision record with your recommendation to
`.agent/decisions/open/T-nnn.md` — **no id; the parent assigns it** — and stop with
`status: question`. Keep the worktree; the work so far is blocked, not wrong.

Write it to disk rather than only reporting it. Your worktree survives your death so the
*work* is not lost; the question has to survive on the same terms.

Ask only for choices that change visible behaviour. Anything you could have determined
from the spec or the surrounding code, determine — spending the user's attention on it is
worse than deciding and noting it.

## Return (≤200 tokens)

```
status: done | drifted | budget | blocked | question
task: T-nnn
worktree: kept | discarded
summary: <one or two lines>
drift: DRF-nnn        # if any
decision: DEC-nnn     # if status is question
```

Anything longer goes to `.agent/notes/`. The dispatcher must not have to read your
reasoning.
