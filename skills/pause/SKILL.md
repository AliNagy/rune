---
name: pause
user-invocable: false
description: Use when you want work to stop - at the end of the current task, or before anything else starts. Lets in-flight tasks finish and merge cleanly rather than abandoning them mid-edit, then holds until you resume. Also use to check whether work is currently paused.
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
| **abandon** | In-flight worktrees discarded, tasks reset to queued. | The current batch is going somewhere wrong |

`abandon` throws away real work. Say what will be lost and confirm before doing it.

If nothing is running, pause still applies — it becomes a *don't start* flag. Useful
before handing the repo to someone else.

### Why there is no "stop now"

Rune dispatches a worker and waits for its return. There is no channel back to one that is
already running: no handle to address, no acknowledgement, no way to know a signal arrived.
A mode that claimed to interrupt live workers would be promising something neither Claude
Code nor OpenCode can deliver.

What actually happens is the same either way. The flag goes down first, so nothing new
starts the moment you run pause. Whatever is already running has two honest endings:

- **wait for it** — `drain`, usually the shorter of the two
- **throw it away** — `abandon`, which loses that task's work and needs your confirmation

If a worker dies with the session instead of returning, that is not a pause mode either.
`continue` reconciles it on the next run.

## What you may do

**You stop the loop and leave the tree safe to walk away from.** This list is exhaustive:

- **Run** only the exact bounded state probes named below.
- **Follow** `root`; its narrowly scoped coordination migration is the sole write
  exception outside this route's pause and ledger records.
- **Read** `<main_root>/.rune/` coordination files.
- **Write** `<main_root>/.rune/PAUSED`, and `ledger.md` to settle the rows you drained.
- **Write** the parent-assigned result of a drained worker question to
  `<main_root>/.rune/decisions.md`, then **delete** only its consumed
  `<main_root>/.rune/decisions/open/T-nnn-eN.md` staging file, using `taskfmt`'s exact
  promotion transaction.
- **Delete** `<main_root>/.rune/PAUSED` only when an already-paused user explicitly asks
  this route to resume.
- **Promote** a complete assigned report staging file to its exact final path with one
  same-filesystem atomic no-replace operation. You never compose or edit report content.
- **Talk to the user** — the report, and the confirmation before `abandon`.
- **Dispatch subagents**, naming the skill each one must follow.

## Permitted commands and probes

This is the complete command interface for the parent route.

### State probes

```rune-commands
git rev-parse --show-toplevel
```

The probe returns exactly one line. `root` may run only its own separately bounded
migration probe while this route follows it. Worker state is read from durable returns and
coordination files, not process-list commands.

### Mutating lifecycle commands

`none` — verification and landing are dispatched; `drift` abandon mode owns discard of
each exact unpublished task worktree and branch.

## Coordination-root preflight

Resolve `main_root` once with the bounded probe `git rev-parse --show-toplevel`, then
follow `root` with `work: coordination-root`, that absolute root, and
`mode: initialize` before setting the flag or
reading state. Stop and report any failure it returns. Resolve every coordination path
against the returned root. Verification and landing dispatches must carry `main_root`, the
task's exact absolute `worktree_path` from the ledger, and absolute pointers.

Before consuming any followed or dispatched result, validate `taskfmt`'s common
return envelope: `work` must equal the assigned token, `summary` must be one line, and
`worktree`/`worktree_path` must agree. Only then read the worker-specific outcome.

**Anything not on that list is a dispatch** — including the verification and the checks in
the drain below. You do not run them; you dispatch them and record what comes back.

## What it writes

`<main_root>/.rune/PAUSED` is its own file rather than a ledger field so the flag can be
set *before* the ledger is even read — step 1 below — and so `work`'s precondition is one
file-existence test rather than a ledger parse.

**You also write `ledger.md`.** Single-writer means one *role*, and pause is the parent,
exactly as `work` and `continue` are. There is no second agent here, only the same main
agent in a later turn — and without that write, step 4's promise that no task is left
`in_progress` would be impossible to keep.

Validate schema 2 before draining and validate every complete replacement per `ledger`.
Settling a row includes its counters, finding, blocker, resume token, and replacement
lineage; never change only `status` and leave fields that describe the old phase. Pause
never retires a task or populates `replaced_by`.

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
   - **drain** — wait for each in-flight worker. A completed `bug` diagnosis leaves its
     reservation `diagnosing`, clean worktree kept, and planning for the next session; do
     not begin decomposition while pausing. Consume each executor's reserved drift-report
     slot exactly as `work` does: non-drift outcomes mark it unused; a drifted outcome is
     recorded only after its assigned staging file is atomically promoted, and it never
     advances to verification. A `question` outcome follows `taskfmt`'s deterministic
     per-attempt allocation transaction: persist the assigned decision, set the row
     `awaiting`, and delete staging last; it is safely drained but remains waiting on the
     user. For completed `done` executors, atomically set `verifying`,
     increment `v`, and **dispatch `verify`** against each ledger-recorded
     `worktree_path`; after a pass, set `landing`, increment `l`, and **dispatch `land`**
     one task at a time against that same path. Pass each recorded attempt. Then stop. You
     neither merge nor run the checks yourself. A task the lander could not land goes back
     to `pending` with its worktree kept; a drain does not force work in on the way out.
   - **abandon** — after confirmation and after each active worker is confirmed stopped,
     dispatch one `drift` worker in `abandon` mode for each exact ledger-recorded
     worktree. Only an `abandoned` return permits resetting an executable task to
     `pending` with worktree `discarded`, blocker `—`, and resume `fresh`. For a
     `diagnosing` reservation, preserve its progress record, remove the provisional row,
     and burn the id after the same cleanup return.
4. Settle report slots only after the paired worker is confirmed stopped. Promote and
   record a complete assigned staging report; if both assigned paths are absent, mark the
   slot `unused`. A mismatched, malformed, or duplicate artifact stays `blocked` for
   `continue`; never recycle its id or discard its evidence during `abandon`.
5. Confirm no worker is live and no task is left `in_progress` or `landing`. A completed
   reproduced reservation may remain `diagnosing` for planning after resume. A paused
   task may remain `awaiting` on the promoted decision. A staged question that could not
   be validated keeps the tree non-clean and routes recovery through `continue`; do not
   claim a clean drain. A paused ledger with a task still marked in progress is a lie
   about the state of the world, same as after a crash.
6. Report.

## Report

Follow `report`. The reader is about to walk away, so tell them what they are walking
away from.

```
TL;DR
- Paused. 2 tasks finished and merged on the way out, nothing left half-done.
- Tests pass, working tree clean — safe to leave or pick up by hand.
- 2 tasks still queued for M-03. Say "carry on" when you want them.

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
- T-016 picks up from its notes when you resume — or say "abandon it" to throw that work away.
```

## Resuming

Pause does not lift itself and no other skill lifts it silently.

- `continue` finds the flag, reports the pause and why, and **asks** before resuming.
- `work` refuses to dispatch while paused, and says so rather than sitting quietly.
- `pause` while already paused reports the current state and offers to lift it.

That last one makes this skill the status check too — asking twice is safe and tells you
where things stand.

When the pause lifts, delete `<main_root>/.rune/PAUSED`. Do not leave a stale flag behind
with a note saying it is inactive; the next reader will believe it.

## What pause is not

**Not a stop button for an interview.** `vision` is turn by turn already — just stop
answering. Pause governs the autonomous loop, where work continues without you.

**Not a rollback.** Merged tasks stay merged. To undo work, that is a revert, and it goes
through `work` like any other change so it gets a test and an acceptance check.

**Not a way to abandon a plan.** The milestones and task files survive. Pause is about
when work happens, not what the work is.
