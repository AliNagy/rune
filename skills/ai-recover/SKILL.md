---
name: ai-recover
user-invocable: false
description: Use when a task was left mid-flight by a session that died and there is no handoff note explaining it. Reconstructs how far the work actually got from the worktree diff, decides whether it is salvageable, and names the exact resume point. Runs as a subagent.
---

# Recovering an abandoned task

`continue` handles the easy cases mechanically: a handoff note exists, or the worktree is
empty. This skill is for the one that needs judgement — **a task marked in progress, no
handoff, and a worktree with real changes in it.**

The default without this skill is to discard and restart. That is safe but wasteful when
the work was nearly done. Recovery is worth attempting; blind trust in a torn tree is not.

**Run as a subagent.** This reads diffs and code, and the parent must not. Return a verdict
under 200 tokens; write the detail to `.agent/notes/T-nnn.md` as the handoff the dead
executor never wrote.

**One abandoned task per subagent.** A session that died mid-batch can leave three torn
worktrees; that is three recovery dispatches. Each resume point has to be read off its own
diff, and an agent holding three diffs at once will map a step it saw in one onto another.

## The diff is the truth, the ticks are a floor

Executors are required to make the edit *first* and tick the step *second*. That ordering
is what makes recovery possible: the only reachable desync is a step that was done but not
recorded.

So:

- A **ticked** step is definitely done.
- An **unticked** step may still be done — check the diff before believing otherwise.
- A tick with no corresponding change means the write-order rule was violated. Treat the
  whole progress file as unreliable and work from the diff alone.

## Procedure

1. **Read the task spec** — steps, change surface, acceptance, the stated test.
2. **Read the progress file** — ticks, and whether red-then-green was recorded.
3. **Read `git diff` in the worktree.** This is the authoritative record of what happened.
4. **Map the diff onto the declared steps.** For each step, decide: applied, partly
   applied, or absent. Steps are written to be checkable precisely so this is possible.
5. **Check containment.** Does every changed file appear in the declared change surface?
6. **Decide.** Below.
7. **Write the missing handoff** to `.agent/notes/T-nnn.md`, in the format
   `ai-taskfmt` specifies, so the next executor gets what it should have had.

## Deciding

**Salvage** — keep the worktree, resume from the named step. Requires all of:

- every changed file is inside the declared change surface
- the applied steps are coherent — no half-renamed symbol, no import pointing at something
  that was not created
- enough was done that redoing it costs more than reading it

**Discard** — reset to `pending`, drop the worktree. Any of:

- the diff touches files outside the change surface. The executor had already drifted
  before it died; whatever it was doing is not what the task says.
- the changes are small. Under a handful of lines, restarting from clean is cheaper and
  safer than reasoning about someone else's abandoned edit.
- the diff contradicts itself, or you cannot explain what it was trying to do.
- the task's premise looks false in light of what the diff reveals — that is drift, not a
  recovery problem. Write a drift record and say so.

**Partial salvage** — keep the worktree but reset the test. If a test file exists and the
progress file has **no red evidence**, the red-then-green chain is broken and cannot be
reconstructed after the fact. The code may be fine; the test is unproven. The resumed task
must revert the change, observe the test fail, and re-apply — or write a fresh test.

That case is easy to miss and it matters. A test that was never seen failing is
indistinguishable from one that cannot fail, and `ai-verify` will correctly refuse to pass
it.

## Return

```
task: T-016
verdict: salvage | discard | partial
applied: steps 1-2 complete, step 3 partly (rotate() exists, not wired into handle())
containment: clean            # or: touched src/api/routes.ts, outside surface
red_evidence: missing         # forces a test reset
resume_at: step 3 - wire rotate() into handle(), then redo the test red-first
worktree: kept
```

## What not to do

**Do not finish the task.** You are diagnosing, not executing. A fresh executor does the
work with a proper budget and a clean context; you have neither.

**Do not guess at intent.** If the diff does not explain itself, that is a discard, not an
invitation to invent a story. A confident wrong reconstruction is worse than starting over,
because the next executor will trust it.

**Do not repair the ledger.** Report your verdict. The parent owns that file.
