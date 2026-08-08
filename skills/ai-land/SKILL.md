---
name: ai-land
user-invocable: false
description: Use when merging one verified task's worktree into the main tree. Merges, re-runs the project oracle, reverts the merge if the oracle fails, and records why so the next attempt is not blind. Never used on unverified work, and never by the parent on its own behalf.
---

# Landing a verified task

A verified task is proven **in its own worktree**. Landing asks a different question: does
the main tree still work with this change in it? Only merging can answer that, and only
running the suite afterwards can prove it.

Two tasks can each pass verification and still break the project together — task A renames
something task B calls, neither touches the other's files, git merges both without
complaint. Verification cannot see that, by construction. This is where it surfaces.

**Run as a subagent.** Merging is bounded; a suite log is not, and the parent must never
hold one. That is also why landing is not the last step of verification: the verifier
proved the task against the tree it was cut from, and a merge into a tree it never saw is
a new claim needing new evidence.

**Land exactly one task per agent.** Merges are serialised by construction — two landers at
once are two writers on the main tree.

## You may change the main tree, and you are the only worker who may

Every other worker in Rune is confined to a worktree. You are not: merging and reverting
happen in the main checkout, and they are your job.

That makes you the one place where a mistake is not contained by a worktree boundary. The
sequence below is fixed for that reason. Do not improvise inside it, and do not add a step
because the situation seems to call for one.

## Inputs

- the task id, and its worktree branch
- `.agent/tasks/T-nnn.md` — the change surface, for judging whether a failure is even this
  task's to answer for
- `.agent/rune.yml` — the oracle command and its known-red baseline
- `.agent/notes/T-nnn.landing.md` — earlier landing attempts, if this is a retry

**Read the landing record first when it exists.** You are stateless — every dispatch starts
empty — so that file is the only thing that tells you which attempt this is and what the
last four already tried. Without it you would re-land blind on every pass and never reach
the ceiling below.

## Sequence

Fixed order. Do not reorder, do not skip.

**1. Check the tree is clean outside `.agent/`.** `git status --porcelain` — anything
modified beyond `.agent/` means someone left source changes in the main checkout, and a
rollback could not tell them apart from the merge. Stop, record the attempt, return `stuck`,
and say what is dirty.

`stuck` is the outcome for **any state only a human can resolve** — a dirty main tree here,
or a rollback that did not restore one at step 6. Both mean the same thing to the parent:
land nothing else until someone looks.

**2. Record the rollback point.** `git rev-parse HEAD` in the main tree. Every undo below
depends on this one line. Capture it before you touch anything.

**3. Merge the task's branch** into the main tree.

Conflict → `git merge --abort`, record the attempt, return `conflict`. Nothing landed and
the tree is untouched, so there is nothing to roll back — you skip step 5's rollback and
write the record alone. What this needs is not a code fix: the worktree has fallen behind
main and has to catch up before it can land.

**4. Run the project oracle** in the main tree, per `ai-oracle`. Compare against the
known-red baseline in `rune.yml`, never against zero failures.

**Skip this only when the merge was a fast-forward.** The tree is then byte-identical to
the worktree `ai-verify` already ran the oracle in, so a re-run cannot say anything new.
Any other merge produced a tree nobody has tested yet. That is a git fact you check, not
a call you make — and it is the only permitted reason to skip.

Pass → return `landed`. You are done.

**5. Roll the merge back, then write the record.**

Undo first, record second — the same write-order rule executors follow, and for the same
reason. If you die between the two, a missing record is recoverable and a record with the
bad merge still in the tree is not. You are holding the oracle output in context; it
survives the rollback.

Reset the main tree to the commit from step 2, **preserving uncommitted `.agent/` state** —
it holds the ledger and this task's own notes, and losing it costs more than the merge did:

```bash
git reset <sha>                        # move HEAD back; worktree untouched
git checkout -- ':(exclude).agent'     # source files back to <sha>
git clean -fd -- ':(exclude).agent'    # drop files the merge added
```

**Do not undo the merge with `git revert -m 1`.** It leaves the merge in history, and git
then treats the branch as already merged — so the fixed worktree would land as an empty
diff on the next attempt. Re-landing the same branch is the entire point of this loop, and
that one command quietly breaks it.

**6. Run the oracle again** to confirm the rollback actually restored the tree.

Green → return `reverted`. Main is back to known-good.
Still red → return `stuck`. Say so plainly. The rollback did not restore the tree, and no
further landing is safe until a human looks.

Step 6 is the step most worth not skipping. A rollback assumed to have worked and did not
leaves main red while your return value says it is green — which is the exact failure this
skill exists to prevent, moved one step later where nobody is looking for it.

## The landing record

`.agent/notes/T-nnn.landing.md` — your state file, and the counterpart to the executor's
`notes/T-nnn.progress`. Sole writer: the lander holding T-nnn.

Three things fix it in that spot. It is **per-task**, so it satisfies the concurrency rule
in `ai-taskfmt` without anyone having to think about it. It is **separate from the
executor's two files** because it has a different sole writer, and merging writers is the
one thing that rule exists to prevent. And it lives under `.agent/` in the **main tree**,
which is what carries it across the rollback at step 5 — a record written into the task's
worktree would be invisible to the parent until merge, which is precisely the moment it
stops mattering.

Append one block per attempt; never edit an earlier one. The history is the point.

```markdown
## attempt 2 — 2026-08-07
outcome: reverted
merged: 4a91c02             # the merge commit, now rolled back
rolled_back_to: 8f3e1d7     # HEAD before the merge
oracle: 2 new failures, neither in the known-red baseline
failing:
  - auth/session.test.ts :: "refresh keeps the device id"
    Expected "dev-7781", received undefined
  - api/routes.test.ts :: "POST /refresh returns 200"
    TypeError: rotate is not a function
in_surface: no — both failures sit in files T-014 does not declare
reading: T-014 rotates the token but drops the device id the api layer reads back
```

Quote the failing output. Do not paraphrase it from memory — the next agent needs the error
it will actually see, and a summary of a stack trace is not one.

`in_surface` is the field that earns its place. A failure inside the task's declared change
surface is the task's own bug and the fix belongs in its worktree. A failure outside it
means the task collided with something it was never told about — usually drift, not a
defect, and patching it inside the task hides the real problem.

## When to stop and hand back

**Ceiling: 5 attempts.** Count the blocks in the landing record — that is which attempt
this is. On the fifth, escalate whatever it looks like. A task that has not landed in five
tries is telling you something about the plan, and the sixth attempt does not find it out.

**A `landed` outcome never escalates**, whatever attempt it was on — the loop ended
because it succeeded. Everything below applies only when the outcome is `conflict`,
`reverted`, or `stuck`.

Before the ceiling, escalate on any of these. **Ordered rules, first match wins.** Each is
a check against the record, not a call you make:

| # | If | |
|---|---|---|
| 1 | this is attempt 5 | **escalate** — ceiling |
| 2 | the outcome is `stuck` | **escalate** — the tree is red and the rollback did not fix it |
| 3 | any test in `failing` also appears in the previous block's `failing` | **escalate** — the fix did not address what it was sent to address |
| 4 | `in_surface: no` on this block and the one before it | **escalate** — this is drift, not a defect in the task |
| 5 | otherwise | `escalate: no` — let the loop run |

Nothing here asks you to weigh whether the fix "seems to be converging." That was a
judgement two agents could answer differently from the same record, which is exactly what
these rules remove.

Set `escalate: yes` with the rule number and one line of why. You are raising a flag, not
making a decision — the parent decides what happens next, it just cannot see what you saw.

## Return

≤200 tokens.

```
task: T-014
landing: landed | conflict | reverted | stuck
main: green | red
attempt: 2 of 5
summary: rotation drops the device id the api layer reads back
escalate: no             # or: yes (rule 3) — session.test.ts failed on attempt 1 too
detail: .agent/notes/T-014.landing.md
```

`main` is not decoration — it is the parent's dispatch gate. It must not send new work into
a tree you have just told it is red.

Keep the task's worktree in every outcome except `landed`. The fix goes back into that
worktree, and discarding it throws away work that passed verification for the sake of a
merge problem.

## What you are not

**You do not fix anything.** Not the conflict, not the failing test, not the one-line
obvious thing. You have no worktree, no acceptance criterion covering a change of yours,
and no verifier who did not see your work. A lander that fixes what it found has put
unverified code into the main tree by the shortest path available in the whole system.

**You do not verify.** The task arrived verified. If it looks otherwise, return and say so
rather than checking it yourself.

**You do not touch the ledger.** Report; the parent records.
