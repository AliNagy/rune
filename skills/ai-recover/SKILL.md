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
under 200 tokens; write the detail to `<main_root>/.agent/notes/T-nnn.md` as the handoff
the dead executor never wrote.

The dispatch must include absolute `main_root`, the ledger's exact absolute
`worktree_path`, and absolute pointers to the task and progress files. Validate that the
worktree belongs to the same repository and task branch as `main_root`. **Never create a
fresh recovery worktree or inspect the harness's starting checkout instead.** A missing or
mismatched supplied path is a discard/blocking finding, not permission to search.

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

1. **Read the task spec** — type, verification mode, steps, change surface, acceptance,
   and the stated check.
2. **Read the progress file** — ticks and the mode-specific evidence recorded so far.
3. **Read `git -C <worktree_path> diff`.** This is the authoritative record of what happened.
4. **Map the diff onto the declared steps.** For each step, decide: applied, partly
   applied, or absent. Steps are written to be checkable precisely so this is possible.
5. **Check containment.** Does every changed file appear in the declared change surface?
6. **Decide.** Below.
7. **Write the missing handoff** to `<main_root>/.agent/notes/T-nnn.md`, in the format
   `ai-taskfmt` specifies, so the next executor gets what it should have had.

## Deciding

**Ordered rules. First match wins. Stop there.**

| # | If | Verdict |
|---|---|---|
| 1 | any changed file is outside the declared change surface | **discard** |
| 2 | the diff contradicts itself, or you cannot say what it was trying to do | **discard** |
| 3 | the task's premise looks false in light of the diff | **discard** + write a drift record |
| 4 | fewer than 20 changed lines | **discard** |
| 5 | a `red_then_green` or `green_baseline` task has relevant edits but lacks its required pre-change evidence | **partial** |
| 6 | any declared step is fully or partly applied | **salvage**, resume at the first unfinished step |
| 7 | otherwise | **discard** |

Nothing here asks you to weigh "was it nearly done" or "is this coherent enough". Those
were the old criteria and two agents reading one diff could answer them differently — which
is the whole failure this table removes. Walk the rules in order and take the first hit.

**Why 20 lines.** Below that, restarting from clean is cheaper than any agent reading and
reasoning about an abandoned edit. The exact number matters less than that it is a number.

**Why discard is the fallback.** Under Serena a fresh executor re-acquires its working set
for about 10k. Abandoned work of unknown provenance is worth less than the clean base it
occupies.

**What partial means.** Keep the worktree, but restore the pre-change state before resuming
the evidence chain. A `red_then_green` task must observe the declared failure before the
implementation is reapplied. A `green_baseline` task must observe the existing check and
oracle passing before the refactor is reapplied. `ai-verify` correctly refuses either mode
when its pre-change observation is missing. A `characterization` task does not need this
reset when production source is unchanged; its new check can still be run against that
original behavior.

## Return

```
task: T-016
verdict: salvage | discard | partial
applied: steps 1-2 complete, step 3 partly (rotate() exists, not wired into handle())
containment: clean            # or: touched src/api/routes.ts, outside surface
verification: red_then_green
evidence: missing red         # forces the behavior change to be reset
resume_at: step 3 - restore the base, observe red, then reapply rotate()
worktree: kept
worktree_path: /workspace/acme/.agent/worktrees/T-016
```

## What not to do

**Do not finish the task.** You are diagnosing, not executing. A fresh executor does the
work with a proper budget and a clean context; you have neither.

**Do not guess at intent.** If the diff does not explain itself, that is a discard, not an
invitation to invent a story. A confident wrong reconstruction is worse than starting over,
because the next executor will trust it.

**Do not repair the ledger.** Report your verdict. The parent owns that file.
