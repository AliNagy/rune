---
name: pause
description: Use when you want work to stop - now, at the end of the current task, or before anything else starts. Lets in-flight tasks finish and merge cleanly rather than abandoning them mid-edit, then holds until you resume. Also use to check whether work is currently paused.
---

# pause

Stops the work loop and leaves the repository in a state you can walk away from or take
over by hand.

**Default: drain, don't abort.** In-flight executors finish, get verified, get merged.
Nothing new is dispatched. Killing a worker mid-edit leaves a half-applied change that the
next attempt has to diagnose — the exact problem worktrees exist to prevent. Waiting a
minute is almost always cheaper.

## Modes

| Mode | What happens to in-flight work | Use when |
|---|---|---|
| **drain** (default) | Finishes active diagnosis or execution; completed tasks verify and merge. Then stops. | Almost always |
| **stop** | Active workers write durable state and stop where they are. Worktrees kept. | You need the machine or your attention back now |
| **abandon** | In-flight worktrees discarded, tasks reset to queued. | The current batch is going somewhere wrong |

`abandon` throws away real work. Say what will be lost and confirm before doing it.

If nothing is running, pause still applies — it becomes a *don't start* flag. Useful
before handing the repo to someone else.

## What you may do

**You stop the loop and leave the tree safe to walk away from.** This list is exhaustive:

- **Run** `git rev-parse --show-toplevel` as the one bounded identity probe.
- **Read** `<main_root>/.agent/` coordination files.
- **Write** `<main_root>/.agent/PAUSED`, and `ledger.md` to settle the rows you drained.
- **Talk to the user** — the report, and the confirmation before `abandon`.
- **Dispatch subagents**, naming the skill each one must follow.

Resolve `main_root` once with the bounded probe `git rev-parse --show-toplevel`. Resolve
every coordination path against it. Verification and landing dispatches must carry that
root, the task's exact absolute `worktree_path` from the ledger, and absolute pointers.

**Anything not on that list is a dispatch** — including the verification and the checks in
the drain below. You do not run them; you dispatch them and record what comes back.

## What it writes

`<main_root>/.agent/PAUSED` is its own file rather than a ledger field so the flag can be
set *before* the ledger is even read — step 1 below — and so `work`'s precondition is one
file-existence test rather than a ledger parse.

**You also write `ledger.md`.** Single-writer means one *role*, and pause is the parent,
exactly as `work` and `continue` are. There is no second agent here, only the same main
agent in a later turn — and without that write, step 4's promise that no task is left
`in_progress` would be impossible to keep.

```markdown
paused: 2026-08-05T14:22Z
mode: drain
reason: heading into a meeting
in_flight_when_paused: [T-014, T-017]
drained: [T-014 merged, T-017 merged]
tree: clean
```

`tree: clean` is the important line. It records whether the repository was left consistent
— all merges applied, no orphan worktrees, checks passing. If a drain could not reach that
state, say so explicitly and say what is dangling.

## Procedure

1. **Set the flag first**, before anything else. If this turn dies, the pause still holds.
2. Read the ledger. Identify what is in flight.
3. Apply the mode:
   - **drain** — wait for each in-flight worker. A completed `ai-bug` diagnosis leaves its
     reservation `diagnosing`, clean worktree kept, and planning for the next session; do
     not begin decomposition while pausing. For completed executors, **dispatch
     `ai-verify`** against each ledger-recorded `worktree_path`, then **dispatch `ai-land`**
     one task at a time against that same path. Then stop. You neither merge nor run the
     checks yourself. A task the lander could not land goes back to `pending` with its
     worktree kept; a drain does not force work in on the way out.
   - **stop** — signal active workers to write durable state and stop. Executors write
     handoffs and return to `pending`; an `ai-bug` worker appends its partial diagnosis and
     leaves the reservation `diagnosing`. Keep the worktrees.
   - **abandon** — discard in-flight worktrees, reset executable tasks to `pending`. For a
     `diagnosing` reservation, preserve its progress record, remove the provisional row,
     and burn the id.
4. Confirm no worker is live and no task is left `in_progress` or `landing`. A completed
   reproduced reservation may remain `diagnosing` for planning after resume. A paused
   ledger with a task still marked in progress is a lie about the state of the world, same
   as after a crash.
5. Report.

## Report

Follow `ai-report`. The reader is about to walk away, so tell them what they are walking
away from.

```
TL;DR
- Paused. 2 tasks finished and merged on the way out, nothing left half-done.
- Tests pass, working tree clean — safe to leave or pick up by hand.
- 2 tasks still queued for M-03. Resume with /rune:continue.

Finished while draining
- T-014 rotate refresh tokens — merged
- T-017 expiry sweep job — merged

Still queued
- T-016 restart persistence
- T-018 session listing

Waiting on you
- nothing
```

If something is dangling, lead with that instead:

```
TL;DR
- Paused, but not cleanly. T-016 stopped partway and its changes are parked.
- Everything else merged. Tests pass on what landed.
- T-016 picks up from its notes when you resume — or discard it with /rune:pause abandon.
```

## Resuming

Pause does not lift itself and no other skill lifts it silently.

- `/rune:continue` finds the flag, reports the pause and why, and **asks** before resuming.
- `/rune:work` refuses to dispatch while paused, and says so rather than sitting quietly.
- `/rune:pause` while already paused reports the current state and offers to lift it.

That last one makes this skill the status check too — running it twice is safe and tells
you where things stand.

When the pause lifts, delete `<main_root>/.agent/PAUSED`. Do not leave a stale flag behind
with a note saying it is inactive; the next reader will believe it.

## What pause is not

**Not a stop button for an interview.** `/rune:vision` is turn by turn already — just stop
answering. Pause governs the autonomous loop, where work continues without you.

**Not a rollback.** Merged tasks stay merged. To undo work, that is a revert, and it goes
through `/rune:work` like any other change so it gets a test and an acceptance check.

**Not a way to abandon a plan.** The milestones and task files survive. Pause is about
when work happens, not what the work is.
