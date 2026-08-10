---
name: work
description: Use when building a feature, fixing a bug, refactoring, or advancing the current milestone. Triages the request against real code, decomposes it into tasks, dispatches isolated executors, and verifies each one independently.
---

# rune:work

The execution loop. Triage → diagnose bugs → plan → dispatch → verify → reconcile.

## What you may do

**You exist to tell the user what is happening.** Everything you are allowed to do follows
from that, and this list is exhaustive:

- **Run** `git rev-parse --show-toplevel` as the one bounded identity probe.
- **Read** `<main_root>/.agent/` coordination files — enough to report status accurately.
- **Write** `<main_root>/.agent/ledger.md`, and **append** the drain result to
  `<main_root>/.agent/PAUSED` if the flag
  appears mid-run. You never create or delete that file — `pause` and `continue` do.
- **Create** one immutable
  `<main_root>/.agent/drafts/<milestone>/R-nnn/protocol.md` before dispatching that
  decomposition run. For a bug, create it before diagnosis and include the reserved task
  id. You never edit it after any worker can see it.
- **Talk to the user** — reports, the gate, questions.
- **Dispatch subagents**, naming the skill each one must follow. The dispatch table in
  `ai-taskfmt` says which skill does which job.

Before any coordination read or dispatch, resolve `main_root` once with
`git rev-parse --show-toplevel`. This bounded identity probe is the only command added by
this contract. Resolve every `.agent/...` read against that absolute root and carry the
same value in every dispatch.

**Anything not on that list is a dispatch.** Writing any other file, running any command,
reading any source file — each one is a subagent's job, without exception and without a
case where it is quicker to just do it yourself.

**You do not merge.** That was once on this list, as the single command you were allowed to
run. It came off because a merge cannot be separated from what has to follow it: the suite
is re-run against the merged tree, and if it fails the merge has to come back out. Only the
first of those three is bounded, so the sequence is one dispatch — `ai-land` — and not a
command of yours with two dispatches around it.

Stated this way round on purpose. A list of forbidden actions can always be stepped
around by an action nobody thought to forbid — which is exactly how task files ended up
being written here. A list derived from a reason covers the cases nobody anticipated: if
a thing is not needed to report status, route correctly, or record what happened, it does
not belong in the context you are protecting.

Two consequences are load-bearing:

- Every subagent returns **≤200 tokens**. Anything longer goes to disk; you read it only
  if you must act on it.
- You **re-read `ledger.md` from disk** between dispatches. Never carry ledger state in
  context — a stale in-memory copy is how you dispatch a task someone already finished.
- Validate schema 1 on every read and every candidate replacement, per `ai-ledger`. An
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

- **`<main_root>/.agent/PAUSED` exists → stop.** Report that work is paused, when and why, and that
  `rune:pause` lifts it. Do not dispatch. Do not quietly resume because the user asked for
  something — they may have forgotten the pause is set, and silently overriding a
  deliberate stop makes it worthless.
- No `<main_root>/.agent/rune.yml` → run `rune:init` first.
- No `milestones.md` and the request is broad ("continue the project") → route to
  `rune:vision`. Do not invent a plan; that is vision's job and it requires the user.
- A specific request ("fix the login bug") with no vision → proceed. Not everything needs
  a milestone graph.

## 1. Triage

Classification often cannot be done from the user's sentence. "Is this a bug or is it
simply not implemented?" is undecidable without evidence — and it is the most common
ambiguity on an unfinished codebase.

Since you cannot read code, **dispatch a subagent that follows `ai-triage`** — **one per
issue**, per *One agent, one issue* above. If the user reported three things, that is
three triage dispatches, run concurrently. Never hand one triage agent a
list, even when the issues sound related: "sounds related" is a hypothesis, and batching
them destroys the independence needed to test it.

Each returns:

```
type: bug | feature | refactor | investigation
evidence: SessionMiddleware.handle exists and is called; rotate() returns null (stub)
shape: single fix in src/auth — reproduction likely straightforward
milestone: M-03 (fits scope) | none | conflicts with M-03 scope
```

Then load the matching protocol:

| type | skill | first move |
|---|---|---|
| bug | `ai-bug` | reserve its task and reproduce in that worktree before planning |
| feature | `ai-feature` | scope boundary, then decisions |
| refactor | `ai-refactor` | confirm a characterization net exists |
| investigation | `ai-investigate` | read-only, terminates in an answer |

**Investigation exits here.** It produces a written answer, no tasks, no ledger entries.
Do not continue into planning — that gap is the entire point of the classification.

Protocols may reclassify once they see real code. Accept it and reroute; correcting early
is cheap.

### Bug reservation and diagnosis

A bug is the one type whose worktree must exist before decomposition, because its failing
check is both planning evidence and part of the eventual source change.

After triage returns `bug`:

1. Choose the next unused decomposition run and next globally unused `T-nnn`. An id is
   used if it appears anywhere under `.agent/`, not only in `tasks/` or the ledger.
2. Write the run's immutable `protocol.md` with `type: bug`, `protocol: ai-bug`, triage
   evidence and shape, and `reserved_task: T-nnn`.
3. In one validated ledger update add a provisional row with the milestone, title,
   `status: diagnosing`, the absolute `<main_root>/.agent/worktrees/T-nnn` path,
   `attempts: d1/e0/v0/l0`, zero failures, no finding or blocker, and
   `resume_at: diagnose`. This reserves identity and claims diagnosis; no task spec exists
   and the row is not executable.
4. Dispatch one `ai-bug` worker with that task id, `attempt: 1`, `main_root`, `worktree_path`, and
   absolute protocol and `notes/T-nnn.progress` pointers. The worker creates or validates
   the exact worktree before writing the reproduction check.
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

**Dispatch workers that follow `ai-decompose`. You do not read source or write planner
drafts or task files.** Include `main_root` and absolute pointers under
`<main_root>/.agent/`, per the canonical dispatch envelope. Decomposition requires real
code — the one thing you may not read — so a task file composed in your context is fiction.

Use this exact two-phase protocol:

1. Under `<main_root>/.agent/drafts/<milestone>/`, choose the next unused `R-nnn`
   directory. Never reuse a run, including one left incomplete by a dead session. For a
   confirmed bug, reuse the exact run whose protocol and `reserved_task` produced the
   diagnosis; for every other type, create the run here. Write `protocol.md` using the
   canonical schema in `ai-taskfmt`: the final `type`, exact protocol skill, and triage
   evidence and shape. The only valid mappings are `bug -> ai-bug`, `feature -> ai-feature`,
   and `refactor -> ai-refactor`. Then assign `P-01` through `P-03`; the parent is the only
   allocator for the run, protocol record, bug reservation, and planner slots.
2. Dispatch two or three planners in parallel. Each gets one work id such as
   `M-03/R-002/P-01`, the same `main_root` and absolute milestone inputs, and one distinct
   output pointer such as `<main_root>/.agent/drafts/M-03/R-002/P-01.md`. Every dispatch
   also gets the absolute pointer to that run's `protocol.md`. A planner loads the named
   protocol and writes only its complete draft, using local `D-nnn` ids; it never writes a
   final task file or the ledger. For a bug, also pass the reserved task's exact
   `worktree_path` plus the absolute diagnosis progress pointer. The planner reads the
   committed reproduction there and marks exactly one proposed task
   `reservation: primary`.
3. Accept `plan: drafted` only when `artifact:` exactly matches the assigned pointer. If a
   planner stops without a complete artifact, any retry gets a new unused `P-nn` slot so a
   late original worker cannot collide with it. Wait until every planner in the run has
   returned or is confirmed stopped; do not reconcile while one may still produce another
   cut, and do not reconcile fewer than two complete cuts.
4. Dispatch one fresh reconciler with work id `M-03/R-002` and pointers to every completed
   draft artifact. Give it the same `main_root`, the same absolute protocol pointer, and
   the absolute draft pointers. For a bug, give it the same diagnosis pointer and
   `worktree_path`. It validates that every draft used that protocol, repeats the
   type-specific sanity pass, compares the cuts, and writes the final task files. The
   reconciler maps the selected `reservation: primary` task to the protocol's already-used
   `T-nnn`; it allocates ids only for any additional tasks.
5. Accept `plan: reconciled` only with final task paths, one-line titles, and dependency
   edges. Then register exactly those tasks in `<main_root>/.agent/ledger.md` in one
   validated parent update. New rows start `pending`, `d0/e0/v0/l0`, zero failures, no
   finding or blocker, `resume_at: fresh`, and no worktree. For a bug, update the existing
   reserved row's title and dependencies, move `diagnosing -> pending`, preserve `d1` and
   its absolute worktree, clear the blocker, and set `resume_at: fresh`; add only the extra
   rows. Draft planners and the reconciler never register tasks themselves.

The draft files remain immutable after reconciliation. They are the evidence for what the
planners agreed on, where they disagreed, and what the reconciler changed.

If a protocol reclassifies work after a run has been created, abandon that run and start a
fresh `R-nnn` with a new protocol record. A bug reservation is also removed from the live
ledger and burned as described above. Never rewrite an old record: a worker or late retry
may already be using it.

This is the one step in Rune that earns a fan-out, per *Judgment fans out, mechanics do
not* below. Where the independent artifacts agree, the cut is probably sound. Where they
disagree, that seam is exactly where decomposition goes wrong, and it is now named instead
of being discovered four tasks later.

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

## 3. The gate — always

**Stop here. Every time. No implementation begins until the user has seen the plan and
been asked whether they want to add anything.** There is no flag that skips this.

Not "proceed?" — that invites a yes and nothing else. Ask for **additions**, and give them
something concrete to react to: what you are about to do, what you decided on their behalf,
and what you are deliberately leaving out.

```
About to start M-03 · session lifecycle — 4 tasks

  T-014  rotate refresh tokens        auth      ~3 files
  T-015  refresh endpoint             api       after T-014
  T-016  session restart persistence  auth,db   ~4 files
  T-017  expiry sweep job             worker    ~2 files

T-014, T-016 and T-017 touch different files, so they can run at the same time.

Assumed
- sessions expire after 30 days — nothing in the code says, I took the config default
- rotation happens on refresh only, not on every request

Not doing
- device management and OAuth — those are M-06 and M-07

Anything you want to add, change, or take out before I start?
```

The three things that make this gate earn its place:

- **Assumptions, stated.** Anything you settled without being told. This is the last cheap
  moment to correct them — after four tasks are built on one, it is not cheap.
- **Exclusions, stated.** Users often assume something is included. Saying what is out
  surfaces that before it becomes a surprise.
- **An open question, not a yes/no.** "Proceed?" gets a yes. "Anything to add?" gets the
  thing they had been meaning to mention.

If they add something, fold it in and show the revised plan. If it changes the shape of the
work, re-decompose rather than bolting a task on the end.

A single-task fix gets a shorter version of the same thing, not a skipped one:

```
About to fix the login redirect bug.

  one task, ~2 files in src/auth. Reproduced it first: the redirect drops the
  query string when the session is renewed.

Assumed you want the query string preserved rather than the redirect removed.

Anything to add before I start?
```

## 4. Dispatch

### Choosing a batch

A task is eligible when its `blocked_by` are all resolved. Among eligible tasks, dispatch
several at once when — and only when — **their change surfaces are disjoint.**

That second condition is the real constraint, and it is checkable: every task declares its
change surface, so compare the file lists. Two tasks touching the same file will conflict
at merge, and the time lost untangling that exceeds anything parallelism won.

- **Cap: 3 concurrent executors.** Past that, merge conflicts and cost dominate.
- Prefer lowest ids when choosing which eligible tasks to include — earlier tasks usually
  establish ground later ones assume.
- One task left, or all eligible tasks overlap? Run it alone. Serial is the fallback, not
  a failure.

Tell the user what went out, per `ai-report`:

```
Dispatched 3 in parallel: T-014 (auth), T-017 (worker), T-019 (api).
No shared files. T-015 waits on T-014.
```

### What each executor gets

- **`ai-execute` to follow**, which loads `ai-taskfmt`, `ai-serena` and `ai-drift` itself.
- **`main_root`**, the same absolute orchestration checkout used by the parent.
- **`worktree_path`**, preallocated as the absolute
  `<main_root>/.agent/worktrees/T-nnn` and recorded in the ledger before dispatch.
- **`attempt`**, the row's executor counter after it was incremented and persisted.
- One task id and absolute pointers to its task file plus any handoff, verification, or
  landing record it must consume.

For a confirmed bug, `ai-bug` already created `worktree_path` and committed the failing
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
`resume_at: recover`. Validate and persist that complete row, then dispatch. If the
dispatch never returns, `continue` can see both that an attempt happened and that recovery
is required.

Executors report ≤200 tokens:

```
status: done | drifted | budget | blocked | question
task: T-014
attempt: 2
worktree: kept | discarded        # done requires kept until ai-land cleans it
worktree_path: /workspace/acme/.agent/worktrees/T-014
summary: rotate() implemented and wired; required verification evidence recorded
base_commit: a3f91c2       # required for done; repeated from the progress file
artifact_commit: 4a91c02   # required for done; the task branch HEAD
drift: DRF-003          # if any
decision: DEC-012       # if status is question
blocker: service-down   # blocked only; parent stores external:service-down
resume_at: step:3       # budget, blocked, or question
detail: /workspace/acme/.agent/notes/T-014.md
```

Consume every outcome in one validated ledger update:

| Executor status | Complete row update |
|---|---|
| `done` | require both commit ids; set `verifying`, increment `v`, resume `verify`, then dispatch the verifier with that attempt |
| `budget` | set `pending`, preserve the absolute worktree, point `latest_finding` at the handoff, set the returned pending resume token |
| `blocked` | set `blocked`, keep the absolute worktree or mark it `discarded` exactly as returned, store `external:<slug>`, and point at the handoff containing `blocker_reason`, `unblocks_when`, and the compatible resume token |
| `question` | after parent id allocation set `awaiting`, `decision:DEC-nnn`, the decision pointer, and the returned resume token |
| `drifted` | set `drifted`, `drift:DRF-nnn`, the drift pointer, and `resume_at: replan` |

For `done`, the commit ids are routing data, not the durable record — the executor wrote
the same publication to `<main_root>/.agent/notes/T-nnn.progress`. Do not read the
worktree or accept an uncommitted success claim. The update to `verifying` and `v++` must
land before the verifier is dispatched.

The status meanings and row validity rules remain owned by `ai-ledger`; the table above is
this route's atomic action for each returned outcome.

### When an executor is blocked

`status: blocked` ends that dispatch attempt. Validate that the return names the live task,
its recorded `attempt` and `worktree_path`, a valid kept/discarded disposition, lowercase
`blocker` slug, schema-safe `resume_at`, and absolute `detail` handoff. The handoff must
repeat the slug and contain `blocker_reason` plus observable `unblocks_when`. Consume it
with the complete row update above; the executor attempt was already counted when claimed,
so returning blocked does not increment `e` again.

Do not verify, land, or immediately retry it. If any required field is missing or
mismatched, fail closed without constructing an invalid schema-1 blocked row: preserve the
already-valid claimed row and recorded worktree, append the incomplete dispatch outcome in
one validated write, stop the normal loop, and enter `continue` reconciliation before
reporting. Never invent missing blocker fields, discard source state, or leave the stale
`in_progress` claim unreconciled.

Keep unrelated tasks in the batch running. Report the blocker and the exact condition that
would clear it. A later `work` or `continue` may move it back to `pending` only after that
condition is proven through an allowed bounded probe, durable coordination state such as a
reconciled replacement, or explicit user confirmation. If none can prove it, report and
wait. Clear `blocker`, retain `latest_finding` as history, and preserve the compatible
resume token and any live worktree in the same validated write.

### Landing a batch

Verify each task independently first (step 5), then land them **one at a time, in the order
they finished**. Before each landing, atomically set `landing`, increment `l`, and set
`resume_at: land`. Each landing is a **dispatch to `ai-land`** carrying one task id, that
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

Five outcomes:

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
pending is done; `continue` removes the orphan later.

### The landing loop

`refused`, `conflict`, and `reverted` mean the same thing operationally: the task is not
done, its worktree still holds real work, and something has to change *in that worktree*
before it can land. The landing record distinguishes publication failure, integration
conflict, and a post-merge regression so the next executor works the right problem.

So dispatch a fresh executor on `ai-execute` for the same task, and give it
`<main_root>/.agent/notes/T-nnn.landing.md` as a second absolute pointer alongside its
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
- `escalate: yes` → **stop and go to the user**, per `ai-report`. Give them the reason the
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

The record arrives in `<main_root>/.agent/decisions/open/T-nnn.md` with no id. **Assign the
`DEC-nnn`, move it into `decisions.md`, and delete the open file.** That hop is yours
because id allocation cannot be done safely by three concurrent workers.

Do not answer it yourself. In the same update that moves the task to `awaiting`, store
`decision:DEC-nnn`, point `latest_finding` at that record, and preserve the worker's
`resume_at`. Surface it to the user per `ai-report` — question first,
options, your recommendation — and keep the rest of the batch running while you wait. When
the decision lands, re-dispatch the task; a fresh executor picks up the handoff, the
worktree diff, and the now-resolved decision.

## 5. Verify

Every `done` claim goes to a **separate** verifier in a **clean context** —
`ai-verify`. Never the same agent, never the same context. An executor is the worst
possible judge of its own work.

- Before acting on the verdict, require its `artifact_commit` to match the executor's
  latest publication and require `verified_commit` to equal it on `pass`. A mismatch is
  `unverified`; never choose which SHA the verifier probably meant.
- `pass` → keep the completed `v` counter, then atomically claim landing and increment `l`
  before handing the task id, landing attempt, and pointers to `ai-land`. It is not `done`
  until that returns `landed` — publishing, passing in a worktree, and surviving the merge
  are three different claims tied together by the same commit.
- `fail` → back to `pending`, increment `failures`, set `latest_finding` to the verifier's
  exact attempt anchor, and set `resume_at: fresh`. The verifier wrote its finding to
  `<main_root>/.agent/notes/T-nnn.verify.md` and returned that path on its `detail` line.
  **Give the absolute path to the retry executor as a second pointer, alongside the task
  file, and reuse the exact `worktree_path`.** Do not have the verifier fix it, and do not
  restate its finding in the dispatch — the record is the payload, your dispatch carries
  the pointer.
- `unverified` → not a soft pass. Point `latest_finding` at its verdict block.
  `reason: artifact` goes to `pending` with the worktree kept and `resume_at: publish`; a
  fresh executor must publish one clean immutable range. `reason: evidence`
  or `acceptance` is a task-contract finding: record it as drift, set `drifted` with the
  drift blocker and `resume_at: replan`, then send it back to decomposition.
  `reason: oracle` sets `blocked`, `external:oracle-unavailable`, the verifier finding, and
  `resume_at: verify`; stop the batch until the check is available again.

The verifier must echo the exact `attempt` already persisted in `v` and use the same number
for its appended record block. Reject a mismatch. The two-failure stop rule reads the
ledger's `failures` field after consuming the verdict; it never reconstructs that count
from conversation memory or mistakes an `unverified` result for a failed criterion.

## 6. Reconcile

Per `ai-ledger`:

- Update statuses.
- Any drift record → block the tasks it invalidates, do not delete them.
- Any executor blocker → keep its worktree and durable handoff; do not retry until the
  recorded condition is proven cleared.
- Enough drift in one milestone → stop and re-decompose the remainder against the code as
  it now is. Do not patch task files one at a time; patched specs accumulate
  contradictions with their own amendments until nobody can tell what is still true.

Then report, and **re-check `<main_root>/.agent/PAUSED` before dispatching the next batch.** The user
can pause at any point; the check belongs at the top of every loop iteration, not only at
entry. If the flag appeared mid-run, finish and merge what is in flight, then stop — the
same drain `pause` would have done.

Otherwise, loop to the next batch.

## Keeping the user informed

Load `ai-report` and follow it. The cadence it defines is not optional — the user asked
to hear from you at checkpoints, not only at the end.

Report after **every** verified task, every completed batch, every milestone, and every
blocker. Stay quiet in between: no narrating dispatches, no commentary on your own
reasoning.

Everything you write opens with a TL;DR and uses plain words. Say "the tests pass", not
"the oracle is green". Say "the plan was wrong about X", not "DRF-003".

## Stopping

Stop and return to the user when: the milestone is complete, an `open` decision blocks
progress, an executor asked a question, drift invalidates a substantial part of the plan,
an executor is blocked and nothing else is dispatchable, the ledger reaches `failures >= 2`
for a task, a lander returns `escalate: yes` or `stuck`, or nothing is dispatchable.

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
