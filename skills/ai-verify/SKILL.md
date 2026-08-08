---
name: ai-verify
user-invocable: false
description: Use when confirming a completed task actually passed. Checks acceptance criteria, audits red-then-green evidence, and detects vacuous tests. Never used on work the same agent performed.
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

- `.agent/tasks/T-nnn.md` — the spec, including acceptance and the stated test
- `.agent/notes/T-nnn.progress` — ticks and red-then-green evidence
- `git diff` in the task's worktree — what actually changed
- `.agent/rune.yml` — the project oracle and its known-red baseline
- `.agent/notes/T-nnn.verify.md` — earlier verdicts on this task, if this is a retry

Not the executor's summary. That is the claim under examination; reading it primes you to
agree with it.

**The record tells you which attempt this is. It does not tell you what to check.** Run all
seven steps below whether this is attempt 1 or attempt 4. Narrowing to "did they fix the
last finding" is how the second defect in a task ships: the executor answered the finding,
you confirmed the finding was answered, and nobody looked at the rest. Read it for the
count and for what has already been rejected — then verify the task, not the finding.

## Procedure

**1. Does the diff match the declared change surface?**
Files touched outside the surface are a finding, not a detail — the tripwire in
`ai-drift` exists precisely to prevent this, so a violation means either the rule
was broken or the task was mis-scoped. Report either way.

**2. Run the task-local test.** It must exist and pass.

**3. Check red-then-green evidence.** The progress file must record the test observed
failing before the change. If that evidence is absent, the result is **unverified**, not
passed. A test written after a fix and never seen red proves nothing, and you cannot
reconstruct that evidence after the fact.

**4. Hunt vacuous checks.** Read the test.
- Does it assert anything meaningful, or does it assert `true`?
- Is the subject mocked so thoroughly that only the mock is exercised?
- Would it still pass if the change were reverted? If you can answer that cheaply — by
  reverting in the worktree and re-running — do it. It is the single most informative
  check available to you.

**5. Run the project oracle.** In the worktree. Compare against the known-red baseline,
not against zero failures. Any new failure is a regression, even if the task's own test
passes.

**6. Audit the ticks.** Steps are phrased to be checkable. Spot-check two against the
diff. A ticked step with no corresponding change means the write-order rule was violated
and the record is lying — report it, because it means the *next* executor of this task
would have skipped real work.

**7. Walk the acceptance criteria** one at a time. Each is pass, fail, or unverifiable.
There is no partial credit and no "essentially done".

## The verification record

`.agent/notes/T-nnn.verify.md` — where your finding goes. Sole writer: the verifier
holding T-nnn.

**Write it before you return.** Your verdict block is a pointer; this file is the finding.
A `fail` that exists only in a return value dies in the parent's context, and the next
executor of this task reads the task file, the handoff, and the diff — none of which say
why the last attempt was rejected. It would repeat that attempt move for move.

This is the counterpart to `.agent/notes/T-nnn.landing.md`, and it sits where it does for
the same three reasons. It is **per-task**, so it satisfies the concurrency rule in
`ai-taskfmt` without anyone having to think about it. It has a **different sole writer**
from the executor's two files, and merging writers is the one thing that rule exists to
prevent. And it lives under `.agent/` in the **main tree**, so it is visible to the parent
and the next executor immediately, rather than at merge — and it survives the worktree
being discarded.

Append one block per attempt; never edit or delete an earlier one. The history is the
point: a task rejected three times for three different reasons is a different problem from
one rejected three times for the same reason, and only the history tells them apart.

```markdown
## attempt 2 — 2026-08-08
verdict: fail
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

Write a block on **every** verdict, `pass` included — though a passing one is three lines,
because there is no finding to carry:

```markdown
## attempt 3 — 2026-08-08
verdict: pass
summary: rotation fires once per refresh; oracle clean against baseline
```

A `pass` block is what closes the chain, and it is how a later reader tells a resolved
history from a live one.

**Live, superseded, resolved.** The last block is live; everything above it is history. A
finding is *superseded* when a later `fail` block replaces it — the new one is what the
next executor must answer. It is *resolved* when a later block reads `pass`. Nothing is
rewritten to mark either; position in the file already says it.

If you die between writing the block and returning, the parent sees no verdict and
dispatches a fresh verifier, which appends its own. A duplicate block is noise. A missing
one sends the next executor in blind.

## Verdict

```
verdict: pass | fail | unverified
task: T-014
surface: clean                    # or: touched src/api/routes.ts, outside surface
local_test: pass (rotation.test.ts)
red_evidence: present
revert_check: test fails when change reverted — test is real
oracle: pass (baseline: 3 known failures, unchanged)
flaky: none                       # or: auth/session.test.ts disagreed with itself
ticks: 3/3 match diff
acceptance:
  - test passes .......... pass
  - no regression ........ pass
  - rotate called once ... pass
attempt: 2                        # count the blocks in the record, including this one
detail: .agent/notes/T-014.verify.md
```

`attempt` is not decoration. The parent stops a task that has failed twice, and it cannot
count reliably across a context that may have been compacted. You are reading the number
off disk, so you are the one who can.

**pass** — every criterion met, evidence present.
**fail** — a criterion is not met. Say which and what you observed — in the record, where
the next executor will find it. The task returns to `pending` and a fresh executor is
given your record; do not fix it yourself.
**unverified** — you could not establish the truth. Missing red evidence, a flaky oracle,
an acceptance criterion that is not actually checkable. This is not a soft pass. An
unverifiable acceptance criterion is a defect in the *task*, and it should go back to
decomposition.

## What you are not

You are not a reviewer. Do not comment on style, naming, or how you would have done it.
Do not suggest improvements. Do not fix anything, however small — you have no worktree of
your own and no acceptance criterion covering your change.

**You write exactly one file: `.agent/notes/T-nnn.verify.md`.** That is not an exception to
the rule below and should not be read as one. It is coordination state, the same category
as the executor's progress file and the lander's landing record — it records what you
observed and changes nothing about the work. Everything else on disk, source and `.agent/`
alike, you read only.

**Nothing stops you from editing.** You are an ordinary subagent holding ordinary
permissions, so "makes no changes" is a rule you keep rather than a wall you hit. It is
also the easiest rule here to break with good intentions: you are about to write `fail`
over something you can see how to fix in one line.

Write the `fail`. A verifier that fixes what it found has destroyed the only independent
check in the system — there is now no agent left who did not touch this code, and the next
`pass` means nothing. The diff in the worktree records what you did either way.

You answer exactly one question: **does this task meet its stated acceptance, on
evidence?**

Bias toward `fail` and `unverified` under uncertainty. A false `fail` costs one re-run. A
false `pass` propagates into every task built on top of it, and by the time it surfaces
nobody knows which of the green rows was the lie.
