# Rune

A Claude Code plugin for building software **without letting any single context window
blow up**.

The premise: you cannot get small contexts by telling an agent to be brief. You get them
by moving the project's state out of the context window and onto disk. The plan becomes
the durable artifact; every agent is a short-lived worker that loads one slice of it, does
the work, writes back, and dies.

Target: under ~150k context per unit of work, on projects of any size.

## Requirements

| | |
|---|---|
| **Claude Code** | Recent enough to have `/plugin`. Run `/help` — if you don't see it, update. |
| **git** | Required. Every task executes in its own worktree, and `git diff` is how Rune knows what changed. A repo that isn't under git loses its rollback story entirely. |
| **[Serena](https://github.com/oraios/serena)** | Strongly recommended, as an MCP server. Symbol-level lookup instead of whole-file reads is the single largest lever on the context budget. Rune works without it, but the effective budget per task drops considerably. |

## Install

```
/plugin marketplace add AliNagy/rune
/plugin install rune@rune
```

If the install summary says to, run `/reload-plugins`.

To try it against a local clone before installing:

```bash
claude --plugin-dir /path/to/rune
```

Skills, subagents, and model tiering all install together — there is nothing to copy by
hand.

### OpenCode

Rune is authored for Claude Code, but a generator emits an OpenCode variant:

```bash
node scripts/sync-opencode.mjs
```

Skills become `/rune-init`, `/rune-vision`, and so on. See [docs/opencode.md](docs/opencode.md)
for options and — importantly — the known gaps, chiefly that OpenCode has no worktree
isolation for subagents, which weakens the stateless-restart guarantee.

## Use

| You want to | Run |
|---|---|
| Start on a repo for the first time | `/rune:init` |
| Map out what you're building | `/rune:vision` |
| Build a feature, fix a bug, refactor | `/rune:work` |
| Stop work cleanly, or check if it's stopped | `/rune:pause` |
| Move to a fresh session before context fills | `/rune:handoff` |
| Pick up in a fresh session | `/rune:continue` |

Those six are the whole interface. The twelve `ai-*` skills load themselves when the
situation calls for them and stay out of your slash-command palette.

Typical first run on an existing project:

```
/rune:init        establishes the oracle, maps the codebase
/rune:vision      surveys, interviews you, maps discrepancies, emits milestones
/rune:work        decomposes milestone 1 and starts executing
```

New project, no code yet: `/rune:vision` first — init runs afterward, once the stack
exists to inspect.

`/rune:work` stops and shows you the plan before any executor runs. Pass `--auto` to skip
that gate once you trust it.

## What Rune writes into your repo

Everything durable lives in `.agent/`:

```
.agent/
  rune.yml               oracle, build commands, git baseline, staleness stamp
  map.md                 module map, entry points, conventions, danger zones
  vision.md              the vision document
  decisions.md           decision records — open ones block milestone generation
  milestones.md          the road to v1
  ledger.md              all mutable state. single writer: the dispatcher
  tasks/T-nnn.md         immutable task specs + appended amendments
  notes/T-nnn.md         handoff notes and long results
  drift/DRF-nnn.md       misconceptions, and which tasks they invalidate
```

**Commit it.** The vision, decisions, milestones, and ledger are project knowledge worth
versioning and reviewing — they're written to be read by humans, not just agents. Worktrees
are the exception; add `.agent/worktrees/` to your `.gitignore`.

Deeper background that only agents need — subsystem explanations, architectural gotchas —
goes into Serena memories rather than `.agent/`, so the human-facing files stay readable.

## How it works

Four phases.

**1 · Ground** — `/rune:init` finds and *runs* the pass/fail command that proves the
codebase works. If there isn't one, it says so loudly and enters degraded mode rather than
papering over it. Also maps modules, conventions, and danger zones.

**2 · Road** — `/rune:vision` interviews you to build the project vision, then breaks it
into milestones. Every open choice becomes a decision record, and **no milestone may be
generated that depends on an undecided one** — that's what makes "suggest, never assume" a
checkable property rather than a hope.

**3 · Work** — `/rune:work` triages the request into bug / feature / refactor /
investigation (each has its own protocol), decomposes the current milestone into tasks
*just-in-time* against real code, dispatches an isolated executor per task, then verifies
each in a separate clean context.

**4 · Resume** — `/rune:continue` reads disk, reconciles state left by a dead session, and
routes back into whichever phase you were in.

## The design decisions that matter

**Stateless executors, disk as the only memory.** Resuming a paused agent preserves its
context — which is the opposite of what you want when context is the budget you're
defending. An executor that hits trouble writes a handoff note and dies; a fresh one
restarts from the task file. Under Serena, re-acquiring a working set costs ~10k.

**The parent never reads code.** With subagent dispatch, the dispatcher accumulates every
result. One "just checking" file read imports the exact cost the system exists to avoid.
Subagents return ≤200 tokens; anything longer goes to disk.

**Tasks are encapsulated.** Each carries its own goal, change surface, acceptance
criteria, and test. A task can be executed, retried, or reviewed with no knowledge of its
siblings.

**Red before green.** A task's test must be observed *failing* before the change is made,
with evidence recorded. A test written after the fix and never seen red proves nothing,
and a clean-context verifier can't tell it from a real one.

**Edit first, then tick.** If a process dies between making a change and recording it, the
only reachable desync is a *missing* record — which self-heals, because the next executor
finds the step already applied. The reverse order leaves a record with no change, which
makes real work get skipped.

**git is the journal.** Each executor works in its own worktree. `git diff` is the
authoritative record of what changed — atomic with the edit by construction, so it cannot
desync from reality the way a hand-maintained progress file can.

**Milestones are planned fully; tasks are not.** A task must name real files and real
symbols. For a milestone three steps out those files don't exist yet, so anything written
now is fiction that drifts on contact. Plan the whole road, pave one section at a time.

**Tasks run in parallel when their file lists don't overlap.** Up to three at once, each
in its own worktree, merged one at a time with the checks re-run after each — because
disjoint file lists rule out textual conflicts but not semantic ones.

**Executors can ask you something.** A worker that hits a choice you'd want a say in
writes an open decision with its recommendation and stops, rather than guessing. It only
asks when the answer changes behaviour you'd notice and neither the task nor the
surrounding code settles it.

**You hear from it at every checkpoint.** After each task, each batch, each milestone, and
every blocker — TL;DR first, plain words, no commentary in between.

**Pausing drains rather than aborts.** `/rune:pause` stops new work and lets what's
running finish and merge, so you're never handed a half-applied change. The flag lives on
disk, so nothing lifts it silently — not a new session, not a new request.

**A killed session is recoverable, not just resettable.** Because edits always land before
they're recorded, the only possible desync is a missing record — so the diff can be mapped
back onto the task's declared steps to find the exact resume point. `/rune:continue` sends
that diagnosis to a subagent rather than guessing or discarding by default.

**Handing off is a first-class step, not a summary.** `/rune:handoff` sorts what's in the
conversation into what belongs on disk permanently — conventions, decisions, constraints —
and what's merely session context, then gives you three lines to paste into a fresh
session.

## Layout

```
.claude-plugin/
  plugin.json        the manifest
  marketplace.json   so the repo is directly installable

skills/
  init  vision  work                    you invoke these, as /rune:<name>
  pause  handoff  continue

  ai-taskfmt      the file schemas — the spine
  ai-report       when to speak to the user, and how
  ai-serena       context-frugal code access
  ai-recover      salvaging a task abandoned mid-flight
  ai-oracle       establishing and running pass/fail checks
  ai-survey       codebase reconnaissance
  ai-decompose    milestone to tasks, sizing rules
  ai-bug          reproduce before planning
  ai-feature      vertical slices, decisions first
  ai-refactor     characterization net, no test edits
  ai-investigate  read-only, terminates in an answer
  ai-drift        when the plan turns out wrong
  ai-verify       independent verification
  ai-ledger       state ops and crash reconciliation

agents/
  surveyor  triage  executor  verifier    sonnet
  planner                                 opus
```

The model tiering is the point of that last block: the bulk of the work runs cheap, and
only decomposition — where a bad cut poisons everything downstream — runs on the stronger
model.

## Versioning

Tagged `vMAJOR.MINOR.PATCH`, matching `version` in `plugin.json`. Because that field is
set, installed copies only update when it changes — so every release bumps it.

Pre-1.0, minor versions may break the `.agent/` file formats. `/rune:continue` will tell
you if it finds a layout it doesn't recognise rather than guessing.

## Status

**Untested.** `v0.1.0` is a first cut: the skills are written and internally consistent,
and the plugin manifest validates, but this has not yet been exercised end to end on a
real repository. Expect to adjust:

- the ≤200 token return discipline (models overshoot it)
- worktree isolation behaviour on Windows paths
- whether the plan-approval gate lands at the right frequency or becomes noise

Start with `/rune:init` on a low-stakes repo — it's read-only and will immediately tell
you whether oracle detection works on your stack.

## License

MIT — see [LICENSE](LICENSE).
