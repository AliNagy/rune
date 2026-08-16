---
name: rune-work
user-invocable: false
description: Use when building a feature, fixing a bug, refactoring, or advancing the current milestone. Triages the request against real code, decomposes it into tasks, dispatches isolated executors, and verifies each one independently.
---

# rune-work

The execution loop. Triage → diagnose bugs → plan → dispatch → verify → reconcile.

**How you write to the user, before anything else:** lists not paragraphs, no preamble, no
narrating your own reasoning, plain words instead of Rune's vocabulary. `rune-report` has
the detail and you load it before writing anything the user reads — but these four hold
from this line onward, not from the moment you get around to loading it. This file is
written densely because it is a specification; the user gets none of that register.

## What you may do

**You exist to tell the user what is happening.** Everything you are allowed to do follows
from that, and this list is exhaustive:

- **Run** only the exact bounded state probes named below.
- **Follow** `rune-root`; its narrowly scoped coordination migration is the sole write
  exception outside this route's ledger and protocol records.
- **Read** `<main_root>/.rune/` coordination files — enough to report status accurately.
- **Write** `<main_root>/.rune/ledger.md`, and **append** the drain result to
  `<main_root>/.rune/PAUSED` if the flag
  appears mid-run. You never create or delete that file — `rune-pause` and `rune-continue` do.
- **Write** the parent-assigned result of a worker question to
  `<main_root>/.rune/decisions.md`, then **delete** only that worker's consumed
  `<main_root>/.rune/decisions/open/T-nnn-eN.md` staging file.
- **Write** parent-authored `source: planning` behaviour/scope decision records to
  `<main_root>/.rune/decisions.md` only at the pre-reconciliation gate. This is the same
  sole parent writer; planners never allocate ids or edit the file.
- **Promote** a complete worker-authored `DRF-`, `INV-`, `RES-`, or `FND-` staging file to
  the exact final path already reserved in `ledger.md`, using a same-filesystem atomic
  no-replace operation. You never compose or edit report content.
- **Delete** only a `<main_root>/.rune/findings/open/T-nnn-eN-K.md` claim whose verified
  `FND-nnn` record has already been promoted. You never edit a claim or write a verdict.
- **Create** one immutable
  `<main_root>/.rune/drafts/<milestone>/R-nnn/protocol.md` before dispatching that
  decomposition run. For a bug, create it before diagnosis and include the reserved task
  id. You never edit it after any worker can see it.
- **Talk to the user** — reports, the gate, questions.
- **Dispatch subagents**, naming the skill each one must follow. The dispatch table in
  `rune-taskfmt` says which skill does which job.

## Permitted commands and probes

This is the complete command interface for the parent route.

### State probes

```rune-commands
git rev-parse --show-toplevel
```

The probe returns exactly one line. `rune-root` may run only its own separately bounded
migration probe while this route follows it. Every source, diff, verification, oracle,
merge, and cleanup operation is a named worker dispatch.

### Mutating lifecycle commands

`none` — `rune-execute` creates task worktrees, `rune-land` merges and cleans landed work, and
`rune-drift` discards unpublished work. The parent never runs their Git commands.

## Coordination-root preflight

Before any coordination read or dispatch, resolve `main_root` once with
`git rev-parse --show-toplevel`, then follow `rune-root` with `work: coordination-root`,
that absolute root, and `mode: resolve`. Stop and report any failure it returns. Resolve every `.rune/...` read
against the returned root and carry the same `main_root` in every dispatch.

Before consuming any followed or dispatched result, validate `rune-taskfmt`'s common
return envelope: `work` must equal the assigned token, `summary` must be one line, and
`worktree`/`worktree_path` must agree. Only then read the worker-specific outcome.

**Anything not on that list is a dispatch.** Writing any other file, running any command,
reading any source file — each one is a subagent's job, without exception and without a
case where it is quicker to just do it yourself.

**You do not merge.** That was once on this list, as the single command you were allowed to
run. It came off because a merge cannot be separated from what has to follow it: the suite
is re-run against the merged tree, and if it fails the merge has to come back out. Only the
first of those three is bounded, so the sequence is one dispatch — `rune-land` — and not a
command of yours with two dispatches around it.

Stated this way round on purpose. A list of forbidden actions can always be stepped
around by an action nobody thought to forbid — which is exactly how task files ended up
being written here. A list derived from a reason covers the cases nobody anticipated: if
a thing is not needed to report status, route correctly, or record what happened, it does
not belong in the context you are protecting.

Two consequences are load-bearing:

- Every subagent returns **≤200 tokens**. Anything longer goes to disk; you read it only
  if you must act on it.
- Validate every return through `rune-taskfmt`'s common envelope before its outcome table:
  assigned `work`, one-line `summary`, one primary outcome, and
  `worktree: none | kept | discarded` with a path exactly when required. Apply the
  deterministic legacy `task` normalization only to historical returns.
- You **re-read `ledger.md` from disk** between dispatches. Never carry ledger state in
  context — a stale in-memory copy is how you dispatch a task someone already finished.
- Validate schema 2 on every read and every candidate replacement, per `rune-ledger`. An
  invalid or unknown ledger is a stop condition, not permission to infer missing state.

If either slips, the parent hits its ceiling around task 25 no matter how clean the
workers are.

## One agent, one issue

**A subagent handles exactly one issue. Never two, never a batch.**

Three bug reports in one message is three triage subagents — not one triage subagent
handed a list of three. The same holds at every dispatch point in the system: one
reproduction per bug, one task per executor, one verification per task, one question per
researcher, one recovery per abandoned task.

This governs **scope, not concurrency.** Dispatching three agents at once is fine and
usually right. What is forbidden is a single agent carrying more than one issue's context.

Why it holds without exception:

- **Evidence bleeds between issues.** An agent that has just established issue A is an
  unimplemented stub is primed to read issue B the same way. The second verdict is
  contaminated by the first, and nothing in the returned text shows that it was.
- **Failure stops being isolated.** An agent that exhausts its budget on the third issue
  loses the work it did on the first two. Separate agents fail separately and retry cheaply.
- **A wrong answer cannot be attributed.** When a batched return is wrong, the evidence for
  every issue sits in one context, and there is no way to tell which issue's reading drove
  the error.
- **It spends the budget it was meant to save.** One agent holding three issues holds three
  working sets at once — precisely the accumulation the ≤200 token rule exists to prevent.

If a subagent finds a second issue while working, it **reports it and stops**. It does not
take it on. Whether that becomes another dispatch is the dispatcher's decision, not the
worker's.

## Preconditions

- **`<main_root>/.rune/PAUSED` exists → stop.** Report that work is paused, when and why, and that
  `rune-pause` lifts it. Do not dispatch. Do not quietly resume because the user asked for
  something — they may have forgotten the pause is set, and silently overriding a
  deliberate stop makes it worthless.
- No `<main_root>/.rune/rune.yml` → run `rune-init` first.
- No `milestones.md` and the request is broad ("continue the project") → route to
  `rune-vision`. Do not invent a plan; that is vision's job and it requires the user.
- A specific request ("fix the login bug") with no vision → proceed. Not everything needs
  a milestone graph.

## 1. Triage

Classification often cannot be done from the user's sentence. "Is this a bug or is it
simply not implemented?" is undecidable without evidence — and it is the most common
ambiguity on an unfinished codebase.

Since you cannot read code, **dispatch a subagent that follows `rune-triage`** — **one per
issue**, per *One agent, one issue* above. If the user reported three things, that is
three triage dispatches, run concurrently. Never hand one triage agent a
list, even when the issues sound related: "sounds related" is a hypothesis, and batching
them destroys the independence needed to test it.

Assign each request a batch-local `work: request-N` token and require the return to echo
it; the token routes concurrent triage results but never enters the global task-id space.

Each returns:

```rune-return
work: request-1
summary: existing behavior is wrong in SessionMiddleware.handle
type: bug | feature | refactor | investigation
worktree: none
evidence: SessionMiddleware.handle exists and is called; rotate() returns null (stub)
shape: single fix in src/auth — reproduction likely straightforward
milestone: M-03 (fits scope) | none | conflicts with M-03 scope
```

Then load the matching protocol:

| type | skill | first move |
|---|---|---|
| bug | `rune-bug` | reserve its task and reproduce in that worktree before planning |
| feature | `rune-feature` | scope boundary, then decisions |
| refactor | `rune-refactor` | confirm a characterization net exists |
| investigation | `rune-investigate` | read-only, terminates in an answer |

**Investigation exits here.** Before dispatch, allocate the next unused `INV-nnn` and one
exact staging/final path pair per `rune-taskfmt`. Also reserve a `RES-nnn` pair when outside
evidence may be needed; if that cannot be known cheaply, reserve it and let the worker
return it unused. Record every reservation as a pending `report-slot` row before the
worker starts, then dispatch `rune-investigate` with those assignments. A pure outside-repo
question may dispatch `rune-research` with only its `RES-` assignment.

Accept `answered` only when every returned id and staging pointer matches its pending row.
Validate each complete staging artifact and atomically promote it to the assigned final
path with no-replace semantics, then mark that report slot `recorded`. Settle the INV and
optional RES rows independently from the worker's two explicit outcomes: mark an unused
companion slot `unused` only after proving both paths absent, and mark each blocked slot
`blocked` with its reason. Do not promote or recycle a blocked slot. A crash after
promotion is repaired by `rune-continue` from the pending row and final file. When RES is
answered, promote and record it before INV, then require the INV report's mandatory
`research:` disposition to name that same RES id. When it is unused, require the INV report
to say `research: unused`. Investigation creates no task row and does not continue into
planning — that gap is the entire point of the classification.

Protocols may reclassify once they see real code. Accept it and reroute; correcting early
is cheap.

### Bug reservation and diagnosis

A bug is the one type whose worktree must exist before decomposition, because its failing
check is both planning evidence and part of the eventual source change.

After triage returns `bug`:

1. Choose the next unused decomposition run and next globally unused `T-nnn`. An id is
   used if it appears anywhere under `.rune/`, not only in `tasks/` or the ledger.
2. Write the run's immutable `protocol.md` with `type: bug`, `protocol: bug`, triage
   evidence and shape, and `reserved_task: T-nnn`.
3. In one validated ledger update add a provisional row with the milestone, title,
   `status: diagnosing`, the absolute `<main_root>/.rune/worktrees/T-nnn` path,
   `attempts: d1/e0/v0/l0`, zero failures, no finding or blocker, and
   `resume_at: diagnose`, `replaced_by: —`. This reserves identity and claims diagnosis;
   no task spec exists and the row is not executable.
4. Dispatch one `rune-bug` worker with `work: T-nnn`, `attempt: 1`, `main_root`,
   `worktree_path`, and
   absolute protocol and `notes/T-nnn.progress` pointers. The worker creates or validates
   the exact worktree before writing the reproduction check.

```rune-dispatch
follow: bug
work: T-nnn
attempt: 1
main_root: /workspace/acme
worktree_path: /workspace/acme/.rune/worktrees/T-nnn
pointers:
  protocol: /workspace/acme/.rune/drafts/M-03/R-002/protocol.md
  progress: /workspace/acme/.rune/notes/T-nnn.progress
```

5. Act on its durable result:
   - `reproduced` — require a clean kept worktree, `diagnosis_base_commit`, and
     `diagnosis_commit`; clear any blocker, set `resume_at: plan:<this run>`, and continue
     into decomposition using this same run and reservation.
   - `not_reproduced` — remove the provisional row, keep the progress record, and ask for
     the missing input. The worker discarded the worktree and the id remains burned.
   - `reclassified` — remove the provisional row, preserve the old run and progress record,
     then route the returned type through a fresh run. Never recycle the id.
   - `blocked` — keep the row `diagnosing`, set `blocker: external:<slug>`, point
     `latest_finding` at the progress block containing the reason and unblock condition,
     and stop. Do not plan from partial or inaccessible evidence.

The parent never reads the reproduction diff or test output. The progress pointer and two
commit ids are the interface; planners consume the detail from disk.

The type that remains after this protocol step is the final classification for the next
decomposition run. Do not leave it only in this context: the planners that need it start
fresh and cannot inherit the protocol you loaded here.

## 2. Decompose

Check first that no `open` decision blocks this milestone. If one does, surface it to the
user and stop. The gate is not negotiable.

**Dispatch workers that follow `rune-decompose`. You do not read source or write planner
drafts or task files.** Include `main_root` and absolute pointers under
`<main_root>/.rune/`, per the canonical dispatch envelope. Decomposition requires real
code — the one thing you may not read — so a task file composed in your context is fiction.

Use this exact two-phase protocol:

1. Under `<main_root>/.rune/drafts/<milestone>/`, choose the next unused `R-nnn`
   directory. Never reuse a run, including one left incomplete by a dead session. For a
   confirmed bug, reuse the exact run whose protocol and `reserved_task` produced the
   diagnosis; for every other type, create the run here. Write `protocol.md` using the
   canonical schema in `rune-taskfmt`: the final `type`, exact protocol skill, and triage
   evidence and shape, plus `decisions: [...]` containing every decided record that
   constrains this milestone/request. The only valid mappings are `bug -> bug`,
   `feature -> feature`, and `refactor -> refactor`. Then assign `P-01` through
   `P-03`; the parent is the only allocator for the run, protocol record, bug reservation,
   and planner slots.
2. Dispatch two or three planners in parallel. Each gets one work id such as
   `M-03/R-002/P-01`, the same `main_root` and absolute milestone inputs, and one distinct
   output pointer such as `<main_root>/.rune/drafts/M-03/R-002/P-01.md`. Every dispatch
   also gets absolute pointers to that run's `protocol.md` and to `decisions.md`. A planner
   loads the named protocol and its listed settled decisions, then writes only its complete
   draft, using local `D-nnn` ids; it never writes a final task file or the ledger. For a
   bug, also pass the reserved task's exact
   `worktree_path` plus the absolute diagnosis progress pointer. The planner reads the
   committed reproduction there and marks exactly one proposed task
   `reservation: primary`.
3. Accept `plan: drafted` only when `artifact:` exactly matches the assigned pointer. If a
   planner stops without a complete artifact, any retry gets a new unused `P-nn` slot so a
   late original worker cannot collide with it. Wait until every planner in the run has
   returned or is confirmed stopped; do not reconcile while one may still produce another
   cut, and do not reconcile fewer than two complete cuts.
4. **Run the pre-reconciliation gate below.** No final `tasks/T-nnn.md` file exists yet.
   Present the candidate shapes, assumptions, exclusions, and disputed seams from the
   complete draft artifacts. A harmless implementation assumption is internal,
   reversible, and cannot change behaviour, scope, acceptance, data retention, error
   semantics, or a public interface. Anything else is a behaviour/scope decision: assign
   it a parent-owned `DEC-nnn` with `source: planning`, persist and settle it with the
   user, abandon this immutable run, and start a fresh run whose protocol lists that id.
   All fresh planners therefore read the durable choice before drafting. User additions
   that change the cut also start a fresh run; never patch an old draft or reconcile it
   under new input.
5. Only after the gate accepts a run with no decision candidates, dispatch one fresh
   reconciler with work id `M-03/R-002` and pointers to every completed
   draft artifact. Give it the same `main_root`, the same absolute protocol pointer, and
   the absolute decisions and draft pointers. For a bug, give it the same diagnosis pointer and
   `worktree_path`. It validates that every draft used that protocol, repeats the
   type-specific sanity pass, compares the cuts, and writes the final task files. The
   reconciler maps the selected `reservation: primary` task to the protocol's already-used
   `T-nnn`; it allocates ids only for any additional tasks.
6. Accept `plan: reconciled` only with final task paths, one-line titles, and dependency
   edges. Parse every canonical task contract before registration. A mitigation must link
   a different final task in the same batch and milestone whose immutable contract is a
   root-cause bug; both files must exist and validate before either row is registered.
   Then register exactly those tasks in `<main_root>/.rune/ledger.md` in one
   validated parent update. New rows start `unsized`, `d0/e0/v0/l0`, zero failures, no
   finding or blocker, `resume_at: fresh`, `replaced_by: —`, and no worktree. For a bug,
   update the existing
   reserved row's title and dependencies, move `diagnosing -> unsized`, preserve `d1` and
   its absolute worktree, clear the blocker, and set `resume_at: fresh`; add only the extra
   rows. Draft planners and the reconciler never register tasks themselves.
7. Size every newly registered task, below. Nothing is dispatchable until it passes.

The draft files remain immutable after reconciliation. They are the evidence for what the
planners agreed on, where they disagreed, and what the reconciler changed.

### Sizing the new tasks

A task arrives registered `unsized`, which means nothing can claim it. The planner already
applied the five-file rule while cutting; this asks the different question that rule cannot
answer — whether **one fresh agent could finish this whole task with room left over.**
Five files in one module and five files across three subsystems both pass the rule and are
not the same job.

Dispatch one worker following `rune-size` per new task, with the task, milestone, map, and
`notes/T-nnn.sizing.md` pointers. They are independent and read-only, so run them
concurrently. Never send a planner or reconciler from this run: the reasoning that produced
the task is exactly what would talk a reviewer into accepting it.

| Returned | What you record |
|---|---|
| `pass` | `unsized -> pending`, blocker `—`, resume `fresh`. Now dispatchable. |
| `split` | leave it `unsized` and re-cut, below. |
| `blocked` | stays `unsized`, blocker `sizing:<slug>`, finding points at the sizing record. Report it; a task nobody can assess is not a task you dispatch anyway. |

A `split` goes back through decomposition, not into a patched task file. Allocate a fresh
`R-nnn` whose protocol carries the sizing record and the retiring id, re-cut that one task,
and retire the oversized row with `replaced_by` naming its replacements — the same atomic
handoff a drift replan uses. **The replacements are registered `unsized` and sized like any
other new task**, because a split can be cut too large again.

If the same task returns `split` twice, stop and take it to the user. Two rejections is a
signal about the milestone, not the cut, and a third planning round usually produces the
second cut again.

Report a split at the next checkpoint in plain words: what was too big and how it is now
divided. Do not report a `pass` — a task that fits is the normal case and says nothing.

If a protocol reclassifies work after a run has been created, abandon that run and start a
fresh `R-nnn` with a new protocol record. A bug reservation is also removed from the live
ledger and burned as described above. Never rewrite an old record: a worker or late retry
may already be using it.

This is the one step in Rune that earns a fan-out, per *Judgment fans out, mechanics do
not* below. Where the independent artifacts agree, the cut is probably sound. Where they
disagree, that seam is exactly where decomposition goes wrong, and it is now named instead
of being discovered four tasks later.

### Replanning after drift

Drift uses the same fan-out but has an additional atomic handoff between obsolete and new
contracts:

1. Read the drift record and compute the complete retirement closure: its originating
   unfinished task, every unfinished task it names, and every unfinished task whose
   dependency chain reaches one of them. Keep `done` tasks unchanged. In one schema-2
   update, add a `quiescing` entry under `## Drift` naming the exact frozen ids,
   drift-block every inactive row in that set, and stop **all** new diagnosis, execution,
   verification, retry, and landing dispatches for the set. An inactive row with
   `worktree: —` becomes `worktree: discarded` in that update. The ledger drift entry,
   not an active row's status, is the durable freeze seen after a crash. Count the closure
   as you build it and record both numbers in that entry — `closure: N of M unfinished`,
   where `M` is the milestone's unfinished tasks before the freeze. The stop rule below
   reads those numbers, so a later session never re-derives them.
2. Drain every frozen row by its pre-freeze state; ordinary outcome routing is suspended:
   - `pending`, `awaiting`, `blocked`, or already `drifted`: leave it drift-blocked. If it
     owns an absolute worktree, dispatch `rune-drift` in quiesce mode after its prior worker
     is confirmed stopped; otherwise its worktree is already `discarded`.
   - `diagnosing`, `in_progress`, or `verifying`: wait for the already-dispatched worker
     or reconcile its durable return, but never advance that return to planning,
     verification, retry, or landing. A task that returned drifted and discarded is
     complete; otherwise dispatch `rune-drift` quiesce on its registered worktree, then set
     `drifted`, the causal drift blocker and pointer, `resume_at: replan`, and
     `worktree: discarded` in one update.
   - `landing`: wait for the live lander. `landed` with a green main becomes `done` and is
     removed from the retirement set; its code is part of the replan baseline. Any
     non-landed return starts no retry and goes through `rune-drift` quiesce. If the return
     was lost, increment `l` and dispatch `rune-land` with `mode: drift-observe`: an artifact
     already reachable from main is oracle-checked and becomes `done`; `not_landed` is
     quiesced without merging; `stuck` sets `main: red` and stops the route.
   A refused cleanup or any source state whose publication cannot be proven is a stop
   condition. Do not replan until every remaining frozen row is inactive with
   `worktree: discarded`; never transfer its branch, commits, diagnosis, or diff to a new
   id.
3. Allocate a fresh `R-nnn`. Its immutable protocol adds `drift: DRF-nnn` and
   `retiring: [...]`. Give every planner the same absolute drift pointer plus absolute
   pointers to all retiring task files. Give the reconciler those pointers, its distinct
   `replacements.md` output pointer, and the completed drafts.
   If the selected protocol is `rune-bug`, also allocate a fresh reserved task id not in the
   retirement set, add its `diagnosing` row, and reproduce the failure in its own new
   worktree before planning. Never transfer the retired task's diagnosis commit or reuse
   its branch; diagnosis evidence is bound to task identity. The final transaction updates
   this reproduced reservation to `pending` instead of adding a second row for it.
4. Accept reconciliation only when every returned task path is new and the replacement
   artifact maps every retiring id exactly once to `none` or new ids, maps every new id at
   least once, leaves no live dependency on a retiring id, and every mitigation links a
   validated same-milestone root-cause task in the replacement set. Never overwrite or
   delete any old task file.
5. After every new file exists, perform the one ledger transaction from `rune-ledger`: add
   the new `unsized` rows (or finalize the fresh reproduced bug reservation as `unsized`)
   and move all
   old rows to terminal `retired` with their immediate `replaced_by` values. If validation
   or the write fails, none of the old rows retires and none of the new tasks becomes
   executable. Unregistered task-file ids remain burned. Then size every new row exactly as
   a first cut is sized; a replan is not evidence that the replacements fit.

The user gate below shows both sides: which task ids became history and which fresh task
ids now carry their outcomes. A `none` disposition is called out explicitly; it means the
replan proved no replacement work is required, not that a task silently disappeared.

### When drift stops the loop

Every drift replans. What varies is whether you then keep working or hand back to the
user, and that is decided by the `closure: N of M unfinished` numbers recorded in step 1 —
never by how serious the drift felt.

| Measure | Stop and ask when |
|---|---|
| `N`, the unfinished tasks retired | 3 or more |
| `N / M`, the share of the milestone retired | half or more |
| the milestone's own acceptance | the drift record names it as invalid |

Any one is enough. Below all three, replan and carry on; the replan still appears in the
next report. Quote the two numbers whenever you stop on this rule, so the user sees the
same measurement you did.

## Judgment fans out, mechanics do not

How many agents a job gets is not a matter of taste. It follows from what kind of job it is:

| The job is | Dispatch | Because |
|---|---|---|
| **Judgment under uncertainty**, where a wrong answer surfaces late | 2–3 in parallel, then reconcile | Disagreement between independent attempts is the only cheap signal that the call was hard |
| **Mechanical**, with one correct outcome | one | A second agent running the same command returns the same string and costs the same again |

Decomposition is the clearest case for fanning out — a bad cut poisons every task under
it and does not show up until executors start colliding. Triage classification is the
second, when the evidence is genuinely ambiguous on an unfinished codebase.

Running a command, writing a file from a settled spec, verifying the task's declared
evidence chain: one agent. Fanning these out buys nothing and spends the budget twice.

Each parallel agent still gets **one issue** — the rule above is unaffected. Three
planners on one milestone is three agents on the same single issue, which is fan-out.
One planner on three milestones is batching, which is forbidden.

### Pre-reconciliation gate — always

**Stop here after draft fan-out and before the reconciler writes final task files. Every
time.** No final task contract or production implementation exists until the user has
seen the candidate plan and been asked whether they want to add anything. A confirmed bug
may already have its committed failing reproduction evidence. There is no flag that skips
this.

Not "proceed?" — that invites a yes and nothing else. Ask for **additions**, and give them
something concrete to react to: what you are about to do, what you decided on their behalf,
and what you are deliberately leaving out.

```
Proposed M-03 · session lifecycle — candidate cut of 4 tasks

  rotate refresh tokens        auth      ~3 files
  refresh endpoint             api       after rotation
  session restart persistence  auth,db   ~4 files
  expiry sweep job             worker    ~2 files

Rotation, persistence, and the sweep touch different files, so the eventual tasks can run
at the same time.

Implementation assumptions
- private helper names follow the existing auth convention

Decision needed before final tasks
- session expiry: fixed 30 days or user-configurable? Recommendation: fixed for v1.

Not doing
- device management and OAuth — those are M-06 and M-07

Anything you want to add, change, or take out before I start?
```

The three things that make this gate earn its place:

- **Implementation assumptions, stated.** These may be made only when harmless and
  reversible. Anything user-visible is a decision, not an assumption.
- **Exclusions, stated.** Users often assume something is included. Saying what is out
  surfaces that before it becomes a surprise.
- **An open question, not a yes/no.** "Proceed?" gets a yes. "Anything to add?" gets the
  thing they had been meaning to mention.

If they add something, or a behaviour/scope decision is discovered, persist it first and
start a fresh run whose protocol carries every settled decision. Show that revised plan.
Never reconcile drafts built before their durable inputs existed.

A single-task fix gets a shorter version of the same thing, not a skipped one:

```
About to fix the login redirect bug.

  one task, ~2 files in src/auth. Reproduced it first: the redirect drops the
  query string when the session is renewed.

Decision needed: preserve the query string or remove the redirect? Recommendation:
preserve it to maintain current navigation behaviour.

Anything to add before I start?
```

## 3. Dispatch

### Choosing a batch

A task is eligible when it is `pending` and its `blocked_by` are all resolved. `unsized`
rows are not eligible and never become so by waiting — they are waiting on `rune-size`, not
on a dependency. Among eligible tasks, dispatch several at once when — and only when —
**their change surfaces are disjoint.**

That second condition is the real constraint, and it is checkable: every task declares its
change surface, so compare the file lists. Two tasks touching the same file will conflict
at merge, and the time lost untangling that exceeds anything parallelism won.

- **Cap: 3 concurrent executors.** Past that, merge conflicts and cost dominate.
- Prefer lowest ids when choosing which eligible tasks to include — earlier tasks usually
  establish ground later ones assume.
- One task left, or all eligible tasks overlap? Run it alone. Serial is the fallback, not
  a failure.

Tell the user what went out, per `rune-report`:

```
Dispatched 3 in parallel: T-014 (auth), T-017 (worker), T-019 (api).
No shared files. T-015 waits on T-014.
```

### What each executor gets

- **`rune-execute` to follow**, which loads `rune-taskfmt`, `rune-serena` and `rune-drift` itself.
- **`main_root`**, the same absolute orchestration checkout used by the parent.
- **`worktree_path`**, preallocated as the absolute
  `<main_root>/.rune/worktrees/T-nnn` and recorded in the ledger before dispatch.
- **`attempt`**, the row's executor counter after it was incremented and persisted.
- One task id and absolute pointers to its task file plus any handoff, verification, or
  landing record it must consume.

For a confirmed bug, `rune-bug` already created `worktree_path` and committed the failing
check there; the first executor validates and reuses it. For every other task, the first
executor creates the path if absent. Every later worker reuses that exact path. Do not
request harness isolation that creates an anonymous worktree; use it only if the harness
can target the supplied path exactly.

**No source code is ever modified outside `worktree_path`.** Executors validate the path
against `main_root`'s Git repository before editing and create it at the supplied location
when needed. The current working directory supplied by the harness is never accepted as a
substitute.

The rule exists twice over because it carries two loads: a dead executor's torn state is
discarded with its worktree, and parallel executors cannot tread on each other.

Claim each task before dispatch in one ledger replacement: allocate or preserve its exact
absolute worktree, set `in_progress`, increment `e`, clear `blocker`, and set
`resume_at: recover`. In that same replacement allocate the next unused `DRF-nnn` and add
its pending `report-slot` row with exact absolute
`drift/open/DRF-nnn.md -> drift/DRF-nnn.md` paths. Validate and persist the complete task
claim and report assignment, then dispatch with that reservation. If the dispatch never
returns, `rune-continue` can see both that an attempt happened, which drift destination it
owned, and that recovery is required. A non-drift return marks the slot `unused`; its id
is never recycled.

Executors report ≤200 tokens:

```rune-return
work: T-014
summary: rotate() implemented and wired; required verification evidence recorded
status: done | drifted | budget | blocked | question
worktree: kept | discarded        # done requires kept until land cleans it
worktree_path: /workspace/acme/.rune/worktrees/T-014
attempt: 2
base_commit: a3f91c2       # required for done; repeated from the progress file
artifact_commit: 4a91c02   # required for done; the task branch HEAD
drift: DRF-003          # if any
artifact: /workspace/acme/.rune/drift/open/DRF-003.md # drifted only
decision: pending-id    # if status is question; workers never allocate DEC ids
decision_artifact: /workspace/acme/.rune/decisions/open/T-014-e2.md
blocker: service-down   # blocked only; parent stores external:service-down
resume_at: step:3       # budget, blocked, or question
detail: /workspace/acme/.rune/notes/T-014.md
```

Consume every outcome in one validated ledger update:

| Executor status | Complete row update |
|---|---|
| `done` | require both commit ids; set `verifying`, increment `v`, resume `verify`, then dispatch the verifier with that attempt |
| `budget` | set `pending`, preserve the absolute worktree, point `latest_finding` at the handoff, set the returned pending resume token |
| `blocked` | set `blocked`, keep the absolute worktree or mark it `discarded` exactly as returned, store `external:<slug>`, and point at the handoff containing `blocker_reason`, `unblocks_when`, and the compatible resume token |
| `question` | after parent id allocation set `awaiting`, `decision:DEC-nnn`, the decision pointer, and the returned resume token |
| `drifted` | require the assigned id, staging pointer, and `worktree: discarded`; validate and atomically promote staging to final before setting `drifted`, `drift:DRF-nnn`, the final drift pointer, `resume_at: replan`, and keeping `replaced_by: —` until replan succeeds |

For `done`, the commit ids are routing data, not the durable record — the executor wrote
the same publication to `<main_root>/.rune/notes/T-nnn.progress`. Do not read the
worktree or accept an uncommitted success claim. The update to `verifying` and `v++` must
land before the verifier is dispatched.

The status meanings and row validity rules remain owned by `rune-ledger`; the table above is
this route's atomic action for each returned outcome.

For every executor status other than `drifted`, first prove both assigned report paths are
absent, then replace that attempt's pending drift report slot with `unused DRF-nnn` in the
same ledger candidate that consumes the outcome. A `blocked` return with
`blocker: report-assignment`, or any unexpected report file on a non-drift outcome, marks
the slot `blocked` and enters `rune-continue` instead. For `drifted`, promote first and replace
it with `recorded DRF-nnn: <absolute final>`. If final exists but
the row is still pending, validate it and finish the ledger update; if both staging and
final exist, either path mismatches, or neither report exists for a drifted return, stop
and enter `rune-continue` rather than allocating another id.

Before applying that table, check the ledger's `## Drift` freeze set. A return for a
frozen task is consumed only by *Replanning after drift*: it may supply durable evidence,
but it cannot trigger a new verifier, retry, diagnosis, or lander. This check closes the
race where drift is recorded after a worker was dispatched but before its result arrives.

### When an executor is blocked

`status: blocked` ends that dispatch attempt. Validate that the return names the live task,
its recorded `attempt` and `worktree_path`, a valid kept/discarded disposition, lowercase
`blocker` slug, schema-safe `resume_at`, and absolute `detail` handoff. The handoff must
repeat the slug and contain `blocker_reason` plus observable `unblocks_when`. Consume it
with the complete row update above; the executor attempt was already counted when claimed,
so returning blocked does not increment `e` again.

Do not verify, land, or immediately retry it. If any required field is missing or
mismatched, fail closed without constructing an invalid schema-2 blocked row: preserve the
already-valid claimed row and recorded worktree, append the incomplete dispatch outcome in
one validated write, stop the normal loop, and enter `rune-continue` reconciliation before
reporting. Never invent missing blocker fields, discard source state, or leave the stale
`in_progress` claim unreconciled.

Keep unrelated tasks in the batch running. Report the blocker and the exact condition that
would clear it. A later `rune-work` or `rune-continue` may move it back to `pending` only after that
condition is proven through an allowed bounded probe, durable coordination state such as a
reconciled replacement, or explicit user confirmation. If none can prove it, report and
wait. Clear `blocker`, retain `latest_finding` as history, and preserve the compatible
resume token and any live worktree in the same validated write.

### Landing a batch

Verify each task independently first (step 5), then land them **one at a time, in the order
they finished**. Before each landing, atomically set `landing`, increment `l`, and set
`resume_at: land`. Each landing is a **dispatch to `rune-land`** carrying one task id, that
recorded attempt, and
the same `main_root` and `worktree_path`, plus absolute pointers to its progress and
verification records — never two at once, because two landers are two writers on the main
tree.

The lander merges, re-runs the project oracle in the main tree, and rolls the merge back if
that fails. You never see a suite log and never touch the main tree yourself.

Disjoint file lists prevent textual conflicts, not semantic ones — task A can rename
something task B calls without either touching the other's files. Re-running the checks
after each landing is what catches that, and landing one at a time is what tells you which
one did it.

Five normal outcomes (`not_landed` exists only for drift-observe recovery):

Consume post-merge oracle evidence without translation: `landed` requires
`oracle_result: passing | none`; `reverted` requires `oracle_result: failing`. `none` is valid only when
`rune.yml` has no project oracle. A contradictory or legacy `pass | fail` value is a
malformed landing return, not a synonym the parent guesses at.

| `landing:` | What happened | What you record |
|---|---|---|
| `landed` | exact verified commit merged, oracle passed | `done`, blocker `—`, resume `—`, worktree `merged` or cleanup-pending absolute path |
| `refused` | artifact missing, dirty, empty, or changed since verification | `pending`, worktree kept, finding points at landing attempt, resume `publish` |
| `conflict` | merge refused, nothing landed | `pending`, worktree kept, finding points at landing attempt, resume `fresh` |
| `reverted` | merged, oracle failed, rolled back | `pending`, worktree kept, finding points at landing attempt, resume `fresh` |
| `stuck` | the main tree needs a human — dirty on arrival, or a rollback that did not restore it | `blocked`, `main:red`, landing finding, resume `land`; stop everything |

**Keep the worktree on anything but `landed` with `cleanup: complete`.** What is in it
passed independent verification; what failed was publication or integration. Discarding
it throws away a verified change to solve a landing problem. A landed task with cleanup
pending is done; `rune-continue` removes the orphan later.

### The landing loop

`refused`, `conflict`, and `reverted` mean the same thing operationally: the task is not
done, its worktree still holds real work, and something has to change *in that worktree*
before it can land. The landing record distinguishes publication failure, integration
conflict, and a post-merge regression so the next executor works the right problem.

So dispatch a fresh executor on `rune-execute` for the same task, and give it
`<main_root>/.rune/notes/T-nnn.landing.md` as a second absolute pointer alongside its
task file. Reuse the ledger's exact `worktree_path`; never ask the harness for a fresh
checkout. That record and that kept worktree are the only things standing between the
retry and repeating the last attempt move for move. Then re-verify, and land again.

```
execute → verify → land ─┐
   ▲                     │ refused | conflict | reverted
   └─────────────────────┘
```

**The ceiling is five dispatched landing attempts.** Before claiming another landing,
stop if the ledger already says `l5`; a dead fifth dispatch still consumed the attempt.
The lander independently rejects a supplied attempt above five and evaluates the
record-based escalation rules. Apart from that mechanical ceiling, act on the `escalate`
line it returns rather than judging whether another loop seems worthwhile.

- `escalate: no` → round the loop again.
- `escalate: yes` → **stop and go to the user**, per `rune-report`. Give them the reason the
  lander named and what has already been tried. The record holds the detail if they want it.

**`stuck` stops everything at once.** The main tree is in a state no agent can safely act
on. Set `main: red` in the ledger, land nothing else, dispatch nothing else, do not start
the next batch. Tell the user what state the tree is in and that it needs them — this is
the one failure Rune cannot get itself out of.

**Never dispatch into a red tree.** The lander returns `main: green | red` for exactly this
reason. A red main poisons every check downstream of it: the next task's verifier compares
against a baseline that no longer matches reality, so it either blames that task for a
regression it did not cause, or the baseline gets widened until the real failure is
invisible.

### When an executor asks a question

`status: question` means the executor hit a choice it has no authority to make. It has
written an open decision record and stopped.

The record arrives in `<main_root>/.rune/decisions/open/T-nnn-eN.md` with no id. Require
the path, `raised_by`, `source_attempt`, returned `work`, and persisted executor attempt to
match. **Assign the
`DEC-nnn`, move it into `decisions.md`, and delete the open file.** That hop is yours
because id allocation cannot be done safely by three concurrent workers.

Reconcile all simultaneously returned question artifacts in numeric task-id/attempt order
and serially apply `rune-taskfmt`'s crash-safe transaction: persist the assigned decision
with unique `source: T-nnn/eN`, then persist the `awaiting` row and pointer, then delete
that exact staging file. On recovery, reuse a record with the same source; never allocate
a second id. A conflicting source/path/attempt stops the route.

Do not answer it yourself. In the same update that moves the task to `awaiting`, store
`decision:DEC-nnn`, point `latest_finding` at that record, and preserve the worker's
`resume_at`. Surface it to the user per `rune-report` — question first,
options, your recommendation — and keep the rest of the batch running while you wait. When
the decision lands, re-dispatch the task; a fresh executor picks up the handoff, the
worktree diff, and the now-resolved decision.

### When a worker raises a finding

Workers write claims about things they noticed outside their own task to
`<main_root>/.rune/findings/open/T-nnn-eN-K.md`. They do not block anything and no
executor status announces them, so sweep that directory once per batch rather than
watching for a return value.

Every claim goes through the same three steps, in this order:

1. **Allocate and dispatch.** In numeric task-id, attempt, then `K` order, give each claim
   an `FND-nnn`, reserve its staging and final paths in the ledger, and dispatch **a fresh
   subagent following `rune-verify-finding`** with the claim pointer. One claim per
   dispatch. Never send the finder, and never send an agent that worked on the task the
   claim came from — the point of the check is that nobody involved is doing it.
2. **Promote the verdict.** Validate the returned staging file and atomically promote it
   to the reserved final path, exactly as a `DRF-`, `INV-`, or `RES-` report. All three
   verdicts get promoted; a refuted claim is a durable result, not a mistake to erase.
3. **Delete the consumed claim** only after its record is promoted. If you die between
   the two, `rune-continue` finds a claim with a promoted record and deletes it then.

Then record it under `## Findings` in the ledger and stop. **You do not act on a confirmed
finding.** It becomes a task only when the user says so, through triage and decomposition
like any other request. Quietly turning a finding into work is how a session that was
asked to fix one bug returns having changed six files.

Report only what came back verified, per `rune-report`. An unverified claim is not something
the user hears about — telling them about it makes them act on it, which is exactly what
the verification step exists to prevent.

## 5. Verify

Every `done` claim goes to a **separate** verifier in a **clean context** —
`rune-verify`. Never the same agent, never the same context. An executor is the worst
possible judge of its own work.

- Before acting on the verdict, require its `artifact_commit` to match the executor's
  latest publication and require `verified_commit` to equal it on `pass`. A mismatch is
  `unverified`; never choose which SHA the verifier probably meant.
- `pass` → keep the completed `v` counter, then atomically claim landing and increment `l`
  before handing the task id, landing attempt, and pointers to `rune-land`. It is not `done`
  until that returns `landed` — publishing, passing in a worktree, and surviving the merge
  are three different claims tied together by the same commit.
- `fail` → back to `pending`, increment `failures`, set `latest_finding` to the verifier's
  exact attempt anchor, and set `resume_at: fresh`. The verifier wrote its finding to
  `<main_root>/.rune/notes/T-nnn.verify.md` and returned that path on its `detail` line.
  **Give the absolute path to the retry executor as a second pointer, alongside the task
  file, and reuse the exact `worktree_path`.** Do not have the verifier fix it, and do not
  restate its finding in the dispatch — the record is the payload, your dispatch carries
  the pointer.
- `unverified` → not a soft pass. Point `latest_finding` at its verdict block.
  `reason: artifact` goes to `pending` with the worktree kept and `resume_at: publish`; a
  fresh executor must publish one clean immutable range. `reason: evidence`
  or `acceptance` is a task-contract finding, but the verifier cannot write its causal
  record. Keep the row `verifying`, allocate one unused `DRF-nnn`, and append a pending
  report-slot row binding that verifier attempt to its exact staging and final drift
  paths. Dispatch `rune-drift` in record-only mode with the assignment plus task and verifier
  pointers. When the staging record returns, validate and atomically promote it, then use
  it as the evidence for one update that adds the exact unfinished dependency closure to
  the ledger drift freeze, sets the originating row and every inactive affected row to
  the causal drift blocker with `resume_at: replan`, and points `latest_finding` at the
  DRF. The DRF in turn preserves the verifier block as its evidence. Then quiesce the set
  before decomposition. If the record dispatch dies, leave the valid `verifying` row and
  its frozen verifier verdict in place; `rune-continue` reuses the assigned id and both paths
  rather than allocating another.
  `reason: oracle` sets `blocked`, `external:oracle-unavailable`, the verifier finding, and
  `resume_at: verify`; stop the batch until the check is available again.

The verifier must echo the exact `attempt` already persisted in `v` and use the same number
for its appended record block. Reject a mismatch. The two-failure stop rule reads the
ledger's `failures` field after consuming the verdict; it never reconstructs that count
from conversation memory or mistakes an `unverified` result for a failed criterion.

## 6. Reconcile

Per `rune-ledger`:

- Update statuses.
- Any drift record → drift-block the full unfinished dependency closure; do not delete or
  edit its task files.
- Any executor blocker → keep its worktree and durable handoff; do not retry until the
  recorded condition is proven cleared.
- Any drift in one milestone → use *Replanning after drift* to write fresh task ids,
  atomically retire the obsolete rows with replacement lineage, and continue only after
  the replacement transaction validates. Whether you then keep going or hand back is the
  measured call in *When drift stops the loop*, not a judgement made here.

Then report, and **re-check `<main_root>/.rune/PAUSED` before dispatching the next batch.** The user
can pause at any point; the check belongs at the top of every loop iteration, not only at
entry. If the flag appeared mid-run, finish and merge what is in flight, then stop — the
same drain `rune-pause` would have done.

Otherwise, loop to the next batch.

## Keeping the user informed

Load `rune-report` and follow it. The cadence it defines is not optional — the user asked
to hear from you at checkpoints, not only at the end.

Report after **every** verified task, every completed batch, every milestone, and every
blocker. Stay quiet in between: no narrating dispatches, no commentary on your own
reasoning.

Everything you write opens with a TL;DR and uses plain words. Say "the tests pass", not
"the oracle is green". Say "the plan was wrong about X", not "DRF-003".

## Stopping

Stop and return to the user when: the milestone is complete, an `open` decision blocks
progress, an executor asked a question, drift crosses the measured threshold in *When
drift stops the loop*, an executor is blocked and nothing else is dispatchable, the ledger
reaches `failures >= 2` for a task, a lander returns `escalate: yes` or `stuck`, or nothing
is dispatchable.

```
TL;DR
- M-03 is 3 of 4 done. Rotation, refresh endpoint, and the sweep job all work.
- One task stalled: the plan assumed one entry point into session handling, there are two.
- Need you: split it in two, or widen the existing task?

Done       T-014 rotate tokens · T-015 refresh endpoint · T-017 expiry sweep
Stalled    T-016 restart persistence
Waiting    T-018, T-019 — they assumed the same single entry point
```

A task failing twice is a signal about the *plan*, not the executor. Say so rather than
dispatching a third attempt.
