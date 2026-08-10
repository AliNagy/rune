---
name: ai-land
user-invocable: false
description: Use when merging one verified task commit into the main tree. Binds the branch to the verifier's exact commit, merges it, re-runs the project oracle, reverts the merge if the oracle fails, and records why so the next attempt is not blind. Never used on unverified work, and never by the parent on its own behalf.
---

# Landing a verified task

A verified task is proven **as one immutable artifact** in its own worktree. Landing asks a
different question: does the main tree still work with that exact commit in it? Only
merging can answer that, and only running the suite afterwards can prove it.

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

- `main_root` — the absolute orchestration checkout where merging and coordination writes happen
- `worktree_path` — the exact absolute task worktree used by execution and verification
- `attempt` — the positive landing attempt already incremented in schema-2 ledger state
- optional `mode` — defaults to `land`; `drift-observe` is allowed only when the task is
  in a ledger drift freeze and the parent supplies its causal `DRF-nnn` pointer
- the task id and its task branch
- `<main_root>/.rune/tasks/T-nnn.md` — the change surface, for judging whether a failure is even this
  task's to answer for
- `<main_root>/.rune/notes/T-nnn.progress` — the executor's latest `base_commit` and
  `artifact_commit`
- `<main_root>/.rune/notes/T-nnn.verify.md` — the verifier's latest verdict and `verified_commit`
- `<main_root>/.rune/rune.yml` — the oracle command and its known-red baseline
- `<main_root>/.rune/notes/T-nnn.landing.md` — earlier landing attempts, if this is a retry

All paths must be absolute. When `worktree_path` exists, confirm it is the registered task
worktree in the same repository as `main_root`; never discover a replacement by scanning
nearby worktrees. A missing path is allowed only for step 2's already-landed recovery.
Run every main-tree Git command with `git -C <main_root>` and every task-tree probe with
`git -C <worktree_path>`. The harness's starting directory is irrelevant.

**Read the landing record first when it exists.** You are stateless — every dispatch starts
empty — so that file tells you what earlier attempts observed. The dispatch's `attempt` is
authoritative: every existing block number must be unique and lower. Gaps are dead
dispatches that wrote no outcome; a duplicate or later number is `refused`, not permission
to invent another attempt.

## Sequence

Fixed order. Do not reorder, do not skip.

**1. Check the main tree is clean outside `.rune/`.** Run
`git -C <main_root> status --porcelain` — anything
modified beyond `.rune/` means someone left source changes in the main checkout, and a
rollback could not tell them apart from the merge. Stop, record the attempt, return `stuck`,
and say what is dirty.

`stuck` is the outcome for **any state only a human can resolve** — a dirty main tree here,
or a rollback that did not restore one at step 7. Both mean the same thing to the parent:
land nothing else until someone looks.

**2. Bind the landing to the verified artifact.** Read the last publication and last
verification blocks. Require all of these:

- the latest verdict is `pass`;
- `base_commit` and `artifact_commit` in the verification block match the latest
  publication block;
- `verified_commit` equals `artifact_commit`;
- `base_commit` is an ancestor of `verified_commit`, and
  `git -C <worktree_path> diff <base_commit>..<verified_commit>` is non-empty.

Any mismatch means the thing in the worktree is unpublished, changed since verification,
or empty. Touch nothing in main, append the exact mismatch to the landing record, and
return `refused` with `main: green`. Never commit it, choose a nearby SHA, or re-verify it
yourself. The executor publishes; the verifier approves; you land.

If `verified_commit` is already an ancestor of main, the artifact already landed before a
prior lander returned. Do not create an empty merge. Run the oracle against main: green
means `landed` and you skip to step 8 for cleanup; red means `stuck`, because there is no
recorded rollback point that safely distinguishes this task from later history.

In `drift-observe` mode, stop at this exact boundary when the verified commit is **not**
an ancestor of main. Append `not_landed` with the causal drift id, touch nothing in main,
keep the worktree, and return `landing: not_landed`, `main: green`. Never continue to step
3 or start a merge in this mode. Its only purpose is to distinguish a merge that completed
before its return was lost from an obsolete artifact that must be discarded by
`ai-drift` quiesce. When the commit is already reachable, the ordinary oracle and cleanup
rules above still apply and the result is `landed` or `stuck`.

Only when the artifact is not already in main, also require the task branch HEAD to equal
the verified commit and `git -C <worktree_path> status --porcelain` to be empty. This ordering
is deliberate: a prior lander may have merged, removed the worktree and branch, then died
before returning. The durable commit in main is enough to recover that case. Before the
first merge, a missing branch, missing worktree, dirty worktree, or moved branch is
`refused`.

**3. Record the rollback point.** `git -C <main_root> rev-parse HEAD`. Every undo below
depends on this one line. Capture it before you touch anything.

**4. Merge the exact verified commit** into the main tree:

```bash
git -C <main_root> merge <verified_commit>
```

Do not merge the branch name. The branch is checked only to prove it still names the
artifact; the SHA is what passed verification and is the only thing authorised to land.

Conflict → `git -C <main_root> merge --abort`, record the attempt, return `conflict`.
Nothing landed and the tree is untouched, so there is nothing to roll back — you skip
step 6's rollback and write the record alone. What this needs is not a code fix: the
worktree has fallen behind main and has to catch up before it can land.

After git reports success, require `verified_commit` to be an ancestor of main `HEAD`.
Otherwise roll back: a successful command that did not make the authorised artifact
reachable did not land the task.

**5. Run the project oracle** in the main tree, per `ai-oracle`. Compare against the
known-red baseline in `rune.yml`, never against zero failures.

**Skip this only when the merge was a fast-forward.** The tree is then byte-identical to
the worktree `ai-verify` already ran the oracle in, so a re-run cannot say anything new.
Any other merge produced a tree nobody has tested yet. That is a git fact you check, not
a call you make — and it is the only permitted reason to skip.

Pass → the artifact landed. Continue to cleanup below, then return `landed`.

**6. On oracle failure, roll the merge back, then write the record.**

Undo first, record second — the same write-order rule executors follow, and for the same
reason. If you die between the two, a missing record is recoverable and a record with the
bad merge still in the tree is not. You are holding the oracle output in context; it
survives the rollback.

Reset the main tree to the commit from step 2, **preserving uncommitted `.rune/` state** —
it holds the ledger and this task's own notes, and losing it costs more than the merge did:

```bash
git -C <main_root> reset <sha>                        # move HEAD back; worktree untouched
git -C <main_root> checkout -- ':(exclude).rune'     # source files back to <sha>
git -C <main_root> clean -fd -- ':(exclude).rune'    # drop files the merge added
```

**Do not undo the merge with `git -C <main_root> revert -m 1`.** It leaves the merge in history, and git
then treats the branch as already merged — so the fixed worktree would land as an empty
diff on the next attempt. Re-landing the same branch is the entire point of this loop, and
that one command quietly breaks it.

**7. Run the oracle again** to confirm the rollback actually restored the tree.

Green → return `reverted`. Main is back to known-good.
Still red → return `stuck`. Say so plainly. The rollback did not restore the tree, and no
further landing is safe until a human looks.

Step 7 is the step most worth not skipping. A rollback assumed to have worked and did not
leaves main red while your return value says it is green — which is the exact failure this
skill exists to prevent, moved one step later where nobody is looking for it.

**8. Record success, then clean up.** Append a `landed` block naming `base_commit`,
`artifact_commit`, `verified_commit`, and the resulting main `HEAD`. Write that durable
fact before cleanup: if you die after it, reconciliation knows the code landed and only
garbage collection remains.

Then remove the clean task worktree, and delete its merged task branch when they still
exist:

```bash
git -C <main_root> worktree remove <worktree_path>
git -C <main_root> branch -d <task_branch>
```

Cleanup is after the oracle because the worktree is the recovery asset for every earlier
failure. If either cleanup command fails after the artifact is green in main, do not roll
the merge back and do not call the task failed. Return `landed` with `cleanup: pending` and
record what remains; `continue` can remove the orphan later. Otherwise return
`cleanup: complete`.

## The landing record

`<main_root>/.rune/notes/T-nnn.landing.md` — your state file, and the counterpart to the executor's
`notes/T-nnn.progress`. Sole writer: the lander holding T-nnn.

Three things fix it in that spot. It is **per-task**, so it satisfies the concurrency rule
in `ai-taskfmt` without anyone having to think about it. It is **separate from the
executor's two files** because it has a different sole writer, and merging writers is the
one thing that rule exists to prevent. And it lives under `<main_root>/.rune/`,
which is what carries it across the rollback at step 5 — a record written into the task's
worktree would be invisible to the parent until merge, which is precisely the moment it
stops mattering.

Append one block for the exact dispatched `attempt`; never edit an earlier one. The
history is the point.

```markdown
## attempt 2 — 2026-08-07
outcome: reverted
base_commit: a3f91c2
artifact_commit: 4a91c02
verified_commit: 4a91c02
merged: b72de10             # resulting main HEAD, now rolled back
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

**Ceiling: 5 attempts.** The ledger-provided `attempt` is which attempt this is; refuse an
attempt above five. On the fifth, escalate whatever it looks like. A task that has not
landed in five tries is telling you something about the plan, and the sixth attempt does
not find it out.

**A `landed` outcome never escalates**, whatever attempt it was on — the loop ended
because it succeeded. Everything below applies only when the outcome is `refused`,
`conflict`, `reverted`, or `stuck`.

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
landing: landed | refused | conflict | reverted | stuck | not_landed
main: green | red
worktree_path: /workspace/acme/.rune/worktrees/T-014
verified_commit: 4a91c02
attempt: 2 of 5              # exactly the attempt supplied by the parent
summary: rotation drops the device id the api layer reads back
escalate: no             # or: yes (rule 3) — session.test.ts failed on attempt 1 too
detail: /workspace/acme/.rune/notes/T-014.landing.md
cleanup: complete | pending   # only for landed
```

`not_landed` is valid only for `mode: drift-observe`; the record and return name the
causal drift id. Normal landing never emits it.

`main` is not decoration — it is the parent's dispatch gate. It must not send new work into
a tree you have just told it is red.

Keep the task's worktree in every outcome except a `landed` result whose cleanup completed.
The fix goes back into that worktree, and discarding it throws away work that passed
verification for the sake of a publication or merge problem.

## What you are not

**You do not fix anything.** Not the conflict, not the failing test, not the one-line
obvious thing. You have no worktree, no acceptance criterion covering a change of yours,
and no verifier who did not see your work. A lander that fixes what it found has put
unverified code into the main tree by the shortest path available in the whole system.

**You do not verify.** The task arrived verified. If it looks otherwise, return and say so
rather than checking it yourself.

**You do not touch the ledger.** Report; the parent records.
