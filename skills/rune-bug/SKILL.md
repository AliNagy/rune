---
name: rune-bug
user-invocable: false
description: Use when something that used to work no longer does, or a request is classified as a defect. Reproduces it inside a reserved task worktree before planning, finds root cause over symptom, and turns the reproduction into the regression test.
---

# Bug protocol

**Governing rule: no fix without a failing reproduction.**

Bug diagnosis is task-bound even though the immutable task specification does not exist
yet. The parent reserves the task identity first and dispatches all of these:

```rune-dispatch
follow: bug
work: T-nnn
attempt: N
main_root: /workspace/acme
worktree_path: /workspace/acme/.rune/worktrees/T-nnn
pointers:
  protocol: /workspace/acme/.rune/drafts/M-03/R-002/protocol.md
  progress: /workspace/acme/.rune/notes/T-nnn.progress
```

`attempt` matches the diagnosis counter already persisted by the parent, and the
protocol's `reserved_task` must match `work`.

Reject a missing, relative, or mismatched input. Never infer the repository from the
worker's starting directory, read the ledger, allocate another id, or create an anonymous
worktree. The `diagnosing` ledger row already exists and belongs to the parent.

Not a description of the failure. Not a stack trace. An executable case that fails now
and will pass after. Everything else in this protocol follows from that.

## 1. Reproduce first

Before any planning or decomposition, but **after** the task id and ledger row have been
reserved. Identity comes before diagnosis; the immutable task contract comes after it.

Validate or create the exact supplied worktree before writing a reproduction:

```bash
git -C <main_root> worktree add <worktree_path> -b task/T-nnn
cd <worktree_path>
```

If `task/T-nnn` already exists, attach or reuse only that branch at the supplied path.
Confirm it belongs to the same repository as `main_root`. A mismatch is
`diagnosis: blocked`, not permission to search for a nearby checkout.

Every blocked diagnosis appends a terminal progress block with a lowercase `blocker` slug,
`blocker_reason`, and one observable `unblocks_when` condition before returning. The
parent stores `external:<slug>` and points `latest_finding` at this block; a short return
alone is not durable enough to recover after a crash.

You are the reproduction subagent — reproduction reads code and runs things, while the
parent stays clean.
**One bug per subagent.** Several reported bugs get several reproduction agents, never one
agent working a list: a reproduction that has just found the cause of one bug will see that
same cause in the next, and two bugs with one root cause is a conclusion that has to be
reached independently, not assumed by batching.

- Establish the failing case as code where possible: a test, a script, a curl.
- Confirm it fails **now**, on the current tree, and capture the exact output.
- Establish the boundary: what inputs fail, what adjacent inputs succeed. A bug you can
  only trigger one way is under-characterised, and you will not know if the fix was
  general.
- Do not edit production code. Diagnosis may add only the reproduction check and fixtures
  needed to run it. The later task contract decides the implementation surface.

### If you cannot reproduce

Stop. Do not plan a fix. Append `diagnosis: not_reproduced`, what you tried, and what input
is missing to the supplied progress file. Discard the exact reserved worktree and branch;
the durable evidence remains under `main_root`. The parent removes the provisional ledger
row but never reuses its id.

A fix for an unreproduced bug is a guess with a test that was green before you started.
There is no way to tell it from a no-op, and it will be marked `done` regardless.

Reclassify as `rune-investigate` if the request is really "why does this happen"
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
`remediation: mitigation`, link `root_cause_followup` to a separate root-cause bug task,
and preserve both in the reconciled cut. Never let a mitigation be recorded as a fix or
accepted without that durable follow-up. Legacy `kind: mitigation` means the same thing
during recovery; it must never be normalized to a root-cause fix.

Choosing temporary containment over the cause changes scope. Unless the request already
settles it, record it as a planning decision candidate; the parent resolves that choice
before final reconciliation. Diagnosis may recommend mitigation, but it does not silently
authorize one.

## 3. The reproduction becomes the test

This is where the bug protocol pays off. Red-then-green is free — you already observed
red in step 1, before any production change existed. Record it in the supplied progress
file before returning:

```text
## diagnosis — 2026-08-10
diagnosis: reproduced
verification: red_then_green
check_file: src/auth/__tests__/rotation.test.ts
check_command: npm test -- rotation.test.ts
assertion: refresh issues a new token and invalidates the prior one
red: confirmed — fails because rotate is not implemented
boundary: refresh fails; login and logout still pass
root_cause: TokenStore.rotate is missing from the refresh path
diagnosis_base_commit: a3f91c2
diagnosis_commit: b7a03d4
```

Stage only the reproduction check and its necessary fixtures, commit them on
`task/T-nnn`, and record both commit ids. `diagnosis_base_commit` is the branch `HEAD`
immediately before that commit; `diagnosis_commit` is the new `HEAD`. Prove the former is
an ancestor of the latter, their diff is non-empty, and the worktree is clean. The commit
is durable diagnosis input, **not** a completed task publication: it has no
`artifact_commit`, cannot be verified, and cannot be landed on its own. Leave the worktree
kept so planners and the eventual executor see the exact same test.

Put it where the suite will keep running it. A reproduction living in a scratch file is
not a regression test.

## 4. Task shape

Most bugs are **one task**. Diagnosis is the expensive half and it is already done by the
time the task is written; the change itself is usually small and local.

Cut a second task when a mitigation is accepted: the mitigation task names the other
task's final id in `root_cause_followup`, and that target is the `remediation: root_cause`
bug task. Also cut separately when the cause spans subsystems. The reserved primary task
owns the reproduction and root-cause fix; a mitigation uses another id and never replaces
that primary contract.

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
  code was never written. This is a feature — hand it to `rune-feature`. The
  distinction matters: features need decomposition and possibly decisions, bugs do not.
- **It works as designed and the design is wrong.** Not a bug either. That is a decision
  to surface, then a feature or refactor.

Say so plainly and reroute. Reclassifying early is cheap; discovering it three tasks in
is not. Append `diagnosis: reclassified` plus
`reclassified_as: feature | refactor | investigation`
to the progress file, discard the reserved worktree and branch, and return the id to the
parent as burned. A change-producing route receives a fresh decomposition run; it never
recycles the abandoned task id or rewrites the old protocol record. An investigation exits
without a run, as usual.

## Return (≤200 tokens)

```rune-return
work: T-nnn
summary: failing check and root cause, missing reproduction input, reclassification, or blocker
diagnosis: reproduced | not_reproduced | reclassified | blocked
worktree: kept | discarded
worktree_path: /workspace/acme/.rune/worktrees/T-nnn
attempt: 1
progress: /workspace/acme/.rune/notes/T-nnn.progress
reclassified_as: feature | refactor | investigation  # reclassified only
remediation: root_cause | mitigation      # reproduced bug only
blocker: repository-access                # blocked only
diagnosis_base_commit: a3f91c2            # reproduced only
diagnosis_commit: b7a03d4                 # reproduced only
```

`reproduced` requires a kept, clean worktree plus both commit ids. Every other outcome
must explain itself in the progress file before returning. The parent acts on this short
result; it never reads the source diff or test output itself.
