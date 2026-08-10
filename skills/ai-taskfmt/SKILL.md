---
name: ai-taskfmt
user-invocable: false
description: Use when writing or amending any file under .agent/ - task files, milestones, decision records, handoff notes, or drift records. Defines the schemas, the encapsulated-task contract, checkable steps, task-specific verification evidence, and single-writer ownership.
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
  drafts/M-nn/R-nnn/protocol.md # immutable type/protocol selection for one run
  drafts/M-nn/R-nnn/P-nn.md # one complete, immutable cut from one planner
  tasks/T-nnn.md         # immutable spec + appended amendments
  notes/T-nnn.md         # handoff notes, long results
  notes/T-nnn.progress   # diagnosis, step ticks, verification evidence, publications
  notes/T-nnn.verify.md  # verdicts and findings, one block per attempt. single writer: the verifier
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
**`.agent/` always lives at `<main_root>/.agent/`**, including files a worker writes
while working in a task worktree. `main_root` is the absolute orchestration-checkout path
from the dispatch envelope below; it is never inferred from a worker's current directory.

| Written by a worker | Lands in |
|---|---|
| source changes while incomplete | its worktree as an uncommitted diff |
| confirmed bug reproduction | a diagnosis commit on its reserved task branch |
| source changes when complete | commits on its task branch |
| planner drafts and reconciled task files | `<main_root>/.agent/` |
| `notes/T-nnn.progress`, handoff notes | `<main_root>/.agent/` |
| drift and decision records | `<main_root>/.agent/` |

Coordination state has to be visible to the dispatcher, the verifier, and the next session
*before* anything merges. Written inside a worktree it would appear only on merge — which
is precisely when nobody needs it any more.

Global ID prefixes never collide: `M-` milestone, `T-` task, `DEC-` decision, `DRF-`
drift, `INV-` investigation, `RES-` research. Planning drafts use a separate local
namespace: `R-nnn` is a decomposition run under one milestone, `P-nn` is a planner slot
assigned by the parent, and `D-nnn` identifies a proposed task only inside that planner's
artifact. None of those local ids may appear as a final task id or ledger task row.

A bug reservation burns its `T-nnn` as soon as its protocol record, ledger row, or progress
file is written. Allocation treats an id found in **any** coordination artifact as used,
even when diagnosis later fails or reclassifies the request. Reusing an abandoned id would
let a late diagnosis return attach evidence to a different task.

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
| `drafts/M-nn/R-nnn/protocol.md` | the parent, once before that run is dispatched |
| `drafts/M-nn/R-nnn/P-nn.md` | the planner assigned that exact run and slot |
| `tasks/T-nnn.md` | the single reconciling worker on `ai-decompose` (creates), fixer (appends amendments only) |
| `notes/T-nnn.progress` | the worker holding T-nnn: `ai-bug` during diagnosis, then `ai-execute` |
| `notes/T-nnn.md` | the worker holding T-nnn |
| `notes/T-nnn.verify.md` | a worker on `ai-verify` |
| `notes/T-nnn.landing.md` | a worker on `ai-land` |
| `decisions/open/T-nnn.md` | the worker holding T-nnn |
| `notes/init-commands.md` | a worker on `ai-oracle` |
| `notes/INV-nnn.md`, `notes/RES-nnn.md` | the worker that answered |
| `drift/DRF-nnn.md` | whoever detected the drift |

## The concurrency rule that generates this table

**Any output that two workers could write at the same time must be split into a unique
artifact for each writer.**

Up to three executors run concurrently. A shared file they all append to is a race by
construction — and worse, they race on *id allocation*: two executors both reach for
`DEC-012`. Per-task files have no such problem, because the filename already contains the
thing that makes each executor unique. Planner drafts apply the same rule with an assigned
run and planner slot because several planners are working on the same milestone and cannot
use the task id to distinguish themselves yet.

That rule is why `notes/T-nnn.progress`, `decisions/open/T-nnn.md`, and planner drafts are
shaped the way they are. Parallel planners never share a destination: the parent assigns
each one an exact `M-nn/R-nnn/P-nn.md` path before dispatch. The run's `protocol.md` is
safe to share because the parent writes it once before any planner starts and every worker
afterward is read-only with respect to it. Apply the rule to any new file before adding a
row above.

Status lives in `ledger.md` and nowhere else. Never duplicate it into task frontmatter —
two copies of a mutable fact diverge within a day and then neither can be trusted.

The parent writes mutable coordination and user-owned planning state. Workers write the
outputs that require delegated context — maps, planner drafts, reconciled task files,
progress, and results. A parent about to write anything outside its rows has found a
dispatch it skipped.

`milestones.md` is the exception worth explaining: the parent owns the file, but it never
composes it. A worker on `ai-decompose` writes the graph and the parent records it, for the
same reason the parent does not read code.

## Checkout identity contract

Current working directory is not an identity. A harness may start a worker in the main
checkout, an anonymous fresh worktree, or a directory inherited from an earlier tool
call. No worker may use that directory to decide where coordination state or task source
lives.

Before its first read or dispatch, the parent resolves the root of the checkout it owns
with the harness workspace root or the bounded probe `git rev-parse --show-toplevel`.
That absolute path is `main_root` and stays constant for the run.

Every dispatch carries `main_root`. Every `.agent/...` path named anywhere in Rune is a
logical repo-relative name that must be resolved to `<main_root>/.agent/...` before it is
read or written. Dispatch pointers are already-resolved absolute paths. A worker rejects a
relative pointer rather than guessing what it is relative to.

Task-bound work also carries `worktree_path`:

- The parent chooses `<main_root>/.agent/worktrees/T-nnn` before the first task-bound
  worker, records that absolute path in the ledger, and never changes it during the task.
- For a bug, `ai-bug` creates that exact worktree during `diagnosing`, before it writes the
  reproduction check. For every other task, the first executor creates it. Either worker
  validates and reuses an existing path; neither substitutes the directory where the
  harness happened to start it.
- Retries, verifiers, recoverers, and landers receive the same `worktree_path`. They must
  target it directly and must not request or create a fresh worktree.
- After confirmed reproduction, only a successful lander may remove it. Before that,
  `ai-bug` may discard its own exact provisional worktree when diagnosis cannot reproduce
  or reclassifies the request. The burned id and progress record survive either way.
  Otherwise the path is part of the task's durable identity, alongside its id and branch.

Harness worktree isolation may be used only when it can target this exact existing path.
An isolation mode that silently creates a new worktree must be omitted: a clean anonymous
checkout is not the task checkout.

## The dispatch table

**There are no agent definitions in Rune.** Every worker is an ordinary subagent told
which skill to follow. A dispatch names one job, one skill, stable checkout identities,
and pointers — never file contents.

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

Every dispatch hands over the same shape. `main_root` is required for all workers;
`worktree_path` is required only for task-bound work and is omitted otherwise:

```
follow:        ai-execute
task:          T-014
main_root:     /workspace/acme
worktree_path: /workspace/acme/.agent/worktrees/T-014
pointers:
  - /workspace/acme/.agent/tasks/T-014.md
```

Bug diagnosis uses the same task-bound envelope before the task-file pointer exists:

```yaml
follow:        ai-bug
task:          T-014
main_root:     /workspace/acme
worktree_path: /workspace/acme/.agent/worktrees/T-014
pointers:
  protocol: /workspace/acme/.agent/drafts/M-03/R-002/protocol.md
  progress: /workspace/acme/.agent/notes/T-014.progress
```

The parent writes the protocol and `diagnosing` ledger row before this dispatch. The
worker creates or validates the exact supplied worktree before any source write.

The values sent in a real dispatch are absolute paths — never the literal
`<main_root>` placeholder used in prose. Before doing any work, a task-bound worker
confirms that `worktree_path` belongs to the same Git repository as `main_root`. A
mismatch, a missing verifier/recovery path, or a wrong task branch is a blocked outcome,
not permission to search for another checkout. A lander alone may accept a missing path
after proving the exact verified commit is already in main, per its crash-recovery path.

**Pointers, not payloads.** The parent names where things are; the worker reads them
itself. Passing content down means the parent had to hold it first, which is the cost the
whole system exists to avoid — and it keeps every dispatch the same size no matter how big
the job is.

If a worker needs something not reachable from those pointers, that is a missing pointer,
not a reason to paste text into the prompt or resolve a relative path from its current
directory.

For decomposition, the one work id is hierarchical because the work has two phases. A
planner gets one assigned slot such as `M-03/R-002/P-01`; the reconciler gets the enclosing
run `M-03/R-002`. The exact output destination is still a pointer, not prompt payload:

```
follow:    ai-decompose
task:      M-03/R-002/P-01
main_root: /workspace/acme
pointers:
  milestone: /workspace/acme/.agent/milestones.md#M-03
  protocol:  /workspace/acme/.agent/drafts/M-03/R-002/protocol.md
  draft:     /workspace/acme/.agent/drafts/M-03/R-002/P-01.md
```

A bug planner or reconciler additionally receives the reserved task's
`worktree_path` and `diagnosis: /workspace/acme/.agent/notes/T-014.progress`. Its assigned
work id remains the run or planner slot; it validates the task branch against
`reserved_task` in the protocol. It may read that worktree but never write source there.

The parent chooses the next unused `R-nnn` beneath the milestone and assigns distinct
`P-nn` slots before dispatch. Before starting any planner, it writes the run's immutable
`protocol.md` from the final triage result. For a bug it writes that record earlier, before
dispatching diagnosis, with a `reserved_task`; confirmed diagnosis then becomes another
planner pointer. A retry gets a new unused slot; it never reuses a path that a late worker
could still write. The reconciler is dispatched only after the parent has the completed
absolute draft paths, and receives the same protocol pointer plus every draft as a pointer.

The protocol record is deliberately small:

```markdown
---
run: M-03/R-002
type: feature
protocol: ai-feature
---
evidence: SessionMiddleware.handle exists, but profile storage does not.
shape: thin end-to-end slice through the existing session boundary
```

A bug run adds exactly one field before diagnosis:

```yaml
reserved_task: T-014
```

That id binds the ledger row, `task/T-014` branch, worktree, progress file, and eventual
primary bug task. Bug planner and reconciler dispatches also receive absolute `diagnosis`
and `worktree_path` pointers. The protocol does not copy the diagnosis result or absolute
paths; the progress file and dispatch envelope remain authoritative.

Only these mappings are valid: `bug -> ai-bug`, `feature -> ai-feature`, and
`refactor -> ai-refactor`. An investigation never reaches decomposition. The record is a
durable routing input, not a planner opinion: planners and reconcilers load the named skill
and may not infer another protocol from titles or source. If the selected type changes,
the parent abandons that run and creates a fresh `R-nnn` plus protocol record; it never
rewrites a record workers may already have read.

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
| `ai-land` | `landing: landed \| refused \| conflict \| reverted \| stuck` |
| `ai-recover` | `verdict: salvage \| discard \| partial` |
| `ai-triage` | `type: bug \| feature \| refactor \| investigation` |
| `ai-bug` | `diagnosis: reproduced \| not_reproduced \| reclassified \| blocked` |
| `ai-oracle` | `oracle: passing \| failing \| none` |
| `ai-decompose` | `plan: graph \| drafted \| reconciled \| blocked` |

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

An `ai-decompose` planner returning `plan: drafted` also returns exactly one `artifact:`
path, and it must equal its assigned draft pointer. A reconciler returning
`plan: reconciled` returns `artifacts:` with the final `tasks/T-nnn.md` paths plus the
one-line titles and dependency edges the parent needs to register. `plan: blocked`
returns no invented paths and names the missing or contradictory pointer in `summary`.

### The published task artifact

One small interface crosses execution, verification, and landing:

```yaml
base_commit: a3f91c2
artifact_commit: 4a91c02
verified_commit: 4a91c02   # added only by a passing verifier
```

Only an executor returning `status: done` publishes an artifact. It commits the completed
source change on the task branch, proves `worktree_path` clean, and appends `base_commit`
plus `artifact_commit` to `<main_root>/.agent/notes/T-nnn.progress`. Incomplete outcomes
keep their uncommitted diff in that same task worktree and do not invent an artifact.
A bug's earlier `diagnosis_commit` is an input inside the eventual publication range, not
a publication by itself; its absence of `artifact_commit` is deliberate.

The verifier reads the latest publication and checks exactly
`git diff <base_commit>..<artifact_commit>`. A pass writes the identical SHA as
`verified_commit` in `notes/T-nnn.verify.md`. The lander refuses unless the task branch
still points to that SHA and merges the SHA itself, never an unnamed worktree diff or a
branch that moved after verification.

**Invariant: the executor publishes one immutable range, the verifier approves its head,
and the lander merges that same head.** The ids are repeated in short returns for routing,
but the per-task files are authoritative because they survive a dead parent.

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

## Planner draft

A planner draft is the durable, complete candidate cut passed to the reconciler. It is
not a task file and it never reserves a `T-nnn` id.

```markdown
---
run: M-03/R-002
planner: P-01
milestone: M-03
type: feature
protocol: ai-feature
---

# Candidate cut

## D-001 · Rotate refresh tokens inside session middleware
type: feature
verification: red_then_green
blocked_by: []

### Goal
One paragraph describing the independently verifiable outcome.

### Context contract
read:
  - serena: find_symbol SessionMiddleware/handle -> src/auth/session.ts
forbidden:
  - src/legacy/** # unrelated and scheduled for deletion

### Change surface
- src/auth/session.ts :: SessionMiddleware.handle

### Steps
- [ ] Add the check that demonstrates the missing behavior
- [ ] Implement token rotation at the existing refresh seam

### Check
file: src/auth/__tests__/rotation.test.ts
command: npm test -- rotation.test.ts
assert: refresh issues a new token and invalidates the prior one
before: must fail for the missing rotation behavior
after: must pass

### Acceptance
- [ ] The check above passes
- [ ] Project oracle still passes

## D-002 · Wire the refresh endpoint
type: feature
verification: red_then_green
blocked_by: [D-001]
...

## Cut notes
assumptions:
  - rotation uses the existing configured expiry
exclusions:
  - device management remains in M-06
seams:
  - middleware and endpoint are separated because they share no change-surface files
```

The draft's `type` and `protocol` must exactly match the run's `protocol.md`. Every
`D-nnn` repeats the complete final task contract: title, type, verification mode, local
dependencies, goal, context contract, change surface, steps, check, and acceptance. `Cut
notes` records the assumptions, exclusions, and disputed seams the user gate and
reconciler need. A summary that omits those sections is not a draft artifact.

For a bug run, every complete draft marks exactly one proposed task
`reservation: primary`. That local marker is not a second id: it tells the reconciler
which proposed task must become the protocol's `reserved_task`. The primary task owns the
reproduction check and root-cause fix. Other proposed tasks keep local `D-nnn` ids and are
allocated normally. Non-bug drafts must not use the marker, and the reconciler removes the
local marker when it writes the final task contract.

The file becomes immutable when its planner returns. That planner writes only its exact
assigned draft path: it does not create `tasks/T-nnn.md`, inspect or update `ledger.md`, or
write another planner's slot. The reconciler maps the selected local dependencies to final
`T-nnn` ids and writes new final task files; it never renames a draft into the final
namespace because a draft may be grafted from more than one cut.

## Task file

A task is **encapsulated**: it carries its own goal, change surface, acceptance, and
check. It can be executed, retried, or reviewed with no knowledge of its siblings.

Encapsulate the *contract*, reference the *context*. Goal, surface, acceptance and check
belong in the task. Conventions and module layout are pointed at, never copied — copies
drift apart from `map.md` and from each other.

```markdown
---
id: T-014
title: Rotate refresh tokens inside session middleware
milestone: M-03
type: feature            # feature | bug | refactor | characterization | chore
verification: red_then_green # red_then_green | green_baseline | characterization
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

## Check
file: src/auth/__tests__/rotation.test.ts
command: npm test -- rotation.test.ts
assert: a refresh issues a new token and invalidates the prior one
before: must fail for the missing rotation behavior
after: must pass

## Acceptance
- [ ] The check above passes
- [ ] Project oracle still passes (no regression)
- [ ] rotate() is called exactly once per refresh

## Amendments
<!-- fixers append here; never edit sections above -->
```

**A verification finding is not an amendment.** When a verifier rejects a task, its finding
goes to `notes/T-nnn.verify.md` and never into this file. The task file is the contract,
and the contract did not change just because an attempt failed to meet it. Amendments are
for the contract itself changing; findings are evidence about one attempt at it. Keeping
them apart is what lets a task file stay readable after four attempts.

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

Bug diagnosis, ticks, verification evidence, and publication blocks live in
`notes/T-nnn.progress`. Ownership follows the task sequentially: `ai-bug` writes the first
diagnosis block while the row is `diagnosing`; `ai-execute` appends execution evidence only
after reconciliation changes the row to `pending`.

A confirmed bug diagnosis block names the exact check, expected assertion, boundary cases,
root cause, and its immutable task-branch commit:

```text
## diagnosis — 2026-08-10
diagnosis: reproduced
verification: red_then_green
check_file: src/auth/__tests__/rotation.test.ts
check_command: npm test -- rotation.test.ts
assertion: refresh issues a new token and invalidates the prior one
red: confirmed — fails because rotate is not implemented
boundary: login and logout still pass
root_cause: TokenStore.rotate is missing from the refresh path
diagnosis_base_commit: a3f91c2
diagnosis_commit: b7a03d4
```

`diagnosis_commit` contains only the reproduction check and necessary fixtures. It is not
an `artifact_commit`, so verification and landing must refuse to treat it as completed
work. The reconciled task and later publication include that commit in their full range.

**Always make the edit first, then tick.** This is not stylistic. If the process dies
between the two, the only reachable desync is a *missing* tick — and that self-heals,
because the next executor attempts the step, finds it already applied, and ticks it.
The reverse order permits a tick with no edit, which makes the record lie and causes the
next executor to skip real work. One direction is recoverable; the other is silent
corruption.

The ticks are a convenience, not the truth. While a task is incomplete, its uncommitted
`git diff` is the authoritative record of partial work. Once an executor reports `done`,
the last `base_commit..artifact_commit` publication is authoritative and the worktree must
be clean. That split preserves crash recovery for half-finished work while giving
verification and landing one immutable artifact.

### Verification contracts

Every task declares exactly one `verification` mode. The mode is part of the immutable
contract: executors gather its evidence and verifiers reject a missing or incompatible
mode instead of guessing from the diff.

| Task type | Required mode | Before the edit | After the edit |
|---|---|---|---|
| `feature`, `bug`, `chore` | `red_then_green` | the declared check fails for the behavior being changed | the same check passes |
| `refactor` | `green_baseline` | the declared existing check and project oracle pass | the same unchanged check and oracle still pass |
| `characterization` | `characterization` | the behavior exists but is not pinned by the new check | the new check passes against unchanged production code |

`red_then_green` is Rune's TDD contract for behavior changes. Observe the check failing
against the pre-change state, make the change, then observe the same check passing. Record
both facts in the progress file:

```yaml
verification: red_then_green
red: confirmed 2026-08-04 - rotation.test.ts fails (rotate is not a function)
green: confirmed 2026-08-04 - rotation.test.ts passes
```

A check written after the change and never seen red proves nothing. Nobody downstream can
reconstruct that evidence reliably, so the executor must leave it.

For a bug, `ai-bug` creates the check and first red observation during `diagnosing`, before
the task contract exists. The executor must verify that the reconciled check matches that
diagnosis and re-run it red before its first production edit. It appends the reconfirmed
red and eventual green result; it never overwrites the diagnosis block.

`green_baseline` is the behavior-preservation contract for refactors. Before changing
production code, run the declared existing check and the project oracle and record the
passing baseline. After the refactor, run the same commands and record that they still
pass. Test and fixture files must not appear in the artifact diff:

```yaml
verification: green_baseline
baseline: confirmed 2026-08-04 - session tests pass; oracle matches known baseline
preserved: confirmed 2026-08-04 - same session tests pass; oracle unchanged
```

Do not manufacture a failing test for a behavior-preserving change. A forced red would
either change behavior or weaken a valid check, violating the refactor contract.

`characterization` is a separate, test-only task type used when a later refactor lacks a
safety net. It may change tests and their fixtures, but not production source. Its evidence
is the new check passing against the original production behavior:

```yaml
verification: characterization
characterized: confirmed 2026-08-04 - new session-path check passes against unchanged source
```

The verifier still audits that the check is meaningful and exercises real production
behavior. Passing by construction, asserting `true`, or mocking the subject away is a
failure, not characterization.

Not every check needs to be a unit test. A config rename or dependency bump can use a
scripted or observable assertion that fails before the change and passes after it.
Mandating unit tests everywhere produces ceremonial ones; mandating evidence does not.

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
