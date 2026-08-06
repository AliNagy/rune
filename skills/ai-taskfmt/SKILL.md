---
name: ai-taskfmt
user-invocable: false
description: Use when writing or amending any file under .agent/ - task files, milestones, decision records, handoff notes, or drift records. Defines the schemas, the encapsulated-task contract, checkable steps, red-then-green, and single-writer ownership.
---

# Rune file formats

The spine. Every durable fact lives on disk under `.agent/`. No agent may rely on
conversation memory for anything another agent will need — assume every reader is a
stranger with an empty context.

## Layout

```
.agent/
  rune.yml              # init output: oracle, commands, baseline, staleness stamp
  map.md                 # module map, entry points, conventions, danger zones
  vision.md              # the vision document
  decisions.md           # decision records (DEC-nnn)
  milestones.md          # milestone graph (M-nn)
  ledger.md              # ALL mutable state. single writer: the parent
  tasks/T-nnn.md         # immutable spec + appended amendments
  notes/T-nnn.md         # handoff notes, long results
  notes/T-nnn.progress   # step ticks. single writer: the executor
  drift/DRF-nnn.md       # misconceptions + which tasks they invalidate
  sessions/<stamp>.md    # session handoffs. written by `handoff`
  PAUSED                 # present only while work is stopped. written by `pause`
```

Two different things are called a handoff, and they do not overlap. A **task** handoff
(`notes/T-nnn.md`) explains one stopped task to the next executor. A **session** handoff
(`sessions/<stamp>.md`) carries what a conversation knew but never wrote down, to a fresh
session.

`PAUSED` is deliberately its own file rather than a field in the ledger. Pause is invoked
from a separate turn by a separate agent, and the ledger has exactly one writer.

## Where writes land

Source code is only ever modified inside a git worktree — never the main checkout. But
**`.agent/` always lives in the main tree**, including files an executor writes while
working in a worktree.

| Written by an executor | Lands in |
|---|---|
| source changes | its worktree |
| `notes/T-nnn.progress`, handoff notes | `.agent/` in the main tree |
| drift and decision records | `.agent/` in the main tree |

Coordination state has to be visible to the dispatcher, the verifier, and the next session
*before* anything merges. Written inside a worktree it would appear only on merge — which
is precisely when nobody needs it any more.

ID prefixes never collide: `M-` milestone, `T-` task, `DEC-` decision, `DRF-` drift,
`INV-` investigation, `RES-` research.

## Single-writer rule

Every file has exactly one writer. Nothing races, nothing needs locking, and no two
files can disagree about the same fact.

| File | Sole writer |
|---|---|
| `ledger.md` | parent / dispatcher |
| `tasks/T-nnn.md` | planner (creates), fixer (appends amendments only) |
| `notes/T-nnn.progress` | the executor holding the task |
| `notes/T-nnn.md` | the executor holding the task |
| `drift/DRF-nnn.md` | whoever detected the drift |
| `rune.yml`, `map.md` | `rune:init` |
| `vision.md`, `decisions.md`, `milestones.md` | `rune:vision` |

Status lives in `ledger.md` and nowhere else. Never duplicate it into task frontmatter —
two copies of a mutable fact diverge within a day and then neither can be trusted.

## Task file

A task is **encapsulated**: it carries its own goal, change surface, acceptance, and
test. It can be executed, retried, or reviewed with no knowledge of its siblings.

Encapsulate the *contract*, reference the *context*. Goal, surface, acceptance and test
belong in the task. Conventions and module layout are pointed at, never copied — copies
drift apart from `map.md` and from each other.

```markdown
---
id: T-014
title: Rotate refresh tokens inside session middleware
milestone: M-03
type: feature            # feature | bug | refactor | chore
blocked_by: [T-011]
---

## Goal
One paragraph, prose. What the world looks like when this is done.

## Context contract
read:
  - serena: find_symbol SessionMiddleware/handle   -> src/auth/session.ts
  - serena: find_symbol TokenStore                 -> src/auth/store.ts
  - file:   .agent/map.md (conventions section)
forbidden:
  - src/api/**           # unrelated; ~40k tokens if opened
  - src/legacy/**         # scheduled for deletion in M-05

## Change surface
- src/auth/session.ts :: SessionMiddleware.handle
- src/auth/store.ts   :: TokenStore.rotate          (new)

## Steps
- [ ] Add `rotate(): Promise<Token>` to the TokenStore interface
- [ ] Implement rotation in the concrete store, reusing the existing issue path
- [ ] Call it from handle() before the session is refreshed

## Test
file: src/auth/__tests__/rotation.test.ts
assert: a refresh issues a new token and invalidates the prior one
must fail before the change   # mandatory - see Red-then-green

## Acceptance
- [ ] The test above passes
- [ ] Project oracle still passes (no regression)
- [ ] rotate() is called exactly once per refresh

## Amendments
<!-- fixers append here; never edit sections above -->
```

### Sizing

One task = **at most 5 files, one subsystem, one verifiable outcome.** If it needs more,
it is two tasks. Oversized tasks are the root cause of blown context budgets and of
drift bounces — a task that keeps drifting was cut too large, and that is a signal about
the planner, not the executor.

### Step rules

Steps are coarse intent, not a script.

- **Symbol- or intent-addressed, never line-addressed.** `session.ts:240` is wrong the
  moment any edit lands above it. `session.ts :: handle` survives.
- **Every step must be checkable** — a later reader must be able to answer "is this
  already done?" by looking. `Add field x to interface Y` is checkable. `Refactor the
  handler` is not.
- **Do not plan too deep.** Step 7 requires predicting the state after steps 1–6. Three
  to six coarse steps is the useful range.

### Progress and the write-order rule

Ticks live in `notes/T-nnn.progress`, owned by the executor.

**Always make the edit first, then tick.** This is not stylistic. If the process dies
between the two, the only reachable desync is a *missing* tick — and that self-heals,
because the next executor attempts the step, finds it already applied, and ticks it.
The reverse order permits a tick with no edit, which makes the record lie and causes the
next executor to skip real work. One direction is recoverable; the other is silent
corruption.

The ticks are a convenience, not the truth. `git diff` in the task's worktree is the
authoritative record of what changed — it is atomic with the edit by construction and
cannot desync.

### Red-then-green

A task's test must be **observed failing against the pre-change state** before the
change is made. Record it in the progress file:

```
red: confirmed 2026-08-04 - rotation.test.ts fails (rotate is not a function)
```

A test written after the fix and never seen red proves nothing, and a clean-context
verifier cannot tell it apart from a real one. Nobody downstream can reconstruct this
evidence, so the executor must leave it.

Not every acceptance needs a unit test. Where a test does not fit (a config rename, a
dependency bump), acceptance is a scripted or observable assertion instead. Mandating
tests everywhere produces ceremonial ones.

## Milestone

```markdown
## M-03 · Session lifecycle
status_note: depends on M-01 auth primitives
depends_on: [M-01]
goal: Sessions survive restart and refresh without re-login.
scope:
  in:  token rotation, session store, refresh endpoint
  out: OAuth providers (M-06), device management (M-07)
acceptance:
  - a session survives a server restart
  - a refresh rotates the token and invalidates the old one
decisions: [DEC-004, DEC-007]
```

Milestones are decomposed into tasks **just before execution**, never during vision. A
task must name real files and real symbols; for a milestone three steps out, those do
not exist yet, so any task written now is fiction that will drift on contact.

## Decision record

```markdown
## DEC-007 · State management
status: open              # open | decided
options:
  - Zustand — light, minimal ceremony
  - Redux Toolkit — heavy, more structure, familiar to the team
recommendation: Zustand
decided: —
rationale: —
```

**Gate: no milestone may be generated that depends on an `open` decision.** This is what
converts "make suggestions, never assumptions" from a personality instruction into a
checkable property. Recommendations are encouraged; silently adopting one is not.

Executors use the same record to ask questions mid-task. They add `raised_by: T-nnn`, stop
with `status: question`, and the task sits `awaiting` until the decision is made. Reusing
this format rather than inventing a question artifact means one gate, one place to look,
and one thing for the user to resolve.

## Handoff note

Written when an executor stops early. Read by a stranger, always.

```markdown
# T-014 handoff
stopped_at: step 2 of 3
reason: drift | budget | blocked | question
what_exists: TokenStore.rotate implemented and unit-tested; not yet wired into handle()
what_surprised_me: handle() is called from two places, not one — see src/ws/upgrade.ts
worktree: kept | discarded
next: wire both call sites, or split the second into its own task
```

No pronouns pointing at a conversation. No "as discussed". No "the approach we agreed".
The reader has none of that.
