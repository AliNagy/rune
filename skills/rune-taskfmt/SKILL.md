---
name: rune-taskfmt
user-invocable: false
description: Use when writing any file under .rune/ - task files, milestones, decision records, handoff notes, or drift records. Defines the schemas, the encapsulated-task contract, checkable steps, task-specific verification evidence, and single-writer ownership.
---

# Rune file formats

The spine. Every durable fact lives on disk under `.rune/`. No agent may rely on
conversation memory for anything another agent will need — assume every reader is a
stranger with an empty context.

## Layout

```
.rune/
  rune.yml              # init output: oracle, commands, baseline, staleness stamp
  map.md                 # module map, entry points, conventions, danger zones
  vision.md              # the vision document
  decisions.md           # decision records (DEC-nnn)
  milestones.md          # milestone graph (M-nn)
  ledger.md              # versioned mutable task state. single writer: the parent
  drafts/M-nn/R-nnn/protocol.md # immutable type/protocol selection for one run
  drafts/M-nn/R-nnn/P-nn.md # one complete, immutable cut from one planner
  drafts/M-nn/R-nnn/replacements.md # replan-only old -> new task lineage
  drafts/M-nn/R-nnn/mitigation-repair.md # completed legacy mitigation -> root-cause task
  tasks/T-nnn.md         # immutable task specification; never edited or deleted
  notes/T-nnn.md         # handoff notes, long results
  notes/T-nnn.progress   # diagnosis, step ticks, verification evidence, publications
  notes/T-nnn.sizing.md  # does this fit one agent? single writer: the sizer
  notes/T-nnn.verify.md  # verdicts and findings, one block per attempt. single writer: the verifier
  notes/T-nnn.landing.md # merge attempts and what broke. single writer: the lander
  notes/INV-nnn.md       # promoted investigation answer
  notes/RES-nnn.md       # promoted external research answer
  notes/open/INV-nnn.md  # complete investigation awaiting parent promotion
  notes/open/RES-nnn.md  # complete research awaiting parent promotion
  drift/DRF-nnn.md       # misconceptions + which tasks they invalidate
  drift/open/DRF-nnn.md  # complete drift record awaiting parent promotion
  findings/FND-nnn.md    # a checked claim: confirmed, refuted, or inconclusive
  findings/open/T-nnn-eN-K.md # one unverified claim, awaiting a fresh verifier
  findings/open/FND-nnn.md # complete verified finding awaiting parent promotion
  decisions/open/T-nnn-eN.md # one executor attempt's question, awaiting a parent id
  sessions/<stamp>.md    # session handoffs. written by `rune-handoff`
  worktrees/T-nnn/       # disposable task source checkout; never coordination state
  PAUSED                 # present only while work is stopped. written by `rune-pause`
```

Two different things are called a handoff, and they do not overlap. A **task** handoff
(`notes/T-nnn.md`) explains one stopped task to the next executor. A **session** handoff
(`sessions/<stamp>.md`) carries what a conversation knew but never wrote down, to a fresh
session.

`PAUSED` is its own file rather than a ledger field so the flag can be set *before* the
ledger is even read, and so `rune-work`'s precondition is one file-existence test rather than a
ledger parse. Not because pause is a second writer — it is the same parent.

## Where writes land

Source code is only ever modified inside a git worktree — never the main checkout. But
**`.rune/` always lives at `<main_root>/.rune/`**, including files a worker writes
while working in a task worktree. `main_root` is the absolute orchestration-checkout path
from the dispatch envelope below; it is never inferred from a worker's current directory.

| Written by a worker | Lands in |
|---|---|
| source changes while incomplete | its worktree as an uncommitted diff |
| confirmed bug reproduction | a diagnosis commit on its reserved task branch |
| source changes when complete | commits on its task branch |
| planner drafts and reconciled task files | `<main_root>/.rune/` |
| `notes/T-nnn.progress`, handoff notes | `<main_root>/.rune/` |
| staged drift, investigation, research, and decision records | `<main_root>/.rune/` |

Coordination state has to be visible to the dispatcher, the verifier, and the next session
*before* anything merges. Written inside a worktree it would appear only on merge — which
is precisely when nobody needs it any more.

Global ID prefixes never collide: `M-` milestone, `T-` task, `DEC-` decision, `DRF-`
drift, `INV-` investigation, `RES-` research. Planning drafts use a separate local
namespace: `R-nnn` is a decomposition run under one milestone, `P-nn` is a planner slot
assigned by the parent, and `D-nnn` identifies a proposed task only inside that planner's
artifact. None of those local ids may appear as a final task id or ledger task row.

The parent is the sole allocator for the `DRF-`, `INV-`, and `RES-` report spaces. Before
dispatching work that may write one of those reports, it reserves the next unused id and
binds it to one exact absolute staging path and one exact absolute final path in
`## Dispatches`. An id is used if it appears in a final file, an `open/` staging file, or
any `report-slot` row regardless of outcome. Gaps are permanent: an unused, blocked, or
interrupted reservation is never recycled, because a late worker may still hold its
staging pointer.

A bug reservation burns its `T-nnn` as soon as its protocol record, ledger row, or progress
file is written. Allocation treats an id found in **any** coordination artifact as used,
even when diagnosis later fails or reclassifies the request. Reusing an abandoned id would
let a late diagnosis return attach evidence to a different task.

## Single-writer rule

Every file has exactly one writer. Nothing races, nothing needs locking, and no two
files can disagree about the same fact.

**Writers are roles, not skills.** There is one parent — the main agent — and it is the
same writer whether it is running `rune-work`, `rune-init`, `rune-vision`, `rune-continue`, `rune-pause`, or
`rune-handoff`. Those are routes through one role, not six agents. Getting this backwards is
what made `rune-pause` and `rune-handoff` look like second writers when they are the same writer.

| File | Sole writer |
|---|---|
| `ledger.md` | the parent |
| `PAUSED` | the parent |
| `rune.yml` | the parent |
| `vision.md`, `decisions.md` | the parent |
| `milestones.md` | the one worker on `rune-decompose` assigned the milestone-graph job |
| `sessions/<stamp>.md` | the parent |
| `map.md` | a worker on `rune-survey` |
| `drafts/M-nn/R-nnn/protocol.md` | the parent, once before that run is dispatched |
| `drafts/M-nn/R-nnn/P-nn.md` | the planner assigned that exact run and slot |
| `drafts/M-nn/R-nnn/replacements.md` | the single reconciler for that replan run |
| `drafts/M-nn/R-nnn/mitigation-repair.md` | the single reconciler for that mitigation-repair run |
| `tasks/T-nnn.md` | the single reconciling worker on `rune-decompose` that creates it |
| `notes/T-nnn.progress` | the worker holding T-nnn: `rune-bug` during diagnosis, then `rune-execute` |
| `notes/T-nnn.md` | the worker holding T-nnn |
| `notes/T-nnn.sizing.md` | a worker on `rune-size` |
| `notes/T-nnn.verify.md` | a worker on `rune-verify` |
| `notes/T-nnn.landing.md` | a worker on `rune-land` |
| `decisions/open/T-nnn-eN.md` | the worker holding that exact T-nnn executor attempt |
| `findings/open/T-nnn-eN-K.md` | the worker holding that exact T-nnn executor attempt |
| `notes/init-commands.md` | a worker on `rune-oracle` |
| `notes/open/INV-nnn.md`, `notes/open/RES-nnn.md` | the worker assigned that exact id and staging path |
| `drift/open/DRF-nnn.md` | the detector or record-only worker assigned that exact id and staging path |
| `findings/open/FND-nnn.md` | the `rune-verify-finding` worker assigned that exact id and staging path |
| final `notes/INV-nnn.md`, `notes/RES-nnn.md`, `drift/DRF-nnn.md`, `findings/FND-nnn.md` | unchanged worker content, atomically promoted by the parent |
| the `rune` block in `CLAUDE.md` | the parent, only on `rune-init` |

## The concurrency rule that generates this table

**Any output that two workers could write at the same time must be split into a unique
artifact for each writer.**

Up to three executors run concurrently. A shared file they all append to is a race by
construction — and worse, they race on *id allocation*: two executors both reach for
`DEC-012`. Per-task files have no such problem, because the filename already contains the
thing that makes each executor unique. Planner drafts apply the same rule with an assigned
run and planner slot because several planners are working on the same milestone and cannot
use the task id to distinguish themselves yet.

That rule is why `notes/T-nnn.progress`, `decisions/open/T-nnn-eN.md`, report staging files,
and planner drafts are shaped the way they are. Parallel report workers never choose a
number or destination: the parent assigns both before dispatch, and each worker writes
only its own `open/` path. Parallel planners similarly receive one exact
`M-nn/R-nnn/P-nn.md` path. The run's `protocol.md` is safe to share because the parent
writes it once before any planner starts and every worker afterward is read-only with
respect to it. Apply the rule to any new file before adding a row above.

Status lives in `ledger.md` and nowhere else. Never duplicate it into task frontmatter —
two copies of a mutable fact diverge within a day and then neither can be trusted.

The canonical ledger schema is owned by `rune-ledger`. Schema 2 has one task row containing
identity, status, dependencies, stable worktree, phase attempt counters, verifier-failure
count, latest-finding pointer, live blocker, resume token, and the immediate replacement
task ids or explicit no-replacement disposition for a retired contract. The detailed
finding remains in its per-task sole-writer file; the ledger pointer is the authoritative
routing field.

Every parent route validates the ledger before reading it as state and validates a complete
candidate before replacing it. A transition is one replacement containing all changed
fields and its returned dispatch row. No worker starts between partial edits.

The parent writes mutable coordination and user-owned interview state. Workers write the
outputs that require delegated context — maps, the milestone graph, planner drafts,
reconciled task files, progress, and results. The parent's only interaction with worker
report content is the unchanged atomic no-replace `open/` → final promotion defined below.
A parent about to compose or edit anything outside its rows has found a dispatch it
skipped. `milestones.md` has no promotion step: its one graph worker writes the final path
directly, and the parent only validates the returned absolute pointer before reporting it.

## Worktree container lifecycle

`<main_root>/.rune/worktrees/` is an idempotently scaffolded container, not a source of
task identity. Init creates the container when missing and never clears or replaces it.
Task identity remains the ledger's exact absolute `worktree_path`.

Only task-bound workers create child `T-nnn/` worktrees. A successful `rune-land` removes
the clean landed child; `rune-bug` may remove its own unreproduced provisional child; and
`rune-drift` removes an assigned unpublished child while quiescing or abandoning work.
`rune-continue` sends a clean, fully merged orphan to `rune-land`'s cleanup mode. No public route
removes a worktree or branch directly, and the container itself is never removed during
normal operation.

## Checkout identity contract

Current working directory is not an identity. A harness may start a worker in the main
checkout, an anonymous fresh worktree, or a directory inherited from an earlier tool
call. No worker may use that directory to decide where coordination state or task source
lives.

Before its first read or dispatch, the parent resolves the root of the checkout it owns
with the harness workspace root or the bounded probe `git rev-parse --show-toplevel`.
That absolute path is `main_root` and stays constant for the run.

The parent must then follow `rune-root` before reading state. `rune-init`, `rune-vision`, `rune-pause`, and
`rune-handoff` use `mode: initialize`; `using-rune`, `rune-work`, and `rune-continue` use `mode: resolve`.
That skill returns the absolute canonical root, performs or resumes the one supported
legacy-directory migration, and refuses dual roots or registered task worktrees beneath
the legacy root. Any failure is a stop condition whose full diagnostic is reported to the
user. `rune-root` is the only skill allowed to interpret a legacy root; workers receive only
canonical absolute pointers after this preflight.

Every dispatch carries `main_root`. Every `.rune/...` path named anywhere in Rune is a
logical repo-relative name that must be resolved to `<main_root>/.rune/...` before it is
read or written. Dispatch pointers are already-resolved absolute paths. A worker rejects a
relative pointer rather than guessing what it is relative to.

Task-bound work also carries `worktree_path`:

- The parent chooses `<main_root>/.rune/worktrees/T-nnn` before the first task-bound
  worker, records that absolute path in the ledger, and never changes it during the task.
- For a bug, `rune-bug` creates that exact worktree during `diagnosing`, before it writes the
  reproduction check. For every other task, the first executor creates it. Either worker
  validates and reuses an existing path; neither substitutes the directory where the
  harness happened to start it.
- Retries, verifiers, recoverers, and landers receive the same `worktree_path`. They must
  target it directly and must not request or create a fresh worktree.
- Worktree removal has exactly three worker owners. `rune-bug` may discard its own exact
  provisional checkout when diagnosis does not reproduce or reclassifies. `rune-drift` may
  discard an assigned unpublished checkout for detect, quiesce, confirmed abandon, or the
  mechanically empty recovery case. `rune-land` removes a successfully landed checkout or
  a clean orphan whose branch tip it proves is already in main. Every case preserves
  coordination history; no parent route removes a worktree or branch directly. Outside
  those cases the path remains part of the task's durable identity alongside its id and
  branch.

Harness worktree isolation may be used only when it can target this exact existing path.
An isolation mode that silently creates a new worktree must be omitted: a clean anonymous
checkout is not the task checkout.

## The dispatch table

**There are no agent definitions in Rune.** Every worker is an ordinary subagent told
which skill to follow. A dispatch names one job, one skill, stable checkout identities,
and pointers — never file contents.

**Dispatch is not a figure of speech.** Every worker skill in the table below declares
`context: fork` in its frontmatter, so invoking one runs it in a separate context and
returns only its result. Invoking a skill without `context: fork` — `rune-root`,
`rune-report`, `rune-serena`, `rune-taskfmt`, `rune-ledger` — loads it into the caller's
own context. That is the whole difference between the two verbs this system uses:

- **Follow** `rune-x` — load it here, act on it yourself. Reference skills only.
- **Dispatch** `rune-x` — invoke the skill; the fork happens because its frontmatter says
  so. You get a short return, not the work.

A parent that finds itself reading source, creating a worktree, or running a test suite
has followed a worker skill that should have forked. Check its frontmatter before
continuing; do not carry on doing the worker's job by hand.

| Job | The worker follows |
|---|---|
| map an unfamiliar codebase | `rune-survey` |
| classify a request | `rune-triage` |
| milestone graph, and milestone → tasks | `rune-decompose` |
| run build / test / lint / typecheck | `rune-oracle` |
| execute one task | `rune-execute` (which also loads `rune-serena`, `rune-drift`) |
| verify one finished task | `rune-verify` |
| land one verified task in the main tree | `rune-land` |
| salvage an abandoned task | `rune-recover` |
| answer a question about the code | `rune-investigate` |
| answer a question from outside the repo | `rune-research` |
| reproduce a bug | `rune-bug` |

`rune-oracle` and `rune-drift` are the two exceptions: both are dispatched by parents and
followed inline by workers, so neither forks yet. Until that is split, a parent dispatching
either one must confirm it is not doing the work in its own context.

**Never specify a model.** A subagent runs on whatever the session is running on. Model
selection is a separate concern that does not belong in these files.

### The dispatch envelope — what a worker is given

Every dispatch hands over the same shape. `main_root` is required for all workers;
`work` is the dispatcher's immutable routing token and is echoed unchanged in the return;
new dispatches never use a `task` field. A task-bound job simply uses its `T-nnn` as
`work`, while non-task jobs use their assigned report, run, request, or fixed job token.
`worktree_path` is required only for task-bound work and is omitted otherwise. Diagnosis,
execution, verification, and landing also receive `attempt`, copied from the counter the
parent incremented and persisted before dispatch:

```rune-dispatch
follow:        execute
work:          T-014
attempt:       2
main_root:     /workspace/acme
worktree_path: /workspace/acme/.rune/worktrees/T-014
pointers:
  - /workspace/acme/.rune/tasks/T-014.md
reports:
  drift:
    id: DRF-007
    staging: /workspace/acme/.rune/drift/open/DRF-007.md
    final: /workspace/acme/.rune/drift/DRF-007.md
```

Pre-envelope historical assignments may contain `task: <value>`. A recovery reader may
normalize that field to `work` only while consuming an already-durable pre-change dispatch
or note. Canonical dispatch construction, examples, caller prompts, and new log rows reject
`task` even when `work` is absent; compatibility is never permission to emit the old field.

Every caller crosses the matching return seam before outcome routing: require the echoed
`work` to equal this assignment, require a one-line `summary`, and validate
`worktree: none | kept | discarded` plus its conditional path. Only after this common
check may a route consume `status`, `verdict`, `plan`, or another worker-specific outcome.

Every executor attempt receives one fresh drift-report reservation because drift is
discovered inside that worker, after dispatch. Most attempts leave the slot unused; the
parent records that outcome and never recycles the id. Spending numbers is cheaper than
letting concurrent detectors race for one filename.

Investigation and research use the same assignment shape without a worktree:

```rune-dispatch
follow:    investigate
work:      INV-004
main_root: /workspace/acme
reports:
  investigation:
    id: INV-004
    staging: /workspace/acme/.rune/notes/open/INV-004.md
    final: /workspace/acme/.rune/notes/INV-004.md
  research:
    id: RES-007
    staging: /workspace/acme/.rune/notes/open/RES-007.md
    final: /workspace/acme/.rune/notes/RES-007.md
```

The research slot is optional for a pure repository investigation, but when the parent
cannot know whether outside evidence will be needed it reserves both and records the
unused one on return. A direct `rune-research` dispatch receives only its `RES-` assignment.
Before any such dispatch, the parent writes one pending report assignment per id to
`## Dispatches`; that durable row is part of allocation, not an after-the-fact audit entry.

Bug diagnosis uses the same task-bound envelope before the task-file pointer exists:

```rune-dispatch
follow:        bug
work:          T-014
attempt:       1
main_root:     /workspace/acme
worktree_path: /workspace/acme/.rune/worktrees/T-014
pointers:
  protocol: /workspace/acme/.rune/drafts/M-03/R-002/protocol.md
  progress: /workspace/acme/.rune/notes/T-014.progress
```

The parent writes the protocol and complete `diagnosing` ledger row, including `d1`,
before this dispatch. The worker creates or validates the exact supplied worktree before
any source write.

The values sent in a real dispatch are absolute paths — never the literal
`<main_root>` placeholder used in prose. Before doing any work, a task-bound worker
confirms that `worktree_path` belongs to the same Git repository as `main_root`. A
mismatch, a missing verifier/recovery path, or a wrong task branch is a blocked outcome,
not permission to search for another checkout. An executor that blocks uses the durable
blocked-return contract below: it records the worktree disposition, writes a task handoff,
and names the objective condition that permits a retry. A lander alone may accept a
missing path after proving the exact verified commit is already in main, per its
crash-recovery path.

**Pointers, not payloads.** The parent names where things are; the worker reads them
itself. Passing content down means the parent had to hold it first, which is the cost the
whole system exists to avoid — and it keeps every dispatch the same size no matter how big
the job is.

If a worker needs something not reachable from those pointers, that is a missing pointer,
not a reason to paste text into the prompt or resolve a relative path from its current
directory.

### Report staging and promotion

An assigned report worker writes only its exact `staging` path. It first validates the
complete report in a collision-resistant sibling candidate unique to that dispatch, then
uses a same-filesystem atomic **no-replace** install to create the staging path. The
operation itself must fail if staging already exists; a check followed by an overwriting
rename is not safe. The worker also refuses an existing final path. It returns the assigned
id and staging pointer. It never scans for the next id and never writes the final path.

The parent accepts only the id and staging path already recorded in the pending assignment.
It validates the report's required shape and uses a same-filesystem atomic **no-replace**
promotion from staging to final without changing the worker's content. The filesystem
operation—not an earlier existence check—must refuse an occupied final path. Only then
does it replace the pending outcome with `recorded`. If the report was not needed, it
records `unused`; the id remains burned.

If the platform cannot guarantee atomic no-replace creation or promotion on that
filesystem, return blocked and preserve the assignment. Never fall back to an
overwrite-capable rename, copy, or check-then-write sequence.

Crash recovery follows the file order rather than guessing: a complete staging file is
promoted to its assigned final path; an existing final file completes the pending row; two
files, a mismatched path or id, or an artifact with no pending assignment is a stop
condition. Because staging and final are on the same filesystem, the final path is either
absent or a complete worker-authored report—never a partial copy.

For decomposition, the one work id is hierarchical because the work has two phases. A
planner gets one assigned slot such as `M-03/R-002/P-01`; the reconciler gets the enclosing
run `M-03/R-002`. The exact output destination is still a pointer, not prompt payload:

```rune-dispatch
follow:    decompose
work:      M-03/R-002/P-01
main_root: /workspace/acme
pointers:
  milestone: /workspace/acme/.rune/milestones.md#M-03
  protocol:  /workspace/acme/.rune/drafts/M-03/R-002/protocol.md
  decisions: /workspace/acme/.rune/decisions.md
  draft:     /workspace/acme/.rune/drafts/M-03/R-002/P-01.md
```

A bug planner or reconciler additionally receives the reserved task's
`worktree_path` and `diagnosis: /workspace/acme/.rune/notes/T-014.progress`. Its assigned
work id remains the run or planner slot; it validates the task branch against
`reserved_task` in the protocol. It may read that worktree but never write source there.

The parent chooses the next unused `R-nnn` beneath the milestone and assigns distinct
`P-nn` slots before dispatch. Before starting any planner, it writes the run's immutable
`protocol.md` from the final triage result. For a bug it writes that record earlier, before
dispatching diagnosis, with a `reserved_task`; confirmed diagnosis then becomes another
planner pointer. A retry gets a new unused slot; it never reuses a path that a late worker
could still write. The reconciler is dispatched only after the parent has the completed
absolute draft paths, and receives the same protocol pointer plus every draft as a pointer.

The protocol record is deliberately small. `decisions` contains every decided
`DEC-nnn` whose choice constrains this run; an empty list is explicit:

```markdown
---
run: M-03/R-002
type: feature
protocol: feature
decisions: [DEC-004, DEC-007]
---
evidence: SessionMiddleware.handle exists, but profile storage does not.
shape: thin end-to-end slice through the existing session boundary
```

A drift replan adds the causal record and the complete retirement set. These are ids, not
copied contracts; planner dispatches carry absolute pointers to the drift record and every
old task file:

```yaml
drift: DRF-003
retiring: [T-016, T-018, T-019]
```

The parent computes the transitive retirement set before writing this record: the drifted
task, every unfinished task named by the drift record, and every unfinished task whose
dependency chain reaches one of them. A `done` task is excluded and remains history. Once
written, the protocol record is immutable like every other run.

A bug run adds exactly one field before diagnosis:

```yaml
reserved_task: T-014
```

For a drift replan of a diagnosed bug, `reserved_task` is a fresh globally unused id and
must not appear in `retiring`. Diagnosis evidence is task-bound: the old task's reproduction
and branch remain historical inputs, but they do not transfer to the new identity. The
parent creates the new reservation and `rune-bug` reproduces the failure in its new worktree
before replacement planning continues.

That id binds the ledger row, `task/T-014` branch, worktree, progress file, and eventual
primary bug task. Bug planner and reconciler dispatches also receive absolute `diagnosis`
and `worktree_path` pointers. The protocol does not copy the diagnosis result or absolute
paths; the progress file and dispatch envelope remain authoritative.

Only these mappings are valid: `bug -> bug`, `feature -> feature`, and
`refactor -> refactor`. An investigation never reaches decomposition. The record is a
durable routing input, not a planner opinion: planners and reconcilers load the named skill
and may not infer another protocol from titles or source. If the selected type changes,
the parent abandons that run and creates a fresh `R-nnn` plus protocol record; it never
rewrites a record workers may already have read.

### The return envelope — what a worker hands back

Every worker return crosses one canonical seam. These three fields are always present,
whether the job changes source, reads source, or only coordinates files:

```rune-return
work: T-014                   # assigned id, or the job token named by the dispatch
summary: <one line, plain words>
worktree: kept                # none | kept | discarded
worktree_path: /workspace/acme/.rune/worktrees/T-014
status: done                  # exactly one worker-specific outcome field
```

`work` is deliberately not named `task`: `T-014`, `INV-004`, `RES-007`,
`M-03/R-002/P-01`, `request-1`, `survey`, `init/commands`, and `coordination-root` all fit
it without inventing a task. The dispatcher assigns the value and the worker echoes it;
workers never allocate or change the envelope's `work` token. Artifact and final-id
ownership remains governed by each job's own contract. `summary` is exactly one
plain-words line. `worktree`
describes the source checkout after the worker returns: `none` when this job has no task
checkout, `kept` when the supplied checkout still exists, and `discarded` only when the
worker proved it absent or removed it under its own lifecycle interface. `worktree_path`
is required with `kept` or `discarded` and forbidden with `none`.

Then there is **exactly one primary outcome field, named and enumerated by that worker's own
skill**:

| The worker followed | Its outcome field |
|---|---|
| `rune-execute` | `status: done \| drifted \| budget \| blocked \| question` |
| `rune-verify` | `verdict: pass \| fail \| unverified` |
| `rune-land` | `landing: landed \| refused \| conflict \| reverted \| stuck \| not_landed \| cleaned` |
| `rune-recover` | `verdict: salvage \| discard \| partial` |
| `rune-triage` | `type: bug \| feature \| refactor \| investigation` |
| `rune-bug` | `diagnosis: reproduced \| not_reproduced \| reclassified \| blocked` |
| `rune-oracle` | `oracle: passing \| failing \| none` |
| `rune-decompose` | `plan: graph \| drafted \| reconciled \| blocked` |
| `rune-investigate` | `investigation: answered \| blocked` |
| `rune-research` | `research: answered \| blocked` |
| `rune-drift` | `status: drifted \| recorded \| quiesced \| abandoned \| discarded \| refused \| budget \| question` |
| `rune-survey` | `survey: mapped \| amended \| unchanged \| conflict \| blocked` |
| `rune-root` | `migration: none \| completed \| resumed \| blocked` |
| `rune-verify-finding` | `finding: confirmed \| refuted \| inconclusive` |
| `rune-size` | `sizing: pass \| split \| blocked` |

Then whatever else that skill defines.

`rune-execute` has one required conditional interface. `status: blocked` always adds:

```rune-return
work: T-014
summary: package registry is unreachable; resume after service health is restored
status: blocked
worktree: kept
worktree_path: /workspace/acme/.rune/worktrees/T-014
blocker: registry-unreachable
resume_at: step:2
detail: /workspace/acme/.rune/notes/T-014.md
```

`blocker` is a short lowercase slug stored as `external:<slug>`; `detail` points at the
handoff whose `blocker_reason` says what is true now and whose `unblocks_when` says what
observable fact makes another attempt safe. Neither may be "retry later" or another
restatement of `blocked`. The executor also returns the worktree disposition and a
schema-safe resume token rather than forcing the parent to infer them.

**Do not force one outcome vocabulary across all of them.** A verifier's outcome genuinely is not
an executor's outcome, and `rune-execute`'s values are the ones the ledger's state machine
consumes by name. Collapsing them into a generic `ok | failed` would lose the transition
and gain nothing.

The same goes for conditional fields. A worker handed a field it has nothing to say about
will fill it anyway, and an invented value is worse than an absent one. The common
`worktree` field avoids that ambiguity with the explicit `none` value; only the conditional
`worktree_path` is omitted.

What *is* shared: the dispatch-owned work id, one plain-words summary, one enumerated
outcome, the source-checkout disposition, and a hard **≤200 tokens**. There are no per-job
exceptions. Anything longer goes to disk and the summary points at it.

Schema-2 coordination state may contain short returns from before this field was renamed.
Recovery accepts legacy `task: <value>` only when `work` is absent, normalizes it in memory
to `work`, and validates the rest of this envelope. A return containing both fields, or a
legacy return without `summary`, is invalid. New dispatches and durable records always use
`work`; migration never rewrites historical note bytes merely to modernize an example.

An `rune-decompose` planner returning `plan: drafted` also returns exactly one `artifact:`
path, and it must equal its assigned draft pointer. A reconciler returning
`plan: reconciled` returns `artifacts:` with the final `tasks/T-nnn.md` paths plus the
one-line titles and dependency edges the parent needs to register. A drift replan also
returns `replacement_artifact:` pointing to its immutable `replacements.md`; the parent
uses that map rather than inferring lineage from the task summaries. `artifacts: []` is
valid only for a drift replan whose map explicitly assigns every retiring task to `none`
and whose reconciler confirms the milestone acceptance already holds. `plan: blocked`
returns no invented paths and names the missing or contradictory pointer in `summary`.

### Check-result vocabulary

There are two canonical enums and one explicit mapping; producers and consumers do not
invent synonyms:

| Meaning | Canonical enum | Where it is used |
|---|---|---|
| an individual command was executed or unavailable | `passing \| failing \| unavailable` | each stored `rune.yml` `commands.<name>.status` and the transient `rune-oracle` command digest |
| the configured project oracle's verdict or absence | `passing \| failing \| none` | stored `rune.yml` `oracle.status`, `rune-oracle`'s outcome, verifier evidence, and landing evidence |

The intentional stored/transient mapping is identity: transient `passing`, `failing`, and
`unavailable` command verdicts are stored unchanged; the selected oracle's transient
`passing`, `failing`, or `none` is stored unchanged in `oracle.status`. `unavailable`
belongs to a candidate command that could not run. `none` means no project oracle exists;
it never means a configured command was skipped or its result was forgotten. Task-local
acceptance remains `pass | fail` because those words score individual criteria rather than
representing a command or project-oracle verdict.

Post-merge landing uses the same oracle enum in `oracle_result`. `landed` returns
`oracle_result: passing` (or `none` in degraded mode); `reverted` returns
`oracle_result: failing` for the merge check even
though rollback restored `main: green`. A fast-forward may reuse the verifier's identical
tree verdict but still returns that canonical verdict. `refused`, `conflict`,
`not_landed`, and cleanup returns omit `oracle`; a preflight `stuck` also omits it, while
a rollback-red `stuck` returns `oracle_result: failing`.

Existing `rune.yml` files may use the old command-only synonyms `ok | fail`. `rune-init` owns
their deterministic migration: `ok -> passing`, `fail -> failing`, and a recorded
`none found -> unavailable`; the already-canonical oracle values remain unchanged. It
validates the complete candidate and replaces the manifest once. An unknown value stops;
no reader guesses. `rune-continue` detects this legacy shape and routes through `rune-init` rather
than writing another owner's file.

### Findings — a claim is not a fact

Work turns things up that nobody asked about. An executor fixing a session bug notices a
second bug two files away. A verifier spots a test that has been passing for the wrong
reason. A surveyor sees a config key nothing reads.

These are worth keeping, and they are also the most dangerous thing an agent can produce,
because they arrive already phrased as facts. The agent that noticed it was looking at
something else at the time, had it in view for a few seconds, and has every incentive to
believe a plausible guess. Left alone, that guess gets reported to the user, planned
against, and eventually acted on — and nobody ever went back to check it was true.

So: **a finding is a claim until a fresh subagent confirms it.** Until then nobody reports
it as true, plans from it, files an issue for it, or fixes it.

Findings are not the other two things Rune already records:

| | What it is | Blocks the task? |
|---|---|---|
| **drift** | the task's own plan is wrong | yes, that is the point |
| **investigation** | a question the parent deliberately asked | no, it was scheduled |
| **finding** | something noticed in passing, outside this task's contract | no |

If it stops the task you are on, that is drift. Use `rune-drift` and do not open a finding.

**1. The finder writes a claim and moves on.** One file per claim, in this exact shape, at
`<main_root>/.rune/findings/open/T-nnn-eN-K.md` — your task, your attempt, and `K`
counting from 1 for each claim you raise in that attempt. You are the only worker holding
that attempt, so those names cannot collide and need no allocated id.

```markdown
---
status: unverified
raised_by: T-014
source_attempt: e2
---

## Claim
`SessionStore.purge` deletes rows whose expiry is null, so sessions that never expire are
swept on the first run.

## Where I saw it
src/auth/store.ts :: SessionStore/purge — the `WHERE expires_at < now()` branch

## Why I did not check it
Outside T-014's change surface. I read the query while wiring rotate(); I did not run it,
write a test for it, or look at any caller.
```

That last section is required and it is the honest one. Say exactly how much you actually
looked at, because the verifier needs to know whether it is checking a hunch or a
near-certainty. "I did not check it" is a complete answer.

Then keep going. Raising a claim is not permission to investigate it, widen your change
surface, or fix it — those are the failures this artifact exists to prevent.

**2. The parent gets it checked by someone who was not there.** For each claim it
allocates `FND-nnn`, assigns the staging and final paths, and dispatches **a fresh
subagent following `rune-verify-finding`** with the claim pointer. Fresh matters: the finder
cannot review its own guess, because the context that produced the guess is exactly what
would make it look right.

**3. The verifier writes the record and the parent promotes it.** Confirmed, refuted, or
inconclusive — all three are promoted to `findings/FND-nnn.md`, then the consumed claim
file is deleted. A refuted claim is kept on purpose: it stops the same wrong observation
being raised again next month.

Only `confirmed` is actionable. A confirmed finding may become a task, an issue, or
nothing at all — that call belongs to the user, and it is made with the verifier's
evidence in front of them.

### The published task artifact

One small interface crosses execution, verification, and landing:

```yaml
base_commit: a3f91c2
artifact_commit: 4a91c02
verified_commit: 4a91c02   # added only by a passing verifier
```

Only an executor returning `status: done` publishes an artifact. It commits the completed
source change on the task branch, proves `worktree_path` clean, and appends `base_commit`
plus `artifact_commit` to `<main_root>/.rune/notes/T-nnn.progress`. Incomplete outcomes
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

Every executable command in a public route must occupy a fenced block whose info string
is exactly `rune-commands`. The route's `Permitted commands and probes` section is the
allowlist: a `rune-commands` line later in the procedure must match one admitted command
verbatim after stripping its explanatory trailing comment. Shell commands in unlabeled,
`text`, `bash`, `sh`, or other fences are invalid; those fences are examples or data only.
An unknown command—including `rm`, `mv`, or a newly introduced shell executable—is
rejected rather than quietly read as prose. Nothing automates that comparison; the
allowlist exists so it is a lookup instead of a judgement call.

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
what one agent holds, not how many run at once. Stated in full in `rune-work` under *One agent,
one issue*.

The consequence for a worker: if you find a second issue while working, **report it and
stop**. Whether it becomes another dispatch belongs to whoever dispatched you. Taking it on
yourself merges two contexts that the system spent a dispatch to keep apart.

## Vision document

`vision.md` is incremental interview content, not the authoritative phase marker. It has
this exact routing shape so `rune-continue` can determine whether the final answer reached disk:

```markdown
# Vision

mode: new

## What and why
status: settled
decisions: []
<nonempty settled answer>

## V1 line
status: settled
decisions: [DEC-001]
<nonempty settled answer and explicit exclusions>

## Shape
status: settled
decisions: []
<nonempty settled answer>

## Data
status: settled
decisions: [DEC-002]
<nonempty settled answer>

## Stack
status: settled
decisions: [DEC-003]
<nonempty settled answer>

## Constraints
status: settled
decisions: []
<nonempty settled answer>

## Done
status: settled
decisions: []
<nonempty observable v1 acceptance>
```

`mode` is exactly `new | in-progress`. Each of the seven headings occurs exactly once in
that order. A topic is complete only with `status: settled`, a `decisions: [...]` list,
and nonempty answer content. Every listed id must exist in `decisions.md`; every
unanswered behaviour/scope choice in the topic must be represented by one of those ids.
An in-progress vision then adds exactly one `## Survey reality` and one
`## Discrepancies` section, each with `status: settled`, decision ids, and nonempty content;
the latter includes the discrepancy table described by `rune-vision`.

The parent may add prose or subheadings inside a topic, but may not rename, reorder, or
duplicate the routing headings. Partial files simply omit later topics or mark the current
one `status: open`. Only the validated ledger field says whether the interview is
`absent`, `drafting`, or `complete`; this shape is the durable input checklist used for the
one recoverable `drafting -> complete` transition, not a second phase marker.

## Planner draft

A planner draft is the durable, complete candidate cut passed to the reconciler. It is
not a task file and it never reserves a `T-nnn` id.

```markdown
---
run: M-03/R-002
planner: P-01
milestone: M-03
type: feature
protocol: feature
---

# Candidate cut

## D-001 · Rotate refresh tokens inside session middleware
type: feature
remediation: not_applicable
root_cause_followup: none
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
remediation: not_applicable
root_cause_followup: none
verification: red_then_green
blocked_by: [D-001]
...

## Cut notes
assumptions:
  - private helper follows the repository's existing naming convention
decision_candidates: []
exclusions:
  - device management remains in M-06
seams:
  - middleware and endpoint are separated because they share no change-surface files
```

The draft's `type` and `protocol` must exactly match the run's `protocol.md`. Before
writing, its planner reads every id in the protocol's `decisions` list from
`decisions.md`, requires each record to be `decided`, and treats the recorded choice and
rationale as input. A missing, duplicate, or open id blocks the run; conversation context
never fills the gap. Every
`D-nnn` repeats the complete final task contract: title, type, remediation,
root-cause-follow-up link, verification mode, local dependencies, goal, context contract,
change surface, steps, check, and acceptance. `Cut notes` records the assumptions,
exclusions, and disputed seams the user gate and reconciler need. A summary that omits
those sections is not a draft artifact.

An assumption is allowed here only when it is a **harmless implementation assumption**:
an internal, reversible choice that preserves requested behaviour, scope, acceptance,
data retention, error semantics, and public interfaces. Anything that changes one of
those is a **behaviour/scope decision candidate**, not an assumption. Put it under
`decision_candidates`; the parent resolves it before final reconciliation and abandons
this run so a fresh run can carry the settled `DEC-nnn` to every planner.

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

### Replacement map

A drift replan's reconciler also writes its one assigned
`drafts/M-nn/R-nnn/replacements.md` artifact after every new task file exists:

```markdown
# Replacements

run: M-03/R-004
drift: DRF-003

| retired | replaced_by | disposition |
|---|---|---|
| T-016 | T-020,T-021 | split persistence from restore behavior |
| T-018 | T-022 | recut against both session entry points |
| T-019 | none | existing code already satisfies the obsolete task outcome |
```

Every id in the protocol record's `retiring` list appears exactly once. `replaced_by` is
either `none` or one or more of the newly written task ids; every new task appears at least
once, though one new task may replace several old contracts. The disposition is one line
and never substitutes for the causal drift record. This file is immutable when the
reconciler returns and is the parent's durable input for the atomic schema-2 ledger update.
The parent never infers lineage from titles.

## Task file

A task is **encapsulated**: it carries its own goal, change surface, acceptance, and
check. It can be executed, retried, or reviewed with no knowledge of its siblings.

A task specification is also **immutable from creation**. The reconciler writes it once;
no later role edits, appends to, overwrites, or deletes it. A verification finding is
evidence about an attempt and belongs in
`notes/T-nnn.verify.md`. If drift changes the contract itself, the old task is retired in
the ledger and a fresh reconciler writes replacement tasks with globally unused ids. The
old file remains the exact historical contract that produced its attempts and findings.

Schema 0 and 1 projects may already contain task files with the removed
`## Amendments` footer. Migration never treats that footer as valid schema-2 input and
never tries to merge its prose into the sections above. A file whose footer contains
anything beyond whitespace or the old placeholder comment is a **legacy amended task**.
`rune-continue` preserves its bytes as historical evidence; if its row is unfinished, it
creates a migration drift record and sends the complete unfinished dependency closure
through retirement and fresh re-decomposition. A `done` legacy task stays done and its
whole file is frozen as the historical contract that was actually executed. No role may
append another amendment before, during, or after migration.

Older immutable tasks also predate `remediation`. Normalize them only in the reader:

- a non-bug task without the field becomes `remediation: not_applicable` and
  `root_cause_followup: none`;
- a bug without `kind: mitigation` becomes `remediation: root_cause` and
  `root_cause_followup: none`, matching the old bug protocol's root-cause requirement;
- a bug with legacy `kind: mitigation` becomes `remediation: mitigation` and must not be
  relabeled as root-cause. If it has no valid durable root-cause follow-up, recovery
  records planning drift and re-decomposes the unfinished closure into immutable
  replacement tasks. A completed legacy mitigation instead uses the repair overlay below;
  its historical task bytes remain unchanged.

Never edit the old task bytes to add these fields. A legacy mitigation is usable only
after the follow-up relationship is durable in the replacement task set or recovery
overlay; ambiguity over whether `kind` meant mitigation is a stop, not a default to
`root_cause`.

Encapsulate the *contract*, reference the *context*. Goal, surface, acceptance and check
belong in the task. Conventions and module layout are pointed at, never copied — copies
drift apart from `map.md` and from each other.

```markdown
---
id: T-014
title: Rotate refresh tokens inside session middleware
milestone: M-03
type: feature            # feature | bug | refactor | characterization | chore
remediation: not_applicable # root_cause | mitigation | not_applicable
root_cause_followup: none # T-nnn for mitigation; none otherwise
verification: red_then_green # red_then_green | green_baseline | characterization
blocked_by: [T-011]
---

## Goal
One paragraph, prose. What the world looks like when this is done.

## Context contract
read:
  - serena: find_symbol SessionMiddleware/handle   -> src/auth/session.ts
  - serena: find_symbol TokenStore                 -> src/auth/store.ts
  - file:   .rune/map.md (conventions section)
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
```

`remediation` is the canonical distinction between a root-cause fix and a temporary
mitigation. A `bug` task uses exactly `root_cause | mitigation`; every other task uses
`not_applicable`. `root_cause_followup` is `none` except on a mitigation, where it is one
different final `T-nnn` in the same milestone whose task has `type: bug`,
`remediation: root_cause`, and `root_cause_followup: none`. The relationship does not
imply execution order; `blocked_by` remains the only dependency field. The reconciler
allocates both files before registering either row, maps the mitigation draft's local
`D-nnn` link to the final id, and refuses an orphan, self-link, cycle, missing target, or
link to another mitigation. A mitigation may satisfy its own acceptance and land, but it
never closes, retires, or substitutes for the linked root-cause task.

### Completed legacy mitigation repair overlay

A completed immutable legacy task cannot gain `root_cause_followup` without destroying
the historical contract. Its one authoritative overlay is an `## Dispatches` row plus the
immutable artifact written by the assigned `rune-decompose` reconciler. Before dispatch,
the parent serially allocates a fresh run plus a globally unused root-cause `T-nnn`, writes
the run's immutable protocol, and persists the pending row in a valid schema-2 ledger.
The protocol is the durable allocation record even if the parent dies before the ledger
replacement:

```rune-mitigation-repair-protocol
run: M-03/R-005
repair: completed_legacy_mitigation
legacy_mitigation: T-031
reserved_root_cause: T-033
legacy_task: /workspace/acme/.rune/tasks/T-031.md
root_cause_task: /workspace/acme/.rune/tasks/T-033.md
repair_artifact: /workspace/acme/.rune/drafts/M-03/R-005/mitigation-repair.md
```

All seven fields are required and no others are accepted. `repair` has the single enum
`completed_legacy_mitigation`; both task ids must match their exact absolute task paths,
and `legacy_task`, `root_cause_task`, and `repair_artifact` must share the same absolute
`main_root` while the artifact path embeds the exact run. A relative or mismatched path
invalidates the protocol before any ledger row is written.

These are the exact canonical row shapes:

```rune-mitigation-repair-rows
| mitigation-repair | decompose | M-03/R-005 | pending T-031 -> T-033: protocol /workspace/acme/.rune/drafts/M-03/R-005/protocol.md; task /workspace/acme/.rune/tasks/T-033.md; repair /workspace/acme/.rune/drafts/M-03/R-005/mitigation-repair.md |
| mitigation-repair | decompose | M-03/R-005 | linked T-031 -> T-033: protocol /workspace/acme/.rune/drafts/M-03/R-005/protocol.md; task /workspace/acme/.rune/tasks/T-033.md; repair /workspace/acme/.rune/drafts/M-03/R-005/mitigation-repair.md |
| mitigation-repair | decompose | M-03/R-005 | blocked T-031 -> T-033: protocol /workspace/acme/.rune/drafts/M-03/R-005/protocol.md; task /workspace/acme/.rune/tasks/T-033.md; repair /workspace/acme/.rune/drafts/M-03/R-005/mitigation-repair.md; blocker evidence-insufficient; detail diagnosis-does-not-identify-causal-boundary; unblocks_when decision:DEC-004:decided |
```

The parent is the allocator and ledger writer for repair reservations; it never composes
the task. The reconciler remains sole writer of the reserved task path and repair artifact.
Allocation scans task files, every protocol's `reserved_root_cause`, and every pending,
blocked, or linked repair row. A reservation burns both run and task id permanently.
When several repairs are found together, the one parent assigns distinct ids and paths in
numeric legacy-task order, writes each no-replace protocol, then persists all pending rows
in one validated ledger replacement before any worker starts. Duplicate root ids, runs,
task paths, or repair paths are invalid; simultaneous reconcilers therefore cannot collide.

The durable order is strict: publish the no-replace protocol, persist its pending ledger
row, then dispatch the worker. A row without its exact protocol and a dispatch without its
pending row are invalid. A crash after protocol publication creates an attributable orphan;
after schema 2 is durable, recovery validates that protocol and writes its uniquely derived
pending row before any dispatch. It never invents or reallocates a field.

The row's `work` is the fresh run id. Its outcome binds both task identities and every
absolute path before dispatch. The reconciler receives the protocol, old task, its
evidence, and milestone. It uses `reserved_root_cause` rather than allocating an id, and
alone writes both the new immutable root-cause task and this complete artifact:

```rune-mitigation-repair
legacy_mitigation: T-031
root_cause_followup: T-033
milestone: M-03
run: M-03/R-005
legacy_task: /workspace/acme/.rune/tasks/T-031.md
root_cause_task: /workspace/acme/.rune/tasks/T-033.md
```

The parent accepts the return only when the assignment, artifact, and both task files
agree; the old task has `type: bug`, legacy `kind: mitigation`, and a `done` ledger row;
and the new task is different, in the same milestone, and declares `type: bug`,
`remediation: root_cause`, and `root_cause_followup: none`. In one validated ledger
replacement it registers the new task and changes only that pending outcome to the linked
shape above.

That linked row and immutable artifact are the durable relationship. Task readers
normalize the old task to `remediation: mitigation` and obtain its follow-up from exactly
one matching linked repair row; they never rewrite or pretend the field existed in the
old bytes. A missing, duplicate, pending, mismatched, cross-milestone, self, or mitigation
target is unresolved repair work, not a valid task contract. Report, ledger, verification,
and milestone-completion readers all perform this same join.

Publication order is task file first, repair artifact second, both with atomic no-replace
installation. Recovery handles every state without guessing:

- neither exists: after proving the prior worker stopped, redispatch the same pending
  assignment;
- only the reserved task exists: validate it, keep it immutable, and redispatch the same
  assignment only to validate that file and write the missing repair artifact;
- only the repair artifact exists: this violates publication order, so change the row to
  blocked with `blocker artifact-without-task` and an observable restore condition;
- both exist and agree: perform the one registration-plus-linked ledger replacement;
- either exists but conflicts with the reservation or the other output: preserve all
  bytes and record a blocked mismatch; never overwrite or allocate around it;
- an already-linked row: validate the registered task, both files, and row, then do nothing.

`plan: blocked` writes neither task nor repair artifact. The parent persists the worker's
lowercase `blocker`, single-token-or-pointer `detail`, and objective `unblocks_when` in the
blocked row shape above. Blocked is durable and is never redispatched merely because a
session restarted. Replaying the identical blocker, detail, and condition is a no-op;
different values for an already-blocked reservation are a conflict and leave the row
unchanged. Only after the named durable condition is observed does the parent
atomically replace blocked with the same pending reservation, then redispatch; ids and
paths never change. Reports show the blocked repair and its condition, and milestone
completion remains false.

Predecessor-ledger migration may put fully reserved pending assignments in its complete
schema-2 candidate, but it must first write their protocols and then persist that candidate
before dispatching `rune-decompose`. Thus the only pre-migration worker remains the amendment
drift recorder. An orphan valid repair protocol is not dispatched pre-migration: recovery
finishes its uniquely matching pending row after schema 2 is durable. A protocol/row
collision or ambiguity stops.

When a verifier rejects a task, its finding goes to `notes/T-nnn.verify.md` and never into
the task file. The contract did not change merely because an attempt failed to meet it.
When the contract really is wrong, retiring it and allocating replacement ids keeps the
old evidence attributable to the contract that was actually executed.

### Sizing

One task = **at most 5 files, one subsystem, one verifiable outcome.** If it needs more,
it is two tasks. Oversized tasks are the root cause of blown context budgets and of
drift bounces — a task that keeps drifting was cut too large, and that is a signal about
the planner, not the executor.

That rule is necessary and not sufficient, so it is checked twice. The planner applies it
while cutting. Then **every newly written task is sized again by a fresh worker on
`rune-size`, before it can be executed** — because five files can be a small job or an
enormous one, and the planner holding the whole milestone is the least able to tell which.
A task is registered `unsized` and only a `pass` moves it to `pending`; see `rune-ledger`.

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
`notes/T-nnn.progress`. Ownership follows the task sequentially: `rune-bug` writes the first
diagnosis block while the row is `diagnosing`; `rune-execute` appends execution evidence only
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

For a bug, `rune-bug` creates the check and first red observation during `diagnosing`, before
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
source: vision            # vision | planning | T-nnn/eN
options:
  - Zustand — light, minimal ceremony
  - Redux Toolkit — heavy, more structure, familiar to the team
recommendation: Zustand
decided: —
rationale: —
```

`source` is optional for parent-authored vision and planning records: `rune-vision` identifies
an interview decision and `planning` a behaviour/scope candidate promoted before final
reconciliation. It is mandatory as `T-nnn/eN` for every newly promoted worker question
from that exact per-attempt staging file. Only the task-attempt form is a uniqueness key:
at most one durable decision may have a given `T-nnn/eN`, and its task and attempt must
match the staged record, return envelope, and ledger. A staged worker record contains
`raised_by` and `source_attempt` instead of `source`; the parent adds the latter during
allocation. A legacy or parent-authored decision without `source` remains valid and may
be named explicitly in a run protocol, but it is never a task-attempt deduplication key;
the parent does not invent a backfill.

**Gate: no milestone may be generated that depends on an `open` decision.** This is what
converts "make suggestions, never assumptions" from a personality instruction into a
checkable property. Recommendations are encouraged; silently adopting one is not.

Workers use the same format to ask questions mid-task — but they write it to
**`.rune/decisions/open/T-nnn-eN.md`**, not to `decisions.md`, and they **do not assign an
id**. The filename's `T-nnn` and `eN` must equal their `raised_by: T-nnn` and
`source_attempt: eN` fields. They stop with
`status: question`, and keep the worktree. Their short return contains exactly
`decision: pending-id` and the absolute `decision_artifact:` staging path; a worker never
predicts the parent's future id.

The worker builds a complete sibling candidate and installs that exact per-attempt path
with atomic no-replace semantics. An existing path is recovery evidence, never a file to
overwrite. A late earlier attempt has a different filename and therefore cannot replace a
later attempt's question.

The parent is the sole allocator. It validates every staged record against the task and
current executor attempt, sorts simultaneously observed questions by numeric task id and
then attempt, and allocates the next unused `DEC-nnn` in that deterministic order. It
adds `source: T-nnn/eN` to the assigned record in a complete `decisions.md` replacement,
then replaces the ledger row with `awaiting` and `decision:DEC-nnn`, and only then deletes
the staging file.

That order is the recovery interface. A crash before the decisions replacement leaves
only staging. A crash after it reuses the existing record with the same unique `source`
instead of allocating another id. A crash after the ledger replacement sees a matching
`awaiting` row and deletes the consumed staging file. A duplicate `source`, mismatched
task/attempt/path, or conflicting existing row is a stop condition; never guess. The
single parent processes the sorted batch serially, so simultaneous worker returns cannot
race either the id scan or the shared decisions replacement.

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
resume_at: fresh | step:N | evidence:<mode> | publish
what_exists: TokenStore.rotate implemented and unit-tested; not yet wired into handle()
what_surprised_me: handle() is called from two places, not one — see src/ws/upgrade.ts
worktree: kept | discarded
next: wire both call sites, or split the second into its own task
blocker: service-down # required only for blocked; must match the short return
blocker_reason: required only for blocked — state the external condition, not "cannot proceed"
unblocks_when: required only for blocked — one observable condition the parent can re-check
```

No pronouns pointing at a conversation. No "as discussed". No "the approach we agreed".
The reader has none of that.

`resume_at` is copied into the ledger; keep it to the schema-2 tokens. For a blocked
handoff, the parent stores `external:<slug>` and points `latest_finding` here, while these
two conditional lines preserve the full reason and unblock condition. It must not
redispatch merely because time passed; it first observes `unblocks_when`.
