---
name: ai-bug
user-invocable: false
description: Use when something that used to work no longer does, or a request is classified as a defect. Requires a failing reproduction before any planning, root cause over symptom, and turns the reproduction into the regression test.
---

# Bug protocol

**Governing rule: no fix without a failing reproduction.**

Not a description of the failure. Not a stack trace. An executable case that fails now
and will pass after. Everything else in this protocol follows from that.

## 1. Reproduce first

Before any planning, any decomposition, any ledger entry.

Use a subagent — reproduction reads code and runs things, and the parent must stay clean.

- Establish the failing case as code where possible: a test, a script, a curl.
- Confirm it fails **now**, on the current tree, and capture the exact output.
- Establish the boundary: what inputs fail, what adjacent inputs succeed. A bug you can
  only trigger one way is under-characterised, and you will not know if the fix was
  general.

### If you cannot reproduce

Stop. Do not plan a fix. Report what you tried and what you observed, and ask for what
you need — exact input, environment, version, sequence of actions.

A fix for an unreproduced bug is a guess with a test that was green before you started.
There is no way to tell it from a no-op, and it will be marked `done` regardless.

Reclassify as `ai-investigate` if the request is really "why does this happen"
rather than "make this stop".

## 2. Root cause, not symptom

The reproduction tells you *where it surfaces*. That is rarely where it is caused.

- Trace back with `find_referencing_symbols` — who calls this, with what.
- Ask "why is the input wrong" one level up, until the answer is "because this code is
  wrong" rather than "because it was given bad data".
- Check whether the same root cause has other surfaces. If it does, say so — that changes
  the scope and possibly the milestone.

**Symptom fixes are identifiable**: null-guards at the point of crash, try/catch around
the failing call, defaulting a value that should never have been absent. If the fix
consists of tolerating bad state rather than preventing it, you have found a symptom.

Sometimes a symptom fix is the right call — production is down and the root cause sits
three modules away. That is legitimate, but it must be **explicit**: mark the task
`kind: mitigation`, and file a follow-up task for the cause. Never let a mitigation be
recorded as a fix.

## 3. The reproduction becomes the test

This is where the bug protocol pays off. Red-then-green is free — you already observed
red in step 1, before any change existed. Record that evidence in the progress file.

Put it where the suite will keep running it. A reproduction living in a scratch file is
not a regression test.

## 4. Task shape

Most bugs are **one task**. Diagnosis is the expensive half and it is already done by the
time the task is written; the change itself is usually small and local.

Cut a second task only when the root cause fix and the mitigation are genuinely separate
work, or when the cause spans subsystems.

Acceptance for a bug task:

```
- [ ] Reproduction test passes (was failing before the change)
- [ ] Project oracle passes — no new failures vs. baseline
- [ ] The boundary cases from step 1 also pass
```

That third line is what stops a fix that special-cases the one input you happened to try.

## 5. Watch for misclassification

Triage guesses from a sentence. You have now looked at the code. Two common corrections:

- **It was never implemented.** The user calls it a bug because it does not work, but the
  code was never written. This is a feature — hand it to `ai-feature`. The
  distinction matters: features need decomposition and possibly decisions, bugs do not.
- **It works as designed and the design is wrong.** Not a bug either. That is a decision
  to surface, then a feature or refactor.

Say so plainly and reroute. Reclassifying early is cheap; discovering it three tasks in
is not.
