---
name: work
description: Use when building a feature, fixing a bug, refactoring, or advancing the current milestone. Triages the request against real code, decomposes it into tasks, dispatches isolated executors, and verifies each one independently.
---

# rune:work

The execution loop. Triage → plan → dispatch → verify → reconcile.

## The rule that makes this work

**You never read source code.** Not once. You are a dispatcher: you hold the ledger and
tiny reports, and nothing else.

This is not a style preference. With subagent dispatch, the parent accumulates every
result it receives. Read one file "just to check" and you have imported the exact cost the
whole system exists to avoid. Two consequences are load-bearing:

- Every subagent returns **≤200 tokens**. Anything longer goes to disk; you read it only
  if you must act on it.
- You **re-read `ledger.md` from disk** between dispatches. Never carry ledger state in
  context — a stale in-memory copy is how you dispatch a task someone already finished.

If either slips, the parent hits its ceiling around task 25 no matter how clean the
workers are.

## Preconditions

- No `.agent/rune.yml` → run `rune:init` first.
- No `milestones.md` and the request is broad ("continue the project") → route to
  `rune:vision`. Do not invent a plan; that is vision's job and it requires the user.
- A specific request ("fix the login bug") with no vision → proceed. Not everything needs
  a milestone graph.

## 1. Triage

Classification often cannot be done from the user's sentence. "Is this a bug or is it
simply not implemented?" is undecidable without evidence — and it is the most common
ambiguity on an unfinished codebase.

Since you cannot read code, **dispatch a triage subagent** (cheap model, tight budget,
read-only, no edits). It returns:

```
type: bug | feature | refactor | investigation
evidence: SessionMiddleware.handle exists and is called; rotate() returns null (stub)
shape: single fix in src/auth — reproduction likely straightforward
milestone: M-03 (fits scope) | none | conflicts with M-03 scope
```

Then load the matching protocol:

| type | skill | first move |
|---|---|---|
| bug | `ai-bug` | reproduce before planning |
| feature | `ai-feature` | scope boundary, then decisions |
| refactor | `ai-refactor` | confirm a characterization net exists |
| investigation | `ai-investigate` | read-only, terminates in an answer |

**Investigation exits here.** It produces a written answer, no tasks, no ledger entries.
Do not continue into planning — that gap is the entire point of the classification.

Protocols may reclassify once they see real code. Accept it and reroute; correcting early
is cheap.

## 2. Decompose

Per `ai-decompose` plus the type protocol. **Smart model** — this is the one step
where intelligence pays for itself. A bad cut produces tasks that are not independent,
and then every executor blows its budget rediscovering shared context.

Check first that no `open` decision blocks this milestone. If one does, surface it to the
user and stop. The gate is not negotiable.

Write task files, register them in the ledger.

## 3. Plan gate

**Default: stop here and show the user the ledger before any executor runs.**

```
M-03 · Session lifecycle — 4 tasks

  T-014  Rotate refresh tokens        auth      ~3 files
  T-015  Refresh endpoint             api       blocked by T-014
  T-016  Session restart persistence  auth,db   ~4 files
  T-017  Expiry sweep job             worker    ~2 files

Proceed?  (--auto to skip this gate in future runs)
```

Fanning out executors that immediately start editing, off one sentence, is not a good
default. `--auto` skips it when the user has earned confidence in the plan.

## 4. Dispatch

Claim the lowest-id `pending` task whose `blocked_by` are resolved. Independent tasks may
run in parallel.

Each executor gets:

- **`isolation: "worktree"`** — its own git worktree. This is what makes stateless
  restart safe: a dead executor's torn state is discarded with the worktree, and the next
  attempt starts from a clean base with no forensics.
- Cheap model, one task id, and nothing else. It reads its own task file.
- `ai-taskfmt`, `ai-serena`, `ai-drift` loaded.

Executors report ≤200 tokens:

```
status: done | drifted | budget | blocked
task: T-014
worktree: kept | discarded | merged
summary: rotate() implemented and wired; red-then-green recorded
drift: DRF-003          # if any
```

Record it. Do not read the worktree.

## 5. Verify

Every `done` claim goes to a **separate** verifier in a **clean context** —
`ai-verify`, cheap model. Never the same agent, never the same context. An executor
is the worst possible judge of its own work.

- `pass` → merge the worktree, mark `done`.
- `fail` → back to `pending` with the finding attached. Do not have the verifier fix it.
- `unverified` → not a soft pass. Usually a defect in the task (an acceptance criterion
  that is not actually checkable) — send it back to decomposition.

## 6. Reconcile

Per `ai-ledger`:

- Update statuses.
- Any drift record → block the tasks it invalidates, do not delete them.
- Enough drift in one milestone → stop and re-decompose the remainder against the code as
  it now is. Do not patch task files one at a time; patched specs accumulate
  contradictions with their own amendments until nobody can tell what is still true.

Then loop to the next available task.

## Stopping

Stop and return to the user when: the milestone is complete, an `open` decision blocks
progress, drift invalidates a substantial part of the plan, the same task fails twice, or
nothing is dispatchable.

Report against the ledger, briefly:

```
M-03 · 3 of 4 done

  T-014  done       T-015  done       T-016  drifted (DRF-003)
  T-017  blocked by DRF-003

DRF-003: handle() has two call sites; T-016 assumed one.
Re-decompose the remainder of M-03?
```

A task failing twice is a signal about the *plan*, not the executor. Say so rather than
dispatching a third attempt.
