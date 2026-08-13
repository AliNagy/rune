# Task tiers

A proposal, not shipped behaviour. Nothing in `skills/` implements this yet.

Rune dispatches every worker at whatever the session runs on. That is the cheapest possible
policy to state and the most expensive one to run: a rename across four files and a
lock-ordering bug get the same model, because nothing in the system has ever asked how hard
a task is.

This document works out what asking would take.

## Size is not difficulty

Rune already reads every new task cold and judges it. `rune-size` asks whether one fresh
agent could finish the whole lifecycle with room to spare, and answers `pass | split |
blocked`. That gate is close to what is needed here and is not it.

Sizing measures **volume** — how much has to pass through one context window. Difficulty
measures **depth** — how much reasoning each unit of that volume demands. They come apart
in both directions:

| Task | Size | Difficulty |
|---|---|---|
| rename a symbol across five files in one module | at the limit | near zero |
| reorder two lock acquisitions in one function | trivial | maximum |

A tier derived from size would route the second one cheap, which is the exact failure the
mechanism exists to prevent. So difficulty needs its own verdict, on its own evidence.

This is the same argument `rune-size` already makes one level down: the five-file rule is
"necessary and not sufficient", because five files can be a small job or an enormous one.
File count does not determine size, and size does not determine difficulty. Each step needs
its own read.

## The grade rides on a read that already happens

Difficulty grading needs an agent that reads one task cold, from disk, without the context
that produced it, before it can be dispatched. Rune has exactly one of those, and it runs on
every new task including replacements and re-cuts: the sizing worker.

So the grade costs **no extra dispatch**. It is one more field on a return that already
crosses the seam, from a worker that has already paid to read the task, the map, and enough
symbols to judge it. Any other placement pays the read a second time.

The objection is real: one worker answering two questions lets one verdict contaminate the
other — *it is small, so it must be easy*. Three things contain that:

- The two verdicts must be justified on **different evidence lines**. A tier that cites the
  change surface has cited the size evidence and is not a grade.
- The tier verdict may never change the size verdict. A `split` is a `split` whether the
  work is mechanical or not.
- `split` and `blocked` carry no tier at all. A contract about to be retired is not worth
  grading, and its replacements are graded when they are written.

If that proves insufficient in practice, the fallback is a second concurrent worker on the
same pointers. Start with one; the cost of being wrong here is a second read, not a bad
landing.

## The scale

Three tiers. Not five — a scale needs each step to be distinguishable by an agent reading a
task cold, and five would produce a middle three that graders cluster on because nobody can
tell them apart. Rune's house style everywhere else is a short enumeration with hard
boundaries, and this follows it.

Each tier is defined by **what the task demands**, not by how it feels:

| Tier | Name | The task demands |
|---|---|---|
| `T1` | mechanical | The change is fully determined by the task file. Steps name the symbols, the check says how you know, and no step chooses between two defensible implementations. The job is transcription plus care. |
| `T2` | pattern | The change is determined but must first be *found*. Follow a call path, match a convention, copy an established shape. Local choices exist and are bounded by precedent that is present in the repo and can be read. |
| `T3` | novel | Something here is not resolved by reading. Concurrency, an invariant spanning modules, a design decision embedded in the implementation, a failure mode that must be anticipated rather than observed, or a check that could pass for the wrong reason. |

**Every step up must be earned by naming its reason.** A T2 names the lookup the task
depends on. A T3 names the reasoning the reading does not settle. A grade that cannot name
the thing that lifted it is a T1 with an opinion attached — this is what keeps the scale
from inflating into a vibe.

**Between two tiers, take the higher.** Naming discipline stops inflation; this stops the
optimism that would otherwise make every grade a T1. Both are needed, and they do not
conflict: the first governs whether a reason exists, the second governs what to do once one
does.

### Ceilings

Some properties force `T3` whatever the surface looks like, because their failures are the
ones that do not show up in the check:

- concurrency, ordering, or anything with a happens-before argument
- data migration, or any change whose failure is not reversible by reverting the commit
- security-relevant surfaces — authn, authz, secrets, input trust boundaries
- `remediation: mitigation` — deliberately doing the wrong thing on purpose, which must
  neither become permanent nor be mistaken for the fix
- `verification: characterization` — pinning behaviour nobody has yet understood

Tasks whose steps are still undecided need no ceiling rule. `rune-size` already returns
`split` for them.

## What a tier reaches

A task tier only exists for task-bound work. Triage, decomposition, survey, and research
have no task to grade and still have to be dispatched at something. They get a **role
floor** instead — a minimum that holds regardless of any task:

| Role | Floor | Why |
|---|---|---|
| `decompose` | T3 | A bad cut poisons every task under it and surfaces four tasks later. The highest-leverage judgment in the system. |
| `size` / grading | T3 | See below. |
| `verify`, `verify-finding` | T3 | See below. |
| `triage`, `research`, `investigate`, `drift`, `recover` | T2 | Classification and salvage errors route everything downstream of them. |
| `survey` | T2 | Written once, read by everything afterwards. |
| `execute` | T1 | The task tier does the work here. This is the floor the savings come from. |
| `oracle`, `land` | T1 | Run a command, merge a named SHA, report what happened. Genuinely mechanical. |

One composition rule covers every dispatch in the system:

```
effective tier = max(role floor, task tier, escalations so far)
```

Total, single-line, and it degrades cleanly — a job with no task tier is just its floor.

## The rule that makes this safe

Routing cheap is safe exactly where failure is **loud**.

An executor that was graded too low fails visibly: its check stays red, or the verifier
catches it. The system already has machinery for that — retries, failure counts, a
two-failure stop rule. Grading it wrong costs a wasted attempt and gets corrected.

A verifier graded too low fails **silently**. A false pass is byte-identical to a true pass.
There is no downstream check on the checker, and the artifact lands. Same for the grader
itself: a low-tier agent cannot recognise work above its own ceiling, so it under-grades
systematically and its errors correlate rather than cancel.

> **Savings come from the loud roles. The silent ones never run below the top tier.**

That is the whole safety argument, and it is why the floors table above puts `verify`,
`verify-finding`, and grading itself at T3 permanently. It also means the gate is not where
you economise: grading is one small cold read, executing is the long expensive loop.
Cheapening the gate to save on grading breaks the mechanism that produces every other
saving.

This is not a new principle for Rune. It is the existing one — *work is checked, not
claimed* — carried into a place where it would otherwise be quietly abandoned.

## Escalation

A wrong grade must correct itself, or a low tier becomes a loop that burns three cheap
attempts on a task that needed one expensive one.

**A verifier `fail` escalates the task one tier for the retry, and the escalation is
recorded.** T1 that failed verification retries at T2, not T1 — the grade has been
falsified by evidence, and repeating it is the one thing the evidence rules out. At T3 the
existing two-failure stop rule takes over unchanged; there is nowhere further to escalate,
and a second failure was already a signal about the plan rather than the attempt.

Escalation is a ledger transition like any other, written by the parent, in the same atomic
update that consumes the verdict. It bounds the cost of a wrong grade and, over a project,
produces the only number that says whether the grading works at all.

## Where the tier lives

The tier is mutable routing state that the parent reads to decide a dispatch. In Rune that
is the definition of a ledger column.

It cannot go in `tasks/T-nnn.md`: those are immutable from creation, and escalation changes
the tier. It cannot go in `notes/T-nnn.sizing.md` either — the parent would be reading a
worker's note on every dispatch, and escalation would put a second writer in a sole-writer
file.

So: **schema 3, one appended `tier` column**, valid values `T1 | T2 | T3 | —`.

`rune-ledger` states that adding a column creates a new schema version rather than an
optional fact some readers ignore. That is the stated price and this pays it, rather than
smuggling routing state into an artifact that was not built to carry it.

Consequences, all of which follow existing rules rather than adding any:

- **The `unsized -> pending` transition requires a tier.** A `sizing: pass` with no tier is
  an invalid return. That is what guarantees no dispatchable row is ever ungraded.
- **`split` and `blocked` rows keep `tier: —`** and stay `unsized`, as they already do.
- **Migration from schema 2 appends the column with `—`**, exactly as schema 1 → 2 appended
  `replaced_by`. No regrade dispatches, no new work at migration time.
- **`—` routes as T3.** An ungraded row is not a cheap row. Never guess downward.

## Whether this actually saves anything

Worth doing the arithmetic rather than assuming, because the intuition here is wrong in an
interesting way.

Let the top tier cost `1`, a low tier cost `c`, a verification round cost `v`, and `p` be
the fraction of low-graded tasks that escalate. Routing everything high costs `1`. Routing
low costs `c` always, plus the full price and an extra verification round when it escalates:

```
c + p(1 + v) < 1        →        p < (1 - c) / (1 + v)
```

At `c = 0.2` and `v = 0.3`, break-even sits near **`p ≈ 0.6`**. Low-tier routing wins unless
it is wrong most of the time. The margin is much wider than it feels, and the reason is that
the wasted cheap attempt is cheap — that is what makes it a cheap attempt.

Which means **misrouting is not the risk this design has to defend against.** The formula
has no term for a wrong T1 that a cheap verifier waves through, because that cost does not
appear as a retry. It appears as a landed commit that is subtly wrong, discovered later,
attributed to nothing. That failure is unbounded and invisible, and it is entirely a
property of who verified — not of who executed.

Hence the split above. The executor is where the money is and where mistakes are loud. The
verifier is neither. A tier system that cheapens both saves ~20% and loses the property the
rest of Rune is built to provide.

## Calibration

The escalation rate is the number that decides whether grading is working, and it is free —
the ledger already counts verifier failures, and escalation records the rest.

- **Low escalation, mostly T1/T2 grades** — working. A mature codebase should grade mostly
  low, because most work in one follows patterns that already exist in it.
- **Escalation above ~50%** — the grader is systematically optimistic. Long before the
  arithmetic turns negative, the grade has stopped carrying information.
- **Almost everything graded T3** — also a failure, and the likelier one. Nothing is being
  saved and a step was added to every task for nothing.

A user override is allowed — it is their money — but an override downward is recorded as an
override rather than as a grade, so that escalation data stays honest about what the grader
actually said.

## Still no models

None of this names a model, and the rule at `rune-taskfmt` should not be deleted but
narrowed:

> **Never specify a model.** Name the tier a job requires; the harness maps tiers to models.
> A worker runs at whatever its effective tier resolves to in this harness.

That preserves the property the whole no-agents decision was made to protect. Rune states a
capability requirement, which is a fact about the task and travels unchanged. The mapping is
harness configuration, which is spelled differently everywhere and travels nowhere.

Where the harness offers only one model, tier routing is unavailable and every dispatch is
that model. **Grades are still recorded** — they cost nothing extra, and they are the
calibration data that says whether routing would have been worth switching on.

## What this does not do

- It does not grade milestones, requests, or projects. Only tasks, and only after one has
  been written.
- It does not let a planner grade its own cut. Same reason the sizer is blinded to the
  planner's reasoning today.
- It does not make an ungraded task cheap.
- It does not change what any tier *means* over time. A grade is a claim about the task, not
  about the model that happened to be available the week it was written.

## Open decisions

These change the shape of the work and are the user's call:

1. **One gate or two.** Extend `rune-size` to return a tier, or add a separate grading
   worker on the same pointers. One is cheaper and risks contamination; two is clean and
   pays the cold read twice.
2. **Does `unsized` get renamed.** The status would now mean "has not passed the pre-dispatch
   gate", covering two questions. Renaming it is honest and touches every route that
   references it; keeping it is cheap and slightly imprecise.
3. **Where the tier → model mapping is declared.** Harness-side only, as proposed — or a
   `tiers:` block in `rune.yml`, which is more usable but puts harness-specific identifiers
   into project state.
4. **Whether verification tracks the task tier at all.** This proposal pins it at T3
   permanently. The cheaper alternative is verifier tier = task tier, which saves on the
   majority of tasks and forfeits the argument in *The rule that makes this safe*.

## Vocabulary

**Task tier**:
The graded capability demand of one task, decided by a cold read before dispatch.
_Avoid_: difficulty score, complexity rating, task weight

**Role floor**:
The minimum tier a role runs at regardless of which task it is given, or whether it has one.
_Avoid_: default model, role default

**Effective tier**:
The value a dispatch actually resolves to — the maximum of role floor, task tier, and
recorded escalations.
_Avoid_: final tier, resolved model

**Escalation**:
A recorded tier increase after an attempt failed verification. It is evidence about the
grade, not a preference about the retry.
_Avoid_: retry at a better model, upgrade
