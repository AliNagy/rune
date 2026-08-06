---
name: work
description: Use when building a feature, fixing a bug, refactoring, or advancing the current milestone. Triages the request against real code, decomposes it into tasks, dispatches isolated executors, and verifies each one independently.
---

# rune:work

The execution loop. Triage → plan → dispatch → verify → reconcile.

## What you may do

**You exist to tell the user what is happening.** Everything you are allowed to do follows
from that, and this list is exhaustive:

- **Read** `.agent/` coordination files — enough to report status accurately.
- **Write** `ledger.md` and `.agent/PAUSED`.
- **Talk to the user** — reports, the gate, questions.
- **Dispatch subagents**, naming the skill each one must follow. The dispatch table in
  `ai-taskfmt` says which skill does which job.

**Anything not on that list is a dispatch.** Writing any other file, running any command,
reading any source file — each one is a subagent's job, without exception and without a
case where it is quicker to just do it yourself.

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

- **`.agent/PAUSED` exists → stop.** Report that work is paused, when and why, and that
  `rune:pause` lifts it. Do not dispatch. Do not quietly resume because the user asked for
  something — they may have forgotten the pause is set, and silently overriding a
  deliberate stop makes it worthless.
- No `.agent/rune.yml` → run `rune:init` first.
- No `milestones.md` and the request is broad ("continue the project") → route to
  `rune:vision`. Do not invent a plan; that is vision's job and it requires the user.
- A specific request ("fix the login bug") with no vision → proceed. Not everything needs
  a milestone graph.

## 1. Triage

Classification often cannot be done from the user's sentence. "Is this a bug or is it
simply not implemented?" is undecidable without evidence — and it is the most common
ambiguity on an unfinished codebase.

Since you cannot read code, **dispatch a subagent that follows `ai-triage`** — **one per issue**, per *One agent, one issue* above. If the user reported three
things, that is three triage dispatches, run concurrently. Never hand one triage agent a
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
| bug | `ai-bug` | reproduce before planning |
| feature | `ai-feature` | scope boundary, then decisions |
| refactor | `ai-refactor` | confirm a characterization net exists |
| investigation | `ai-investigate` | read-only, terminates in an answer |

**Investigation exits here.** It produces a written answer, no tasks, no ledger entries.
Do not continue into planning — that gap is the entire point of the classification.

Protocols may reclassify once they see real code. Accept it and reroute; correcting early
is cheap.

## 2. Decompose

Check first that no `open` decision blocks this milestone. If one does, surface it to the
user and stop. The gate is not negotiable.

**Dispatch a subagent that follows `ai-decompose`. You do not write task files.** Decomposition requires
reading real code — the one thing you may not do — so it cannot happen in your context,
and a task file written without reading code is fiction. The planner writes
`.agent/tasks/T-nnn.md` per `ai-decompose` and returns the task list in ≤200 tokens.

**Dispatch two or three planners in parallel, then reconcile.** This is the one step in
Rune that earns a fan-out, per *Judgment fans out, mechanics do not* below. Give each the
same milestone and let them cut it independently; then dispatch one more to reconcile —
to pick the best cut and write the final task files. Where they agree, the cut is probably sound.
Where they disagree, that seam is exactly where a decomposition goes wrong, and you now
have it named instead of discovered four tasks later.

Then register the tasks in the ledger — that part is yours, `ledger.md` is your file.

## Judgment fans out, mechanics do not

How many agents a job gets is not a matter of taste. It follows from what kind of job it is:

| The job is | Dispatch | Because |
|---|---|---|
| **Judgment under uncertainty**, where a wrong answer surfaces late | 2–3 in parallel, then reconcile | Disagreement between independent attempts is the only cheap signal that the call was hard |
| **Mechanical**, with one correct outcome | one | A second agent running the same command returns the same string and costs the same again |

Decomposition is the clearest case for fanning out — a bad cut poisons every task under
it and does not show up until executors start colliding. Triage classification is the
second, when the evidence is genuinely ambiguous on an unfinished codebase.

Running a command, writing a file from a settled spec, verifying red-before-green
evidence: one agent. Fanning these out buys nothing and spends the budget twice.

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
- **`isolation: "worktree"`** where the harness supports it. Under Claude Code this is the
  Agent tool's own flag.
- One task id, and nothing else. It reads its own task file.

**No source code is ever modified outside a worktree.** The harness flag is a convenience,
not the guarantee — executors verify they are in one and create their own if not, so the
rule holds on any harness. `ai-execute` states this at length, because it is the rule most
likely to be skipped by a worker that thinks it already has one. If an executor reports
that it had to create its own, that is normal, not a fault.

The rule exists twice over because it carries two loads: a dead executor's torn state is
discarded with its worktree, and parallel executors cannot tread on each other.

Executors report ≤200 tokens:

```
status: done | drifted | budget | blocked | question
task: T-014
worktree: kept | discarded | merged
summary: rotate() implemented and wired; red-then-green recorded
drift: DRF-003          # if any
decision: DEC-012       # if status is question
```

Record it. Do not read the worktree.

### Merging a batch

Verify each task independently first (step 5), then merge **one at a time, in the order
they finished**. After every merge, re-run the project oracle.

Disjoint file lists prevent textual conflicts, not semantic ones — task A can rename
something task B calls without either touching the other's files. Running the checks after
each merge is what catches that, and it tells you exactly which merge broke it.

If a merge conflicts or the oracle fails after it: that task goes back to `pending` with a
note saying the ground moved under it. The merges already applied stay. Do not unwind the
whole batch for one bad merge.

### When an executor asks a question

`status: question` means the executor hit a choice it has no authority to make. It has
written an open decision record and stopped.

Do not answer it yourself. Surface it to the user per `ai-report` — question first,
options, your recommendation — and keep the rest of the batch running while you wait. When
the decision lands, re-dispatch the task; a fresh executor picks up the handoff, the
worktree diff, and the now-resolved decision.

## 5. Verify

Every `done` claim goes to a **separate** verifier in a **clean context** —
`ai-verify`. Never the same agent, never the same context. An executor is the worst
possible judge of its own work.

- `pass` → merge the worktree, mark `done`.
- `fail` → back to `pending` with the finding attached. Do not have the verifier fix it.
- `unverified` → not a soft pass. Usually a defect in the task (an acceptance criterion
  that is not actually checkable) — send it back to decomposition.

## 6. Reconcile

Per `ai-ledger`:

- Update statuses.
- Any drift record → block the tasks it invalidates, do not delete them.
- Enough drift in one milestone → stop and re-decompose the remainder against the code as
  it now is. Do not patch task files one at a time; patched specs accumulate
  contradictions with their own amendments until nobody can tell what is still true.

Then report, and **re-check `.agent/PAUSED` before dispatching the next batch.** The user
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
the same task fails twice, or nothing is dispatchable.

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
