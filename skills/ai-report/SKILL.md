---
name: ai-report
user-invocable: false
description: Use before writing anything the user will read - progress updates, completion reports, questions, or status. Defines when to speak (after each task, milestone, or blocker) and how (TL;DR first, lists over prose, plain words instead of internal vocabulary).
---

# Talking to the user

Two rules govern everything here: **report at the moments that matter**, and **say it in
the fewest words that stay accurate**.

## When to report

Speak at these points, and not between them:

- a task finished and was verified — pass or fail
- a milestone completed
- a batch of parallel tasks was dispatched, and again when it lands
- the plan turned out wrong in a way that affects other tasks
- something needs a decision from the user
- work stopped, for any reason

Between those points, stay quiet. Do not narrate dispatches, tool calls, or reasoning in
progress. The user asked for updates at checkpoints, not a commentary track.

## Every report opens with a TL;DR

Two or three lines. What happened, what is next, what needs them.

```
TL;DR
- 3 of 4 tasks done. Token rotation and the refresh endpoint work.
- One task hit a problem: the plan assumed a single entry point, there are two.
- Need you: split it into two tasks, or widen the existing one?
```

If a reader stops after the TL;DR, they should still know where things stand and whether
they are needed. Everything below it is detail for the reader who wants it.

## Form

- **Lists, not paragraphs.** One fact per line.
- **Tables for status.** Any time there are three or more items with the same shape.
- **No repetition.** Show what changed since the last update, not the whole ledger again.
  If a task was already reported done, it does not reappear.
- **No preamble.** Not "I'll now report on progress" — just report.
- **No restating the request.** They know what they asked for.

## Plain words, not internal vocabulary

The system's internal terms are precise and mean nothing to a reader. Translate:

| Internal | Say instead |
|---|---|
| the oracle passes | the tests pass |
| red-then-green confirmed | the test failed before the fix, passes now |
| green-baseline confirmed | the same tests passed before and after the refactor |
| characterization confirmed | a new test pins the existing behavior without changing it |
| task T-014 is diagnosing | T-014's failing bug test is being established |
| drift / DRF-003 | the plan was wrong about X |
| the ledger | progress / status |
| task T-014 is in the verifying state | T-014 is being checked |
| task T-014 is blocked; `unblocks_when` X | T-014 stopped because Y; it can resume when X |
| decomposed the milestone | split the work into 4 tasks |
| context contract / forbidden list | which files this touches |
| encapsulated task | self-contained task |
| the executor returned status budget | the task ran long and stopped partway |

Task and milestone ids are fine — they are short and the user can point at them. Names for
internal machinery are not.

## Reporting a completed task

```
T-014 done · rotate refresh tokens

- new test covers rotation, failed before the change and passes now
- full test suite still green
- touched 2 files in src/auth

Next: T-015, the refresh endpoint.
```

## Reporting a milestone

```
TL;DR
- M-03 done. Sessions now survive restart and refresh without re-login.
- Next up is M-04, profile CRUD — 4 tasks.

Delivered
- token rotation, refresh endpoint, restart persistence, expiry sweep

Worth knowing
- T-016 needed re-planning: handle() had two call sites, not one.
- Test suite grew by 11 tests. Still ~40s.
```

## Asking a question

Lead with it. Give the options and a recommendation, then stop.

```
TL;DR — need a decision before T-017 can continue.

Expired sessions: delete the row, or keep it flagged?
- Delete — simpler, no cleanup job needed
- Keep flagged — supports "you were logged out at 4pm" in the UI, needs a sweep

Recommend keeping them flagged; the UI story is hard to add back later.
Everything else in M-03 is done and waiting on this.
```

Never ask a question the code or the task spec already answers. Never ask two questions in
one message unless they are genuinely coupled.

## Reporting a failure

State what failed, what was observed, and what happens next. No apologising, no hedging,
no speculating about causes you have not checked.

```
T-016 failed verification.

- the new test passes, but two existing auth tests now fail
- both fail on session lookup after restart
- worktree discarded, task back in the queue

Retrying once with the failure attached. If it fails again the plan is wrong, not the code.
```

## Reporting a blocker

State the present condition and the observable fact that would allow work to resume. Say
whether the user needs to act; do not describe a durable block as a transient retry.

```
TL;DR
- T-017 stopped because the package registry is unreachable from its worktree.
- Its partial work is preserved. It can resume when the registry probe succeeds.
- No action needed yet; the other two tasks are still running.
```
