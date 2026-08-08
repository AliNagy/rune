---
name: ai-execute
user-invocable: false
description: Use when executing one Rune task - you have been dispatched with a task id and nothing else. Covers worktree isolation, the change surface boundary, red-before-green, publishing a completed task as a commit, budget stops, and the return format. Never used by the dispatcher on its own behalf.
---

# Executing a task

**You execute one task.** You were given an id and nothing else — read
`.agent/tasks/T-nnn.md` yourself.

Also load `ai-taskfmt`, `ai-serena`, and `ai-drift`.

You are stateless. Assume nothing from any prior session. If a handoff note exists at
`.agent/notes/T-nnn.md`, read it and inspect both records of source state: the latest
`base_commit..artifact_commit` publication in `.agent/notes/T-nnn.progress`, if one
exists, and the worktree's uncommitted `git diff`. The committed range is what a prior
attempt published; the dirty diff is what happened after it. If there is no publication
but the task branch is ahead of its merge base with main, a prior executor died between
`git commit` and recording the SHA. Inspect that committed range too; an empty dirty diff
does not mean an empty task.

**If `.agent/notes/T-nnn.verify.md` exists, read it — the last block first.** This task has
been through verification before and came back. The last block is why the previous attempt
was rejected; the blocks above it are what earlier attempts tried and had refused.
**Answering the last block is the work.** Running the task's original steps again without
reading it earns the same verdict a second time, which is how a task burns its two attempts
and lands on the user's desk with nothing learned.

**If `.agent/notes/T-nnn.landing.md` exists, read it too.** This task has already been
verified once and then failed to merge into the main tree. That file holds the exact
failures, quoted, and whether they fell inside the task's declared change surface. Skipping
it is how an attempt repeats the one before it move for move — the failure it names is the
work, not the task's original steps over again.

Both records can exist at once. They fail at different gates: the verify record means the
change did not meet its own acceptance, the landing record means it did and then broke the
main tree on merge. Read both, and treat the later one as the live problem.

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

Source into the worktree and, on completion, its task branch. Coordination into `.agent/`
in the main tree.

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

## Publish before reporting `done`

`status: done` means **a commit exists**, not merely that the files look right in one
worktree. Verification and landing run in fresh contexts; an uncommitted diff has no path
through git into the main tree.

Only a completed task is published. `budget`, `blocked`, `question`, and `drifted` keep or
discard their dirty worktree exactly as their stopping rules say; do not commit partial
work merely to make it durable.

After the task-local check and project oracle pass:

1. Stage only files in the declared change surface. Never use a broad add to sweep an
   unexplained file into the artifact.
2. Commit the staged source changes on the task branch with the task id in the subject:
   `git commit -m "T-nnn: <task title>"`. On a retry, earlier task commits may remain; the
   artifact is the complete range, not necessarily one commit.
3. If the worktree is already clean and the task branch already contains the finished
   change, do not create an empty commit. Publish its current `HEAD`.
4. Set `artifact_commit` to `git rev-parse HEAD`. Set `base_commit` to the merge base of
   the main branch and `artifact_commit`.
5. Prove the publication is usable: `base_commit` is an ancestor of `artifact_commit`,
   `git diff <base_commit>..<artifact_commit>` is non-empty, and
   `git status --porcelain` in the task worktree is empty. Any failure means you cannot
   report `done`.
6. Append the publication to `.agent/notes/T-nnn.progress` before returning:

```yaml
publication: 2
base_commit: a3f91c2
artifact_commit: 4a91c02
```

Append; never replace an earlier publication. Verification findings and landing failures
can send a task around the loop, and each attempt needs to say exactly which immutable
range it produced. The last publication is live.

The two commit ids are the handoff interface. The verifier checks that exact artifact;
the lander merges only the commit the verifier names. A return value alone is not durable,
so the progress file is authoritative and the return repeats the ids for routing only.

## Return (≤200 tokens)

```
status: done | drifted | budget | blocked | question
task: T-nnn
worktree: kept | discarded        # done always means kept until ai-land cleans it
summary: <one or two lines>
base_commit: a3f91c2       # required for status: done
artifact_commit: 4a91c02   # required for status: done
drift: DRF-nnn        # if any
decision: DEC-nnn     # if status is question
```

Anything longer goes to `.agent/notes/`. The dispatcher must not have to read your
reasoning.
