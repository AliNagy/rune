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

Not the executor's summary. That is the claim under examination; reading it primes you to
agree with it.

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

## Verdict

```
verdict: pass | fail | unverified
task: T-014
surface: clean                    # or: touched src/api/routes.ts, outside surface
local_test: pass (rotation.test.ts)
red_evidence: present
revert_check: test fails when change reverted — test is real
oracle: pass (baseline: 3 known failures, unchanged)
ticks: 3/3 match diff
acceptance:
  - test passes .......... pass
  - no regression ........ pass
  - rotate called once ... pass
```

**pass** — every criterion met, evidence present.
**fail** — a criterion is not met. Say which and what you observed. The task returns to
`pending` with your finding attached; do not fix it yourself.
**unverified** — you could not establish the truth. Missing red evidence, a flaky oracle,
an acceptance criterion that is not actually checkable. This is not a soft pass. An
unverifiable acceptance criterion is a defect in the *task*, and it should go back to
decomposition.

## What you are not

You are not a reviewer. Do not comment on style, naming, or how you would have done it.
Do not suggest improvements. Do not fix anything, however small — you have no worktree of
your own and no acceptance criterion covering your change.

You answer exactly one question: **does this task meet its stated acceptance, on
evidence?**

Bias toward `fail` and `unverified` under uncertainty. A false `fail` costs one re-run. A
false `pass` propagates into every task built on top of it, and by the time it surfaces
nobody knows which of the green rows was the lie.
