---
name: rune-verify
user-invocable: false
description: Use when confirming a completed task actually passed. Checks acceptance criteria, audits the task's declared verification evidence, and detects vacuous checks. Never used on work the same agent performed.
---

# Verification

An executor reporting success is a claim, not a fact. Verification turns it into one.

**Three hard rules.** Verify in a **clean context** — you must not have the executor's
reasoning, only its artifacts. **Never verify your own work**; the agent that wrote the
code is the worst possible judge of it. This is why verification is a separate dispatch
and not the last step of the executor's turn. And **verify exactly one task per agent** —
a batch of three tasks handed to one verifier produces three correlated verdicts, because
after passing the first two it is judging the third against its own accumulated sense of
what this batch looks like rather than against the spec.

This is checking, not designing.

## Inputs

Only these:

- `main_root` — the absolute orchestration checkout; all coordination paths resolve here
- `worktree_path` — the exact absolute task worktree used by the executor
- `attempt` — the positive verifier attempt already incremented in schema-2 ledger state
- `<main_root>/.rune/tasks/T-nnn.md` — the spec, including type, remediation,
  root-cause-follow-up link, verification mode, acceptance, and the stated check
- `<main_root>/.rune/notes/T-nnn.progress` — ticks, mode-specific evidence, and the latest
  `base_commit` / `artifact_commit` publication
- the clean task worktree at `worktree_path` and `artifact_commit`
- `<main_root>/.rune/rune.yml` — the project oracle and its known-red baseline
- `<main_root>/.rune/ledger.md` — registration and milestone identity for a mitigation's
  linked root-cause row
- `<main_root>/.rune/notes/T-nnn.verify.md` — earlier verdicts on this task, if this is a retry

Both roots and every pointer must be absolute. Confirm that `worktree_path` is a registered
worktree of the same Git repository as `main_root` before reading the artifact. **Never
create or accept a fresh verifier worktree.** If the supplied path is absent, points at the
wrong repository or branch, or differs from the task path in the ledger, return
`unverified` with `reason: artifact`.

Not the executor's summary. That is the claim under examination; reading it primes you to
agree with it.

**The dispatch tells you which attempt this is; the record proves ordering.** Require
every existing block number to be unique and lower than `attempt`. Gaps are allowed: they
are dispatches that died before writing a verdict. A duplicate or later number is
`unverified` with `reason: evidence`; do not invent another number. Run all eight steps
below whether this is attempt 1 or attempt 4. Narrowing to "did they fix the
last finding" is how the second defect in a task ships: the executor answered the finding,
you confirmed the finding was answered, and nobody looked at the rest. Read it for the
history of what has already been rejected — then verify the task, not the finding.

## Procedure

**1. Bind verification to the published artifact.** Read the last publication block from
the progress file. Read `type`, `remediation`, `root_cause_followup`, and `verification`
from the task and require one allowed contract from `rune-taskfmt`. For a completed legacy
task with `type: bug` and `kind: mitigation`, normalize `remediation: mitigation` and
obtain `root_cause_followup` only from exactly one linked mitigation-repair ledger row and
matching immutable repair artifact; never edit or pretend to read it from the old task.
Any other missing or incompatible field, or a pending/missing/duplicate/mismatched repair,
is `unverified` with `reason: evidence`. For a mitigation, require the linked final task
and ledger row to exist, use a different id in the same milestone, and declare `type: bug`,
`remediation: root_cause`, and `root_cause_followup: none`. This
validates the durable follow-up relationship; it does not require the follow-up to be
complete before the mitigation can pass. A self-link, cross-milestone link, mitigation
target, missing target, or chained follow-up is `unverified` with `reason: evidence`.
Then establish all of these mechanically:

- `git -C <worktree_path> rev-parse HEAD` equals `artifact_commit`.
- `git -C <worktree_path> status --porcelain` is empty.
- `base_commit` is an ancestor of `artifact_commit`.
- `git -C <worktree_path> diff <base_commit>..<artifact_commit>` is non-empty.

If any check fails, return `unverified`. Do not infer an id, verify a nearby commit, commit
the dirty files yourself, or silently accept an empty artifact. From this point onward,
"the diff" means only
`git -C <worktree_path> diff <base_commit>..<artifact_commit>`. Set
`reason: artifact` so `rune-work` routes this back to an executor for publication rather than
mistaking it for a defective acceptance criterion.

**2. Does the diff match the declared change surface?**
Files touched outside the surface are a finding, not a detail — the tripwire in
`rune-drift` exists precisely to prevent this, so a violation means either the rule
was broken or the task was mis-scoped. Report either way.

**3. Run the task-local check.** Its command must exist and its declared after-result must
hold. A scripted or observable assertion is valid when a unit test does not fit.

**4. Check the declared evidence mode.** The progress file must name the same
`verification` value as the task and contain its complete evidence chain:

- `red_then_green`: `red` shows the declared check failed for the expected reason before
  the change, and `green` shows the same check passed afterward.
- `green_baseline`: `baseline` shows the declared existing check and project oracle passed
  before production edits, and `preserved` shows the same commands passed afterward. No
  test or fixture file may appear in the artifact diff.
- `characterization`: `characterized` shows the new check passing against unchanged
  production code. The artifact diff may contain only the task's declared tests and
  fixtures; any production-source change is a failure.

If required evidence is absent, mismatched, or internally contradictory, the result is
**unverified**, not passed. Do not substitute red evidence for a refactor or accept a
manufactured failure as proof of behavior preservation.

For `type: bug`, also require the original `diagnosis: reproduced` block, matching check
identity, `diagnosis_base_commit`, and `diagnosis_commit`. Prove that the published
`base_commit..artifact_commit` range contains the diagnosis commit and its reproduction
files. The executor's reconfirmed red and green results complete that chain; a standalone
diagnosis commit is never a verifiable task artifact.

**5. Hunt vacuous checks using the mode.** Read the check in every mode.
- Does it assert anything meaningful, or does it assert `true`?
- Is the subject mocked so thoroughly that only the mock is exercised?
- For `red_then_green`, would it fail if the behavior change were reverted? If cheap,
  answer in a disposable worktree without changing the published task worktree.
- For `green_baseline`, does the same check pass at `base_commit` and `artifact_commit`, and
  are its files unchanged?
- For `characterization`, does the new check exercise existing production behavior? A
  revert check is inapplicable because reverting removes the check; use a disposable
  sensitivity probe only when cheap.

If no disposable check is cheap, record that it was skipped. Never mutate the artifact you
are verifying.

**6. Run the project oracle.** In the worktree. Compare against the known-red baseline,
not against zero failures. Any new failure is a regression, even if the task's own test
passes.

**7. Audit the ticks.** Steps are phrased to be checkable. Spot-check two against the
diff. A ticked step with no corresponding change means the write-order rule was violated
and the record is lying — report it, because it means the *next* executor of this task
would have skipped real work.

**8. Walk the acceptance criteria** one at a time. Each is pass, fail, or unverifiable.
There is no partial credit and no "essentially done".

## The verification record

`<main_root>/.rune/notes/T-nnn.verify.md` — where your finding goes. Sole writer: the verifier
holding T-nnn.

**Write it before you return.** Your verdict block is a pointer; this file is the finding.
A `fail` that exists only in a return value dies in the parent's context, and the next
executor of this task reads the task file, the handoff, and the diff — none of which say
why the last attempt was rejected. It would repeat that attempt move for move.

This is the counterpart to `<main_root>/.rune/notes/T-nnn.landing.md`, and it sits where it does for
the same three reasons. It is **per-task**, so it satisfies the concurrency rule in
`rune-taskfmt` without anyone having to think about it. It has a **different sole writer**
from the executor's two files, and merging writers is the one thing that rule exists to
prevent. And it lives under `<main_root>/.rune/`, so it is visible to the parent
and the next executor immediately, rather than at merge — and it survives the worktree
being discarded.

Append one block for the exact dispatched `attempt`; never edit or delete an earlier one.
The history is the point: a task rejected three times for three different reasons is a
different problem from one rejected three times for the same reason, and only the history
tells them apart.

```markdown
## attempt 2 — 2026-08-08
verdict: fail
remediation: not_applicable
root_cause_followup: none
verification: red_then_green
base_commit: a3f91c2
artifact_commit: 4a91c02
failing_criterion: "rotate() is called exactly once per refresh"
observed: rotate() fires twice — once in handle(), once in the refresh path
evidence: |
  rotation.test.ts :: "refresh rotates once"
  Expected 1 call, received 2
in_surface: yes — both call sites are inside T-014's declared surface
reading: handle() already rotated; the new call duplicates it rather than replacing it
```

Quote what you actually saw. Do not paraphrase a failure from memory — the next agent
needs the output it will meet, and a summary of a stack trace is not one.

`in_surface` earns its place for the same reason it does in the landing record. A failure
inside the task's declared change surface is the task's own bug and the fix belongs in its
worktree. Outside it, the task collided with something it was never told about — usually
drift, and fixing it inside the task hides the real problem.

Write a block on **every** verdict, `pass` included — though a passing one is short because
there is no finding to carry:

```markdown
## attempt 3 — 2026-08-08
verdict: pass
remediation: not_applicable
root_cause_followup: none
verification: red_then_green
base_commit: a3f91c2
artifact_commit: 62be8d1
verified_commit: 62be8d1
summary: rotation fires once per refresh; oracle clean against baseline
```

A `pass` block is what closes the chain, and it is how a later reader tells a resolved
history from a live one.

**Live, superseded, resolved.** The last block is live; everything above it is history. A
finding is *superseded* when a later `fail` block replaces it — the new one is what the
next executor must answer. It is *resolved* when a later block reads `pass`. Nothing is
rewritten to mark either; position in the file already says it.

If you die between writing the block and returning, the parent sees the durable block
during reconciliation and consumes that verdict. If no block exists, it increments `v`
again before dispatching a fresh verifier. Duplicate attempt numbers are invalid state,
not harmless noise.

## Verdict

```rune-return
work: T-014
summary: rotation meets acceptance; oracle is unchanged from its known-red baseline
verdict: pass | fail | unverified
worktree: kept | discarded # discarded only when the supplied path is proven absent
worktree_path: /workspace/acme/.rune/worktrees/T-014
remediation: not_applicable | root_cause | mitigation
root_cause_followup: none | T-nnn
reason: artifact | evidence | oracle | acceptance   # required for unverified
base_commit: a3f91c2
artifact_commit: 62be8d1
verified_commit: 62be8d1              # required only for pass; exactly artifact_commit
surface: clean                    # or: touched src/api/routes.ts, outside surface
local_check: pass (rotation.test.ts)
verification: red_then_green
evidence: red and green present for rotation.test.ts
sensitivity_check: test fails when change reverted — check is real
oracle_result: passing (baseline: 3 known failures, unchanged)
flaky: none                       # or: auth/session.test.ts disagreed with itself
ticks: 3/3 match diff
acceptance:
  - test passes .......... pass
  - no regression ........ pass
  - rotate called once ... pass
attempt: 2                        # exactly the attempt supplied by the parent
detail: /workspace/acme/.rune/notes/T-014.verify.md
```

`attempt` is not decoration. It binds the ledger's `v` counter, this record block, and the
short verdict. The parent separately increments the ledger's `failures` field only for a
`fail` verdict; that durable counter drives the two-failure stop rule.

**pass** — every criterion met, the declared mode's evidence is complete, and
`verified_commit` names the exact published artifact you checked.
**fail** — a criterion is not met. Say which and what you observed — in the record, where
the next executor will find it. The task returns to `pending` and a fresh executor is
given your record; do not fix it yourself.
**unverified** — you could not establish the truth. Missing mode-specific evidence, a
flaky oracle, or an acceptance criterion that is not actually checkable. This is not a
soft pass. An unverifiable acceptance criterion is a defect in the *task*, and it should
go back to decomposition.

## What you are not

You are not a reviewer. Do not comment on style, naming, or how you would have done it.
Do not suggest improvements. Do not fix anything, however small — you have no worktree of
your own and no acceptance criterion covering your change.

**You write exactly one file: `<main_root>/.rune/notes/T-nnn.verify.md`.** That is not an exception to
the rule below and should not be read as one. It is coordination state, the same category
as the executor's progress file and the lander's landing record — it records what you
observed and changes nothing about the work. Everything else on disk, source and `<main_root>/.rune/`
alike, you read only.

**Nothing stops you from editing.** You are an ordinary subagent holding ordinary
permissions, so "makes no changes" is a rule you keep rather than a wall you hit. It is
also the easiest rule here to break with good intentions: you are about to write `fail`
over something you can see how to fix in one line.

Write the `fail`. A verifier that fixes what it found has destroyed the only independent
check in the system — there is now no agent left who did not touch this code, and the next
`pass` means nothing. A dirty worktree or changed `HEAD` exposes the mutation, but detecting
it after the fact does not restore independence.

You answer exactly one question: **does this task meet its stated acceptance, on
evidence?**

Bias toward `fail` and `unverified` under uncertainty. A false `fail` costs one re-run. A
false `pass` propagates into every task built on top of it, and by the time it surfaces
nobody knows which of the green rows was the lie.
