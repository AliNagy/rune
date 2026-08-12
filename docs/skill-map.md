# The Rune skill map

A complete reference to all 28 skills: what each one is, what triggers it, who loads it,
what it is allowed to do, what it writes, and what it hands back.

Rune has no `agents/` directory. Every worker is an ordinary subagent told which skill to
follow, so a skill is the only thing Rune defines. That makes "which subagent is spawned"
the same question as "which skill was named in the dispatch".

---

## 1 · How to read this map

Two mechanisms move control between skills, and they are not interchangeable.

| | **Follow** | **Dispatch** |
|---|---|---|
| What happens | the current agent loads the skill into its own context | a fresh subagent is spawned and told which skill to follow |
| Context cost | paid by the caller | quarantined in the worker, which dies afterwards |
| Return | none — it is the same agent | a `≤200 token` envelope; everything else goes to disk |
| Written as | "follow `ai-report`" | a ```` ```rune-dispatch ```` block naming `follow:` |

There is exactly **one parent role** — the main agent — and it is the same writer whether
it is running `hello`, `init`, `vision`, `work`, `pause`, `handoff`, or `continue`. Those
seven are routes through one role, not seven agents. Everything else is either a library
the parent follows in place, or a worker it spawns.

Four skill classes follow from that:

| Class | Count | Runs as | Examples |
|---|---|---|---|
| **Route** | 7 | the parent, user-invocable | `work`, `continue` |
| **Parent library** | 5 | followed in place, never dispatched | `ai-root`, `ai-ledger` |
| **Worker** | 14 | a dispatched subagent | `ai-execute`, `ai-verify` |
| **Planning protocol** | 3 | loaded by a worker, bound by `protocol.md` | `ai-feature`, `ai-refactor` |

Two skills sit in more than one class, and both are called out where they appear:
`ai-bug` is a dispatched diagnosis worker *and* a planning protocol; `ai-drift` is a
library the executor follows in place *and* a worker dispatched in four bounded modes.

---

## 2 · All 28 skills at a glance

### The seven doors — user-invocable

| Skill | Invoked as | One-line job |
|---|---|---|
| `hello` | `/rune:hello` | Router. Reads state, works out which route the request belongs to, hands over. |
| `init` | `/rune:init` | Establishes ground truth: oracle, commands, module map, danger zones, `.rune/` scaffold. |
| `vision` | `/rune:vision` | Interviews the user, records decisions, produces the milestone graph. |
| `work` | `/rune:work` | The execution loop: triage → diagnose → plan → size → dispatch → verify → land. |
| `pause` | `/rune:pause` | Stops the loop cleanly. Drains in-flight work, or abandons it on confirmation. |
| `handoff` | `/rune:handoff` | Moves a full session to a fresh one; files what only the conversation knows. |
| `continue` | `/rune:continue` | Reconciles state left by a dead session, then reports where things stand. |

### Parent libraries — followed in place, never dispatched

| Skill | Followed by | What it governs |
|---|---|---|
| `ai-root` | all 7 routes, before any coordination read | canonical `.rune` root identity, legacy `.agent/` migration |
| `ai-taskfmt` | the parent and every worker that writes under `.rune/` | every file schema, the dispatch/return envelopes, single-writer table |
| `ai-ledger` | the parent only | ledger schema 2, status machine, claiming, crash reconciliation semantics |
| `ai-report` | the parent, before anything the user reads | when to speak, and in what words |
| `ai-serena` | every worker that reads code | symbol-level lookup over file reads — the largest context lever |

### Workers — dispatched as subagents

| Skill | Dispatched by | Outcome field |
|---|---|---|
| `ai-survey` | `init`, `vision` (Mode B), `handoff` (amend) | `survey: mapped \| amended \| unchanged \| conflict \| blocked` |
| `ai-oracle` | `init` | `oracle: passing \| failing \| none` |
| `ai-triage` | `work` | `type: bug \| feature \| refactor \| investigation` |
| `ai-bug` | `work`, `continue` | `diagnosis: reproduced \| not_reproduced \| reclassified \| blocked` |
| `ai-decompose` | `vision`, `work`, `continue` | `plan: graph \| drafted \| reconciled \| blocked` |
| `ai-size` | `work`, `continue` | `sizing: pass \| split \| blocked` |
| `ai-execute` | `work` | `status: done \| drifted \| budget \| blocked \| question` |
| `ai-verify` | `work`, `pause`, `continue` | `verdict: pass \| fail \| unverified` |
| `ai-land` | `work`, `pause`, `continue` | `landing: landed \| refused \| conflict \| reverted \| stuck \| not_landed \| cleaned` |
| `ai-recover` | `continue` | `verdict: salvage \| discard \| partial` |
| `ai-drift` | `work`, `pause`, `continue` | `status: drifted \| recorded \| quiesced \| abandoned \| discarded \| refused \| budget \| question` |
| `ai-investigate` | `work`, `continue` | `investigation: answered \| blocked` |
| `ai-research` | `work`, `continue`; followed in place by `ai-investigate` | `research: answered \| blocked` |
| `ai-verify-finding` | `work`, `continue` | `finding: confirmed \| refuted \| inconclusive` |

### Planning protocols — loaded by a decomposition worker

| Skill | Bound when `protocol.md` says | Governing rule |
|---|---|---|
| `ai-bug` | `type: bug` → `protocol: ai-bug` | no fix without a failing reproduction |
| `ai-feature` | `type: feature` → `protocol: ai-feature` | vertical slices, not horizontal layers |
| `ai-refactor` | `type: refactor` → `protocol: ai-refactor` | if you had to change a test, it was not a refactor |

`investigation` is the fourth triage class and has no decomposition protocol — it exits at
triage into `ai-investigate` and terminates in a written answer. That gap is the point of
the classification.

---

## 3 · The dispatch graph

```
                                   ┌─────────┐
                        user ─────▶│  hello  │  (router; dispatches nothing)
                                   └────┬────┘
             ┌──────────────┬───────────┼────────────┬──────────────┐
             ▼              ▼           ▼            ▼              ▼
         ┌──────┐      ┌────────┐   ┌──────┐    ┌───────┐    ┌──────────┐
         │ init │      │ vision │   │ work │    │ pause │    │ continue │      handoff
         └───┬──┘      └───┬────┘   └───┬──┘    └───┬───┘    └────┬─────┘        │
             │             │            │           │             │              │
   ai-survey │   ai-survey │            │ ai-verify │   ai-recover│    ai-survey │
   ai-oracle │ ai-decompose│            │   ai-land │     ai-drift│     (amend)  │
             │   (graph)   │            │  ai-drift │    ai-verify│    ai-verify │
             │             │            │  (abandon)│      ai-land│      ai-land │
             │             │            │           │       ai-bug│              │
             ▼             ▼            ▼           ▼    ai-size   ▼              ▼
                                                        ai-decompose
                                                        ai-investigate
                                                        ai-research
                                                        ai-verify-finding

  work's own fan-out, in order:

    ai-triage ──▶ (bug)  ai-bug ──▶ reserve T-nnn, reproduce in its worktree
              ├─▶ (investigation) ai-investigate ──▶ [ai-research]  ── exits here
              └─▶ ai-decompose ×2–3 planners ──▶ gate ──▶ ai-decompose ×1 reconciler
                                                            │
                                              ai-size ×N ───┤ (one per new task)
                                                            ▼
                                        ai-execute ×≤3 ──▶ ai-verify ──▶ ai-land
                                             │                │            │
                                             │                └─ fail ─────┤
                                             ├─ drifted ──▶ ai-drift       │
                                             └─ finding ──▶ ai-verify-finding
```

---

## 4 · The seven doors, in detail

### `hello` — the front door

**Triggered by** `/rune:hello`, or any request where the user does not know which command
they want.

**What it does.** Reads seven cheap coordination files, then routes. It is the shortest
allow-list in Rune: run two bounded probes, follow `ai-root` (`mode: resolve`), read the
named `.rune/` files, list at most 20 top-level entries, ask at most one question, route.

**It writes nothing and dispatches nothing.** The only write that can occur is `ai-root`'s
bounded migration, which is internal to that skill.

**State outranks intent** — these conditions answer the question regardless of what was
asked:

| State on disk | Routes to |
|---|---|
| `.rune/PAUSED` exists | `pause` |
| schema-1 or schema-0 ledger | `continue` |
| a decision is `open` | surface it, stop |
| a task is `awaiting` | surface it, stop |
| a task is `diagnosing` / `in_progress`, fresh session | `continue` |
| a `DRF-`/`INV-`/`RES-` slot pending or blocked | `continue` |
| no `.rune/`, repo has code | `init` → `vision` |
| no `.rune/`, empty directory | `vision` |

Otherwise it routes on what was said: "build/fix/clean up/why is X slow" → `work`;
"start a new project" → `vision`; "where were we" → `continue`; "stop" → `pause`;
"context is full" → `handoff`.

**It never classifies bug vs feature itself** — that needs evidence from code, which is
`work`'s triage dispatch.

---

### `init` — establish ground truth

**Triggered by** first use on a repo; `vision` finding no `rune.yml`; or a re-run once
setup measures stale.

**Staleness is measured, never judged.** Any one of these is stale: the recorded commit no
longer resolves, ≥50 commits since, ≥25 files changed since, or the recorded oracle
command is gone from the manifests. A `stale` verdict is a recommendation shown to the
user, not an automatic re-run.

**Dispatches**

| Worker | `work` token | Why it is a dispatch |
|---|---|---|
| `ai-survey` | `survey` | reading source is unbounded, and this is the session everything else starts from |
| `ai-oracle` | `init/commands` | a failing suite is tens of thousands of tokens of output |

**Writes.** `rune.yml`, the canonical empty schema-2 `ledger.md`, the `.rune/` scaffold,
one `.gitignore` line, and the marked `rune` block in `CLAUDE.md` — replacing only what
lies between `<!-- rune:begin -->` and `<!-- rune:end -->`.

**Write order is load-bearing.** The ledger transition is persisted *before* `rune.yml` is
installed, so `rune.yml` can never claim initialization while the authoritative ledger
still reads `oracle: —`. A crash between the two is a recognized recovery state that only
`init` may finish.

**Three rules.** Never invent an oracle. Report confidence per item. Never fix anything —
init observes; repairs are work, and work needs acceptance criteria init has no mandate to
invent.

---

### `vision` — decide what is being built

**Triggered by** a project with no plan: a new idea with no code, or an in-progress
codebase that has drifted and needs its road to v1 mapped.

**Two modes.** *Mode A · new project* walks seven topics in order — what and why, the v1
line, shape, data, stack, constraints, done. *Mode B · in-progress* dispatches `ai-survey`
first, presents what actually exists, interviews against reality, and produces the
discrepancy table (intended vs actual vs gap).

**Dispatches**

| Worker | `work` token | Job |
|---|---|---|
| `ai-survey` | `survey` | Mode B only — what is really in the repo |
| `ai-decompose` | `vision/graph` | writes `milestones.md`; the parent never writes it |

**The rule that matters: suggest, never assume.** Every choice with more than one
defensible answer becomes a `DEC-nnn` record. **No milestone may be generated that depends
on an `open` decision** — that is what converts "make no assumptions" from a personality
instruction into a checkable property.

**The phase marker is the ledger, not the file.** `vision: absent | drafting | complete`
lives in `ledger.md`; `vision.md` supplies the durable answers but has no competing
completion marker. `drafting` is persisted *before* the first question; `complete` is
persisted *before* graph dispatch.

**Files are written incrementally**, as each section settles, because the graph worker is
generated from the files and cannot see the conversation.

---

### `work` — the execution loop

**Triggered by** building a feature, fixing a bug, refactoring, or advancing the current
milestone.

**Preconditions.** `PAUSED` present → stop and report. No `rune.yml` → `init` first. No
milestones and a broad request → `vision`. A specific request with no vision → proceed.

**The complete sequence**

| Step | Dispatch | Fan-out | Notes |
|---|---|---|---|
| 1 · triage | `ai-triage` | one per issue, concurrently | `work: request-N`; batching is forbidden |
| 1b · bug reservation | `ai-bug` | one | reserves `T-nnn` + worktree, reproduces before planning |
| 1c · investigation | `ai-investigate` (+ optional `ai-research`) | one | **exits here** — no task row, no planning |
| 2 · plan drafts | `ai-decompose` | **2–3 planners in parallel** | each writes one immutable `P-nn.md` |
| 2b · the gate | — | — | user sees the candidate plan; no flag skips it |
| 2c · reconcile | `ai-decompose` | one fresh worker | the only writer of `tasks/T-nnn.md` |
| 2d · size | `ai-size` | one per new task, concurrently | `unsized → pending` only on `pass` |
| 3 · execute | `ai-execute` | **≤3 concurrent**, disjoint file surfaces | each in its own worktree |
| 5 · verify | `ai-verify` | one per task, fresh context | never the executor |
| 3b · land | `ai-land` | strictly one at a time | merges the exact verified SHA |
| — · findings | `ai-verify-finding` | one per claim | swept once per batch |
| — · drift | `ai-drift` | per mode | quiesce, record-only |

**The permission list is derived from a reason, not a prohibition.** The parent exists to
tell the user what is happening; anything not needed to report status, route correctly, or
record what happened is a dispatch. Stated that way round because a list of forbidden
actions can always be stepped around by an action nobody thought to forbid.

**The parent does not merge.** A merge cannot be separated from re-running the suite and
rolling back on failure, and only the first of the three is bounded — so the whole
sequence is one `ai-land` dispatch.

**One agent, one issue.** Three bug reports is three triage subagents, never one holding a
list. This governs scope, not concurrency: fan-out is fine, batching is not. Evidence
bleeds between issues, failure stops being isolated, a wrong answer cannot be attributed,
and one agent holding three issues holds three working sets.

**Judgment fans out, mechanics do not.** Decomposition (2–3 planners) and ambiguous triage
earn parallel attempts, because disagreement between independent cuts is the only cheap
signal that the call was hard. Running a command or writing a file from a settled spec gets
one agent.

**The pre-reconciliation gate — always.** Work stops after draft fan-out and before any
final task file exists. The user is shown the candidate cut, the harmless implementation
assumptions, what is deliberately excluded, and is asked for **additions** — not "proceed?",
which only ever gets a yes. Any behaviour or scope choice found there becomes a parent-owned
`DEC-nnn`, and planning restarts as a fresh run so every planner reads the settled input.

**When drift stops the loop** is measured, not felt: stop and ask the user when ≥3
unfinished tasks were retired, when ≥half the milestone was retired, or when the drift
record invalidates the milestone's own acceptance.

**Stops** when the milestone is complete, a decision blocks progress, an executor asked a
question, drift crosses that threshold, an executor is blocked with nothing else
dispatchable, `failures >= 2` on a task, or a lander returns `escalate: yes` or `stuck`.

---

### `pause` — stop cleanly

**Triggered by** "stop", "hold on", or a check of whether work is already paused.

**Default is drain, not abort.** In-flight executors finish, get verified, get merged;
nothing new is dispatched. `abandon` discards in-flight worktrees and needs explicit
confirmation because it destroys real work.

**There is no "stop now."** Rune dispatches a worker and waits for its return — there is no
channel back to a running one, no handle, no acknowledgement. A mode claiming to interrupt
live workers would promise something neither harness can deliver.

**The flag goes down first**, before anything else is read, so a dying turn still leaves the
pause in force. `PAUSED` is its own file rather than a ledger field precisely so it can be
set before the ledger is parsed, and so `work`'s precondition is one file-existence test.

**Dispatches** `ai-verify` and `ai-land` while draining; `ai-drift` in `abandon` mode, one
per recorded worktree, after the user confirms.

**The invariant it guarantees**: when it returns, no task is left `in_progress` or
`landing`. A paused ledger claiming work in progress is a lie about the state of the world,
exactly as after a crash.

**What pause is not**: not a stop button for an interview (just stop answering), not a
rollback (merged stays merged), not a way to abandon a plan.

---

### `handoff` — move to a fresh session

**Triggered by** context above roughly 70%, a session that has drifted across milestones,
handing the project to someone else, or a long break. Written at 70% it is thorough; at 95%
it is rushed and lossy.

**The job is the part that is not on disk** — everything the user said, corrected, ruled
out, or preferred, which currently lives only in a conversation about to end.

**Triage of what is in your head:**

| What you found | Where it goes |
|---|---|
| a convention the user corrected | **dispatch `ai-survey` `mode: amend`** → `map.md` |
| a codebase gotcha | **dispatch `ai-survey` `mode: amend`** → a Serena memory |
| a choice made verbally | the parent writes it → `decisions.md` |
| a constraint on the project | the parent writes it → `vision.md` |
| something wanted later | the parent writes it → `vision.md`, as a want |
| session-transient | the handoff doc |

**One fact per amend dispatch, one dispatch at a time.** Two amend workers editing `map.md`
concurrently would each preserve the file as they found it and silently erase the other.
Never dispatch `mode: full` from here — a full survey re-derives the codebase to file a
sentence, and overwrites the map doing it.

**Test for durability**: *would this still be true and useful three sessions from now?* If
yes, it belongs in a permanent file, not the handoff doc.

**Rules.** Never invent history. Do not summarise the ledger — point at state, do not
duplicate it. One handoff per session; a second means deleting the first.

---

### `continue` — resume and repair

**Triggered by** a fresh session, a crash, or a cleared context.

**Reconcile before reporting.** A ledger left by a dead session contains claims that are no
longer true, and reporting them as status propagates the lie.

**Order of operations**

1. **Read state** — the cheap coordination files only, never source.
2. **Validate or migrate the ledger.** Schema 2 must validate completely. Schema 1 →
   append `replaced_by`, bump the marker. Schema 0 (no marker) → mapped directly to schema
   2 from durable artifacts. An unknown schema stops. A nonempty legacy `## Amendments`
   footer on an unfinished task fails closed into a migration drift record — the **only**
   pre-migration worker dispatch.
3. **Reconcile the vision phase** from the ledger field, never from file shape.
4. **Reconcile report assignments first** — every pending or blocked `DRF-`/`INV-`/`RES-`
   slot, by file order rather than guesswork.
5. **Reconcile `diagnosing` rows before executable ones** — no task file exists yet, so
   they must never reach `ai-execute` or `ai-recover`.
6. **Every `in_progress` row is a lie.** Nobody is holding it.

**The `in_progress` decision table**

| What is on disk | Action |
|---|---|
| valid complete publication, no return | `verifying`, `v++`, dispatch `ai-verify` |
| handoff note present | follow its `worktree` instruction and recorded state |
| no handoff, empty diff, branch ahead | `pending`, `resume_at: publish` |
| no handoff, empty diff, branch not ahead | dispatch `ai-drift` `discard-empty` |
| no handoff, non-empty diff | **dispatch `ai-recover`** |

**It also sweeps**: orphaned worktrees (→ `ai-land` `cleanup`), stale `verifying` rows
(→ `ai-verify`), stale `landing` rows (→ `ai-land`, or `drift-observe` under a freeze),
interrupted decomposition runs, unregistered replan transactions, `unsized` rows
(→ `ai-size`), mitigation-repair assignments (→ `ai-decompose`), staged worker questions,
and unverified findings (→ `ai-verify-finding`).

**It does not start work.** Reconcile, report, hand to `work` or `vision`. Continue answers
*where are we*; the other routes answer *what next*.

**Discard freely** — under Serena a fresh executor re-acquires its working set for about
10k, and partial work of unknown provenance is worth less than the clean base it occupies.
The exception is a bug's `diagnosis_commit`, which is durable evidence.

---

## 5 · Parent libraries

### `ai-root` — coordination-root identity

**Followed by** all seven routes, before any coordination read or write.
`init`, `vision`, `pause`, `handoff` use `mode: initialize`; `hello`, `work`, `continue`
use `mode: resolve`.

**What it settles.** Which `.rune` is canonical, whether a legacy `.agent/` directory can
be safely migrated, and that every manifest directory exists.

| Filesystem state | Result |
|---|---|
| both `.rune/` and `.agent/` exist | **stop** — report both paths, change neither |
| only `.rune/` | resume any marked migration, return it |
| only `.agent/` | validate ownership + worktree safety, then migrate |
| neither, `initialize` | create `.rune/`, ignore `worktrees/`, return |
| neither, `resolve` | return the path without creating it |

**Filenames are not ownership.** Migration requires at least one independent Rune signal —
an initialized `rune.yml`, a recognizable ledger, a `# Vision`/`# Decisions` pair, a
`# Map — <project>` record, a session handoff or PAUSED record, or an artifact matching an
`ai-taskfmt` schema. Unknown top-level entries make ownership ambiguous, and it stops.

**Registered worktrees block the rename.** One bounded probe counts worktrees at or below
the legacy root; any positive count stops migration rather than stranding Git metadata.

**Migration is resumable** through a durable marker (`prepared` → `rewriting`) and an
exclusive lock directory that moves with the rename. A failed run leaves both in place, so
partial state can never be mistaken for an available migration. Locks are never stolen or
aged out.

**It never does a global text replacement** — only exact absolute legacy paths, enumerated
pointer fields, Markdown link targets, ledger pointer columns, and the exact
`.gitignore` line. Free-form prose describing another tool's path stays as it is.

### `ai-taskfmt` — the spine

**Followed by** the parent and every worker that writes under `.rune/`. It is the largest
skill in Rune and the one everything else references.

It owns:

- **the `.rune/` layout** and every file schema — task file, milestone, decision record,
  planner draft, replacement map, handoff note, progress file, vision document
- **the dispatch envelope** — `follow`, `work`, `attempt`, `main_root`, `worktree_path`,
  `pointers`, `reports`
- **the return envelope** — `work`, one-line `summary`, `worktree: none | kept | discarded`,
  and exactly one worker-specific outcome field, at **≤200 tokens** with no exceptions
- **the single-writer table** — every file has exactly one writer, so nothing races
- **the concurrency rule that generates it**: any output two workers could write at once
  must be split into a unique artifact per writer
- **the checkout identity contract** — current working directory is never an identity
- **report staging and promotion** — workers write only their assigned `open/` path; the
  parent atomically promotes with no-replace semantics
- **findings** — a claim is not a fact until a fresh subagent confirms it
- **the published artifact interface** — `base_commit` / `artifact_commit` /
  `verified_commit`
- **bounded state probes** — each skill lists its own permitted commands by name, so
  whether something qualifies is a lookup, not a judgement call
- **why there are no agents** — and what that trade gives up: a tool allowlist was
  enforcement, and prose is not

**ID spaces.** `M-` milestone · `T-` task · `DEC-` decision · `DRF-` drift ·
`INV-` investigation · `RES-` research · `FND-` finding. Local planning ids —
`R-nnn` run, `P-nn` planner slot, `D-nnn` proposed task — never enter the final namespace.
Ids are burned permanently: an unused, blocked, or interrupted reservation is never
recycled, because a late worker may still hold its pointer.

### `ai-ledger` — mutable routing state

**Followed by the parent only.** Workers never touch `ledger.md`; they report, the parent
records.

**Statuses**

```
diagnosing ─reproduced + reconciled─▶ unsized ─pass─▶ pending ─claim; e++─▶ in_progress
                                                                              │
                             done ◀─landed─ landing ◀─pass; l++─ verifying ◀──┘ done; v++
                                                          │           │
                          pending ◀─refused|conflict|reverted         └─fail─▶ pending
                                                                       (failures++)
   in_progress ─drift─▶ drifted   ─budget─▶ pending   ─blocked─▶ blocked   ─question─▶ awaiting

   drifted / drift-blocked ─atomic replan with new ids─▶ retired  (terminal)
```

**The two pre-executable states.** `diagnosing` has no task spec yet; `unsized` has one
nobody has confirmed is finishable. Neither is ever claimed — the executable queue is the
set of `pending` rows, so sizing needs no separate flag anyone could forget to check.

**Why `landing` exists.** Passing verification and surviving the merge are two separate
claims. Without a state between them, a task that had landed and broken the build was
indistinguishable from one never tried.

**Task row fields**: `id`, `milestone`, `title`, `status`, `blocked_by`, `worktree`,
`attempts` (`dN/eN/vN/lN`), `failures`, `latest_finding`, `blocker`, `resume_at`,
`replaced_by`. Counters are incremented **in the same update that claims the phase, before
dispatch** — so a dead worker still visibly consumed an attempt.

**Atomic transitions.** Re-read and validate, build one complete candidate containing every
changed field plus the dispatch row, validate it, replace in one write, and only then
dispatch. Never write `status` first and fill in its required fields later.

**Log every dispatch.** The point is not the audit trail — it is that *absence becomes
visible*. Reconciled task files with no planner and reconciler rows means the parent wrote
them; a `commands` phase with no `ai-oracle` row means the parent ran the suite. Each of
those was a real defect in Rune before the table existed.

**`## Drift` is routing state** — a `quiescing` entry freezes its closure and suppresses
every new dispatch for those ids. **`## Findings` is a record, never routing state** —
findings block nothing, and `refuted` entries are kept permanently on purpose.

**`main: red` halts dispatch** and is cleared by a human, not by the next agent that finds
it inconvenient.

### `ai-report` — talking to the user

**Followed by the parent** before anything the user reads.

**When to speak**: a task finished and was verified, a milestone completed, a batch was
dispatched and again when it lands, the plan turned out wrong, a decision is needed, work
stopped. Between those points, stay quiet — no narrating dispatches or reasoning.

**Every report opens with a TL;DR** of two or three lines: what happened, what is next,
what needs them.

**Translate the internal vocabulary.** "the tests pass", not "the oracle is green". "the
plan was wrong about X", not "DRF-003 invalidated the closure". "T-016's plan was replaced
by T-020 and T-021", not "`retired`, `replaced_by`". Task ids are fine — they are short and
pointable. Names for internal machinery are not.

**Only report a `confirmed` finding.** A claim still waiting on its verifier is not news,
and telling the user makes them act on something nobody has checked. Refuted findings are
not reported at all — that is the system working.

### `ai-serena` — reading code without spending the budget

**Followed by** every worker that reads code: `ai-execute` loads it explicitly, and
`ai-triage`, `ai-survey`, `ai-decompose`, `ai-size`, `ai-investigate`, `ai-verify-finding`,
and `ai-refactor` all invoke it by name.

**The ladder** — climb only as far as the question requires:
`get_symbols_overview` → `find_symbol(include_body=false)` → `find_symbol(include_body=true)`
→ `Read` (last resort, justify it).

**Substitutions**: `find_referencing_symbols` over `grep -r`; `replace_symbol_body` over
read-then-`Edit`; `replace_in_files` with a dry run over N small edits;
`get_diagnostics_for_file` over guessing whether it compiles.

**Agents do not blow budgets reading what they need. They blow them exploring.** Never read
a file "to get oriented" — orientation comes from `map.md`, which exists precisely so
nobody re-derives it.

**Two stores, different jobs.** Serena memories hold stable agent-facing background, written
only by `ai-survey` workers. `.rune/*` holds the plan and its mutable state, human-readable
and git-tracked. If a human needs to read and edit it, it goes in `.rune/`.

**Budget discipline**: at roughly 60%, stop taking new ground, write the handoff, return.
Returning early with a good handoff is a success; running out of context is not.

---

## 6 · The workers, in detail

### `ai-survey` — map the codebase

**Dispatched by** `init` (`work: survey`), `vision` Mode B (`work: survey`), `handoff`
(`work: survey/amend`).

**Why always a subagent**: surveying burns context by design, and that cost is quarantined
in a worker that returns a digest and dies.

**`mode: full`** works breadth before depth: perimeter → entry points → module map →
conventions (sampled, reporting what the code *does*) → danger zones → **completeness**.
That last pass is the most valuable output on an in-progress codebase: stubs, orphans,
half-wired paths, contradictions, abandoned directions — each with a file reference, stated
as observation with evidence, never as judgement.

**`mode: amend`** files exactly one fact and never surveys. Four outcomes, three of which
write nothing:

| Found | Return | Writes |
|---|---|---|
| the fact is not there | `amended` | adds it in the right section |
| already there in substance | `unchanged` | nothing |
| the map contradicts it | `conflict` | nothing — quotes both lines for the user |
| target missing/unreadable | `blocked` | nothing |

A conflict is not the worker's to resolve: it has one sentence from a conversation it did
not see, while the map has a line somebody surveyed the codebase to write.

**Writes** `map.md` (sole writer) and Serena memories. Read-only with respect to source.

### `ai-oracle` — find and run the pass/fail check

**Dispatched by** `init` with `work: init/commands`. Its *rules* are also applied inside
`ai-verify` (step 6) and `ai-land` (step 5) without a separate dispatch.

**Why it exists**: Rune executors grade their own homework, in a context nobody else can
see, and models are optimistic. Without an independent check you get a ledger of green rows
over a codebase that does not run.

**Run it, do not infer it.** A command in `package.json` proves nothing about this checkout,
on this machine, today — inference is what the dispatcher could already do for free.

**Two oracles.** *Project-global* answers "did I break anything else", is established once,
and runs after every task. *Task-local* answers "did my specific thing work" and is produced
by the task. A project with no suite still accrues one, task by task, which is what makes
degraded mode survivable rather than hopeless.

**Three outcomes**: `passing` (normal), `failing` (record the exact **known-red baseline**;
a task regresses only by adding a failure not in it), `none` (say so loudly, enter degraded
mode). Degraded mode is deliberately noisy so the absence is felt on every task.

**Vacuous checks** are the most common silent verification failure: a test asserting
nothing, a subject mocked away, a behaviour test added after the change and never seen red,
a refactor whose baseline was never run. Absence of proof is not proof — that is
`unverified`, not `pass`.

### `ai-triage` — classify one request

**Dispatched by** `work`, one per issue, concurrently, with `work: request-N`.

**Why it exists**: "is this a bug, or was it never implemented?" cannot be answered from the
user's sentence, and on an unfinished codebase it is the most common ambiguity there is.

**Read-only is on you.** Nothing in the harness stops a triage worker editing, and a bug it
has just diagnosed is often a two-line fix. That fix would be unplanned, unverified, outside
every acceptance criterion, and invisible to the gate that exists to show the user what is
about to change.

**Four classes**: bug (behaviour exists and is wrong), feature (behaviour does not exist),
refactor (behaviour is correct, structure is not), investigation (the request is a
question). When genuinely torn: investigation over change, feature over bug — the receiving
protocol will look harder and can reclassify.

### `ai-bug` — reproduce before planning

**Dispatched by** `work` after triage returns `bug`, and re-dispatched by `continue` when a
diagnosis worker died. **Also loaded as a planning protocol** by `ai-decompose` when
`protocol.md` says `type: bug`.

**Governing rule: no fix without a failing reproduction.**

**Identity comes before diagnosis.** The parent reserves `T-nnn`, writes the run's immutable
`protocol.md` with `reserved_task`, and adds a `diagnosing` ledger row *before* dispatch.
The worker then creates or validates that exact worktree before writing anything.

**Sequence**: reproduce on the current tree and capture the output → establish the boundary
(what fails, what adjacent input succeeds) → trace to **root cause, not symptom** → commit
the reproduction check on `task/T-nnn` and record `diagnosis_base_commit` +
`diagnosis_commit`.

**Symptom fixes are identifiable**: null-guards at the crash point, try/catch around the
failing call, defaulting a value that should never have been absent. If the fix tolerates
bad state rather than preventing it, it is a symptom. Choosing containment is sometimes
right, but it must be explicit — `remediation: mitigation` with `root_cause_followup`
linking a separate root-cause task, and it is a **planning decision candidate**, not
something diagnosis authorizes silently.

**The reproduction becomes the regression test.** Red-then-green is free here, because red
was observed in step 1 before any production change existed.

**`diagnosis_commit` is not an artifact.** It has no `artifact_commit`, cannot be verified,
and cannot be landed on its own.

**Four outcomes.** `reproduced` (clean kept worktree + both commit ids) · `not_reproduced`
(provisional row removed, worktree discarded, id burned) · `reclassified` (id burned, fresh
run for the new type) · `blocked` (row and worktree kept, durable blocker recorded).

### `ai-decompose` — milestone graph, drafts, reconciliation, repair

**Dispatched by** `vision` (graph), `work` (drafts and reconcile), `continue` (mitigation
repair). Four distinct jobs, never more than one at a time:

| Job | `work` token | Writes | Dispatched by |
|---|---|---|---|
| **Milestone graph** | `vision/graph` | `milestones.md` (sole writer, no promotion step) | `vision` |
| **Planner draft** | `M-nn/R-nnn/P-nn` | one immutable `P-nn.md` | `work` |
| **Reconcile** | `M-nn/R-nnn` | the final `tasks/T-nnn.md` files (+ `replacements.md` on a replan) | `work` |
| **Mitigation repair** | the fresh run id | one root-cause task + `mitigation-repair.md` | `continue` |

**The protocol binds first.** Every planner and reconciler reads the run's `protocol.md` and
accepts only `bug → ai-bug`, `feature → ai-feature`, `refactor → ai-refactor`. The record —
not the request wording, not the milestone title — decides. It also carries
`decisions: [...]`; each listed record must resolve as `decided`, and conversation memory
never fills the gap.

**Why just-in-time.** A task must name real files and real symbols; for a milestone three
steps out those files do not exist yet. *Plan the whole road during vision. Pave one section
at a time.* M-01 is the exception — its ground state is known.

**Cutting rules.** Behaviour-changing work is **vertical** (`red_then_green`). Refactors are
**horizontal** (`green_baseline`), cut additive → mechanical → subtractive. Characterization
is a separate test-only task. Ceiling: 5 files, one subsystem, one verifiable outcome.
Independence over elegance — two slightly redundant tasks that run in either order beat one
clever task that couples them.

**Context contracts.** The `read` list is easy; the **`forbidden` list is the one that
matters** and the one planners skip. The planner is the only agent positioned to know that
`src/api/**` is irrelevant and would cost 40k tokens — the executor cannot know that and
*will* look, because looking feels responsible. Always give the reason.

**Dependencies**: `blocked_by` is for hard dependencies only. Every false dependency
serialises work that could have run in parallel.

**Planners cut independently.** A planner that hedges toward what it imagines the others
will produce erases exactly the information the fan-out was dispatched to buy.

**Never register tasks in the ledger** — the parent is its sole writer.

### `ai-size` — will one agent actually finish this?

**Dispatched by** `work` after every new task file is registered `unsized`, and by
`continue` when a sizer died. One task per dispatch, read-only, no worktree.

**Why it exists.** The planner already applied the five-file rule. This asks the different
question that rule cannot answer: five files in one module and five files across three
subsystems both pass the rule and are not the same job — and the planner holding the whole
milestone is the least able to tell them apart.

**Deliberately starved of context**: no planner drafts, no cut notes, no conversation. The
reasoning that produced the task is exactly what would talk a reviewer into accepting it.

**What makes a task too big** (never line counts): breadth of change surface · how much must
be understood before anything is written · decisions still open inside the task · sequencing
assumptions · the whole lifecycle including the check and handoff · how likely it is to need
work outside its surface.

**Headroom is the point.** Ask whether it fits *with the first approach failing*. "Yes, if
nothing goes wrong" is a `split`.

**When in doubt, split.** A wrong `split` costs one planning round. A wrong `pass` costs a
burned executor, a partial task, a worktree somebody has to reconcile, and often a change
that crossed its declared surface to get finished — none of which surfaces until the context
is already gone.

**A `split` must be actionable** — name the seam, which part comes first, what the second
depends on. **There is no "pass with concerns."**

### `ai-execute` — do one task

**Dispatched by** `work` only, with `attempt`, `main_root`, `worktree_path`, task pointers,
and one fresh drift-report reservation. **Loads** `ai-taskfmt`, `ai-serena`, and `ai-drift`.

**It is stateless.** Before touching source it reads whatever exists: the handoff note, the
latest publication in the progress file, the uncommitted diff — and critically:

- **`notes/T-nnn.verify.md`, last block first.** The task came back from verification.
  **Answering the last block is the work.** Running the original steps again earns the same
  verdict a second time, which is how a task reaches two failures with nothing learned.
- **`notes/T-nnn.landing.md`.** The task was verified and then broke the main tree on merge.
  The failure it quotes is the work.

Both can exist at once; they fail at different gates, and the later one is the live problem.

**Two checkout identities are bound first**: `main_root` must resolve to itself, and
`worktree_path` must be a registered worktree of the same repository on `task/T-nnn`. Never
search for a similar worktree, accept the harness's directory, or allocate a new path on
retry.

**Source into the worktree; coordination into `<main_root>/.rune/`.** Progress files,
handoffs, drift, decision, and finding records must be visible to the dispatcher, the
verifier, and the next session *before* anything merges.

**Rules**: stay inside the change surface · honour `forbidden` · follow the declared
verification contract and record its evidence · **edit first, then tick** · stop at ~60% of
budget · **never mark yourself done** · never widen scope to be helpful · you cannot talk to
the user, so a real choice becomes a staged decision record and `status: question`.

**Publishing.** `done` means a commit exists. Stage only declared files, commit on the task
branch, prove `base_commit` is an ancestor of `artifact_commit`, the range is non-empty, and
the worktree is clean — then **append** the publication block. Never replace an earlier one:
each attempt needs to say exactly which immutable range it produced.

**Noticing something outside the task** has exactly three readings: it makes the task's plan
false → **drift**; it needs a user choice → **question**; it is simply noticed and the task
works either way → **write a claim to `findings/open/` and carry on**. Writing it down is
the whole of the involvement — do not look into it, widen the surface, or fix it.

### `ai-verify` — the independent check

**Dispatched by** `work` on every `done` claim, by `pause` while draining, and by `continue`
when a publication survived a dead session.

**Three hard rules**: verify in a **clean context**, **never verify your own work**, and
**exactly one task per agent** — a batch of three produces three correlated verdicts,
because after passing two it is judging the third against its own sense of what this batch
looks like rather than against the spec.

**It does not read the executor's summary.** That is the claim under examination, and
reading it primes agreement.

**Eight steps, run in full on every attempt** — including attempt 4. Narrowing to "did they
fix the last finding" is how the second defect in a task ships.

1. bind to the published artifact — HEAD equals `artifact_commit`, worktree clean,
   `base_commit` an ancestor, diff non-empty
2. does the diff match the declared change surface?
3. run the task-local check
4. check the declared evidence mode is complete and internally consistent
5. hunt vacuous checks *using the mode* — including a revert-sensitivity probe in a
   disposable worktree when cheap
6. run the project oracle in the worktree, against the known-red baseline
7. audit the ticks against the diff — a tick with no change means the record is lying
8. walk the acceptance criteria one at a time; no partial credit

**Writes exactly one file**: `notes/T-nnn.verify.md`, one appended block per attempt,
including on `pass`. A `fail` that exists only in a return value dies in the parent's
context, and the next executor would repeat the attempt move for move.

**Three verdicts.** `pass` writes `verified_commit` — the only SHA the lander may merge.
`fail` returns the task to `pending` with `failures++`. `unverified` is **not a soft pass**;
its `reason` routes precisely: `artifact` → republish, `evidence`/`acceptance` → a
record-only drift record and re-decomposition, `oracle` → blocked until the check is
available.

**Bias toward `fail` and `unverified`.** A false `fail` costs one re-run. A false `pass`
propagates into everything built on top of it, and by the time it surfaces nobody knows
which green row was the lie.

### `ai-land` — merge the exact verified commit

**Dispatched by** `work` (one at a time, in finish order), `pause` (draining), and
`continue` (`cleanup` mode, stale `landing` rows, `drift-observe`).

**The only worker allowed to change the main tree.** Every other worker is confined to a
worktree, so this is the one place a mistake is not contained by a worktree boundary — which
is why the sequence is fixed and improvisation inside it is forbidden.

**Why landing is not the last step of verification**: the verifier proved the task against
the tree it was cut from, and a merge into a tree it never saw is a new claim needing new
evidence. Two tasks can each pass verification and still break the project together — A
renames what B calls, neither touches the other's files, git merges both without complaint.

**The fixed sequence**: 1 main tree clean outside `.rune/` → 2 bind to the verified artifact
→ 3 record the rollback point → 4 **merge the SHA, never the branch name** → 5 run the
oracle (skipped only on a genuine fast-forward, which is a git fact you check) → 6 on
failure **roll back first, record second** → 7 **run the oracle again** to prove the
rollback worked → 8 record success, then clean up.

**Never `revert -m 1`.** It leaves the merge in history, so git treats the branch as already
merged and the fixed worktree would land as an empty diff — which breaks the entire re-land
loop.

**Step 7 is the one most worth not skipping.** A rollback assumed to have worked leaves main
red while the return value says green — the exact failure this skill prevents, moved one
step later where nobody is looking.

**Outcomes**: `landed` · `refused` (artifact missing/dirty/empty/changed) · `conflict`
(nothing applied) · `reverted` (merged, oracle failed, rolled back) · `stuck` (**a human is
needed**) · `not_landed` (`drift-observe` only) · `cleaned` (cleanup mode).

**Escalation is ordered rules, first match wins** — attempt 5 · `stuck` · a test failing in
two consecutive blocks · `in_surface: no` twice running. Nothing asks whether the fix "seems
to be converging"; that was a judgement two agents could answer differently from one record.

**`main: green | red` is the parent's dispatch gate.** It must not send new work into a tree
just declared red.

### `ai-recover` — salvage an abandoned task

**Dispatched by** `continue` only, for the one case that needs judgement: **marked in
progress, no handoff, and a worktree with real changes in it.** One torn worktree per
dispatch.

**The diff is the truth, the ticks are a floor.** Because executors edit first and tick
second, the only reachable desync is a step done but not recorded. A ticked step is
definitely done; an unticked one may still be done; a tick with no change means the whole
progress file is unreliable.

**Ordered decision rules, first match wins**

| # | If | Verdict |
|---|---|---|
| 1 | any changed file is outside the declared surface | **discard** |
| 2 | the diff contradicts itself or is unreadable | **discard** |
| 3 | the task's premise looks false | **discard** + `premise_drift: true` |
| 4 | fewer than 20 changed lines | **discard** |
| 5 | a `red_then_green`/`green_baseline` task has edits but no pre-change evidence | **partial** |
| 6 | any declared step is fully or partly applied | **salvage** at the first unfinished step |
| 7 | otherwise | **discard** |

"Was it nearly done" and "is this coherent enough" were the old criteria, and two agents
reading one diff could answer them differently — which is the failure the table removes.

**Writes the handoff the dead executor never wrote.** Does not finish the task, does not
guess at intent, does not repair the ledger.

### `ai-drift` — when the plan is wrong

**Followed in place** by `ai-execute` (detect mode) and **dispatched** in four bounded
modes. On any real codebase this is the common path, not an edge case.

| Mode | Dispatched by | Does |
|---|---|---|
| **detect** | *(inside the executor)* | writes the causal record + handoff, discards its own worktree |
| **record-only** | `work` (verifier `unverified`), `continue` (legacy amendments, recovery `premise_drift`) | writes the assigned staging record from coordination artifacts only — no source, no worktree |
| **quiesce** | `work`, `continue` | discards one frozen task's unpublished worktree and branch under a drift freeze |
| **abandon** | `pause` | discards one worktree after the user accepted the loss |
| **discard-empty** | `continue` | removes a proven-empty dead executor's worktree after re-proving both preconditions |

**The tripwire is mechanical so it cannot be rationalised away.** Adapt freely inside the
declared change surface; stop the moment the fix requires a file the task did not name, or
a read on the `forbidden` list, or the premise turns out false. *"I had to leave my sandbox"
is exactly the signal that the plan needs revisiting.*

**Stopping properly, in order**: write the drift record to the assigned staging path → write
the handoff for a stranger → **discard the worktree**. Source state must not cross the
identity boundary into a replacement task: keeping the diff would make code written for
T-016 appear under T-020 with no truthful publication history.

**`invalidates` is the load-bearing field.** The drifting worker is the only agent who has
seen this — naming every downstream task whose premise it breaks is what lets the parent
freeze them.

**Asking the user** has its own tripwire: ask only when the answer changes behaviour the
user would notice *and* neither the task spec nor an existing convention settles it. An
agent that asks about things it could have determined is worse than one that guesses,
because it spends the user's attention — the scarcest thing in the system. Always give a
recommendation.

### `ai-investigate` — answer, do not build

**Dispatched by** `work` when triage returns `investigation`, and re-dispatched by
`continue` from a durable assignment.

**Why it exists**: a system that only knows how to make plans will turn "why is this slow?"
into an implementation plan.

**Read-only, terminates in an answer.** Running things is allowed — a suite, a profiler, a
read-only query, a build. Changing them is not: no source edits, no test edits, no package
installs, no migrations, no "just try" a fix. Scratch files go outside the working tree.

**Step 1 is making the question answerable**: "why is the dashboard slow" → "which operation
dominates dashboard load time, and by how much". If the answer does not address the written
question, it drifted.

**Outside evidence** goes through exactly one of: the reserved `RES-nnn` (load `ai-research`
and follow it), or a recovery `research_evidence` pointer to an already-promoted RES final.
Never improvise research — a remembered fact presented as a looked-up one is precisely what
both protocols exist to prevent.

**Four mandatory sections**: answer, evidence, **confidence**, **what I did not check**. The
last two are what make an investigation trustworthy — uniform certainty over a sampled
codebase is worse than named blind spots, because the reader cannot tell what to re-check.

**It does not schedule work.** Proposed next steps do not enter the ledger, do not become
task files, and get no `T-` id. That gap is the entire purpose of the protocol.

### `ai-research` — evidence from outside the repo

**Dispatched by** `work` for a pure outside-repo question and by `continue` on recovery;
**followed in place** by `ai-investigate` when it holds a reserved `RES-nnn`.

**Why it exists**, stated precisely: a model asked a factual question will answer from
training data, write it in the confident register of something looked up, and attach a
plausible link it never opened. It is often roughly right — wrong in exactly the details
that made the question worth asking, and indistinguishable from real research.

**It names no tools** and must not be edited to name any. It requires three capabilities —
search, retrieve, record — and if the first two are unavailable, **it stops**.

**The discipline**: fix the question, scope, inclusion criteria, what would change the
answer, and budget *before the first query* · run **at least five distinct formulations**
including the mandatory negative case and primary source · follow the citation graph both
ways · grade every source on a **five-tier scale**, where Tier 5 is a lead and never
evidence · triangulate, and check that "independent" sources do not share an origin, author,
funder, or wording · **spend part of the budget trying to break your own answer** · stop on
saturation or budget, and record which.

**Fabrication rules are absolute**: never cite a source not retrieved this session · never
reconstruct an address from memory · load-bearing claims carry a verbatim quote · mark every
statement sourced or inferred · **training data is a lead generator, never a source** · if
retrieval is unavailable, stop and say so.

**Five mandatory sections**: answer, certainty, **what contradicts this**, **what I could
not establish**, **search log**. An answer with uniform confidence, nothing against itself,
and no way to re-derive it is exactly what a fabricated one looks like — so a real one must
be visibly different.

### `ai-verify-finding` — check a claim somebody else made

**Dispatched by** `work` (one per swept claim) and `continue` (recovery). One claim per
dispatch.

**The one qualification that matters is that you were not there.** The finder wrote the
code, remembers reading it, and has something invested in the claim being right — which is
exactly why it cannot do this itself.

**Procedure**: restate the claim as something that can be false → look at the actual code
narrowly → **try to prove it wrong first** → run a cheap disposable check where one settles
it → decide, and say what would change your mind.

**Three real outcomes, and `refuted` is the most valuable** — it stops a wrong belief from
being planned against for the next three months. All three get promoted and kept.

**Narrow rather than fail.** "Purge deletes sessions that never expire" that only holds when
a default-off flag is on is `confirmed`, restated to what is actually true.

**Never soften a refutation.** "Technically not true, but a reasonable concern" is a
confirmed finding wearing a disguise.

---

## 7 · Trigger matrix — situation to skill

| Situation | Skill | Loaded how |
|---|---|---|
| user does not know which command | `hello` | invoked |
| first use on a repo; setup measured stale | `init` | invoked / auto from `vision` |
| no plan; drifted codebase needs a road to v1 | `vision` | invoked |
| build, fix, refactor, advance the milestone | `work` | invoked |
| stop work; check whether work is stopped | `pause` | invoked |
| context above ~70%; handing the project over | `handoff` | invoked |
| fresh session, crash, cleared context | `continue` | invoked |
| before any coordination read or write | `ai-root` | followed by all 7 routes |
| writing any file under `.rune/` | `ai-taskfmt` | followed |
| reading or updating `ledger.md` | `ai-ledger` | followed by the parent |
| about to write anything the user reads | `ai-report` | followed by the parent |
| before reading or editing any source file | `ai-serena` | followed by workers |
| unfamiliar or in-progress codebase | `ai-survey` | dispatched |
| one fact learned in conversation | `ai-survey` `amend` | dispatched, one at a time |
| how does this codebase prove itself correct | `ai-oracle` | dispatched |
| bug or feature? cannot tell from the sentence | `ai-triage` | dispatched, one per issue |
| something that worked no longer does | `ai-bug` | dispatched, then bound as protocol |
| behaviour does not exist yet | `ai-feature` | bound as protocol |
| structure wrong, behaviour correct | `ai-refactor` | bound as protocol |
| the request is a question, not a change | `ai-investigate` | dispatched — exits the loop |
| the answer is outside this repository | `ai-research` | dispatched or followed |
| milestone → tasks; graph; replan; repair | `ai-decompose` | dispatched |
| a task file exists but nobody sized it | `ai-size` | dispatched per task |
| a task is `pending` and eligible | `ai-execute` | dispatched, ≤3 concurrent |
| an executor claims `done` | `ai-verify` | dispatched, fresh context |
| a verified commit needs to reach main | `ai-land` | dispatched, one at a time |
| reality contradicts the spec; any early stop | `ai-drift` | followed / dispatched |
| torn worktree, no handoff | `ai-recover` | dispatched |
| a claim raised outside the worker's own task | `ai-verify-finding` | dispatched per claim |

---

## 8 · Four walkthroughs

### A bug, end to end

```
work
 └─ ai-triage           work: request-1                  → type: bug
    · parent reserves T-014, writes protocol.md (reserved_task: T-014),
      adds a `diagnosing` row with d1 and the absolute worktree path
 └─ ai-bug              work: T-014, attempt: 1          → diagnosis: reproduced
    · creates .rune/worktrees/T-014 on task/T-014, commits the failing check,
      records diagnosis_base_commit + diagnosis_commit
 └─ ai-decompose ×2–3   work: M-03/R-002/P-01…P-03       → plan: drafted
    · each reads the same protocol + the committed reproduction; one proposed
      task is marked `reservation: primary`
 ── GATE: user sees the candidate cut, assumptions, exclusions ──
 └─ ai-decompose ×1     work: M-03/R-002                 → plan: reconciled
    · maps `primary` onto the already-reserved T-014; allocates ids only for extras
    · parent registers rows; T-014 moves diagnosing → unsized, keeping d1
 └─ ai-size             work: T-014                      → sizing: pass  → pending
 └─ ai-execute          work: T-014, attempt: 1          → status: done
    · reconfirms red before the first production edit, then publishes
      base_commit..artifact_commit
 └─ ai-verify           work: T-014, attempt: 1          → verdict: pass, verified_commit
 └─ ai-land             work: T-014, attempt: 1          → landing: landed, main: green
```

### A feature that hits a question

```
work → ai-triage → type: feature
     → ai-decompose ×3 drafts → GATE → ai-decompose reconcile → ai-size ×N
     → ai-execute T-017 → status: question
        · worker writes decisions/open/T-017-e2.md with no id, keeps the worktree
        · parent assigns DEC-nnn, moves it into decisions.md, deletes the staging file,
          sets the row `awaiting`, and asks the user — the rest of the batch keeps running
        · when decided: row returns to pending; a fresh executor picks up the handoff,
          the worktree diff, and the resolved decision
```

### Drift and replan

```
ai-execute → status: drifted (DRF-003 staged, worktree discarded)
  parent promotes the record, then in ONE ledger update:
    · adds a `quiescing` entry naming the exact frozen closure
      + `closure: N of M unfinished`
    · drift-blocks every inactive row in that set; stops all new dispatch for it
  drain the frozen set  → ai-drift quiesce / ai-land drift-observe as each row requires
  fresh R-nnn, protocol carries `drift: DRF-003` and `retiring: [...]`
  ai-decompose ×2–3 drafts → GATE → reconcile writes new task files + replacements.md
  ONE atomic transaction: new rows added AND old rows → retired with `replaced_by`
  every replacement is sized like a first cut — a replan is not evidence the new cut fits
  stop and ask the user if N ≥ 3, N/M ≥ ½, or the milestone's own acceptance was invalidated
```

### Crash recovery

```
continue
 ├─ ai-root (resolve) ─ finish any interrupted directory migration
 ├─ validate or migrate the ledger (schema 0/1 → 2)
 ├─ reconcile report slots by file order (pending / recorded / unused / blocked)
 ├─ reconcile `diagnosing` rows      → keep, remove, or re-dispatch ai-bug
 ├─ every `in_progress` row:
 │     publication present  → ai-verify
 │     handoff present      → follow it
 │     empty diff, ahead    → pending, resume: publish
 │     empty diff, not ahead→ ai-drift discard-empty
 │     non-empty diff       → ai-recover   ← the only judgement case
 ├─ stale verifying / landing rows   → ai-verify / ai-land
 ├─ orphan worktrees                 → ai-land cleanup
 ├─ unsized rows                     → ai-size
 ├─ staged questions                 → assign DEC ids serially
 └─ unverified claims                → ai-verify-finding
 then report what was REPAIRED, and hand to work or vision
```

---

## 9 · Cross-cutting invariants

**Context is the budget.** The main session never reads source code. Subagents return 200
tokens or less; anything longer goes to disk. Each carries exactly one issue, so three
reported bugs get three agents — that keeps evidence from one out of the reading of another.

**One agent, one issue** bounds what a single agent holds; it says nothing about how many
run at once.

| Fan-out | Cap |
|---|---|
| planner drafts per run | 2–3 in parallel |
| reconcilers per run | exactly 1 |
| concurrent executors | **3**, and only with disjoint change surfaces |
| concurrent landers | **1**, always |
| concurrent survey `amend` workers | **1**, always |
| milestone-graph workers | 1 at a time |
| issues per worker | **1**, without exception |

**Single writer per file.** Writers are roles, not skills — the parent is one writer across
all seven routes. Any output two workers could write concurrently is split into a unique
artifact per writer, which is why `notes/T-nnn.progress`, `decisions/open/T-nnn-eN.md`,
report staging paths, and planner slots are shaped the way they are.

**Changes before records.** Always make the edit, then tick. The only reachable desync is a
missing record, and that self-heals when the next executor finds the step already applied.
The reverse order permits a record with no change, which makes real work get skipped.

**Checkout identity is explicit.** Current working directory is never an identity. Every
worker receives absolute `main_root`; task-bound workers also receive one absolute
`worktree_path`, allocated before the first source write and unchanged through diagnosis,
retries, verification, recovery, and landing.

**Coordination always lands at `<main_root>/.rune/`**, even when written from inside a task
worktree — otherwise it would appear only on merge, which is exactly when nobody needs it.

**Work is checked, not claimed.** A task's test must be seen *failing* before the change,
with the evidence recorded. The executor publishes one immutable range, a different agent
verifies its head, and the lander merges that same head. `done` requires all three.

**Immutability.** Task specs are never edited, appended to, or deleted. A wrong plan is
retired with explicit `replaced_by` lineage and fresh ids. Planner drafts, protocol records,
replacement maps, and promoted reports are immutable once their writer returns.

**Ids are burned, never recycled.** An unused, blocked, or interrupted reservation keeps its
number, because a late worker may still hold its pointer.

**Atomic no-replace everywhere.** Report staging → final promotion, decision allocation,
task registration, and the drift replan transaction are each ordered so any crash leaves a
state a fresh session can route, never one it has to guess at.

**Enforcement is prose, not walls.** There is no tool allowlist behind these rules — a
verifier that *could not* edit is now a verifier told not to. That is why the skills that
depend on it say so at the top, in the places where breaking the rule would be easiest.

---

## 10 · Outcome vocabularies

Every worker return carries `work`, a one-line `summary`, `worktree: none | kept |
discarded` (with `worktree_path` exactly when required), and **exactly one** outcome field.
They are deliberately not collapsed into a generic `ok | failed` — a verifier's outcome
genuinely is not an executor's, and `ai-execute`'s values are the ones the ledger's state
machine consumes by name.

| Skill | Field | Values |
|---|---|---|
| `ai-execute` | `status` | `done` `drifted` `budget` `blocked` `question` |
| `ai-verify` | `verdict` | `pass` `fail` `unverified` |
| `ai-land` | `landing` | `landed` `refused` `conflict` `reverted` `stuck` `not_landed` `cleaned` |
| `ai-recover` | `verdict` | `salvage` `discard` `partial` |
| `ai-triage` | `type` | `bug` `feature` `refactor` `investigation` |
| `ai-bug` | `diagnosis` | `reproduced` `not_reproduced` `reclassified` `blocked` |
| `ai-oracle` | `oracle` | `passing` `failing` `none` |
| `ai-decompose` | `plan` | `graph` `drafted` `reconciled` `blocked` |
| `ai-investigate` | `investigation` | `answered` `blocked` |
| `ai-research` | `research` | `answered` `blocked` |
| `ai-drift` | `status` | `drifted` `recorded` `quiesced` `abandoned` `discarded` `refused` `budget` `question` |
| `ai-survey` | `survey` | `mapped` `amended` `unchanged` `conflict` `blocked` |
| `ai-root` | `migration` | `none` `completed` `resumed` `blocked` |
| `ai-verify-finding` | `finding` | `confirmed` `refuted` `inconclusive` |
| `ai-size` | `sizing` | `pass` `split` `blocked` |

**Check-result vocabulary** is separate and has exactly two enums:
`passing | failing | unavailable` for an individual command, and
`passing | failing | none` for the project oracle. Task-local acceptance stays `pass | fail`
because those words score individual criteria rather than a command verdict. `unavailable`
means a candidate command could not run; `none` means no project oracle exists.

---

## 11 · Where each skill writes

| Path | Sole writer |
|---|---|
| `rune.yml`, `ledger.md`, `PAUSED`, `vision.md`, `decisions.md`, `sessions/<stamp>.md` | the parent |
| the `rune` block in `CLAUDE.md` | the parent, only on `init` |
| `map.md` + Serena memories | an `ai-survey` worker |
| `milestones.md` | the one `ai-decompose` graph worker |
| `drafts/M-nn/R-nnn/protocol.md` | the parent, once, before the run is dispatched |
| `drafts/M-nn/R-nnn/P-nn.md` | the planner assigned that exact slot |
| `drafts/…/replacements.md`, `…/mitigation-repair.md` | that run's single reconciler |
| `tasks/T-nnn.md` | the reconciling `ai-decompose` worker that creates it |
| `notes/T-nnn.progress` | `ai-bug` during diagnosis, then `ai-execute` |
| `notes/T-nnn.md` (handoff) | the worker holding T-nnn |
| `notes/T-nnn.sizing.md` | an `ai-size` worker |
| `notes/T-nnn.verify.md` | an `ai-verify` worker |
| `notes/T-nnn.landing.md` | an `ai-land` worker |
| `notes/init-commands.md` | an `ai-oracle` worker |
| `decisions/open/T-nnn-eN.md`, `findings/open/T-nnn-eN-K.md` | the worker holding that exact attempt |
| `*/open/{DRF,INV,RES,FND}-nnn.md` | the worker assigned that exact id and staging path |
| final `{DRF,INV,RES,FND}-nnn.md` | unchanged worker content, atomically promoted by the parent |

---

## 12 · Notes on this map

Three things surfaced while reading every skill end to end. They are documentation
accuracy issues, not behavioural defects.

- **`README.md` says "Rune is 26 skills".** There are 28 on disk: 7 user-invocable and 21
  `ai-*`. The "seven" and "twenty-one" counts in the same paragraph are correct, so only
  the total is off.
- **`README.md`'s Layout section lists 19 `ai-*` skills**, omitting `ai-size` and
  `ai-verify-finding` — both of which are load-bearing (`ai-size` gates every dispatch;
  `ai-verify-finding` gates every reported finding).
- **`ai-taskfmt`'s dispatch table lists 11 jobs** and does not include `ai-size`,
  `ai-verify-finding`, or `ai-drift`'s four dispatched modes, though all three are
  dispatched by name elsewhere and appear in that skill's own return-envelope table.
