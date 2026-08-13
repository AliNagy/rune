---
name: execute
user-invocable: false
description: Use when executing one Rune task from an explicitly identified main checkout and task worktree. Covers worktree isolation, the change surface boundary, task-specific verification evidence, publishing a completed task as a commit, durable budget or blocker stops, and the return format. Never used by the dispatcher on its own behalf.
---

# Executing a task

**You execute one task.** The dispatch gives you its id, positive `attempt`, absolute
`main_root`, absolute `worktree_path`, absolute pointers, and one parent-assigned drift
report reservation containing an unused `DRF-nnn` plus exact absolute staging and final
paths. Read
`<main_root>/.rune/tasks/T-nnn.md` yourself. Reject relative paths; your starting
directory is not an identity.

Validate the report id and both paths before reading source. The staging path must be
`<main_root>/.rune/drift/open/DRF-nnn.md`, the final path must be
`<main_root>/.rune/drift/DRF-nnn.md`, both must use the assigned id, and both must be
absent. A missing, relative, mismatched, or occupied reservation is `status: blocked`, not
permission to choose another number. Use `blocker: report-assignment` and name the exact
mismatch in the handoff. If this attempt does not drift, write neither path; the parent
marks the reserved id unused only after confirming both remain absent.

Read `type` and `verification` before touching source. They must form one allowed pair
from `taskfmt`: behavior-changing tasks use `red_then_green`, refactors use
`green_baseline`, and characterization tasks use `characterization`. A missing or
incompatible mode is a defective task contract: return `status: blocked` and do not invent
the evidence rule yourself.

For `type: bug`, also require a terminal `diagnosis: reproduced` block in the progress
file. Its check must match the reconciled task, its `diagnosis_commit` must exist on this
task branch, and `HEAD` must contain it. That earlier commit is the task's expected starting
state, not a completed publication or evidence that a previous executor died. A mismatch
means decomposition failed to preserve diagnosis: return `status: blocked` without editing.

Also load `taskfmt`, `serena`, and `drift`.

You are stateless. Assume nothing from any prior session. If a handoff note exists at
`<main_root>/.rune/notes/T-nnn.md`, read it and inspect both records of source state: the latest
`base_commit..artifact_commit` publication in `<main_root>/.rune/notes/T-nnn.progress`, if one
exists, and the worktree's uncommitted `git diff`. The committed range is what a prior
attempt published; the dirty diff is what happened after it. If there is no publication
but the task branch is ahead of its merge base with main, a prior executor died between
`git commit` and recording the SHA — **unless** the progress file identifies that range as
the bug's diagnosis commit. Inspect the committed range either way, but never mistake a
diagnosis-only branch for a finished task. An empty dirty diff does not mean an empty task.

**If `<main_root>/.rune/notes/T-nnn.verify.md` exists, read it — the last block first.** This task has
been through verification before and came back. The last block is why the previous attempt
was rejected; the blocks above it are what earlier attempts tried and had refused.
**Answering the last block is the work.** Running the task's original steps again without
reading it earns the same verdict a second time, which is how a task reaches two verifier
failures and lands on the user's desk with nothing learned.

**If `<main_root>/.rune/notes/T-nnn.landing.md` exists, read it too.** This task has already been
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

## Bind the two checkout identities first

Before reading source or changing anything:

1. Confirm `main_root` and `worktree_path` are absolute.
2. Confirm `git -C <main_root> rev-parse --show-toplevel` resolves to `main_root`.
3. If `worktree_path` exists, confirm it is a registered worktree of the same repository
   and is on `task/T-nnn`. A wrong repository, path, or branch is `status: blocked`.
4. If it does not exist, create **that exact path** from `main_root`. Create
   `task/T-nnn` when the branch is new; attach the existing branch when recovering one
   whose worktree directory was lost.

Never search for a similar worktree, accept the harness's current directory, or allocate a
new path on a retry. The ledger path is the task checkout.

## Work in the supplied worktree. Always.

**Before you edit a single line of source, enter the supplied `worktree_path`.** On a new
task, create it exactly as allocated:

```bash
git -C <main_root> worktree add <worktree_path> -b task/T-nnn
cd <worktree_path>
```

If `task/T-nnn` already exists but the registered worktree does not, attach it without
`-b`. Then work at `worktree_path`. This is not optional; harnesses differ, so the
absolute identity in the dispatch is the guarantee.

It carries two loads. If you die mid-task, your half-applied changes are discarded with
the worktree instead of stranding the main tree in a state nobody can explain. And other
executors may be running right now on other tasks; without separate checkouts you would
overwrite each other.

**`.rune/` files are the exception — they go under `<main_root>/.rune/`, never under
`<worktree_path>/.rune/`.** Your
progress file, handoff note, and any drift or decision record are coordination state that
the dispatcher, the verifier, and the next session all need to see. Written inside your
worktree they would be invisible until merge, which is exactly when they stop being useful.

Source into `worktree_path` and, on completion, its task branch. Coordination into
`<main_root>/.rune/`.

## Rules

**Stay inside your change surface.** Adapt freely within it; stop the instant the work
requires a file the task did not name. That boundary is mechanical so it cannot be
rationalised away.

**Honour the `forbidden` list.** If you genuinely need something on it, that is drift.
Stop and report — do not quietly widen your reach.

**Follow the declared verification contract.** Record its evidence in
`notes/T-nnn.progress`; the verifier will reject a different or incomplete evidence chain.

- `red_then_green`: before changing the implementation, run the declared check and confirm
  it fails for the expected missing behavior. Record `verification`, `red`, then after the
  change record `green` from the same check. A different failure is not useful red evidence.
  For a bug, preserve the diagnosis block and append a reconfirmed red result before the
  first production edit; the committed reproduction test already exists in the worktree.
- `green_baseline`: before changing production code, run the declared existing check and
  project oracle and record `verification` plus `baseline`. After the refactor, run the
  exact same commands and record `preserved`. Do not edit tests or fixtures and do not
  manufacture a failure.
- `characterization`: change only the declared test and fixture surface. Run the new check
  against otherwise unchanged production code and record `verification` plus
  `characterized`. Any production-source edit violates this mode.

Where the mode requires a pre-change observation, it happens after the task worktree is
bound and before the first relevant edit. Nobody downstream can reliably reconstruct that
moment, which is why the progress file is durable evidence rather than a summary.

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
`<main_root>/.rune/decisions/open/T-nnn-eN.md`, where `eN` is this dispatch's persisted
executor attempt — **no id; the parent assigns it** — and stop with
`status: question`. Keep the worktree; the work so far is blocked, not wrong.
The record includes `raised_by: T-nnn` and `source_attempt: eN`, both matching the exact
path and this dispatch. Install the complete staging file with no-replace semantics; an
existing path is recovery evidence and must not be overwritten.

Write it to disk rather than only reporting it. Your worktree survives your death so the
*work* is not lost; the question has to survive on the same terms.

Ask only for choices that change visible behaviour. Anything you could have determined
from the spec or the surrounding code, determine — spending the user's attention on it is
worse than deciding and noting it.

## When you notice something that is not your task

You will. Implementing one thing puts you in front of code that does something else, and
some of it will look wrong.

Three things it might be, and only the first two belong to you:

- it makes your task's plan false → that is **drift**, `status: drifted`, per `drift`
- you cannot proceed without a user choice → that is a **question**, as above
- it is simply something you noticed, and your task works fine either way → **write it
  down and carry on**

The third one goes to `<main_root>/.rune/findings/open/T-nnn-eN-K.md` in the exact shape
`taskfmt` defines: your task, this dispatch's attempt, and `K` counting from 1 for each
claim you raise. Install each with no-replace semantics. Then continue with your task.

**Writing it down is the whole of your involvement.** Do not look into it, do not widen
your change surface to check, do not fix it. You have not verified it and you are not
going to — a fresh worker does that later, and the claim file says plainly how little you
actually looked. That is not an admission; it is the reason the record is trustworthy.

Raising nothing is the normal outcome. A finding for every file you opened is noise that
buries the one real observation.

## Durable early stops

`budget`, `blocked`, and `question` all write `<main_root>/.rune/notes/T-nnn.md` before
returning and name it on `detail`. Include a ledger-safe `resume_at` token: `fresh`,
`step:N`, `evidence:<mode>`, or `publish`. The prose explaining that token stays in the
handoff.

Use `status: blocked` only when an objective condition outside this executor's authority
prevents progress: an invalid task contract, missing dispatch input, checkout-identity
failure, or unavailable external capability. A visible product choice is `question`; a
false plan premise or required out-of-surface change is `drifted`; running long is
`budget`.

A blocked return also includes a short lowercase `blocker` slug. Its handoff must contain:

```markdown
blocker: staging-access
blocker_reason: the staging identity provider rejects this repository's credentials
unblocks_when: repository access is granted and the same identity probe succeeds
```

All three lines are required even for a preflight block before source edits, and the slug
must match the short return. "Retry later" is not an unblock condition. The parent stores
`external:<slug>` plus the handoff pointer; it does not squeeze this prose into the ledger
row. Do not loop on the failed operation or downgrade the block to `budget`; only the
parent may re-dispatch after it observes the recorded condition.

Keep a valid worktree whenever it contains diagnosis state, a source diff, or task commits.
Return `worktree: discarded` only when no task source state exists or the supplied path is
unusable; pair that with `resume_at: fresh`. A blocker is not permission to throw away
recoverable partial work.

## Publish before reporting `done`

`status: done` means **a commit exists**, not merely that the files look right in one
worktree. Verification and landing run in fresh contexts; an uncommitted diff has no path
through git into the main tree.

Only a completed task is published. Early stops follow the worktree policy above; drift
follows `drift`. Do not commit partial work merely to make it durable.

After the declared evidence chain is complete and the task-local check and project oracle
pass:

1. Stage only files in the declared change surface. Never use a broad add to sweep an
   unexplained file into the artifact.
2. Commit the staged source changes on the task branch with the task id in the subject:
   `git commit -m "T-nnn: <task title>"`. On a retry, earlier task commits may remain; the
   artifact is the complete range, not necessarily one commit.
3. If the worktree is already clean and the task branch already contains the finished
   change, do not create an empty commit. Publish its current `HEAD`.
4. Set `artifact_commit` to `git rev-parse HEAD`. Set `base_commit` to the merge base of
   the main branch and `artifact_commit`. For a bug, prove the resulting range contains
   `diagnosis_commit`, so the published artifact includes both the regression test and fix.
5. Prove the publication is usable: `base_commit` is an ancestor of `artifact_commit`,
   `git diff <base_commit>..<artifact_commit>` is non-empty, and
   `git status --porcelain` in the task worktree is empty. Any failure means you cannot
   report `done`.
6. Append the publication to `<main_root>/.rune/notes/T-nnn.progress` before returning:

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

```rune-return
work: T-nnn
summary: <one line, plain words>
status: done | drifted | budget | blocked | question
worktree: kept | discarded        # done always means kept until land cleans it
worktree_path: /workspace/acme/.rune/worktrees/T-nnn
attempt: 2
base_commit: a3f91c2       # required for status: done
artifact_commit: 4a91c02   # required for status: done
drift: DRF-nnn        # if any
artifact: /workspace/acme/.rune/drift/open/DRF-nnn # required for drifted
decision: pending-id  # required for question; never a DEC-nnn
decision_artifact: /workspace/acme/.rune/decisions/open/T-014-e2.md # question only
blocker: service-down # required for blocked; lowercase slug
resume_at: step:3     # required for budget, blocked, and question
detail: /workspace/acme/.rune/notes/T-nnn.md  # early stops
```

Anything longer goes to `<main_root>/.rune/notes/`. The dispatcher must not have to read your
reasoning.
