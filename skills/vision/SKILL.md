---
name: vision
description: Use when a project has no plan yet - a new idea with no code, or an in-progress codebase that has drifted and needs its road to a working first version mapped. Interviews the user, surfaces every open decision, and produces the milestone graph.
---

# rune:vision

Builds the vision, then the milestone graph that reaches v1. This is a **conversation**,
not a generation task. Take the time it needs.

**You do not read source code.** Survey runs as a subagent. Your context is for the
interview.

## First: is the ground ready?

Check `.agent/rune.yml`.

- **Missing, and the repo has code** → run `rune:init` first. Do not ask; just do it and
  say so. Vision without a map produces a plan disconnected from the codebase.
- **Missing, and the repo is empty** → new project. Vision runs first; init runs after the
  stack is chosen and scaffolded.
- **Present but stale** → mention it, offer a re-run, proceed if the user declines.

## Mode A · New project

Nothing exists. Build the whole picture before any code.

Work through these in order, one topic at a time. **Do not dump all questions at once** —
each answer reshapes what is worth asking next.

1. **What and why.** What is this, who is it for, what does it replace or improve? What
   does the user do with it on day one?
2. **The v1 line.** What is the smallest version that is genuinely useful? What is
   explicitly *not* in it? This is the most valuable question in the interview and the
   one users most want to skip.
3. **Shape.** Web app, CLI, service, library, mobile? Single or multi-user? Online or
   offline? Where does it run?
4. **Data.** What entities exist, what relationships, what must persist, what must never
   be lost?
5. **Stack.** Language, framework, storage, hosting. Each becomes a decision record.
6. **Constraints.** Deadlines, team size, existing systems to integrate, things the user
   already knows they want to avoid.
7. **Done.** How will the user know v1 works? This becomes milestone acceptance.

## Mode B · In-progress project

1. **Survey** — dispatch `ai-survey` (subagent, cheap model). Returns stack,
   modules, conventions, and the completeness assessment: stubs, orphans, half-wired
   paths, contradictions, abandoned directions.
2. **Present what is there.** Show the user what actually exists — including the awkward
   parts. Frequently they do not know a subsystem was abandoned half-built.
3. **Interview** — same topics as Mode A, but anchored to reality. "The billing module
   has no inbound references. Is that planned work, abandoned, or should it be deleted?"
4. **Discrepancy map** — the deliverable of this mode. Intended vision vs. surveyed
   reality:

```markdown
## Discrepancies
| # | intended                      | actual                              | gap        |
|---|-------------------------------|-------------------------------------|------------|
| 1 | sessions survive restart      | in-memory only, lost on restart     | build      |
| 2 | one user model                | two: models/User, db/user           | reconcile  |
| 3 | billing                       | scaffolded, unwired, no tests       | finish/cut |
| 4 | admin CLI                     | complete and working                | none       |
```

Each non-`none` row becomes a milestone or part of one. Row 3 needs a user decision —
finishing and deleting are both legitimate, and the agent may not choose.

## The rule that matters

**Suggest. Never assume.**

Every choice with more than one defensible answer becomes a decision record in
`.agent/decisions.md`, per `ai-taskfmt`:

```markdown
## DEC-007 · State management
status: open
options:
  - Zustand — light, minimal ceremony
  - Redux Toolkit — heavier, more structure, familiar
recommendation: Zustand
decided: —
rationale: —
```

**Gate: no milestone may be generated that depends on an `open` decision.**

That is what makes "no assumptions" checkable instead of aspirational. Recommend freely —
an opinion with reasoning is exactly what the user wants. Adopting it silently is the
failure.

When the user says "you decide": record it as `decided` with `rationale: delegated to
agent`, and state the choice explicitly. Delegation is fine. Invisible delegation is not.

## Leave no stone unturned

Before generating milestones, sweep for the things users forget and agents assume:

auth and permissions · error handling and what the user sees when it breaks · empty and
loading states · data validation · migrations and seed data · configuration and secrets ·
logging · deployment target · backup and recovery · who else touches this code

Anything unanswered is an open decision, not a default.

## Milestones

Only once every blocking decision is `decided`. Write `.agent/milestones.md` per
`ai-taskfmt`.

- **Ordered by dependency**, not by importance.
- **Each independently demonstrable.** "Auth works end to end" — not "the database
  layer", which cannot be shown to anyone.
- **M-01 is a thin end-to-end slice**, not foundations. One path through the whole stack.
  It validates the shape against real code before four milestones are built on an
  assumption.
- **Scope in *and* out** on every milestone.
- **Acceptance criteria** phrased as things a person can observe.

Do **not** break milestones into tasks here. A task must name real files and real
symbols; for M-04 those do not exist yet, and anything written now is fiction. `rune:work`
decomposes just-in-time. (M-01 is the exception — its ground state is known and it may be
decomposed immediately.)

## Resumability

A thorough interview is long. **Write `vision.md` and `decisions.md` incrementally**, as
each section settles — never only at the end.

If the session ends mid-interview, `rune:continue` picks up from the last settled
section and the open decision queue. Nothing is held in conversation memory.

## Finishing

```
Vision complete · 6 milestones to v1

  M-01  thin slice: login → dashboard          ← start here
  M-02  session lifecycle
  M-03  profile CRUD
  ...

  decisions   9 decided · 0 open
  discrepancies  3 gaps mapped (billing: user chose to cut)

Next: /rune:work to decompose and start M-01.
```
