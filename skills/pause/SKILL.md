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
| **drain** (default) | Finishes, verifies, merges. Then stops. | Almost always |
| **stop** | Executors write handoffs and stop where they are. Worktrees kept. | You need the machine or your attention back now |
| **abandon** | In-flight worktrees discarded, tasks reset to queued. | The current batch is going somewhere wrong |

`abandon` throws away real work. Say what will be lost and confirm before doing it.

If nothing is running, pause still applies — it becomes a *don't start* flag. Useful
before handing the repo to someone else.

## What it writes

Its own file, `.agent/PAUSED` — never the ledger. The ledger has exactly one writer, the
dispatcher, and pause is invoked from a different turn by a different agent. A second
writer there would be the one thing `ai-ledger` forbids.

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
   - **drain** — wait for each in-flight executor, verify, merge one at a time, re-run the
     checks after each. Then stop.
   - **stop** — signal executors to write handoffs and stop. Set their tasks to `pending`
     with the handoff attached. Keep the worktrees.
   - **abandon** — discard in-flight worktrees, reset those tasks to `pending`.
4. Confirm no task is left `in_progress`. A paused ledger with a task still marked in
   progress is a lie about the state of the world, same as after a crash.
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

When the pause lifts, delete `.agent/PAUSED`. Do not leave a stale flag behind with a note
saying it is inactive; the next reader will believe it.

## What pause is not

**Not a stop button for an interview.** `/rune:vision` is turn by turn already — just stop
answering. Pause governs the autonomous loop, where work continues without you.

**Not a rollback.** Merged tasks stay merged. To undo work, that is a revert, and it goes
through `/rune:work` like any other change so it gets a test and an acceptance check.

**Not a way to abandon a plan.** The milestones and task files survive. Pause is about
when work happens, not what the work is.
