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
  notes/T-nnn.landing.md # merge attempts and what broke. single writer: the lander
  drift/DRF-nnn.md       # misconceptions + which tasks they invalidate
  decisions/open/T-nnn.md # a worker's question, awaiting a DEC-nnn from the parent
  sessions/<stamp>.md    # session handoffs. written by `handoff`
  PAUSED                 # present only while work is stopped. written by `pause`
```

Two different things are called a handoff, and they do not overlap. A **task** handoff
(`notes/T-nnn.md`) explains one stopped task to the next executor. A **session** handoff
(`sessions/<stamp>.md`) carries what a conversation knew but never wrote down, to a fresh
session.

`PAUSED` is its own file rather than a ledger field so the flag can be set *before* the
ledger is even read, and so `work`'s precondition is one file-existence test rather than a
ledger parse. Not because pause is a second writer — it is the same parent.

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

**Writers are roles, not skills.** There is one parent — the main agent — and it is the
same writer whether it is running `work`, `init`, `vision`, `continue`, `pause`, or
`handoff`. Those are routes through one role, not six agents. Getting this backwards is
what made `pause` and `handoff` look like second writers when they are the same writer.

| File | Sole writer |
|---|---|
| `ledger.md` | the parent |
| `PAUSED` | the parent |
| `rune.yml` | the parent |
| `vision.md`, `decisions.md`, `milestones.md` | the parent |
| `sessions/<stamp>.md` | the parent |
| `map.md` | a worker on `ai-survey` |
| `tasks/T-nnn.md` | a worker on `ai-decompose` (creates), fixer (appends amendments only) |
| `notes/T-nnn.progress` | the worker holding T-nnn |
| `notes/T-nnn.md` | the worker holding T-nnn |
| `notes/T-nnn.landing.md` | a worker on `ai-land` |
| `decisions/open/T-nnn.md` | the worker holding T-nnn |
| `notes/init-commands.md` | a worker on `ai-oracle` |
| `notes/INV-nnn.md`, `notes/RES-nnn.md` | the worker that answered |
| `drift/DRF-nnn.md` | whoever detected the drift |

## The concurrency rule that generates this table

**Any file that two workers could write at the same time must be per-task.**

Up to three executors run concurrently. A shared file they all append to is a race by
construction — and worse, they race on *id allocation*: two executors both reach for
`DEC-012`. Per-task files have no such problem, because the filename already contains the
thing that makes each writer unique.

That rule is why `notes/T-nnn.progress` and `decisions/open/T-nnn.md` are shaped the way
they are. Apply it to any new file before adding a row above.

Status lives in `ledger.md` and nowhere else. Never duplicate it into task frontmatter —
two copies of a mutable fact diverge within a day and then neither can be trusted.

The parent writes coordination and planning state. Workers write everything that comes
out of doing the work — maps, task files, progress, results. A parent about to write
anything outside its rows has found a dispatch it skipped.

`milestones.md` is the exception worth explaining: the parent owns the file, but it never
composes it. A worker on `ai-decompose` writes the graph and the parent records it, for the
same reason the parent does not read code.

## The dispatch table

**There are no agent definitions in Rune.** Every worker is an ordinary subagent told
which skill to follow. A dispatch names a job and a skill, and nothing else.

| Job | The worker follows |
|---|---|
| map an unfamiliar codebase | `ai-survey` |
| classify a request | `ai-triage` |
| milestone graph, and milestone → tasks | `ai-decompose` |
| run build / test / lint / typecheck | `ai-oracle` |
| execute one task | `ai-execute` (which also loads `ai-serena`, `ai-drift`) |
| verify one finished task | `ai-verify` |
| land one verified task in the main tree | `ai-land` |
| salvage an abandoned task | `ai-recover` |
| answer a question about the code | `ai-investigate` |
| answer a question from outside the repo | `ai-research` |
| reproduce a bug | `ai-bug` |

**Never specify a model.** A subagent runs on whatever the session is running on. Model
selection is a separate concern that does not belong in these files.

### The dispatch envelope — what a worker is given

Every dispatch hands over the same shape and nothing more:

```
follow:    ai-execute                # the skill, from the table above
task:      T-014                     # the one id. always exactly one
isolation: worktree                  # where the harness offers it; otherwise omit
pointers:  .agent/tasks/T-014.md     # paths only, never file contents
```

**Pointers, not payloads.** The parent names where things are; the worker reads them
itself. Passing content down means the parent had to hold it first, which is the cost the
whole system exists to avoid — and it keeps every dispatch the same size no matter how big
the job is.

If a worker needs something not reachable from those pointers, that is a missing pointer,
not a reason to paste text into the prompt.

### The return envelope — what a worker hands back

Two lines are shared by every worker:

```
task:    T-014                # or the id it worked on; omit only if the job had none
summary: <one line, plain words>
```

Then **one outcome field, named and enumerated by that worker's own skill**:

| The worker followed | Its outcome field |
|---|---|
| `ai-execute` | `status: done \| drifted \| budget \| blocked \| question` |
| `ai-verify` | `verdict: pass \| fail \| unverified` |
| `ai-land` | `landing: landed \| conflict \| reverted \| stuck` |
| `ai-recover` | `verdict: salvage \| discard \| partial` |
| `ai-triage` | `type: bug \| feature \| refactor \| investigation` |
| `ai-oracle` | `oracle: passing \| failing \| none` |

Then whatever else that skill defines.

**Do not force one vocabulary across all of them.** A verifier's outcome genuinely is not
an executor's outcome, and `ai-execute`'s values are the ones the ledger's state machine
consumes by name. Collapsing them into a generic `ok | failed` would lose the transition
and gain nothing.

The same goes for fields. A worker handed a field it has nothing to say about will fill it
anyway, and an invented value is worse than an absent one — `ai-triage` has no worktree,
so it gets no worktree line.

What *is* shared: the id, one plain-words summary, an enumerated outcome, and a hard
**≤200 tokens**. Anything longer goes to disk and the summary points at it.

### Bounded state probes

The parent may not run commands — with one named exception class.

**A bounded state probe reads state, changes nothing, and returns a fixed number of lines
regardless of how big the project is.** `git rev-parse HEAD` is one. A test suite is not:
its output grows with the codebase, which is the whole reason it gets dispatched.

The class is documentation. **What makes it checkable is that each skill lists its own
permitted probes by name** — an agent should never have to judge whether something
qualifies. If a command is not written down in that skill, it is a dispatch.

### Why there are no agents

Agent definitions bought exactly two things a skill cannot express: a tool allowlist, and
a model tier. Every harness spells both differently — one earlier version of this repo
compressed six agent definitions down to three bits each to cross a single harness
boundary — while the skill is the one artifact that travels unchanged.

The cost of keeping them was concrete. Behaviour split across two files, so four of the
executor's five governing rules lived only in an agent definition and in no skill at all;
any harness without an agent concept lost them silently. And two agents sat defined but
unreachable for weeks because nothing named them.

What that trade gives up is real and worth stating: **a tool allowlist was enforcement,
and prose is not.** A verifier that could not edit has become a verifier that is told not
to. The skills that depend on that now say so explicitly, at the top, in the places where
breaking the rule would be easiest — because a rule that used to be a wall now has to
carry its own reasons.

## Single-issue rule

The counterpart for agents. Single-writer keeps two agents out of one file; **single-issue
keeps two issues out of one agent.**

Every dispatched subagent carries exactly one issue — one bug to reproduce, one task to
execute, one task to verify, one question to research, one torn worktree to recover. Never
a list, however related the items look. Dispatch them concurrently instead; the rule bounds
what one agent holds, not how many run at once. Stated in full in `work` under *One agent,
one issue*.

The consequence for a worker: if you find a second issue while working, **report it and
stop**. Whether it becomes another dispatch belongs to whoever dispatched you. Taking it on
yourself merges two contexts that the system spent a dispatch to keep apart.

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

Workers use the same format to ask questions mid-task — but they write it to
**`.agent/decisions/open/T-nnn.md`**, not to `decisions.md`, and they **do not assign an
id**. They add `raised_by: T-nnn`, stop with `status: question`, and keep the worktree.

The parent then assigns the `DEC-nnn`, moves the record into `decisions.md`, deletes the
open file, and sets the task `awaiting`.

Two reasons for the extra hop. Three executors run at once, so a shared append target
races — and both would reach for the same next id. And a question that exists only in a
return value dies with the worker, while the *work* survives in the kept worktree; the
question has to survive on the same terms.

**The gate scans both files.** A milestone is blocked by an `open` record in
`decisions.md` *or* anything sitting in `decisions/open/`.

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
