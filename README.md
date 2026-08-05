# Rune

A Claude Code plugin for building software **without any single context window filling
up**.

The idea: you can't get small contexts by telling an agent to be brief. You get them by
keeping the project's state on disk instead of in the conversation. The plan is the part
that lasts; every agent is short-lived — it loads one slice of the plan, does the work,
writes the result back, and exits.

Target: under ~150k context per piece of work, on projects of any size.

## Requirements

| | |
|---|---|
| **Claude Code** | Recent enough to have `/plugin`. Run `/help` — if you don't see it, update. |
| **git** | Required. Every task runs in its own worktree, and `git diff` is how Rune knows what changed. Without git there's no way to undo a bad change. |
| **[Serena](https://github.com/oraios/serena)** | Strongly recommended, as an MCP server. Looking up individual functions and classes beats reading whole files, and it saves more context than anything else here. Rune works without it, but each task gets much less room. |

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

Skills, subagents, and the model settings all install together — there is nothing to copy
by hand.

### OpenCode

Rune is written for Claude Code, but a script generates an OpenCode version:

```bash
node scripts/sync-opencode.mjs
```

Skills become `/rune-init`, `/rune-vision`, and so on. See
[docs/opencode.md](docs/opencode.md) for options and — importantly — the known gaps, mainly
that OpenCode can't give subagents their own worktrees, so their work is less isolated.

## Use

One command, and you don't need to know the others:

```
/rune:hello
```

Say what you want in plain language — "start a new project", "fix the login bug", "where
were we", "stop". It reads the state, works out where that goes, and takes you there.

The direct commands still exist if you prefer them:

| You want to | Run |
|---|---|
| Start on a repo for the first time | `/rune:init` |
| Map out what you're building | `/rune:vision` |
| Build a feature, fix a bug, refactor | `/rune:work` |
| Stop work cleanly, or check if it's stopped | `/rune:pause` |
| Move to a fresh session before context fills | `/rune:handoff` |
| Pick up in a fresh session | `/rune:continue` |

The fourteen `ai-*` skills load themselves when they're needed and stay out of your
slash-command list.

Typical first run on an existing project:

```
/rune:init        finds and runs the command that proves the code works, maps the codebase
/rune:vision      looks around, asks you questions, notes what doesn't match, writes milestones
/rune:work        breaks milestone 1 into tasks and starts building
```

New project, no code yet: `/rune:vision` first — init runs afterward, once there's a stack
to look at.

Before any code is written, work stops once and shows you the plan, the assumptions it
made, and what it's leaving out — then asks what you'd like to add. You can't turn that
off.

## What Rune writes into your repo

Everything worth keeping lives in `.agent/`:

```
.agent/
  rune.yml               test command, build commands, git starting point, last-checked date
  map.md                 module map, entry points, conventions, risky areas
  vision.md              the vision document
  decisions.md           decisions made and still open — open ones block milestones
  milestones.md          the road to v1
  ledger.md              everything that changes as work runs. only the main session writes here
  tasks/T-nnn.md         task specs. never edited; changes are appended
  notes/T-nnn.md         handoff notes and long results
  drift/DRF-nnn.md       what the plan got wrong, and which tasks that invalidates
```

**Commit it.** The vision, decisions, milestones, and ledger are project knowledge worth
versioning and reviewing — they're written to be read by people, not just agents.
Worktrees are the exception; add `.agent/worktrees/` to your `.gitignore`.

Background that only agents need — how a subsystem works, where the sharp edges are — goes
into Serena memories rather than `.agent/`, so the files people read stay readable.

## How it works

Four phases.

**1 · Set up** — `/rune:init` finds and *runs* the pass/fail command that proves the
codebase works (`rune.yml` calls it the oracle). If there isn't one, it says so loudly and
works in a reduced mode rather than pretending otherwise. It also maps modules,
conventions, and risky areas.

**2 · Plan** — `/rune:vision` asks you about the project to build the vision, then breaks
it into milestones. Every open choice is written down as a decision, and **no milestone can
be generated while a decision it depends on is unanswered** — which is what turns "suggest,
never assume" into something you can check.

**3 · Build** — `/rune:work` sorts the request into bug / feature / refactor /
investigation (each has its own approach), breaks the current milestone into tasks — only
when it's time to build them, against real code — sends each task to its own agent, then
checks each one in a separate, fresh context.

**4 · Resume** — `/rune:continue` reads disk, sorts out state left behind by a dead
session, and puts you back into whichever phase you were in.

## The design decisions that matter

**Agents restart instead of resuming.** Resuming a paused agent keeps its context — the
opposite of what you want when context is the thing you're trying to save. An agent that
runs into trouble writes a handoff note and exits; a fresh one starts again from the task
file. With Serena, getting back up to speed costs about 10k.

**The main session never reads code.** When it dispatches subagents, everything they
return piles up in its context. One "just checking" file read brings back the exact cost
the whole design avoids. Subagents return 200 tokens or less; anything longer goes to disk.

**Each task stands on its own.** A task carries its own goal, the files it may touch, what
counts as done, and its test. It can be run, retried, or reviewed without knowing anything
about the other tasks.

**The test has to fail first.** A task's test must be seen *failing* before the change is
made, with the evidence recorded. A test written after the fix and never seen failing
proves nothing, and a reviewer working in a fresh context can't tell the two apart.

**Make the change, then record it.** If a process dies between making a change and
recording it, the only way things can end up out of step is a *missing* record — which
fixes itself, because the next agent finds the step already done. The other order leaves a
record with no change behind it, which makes real work get skipped.

**git is the record.** Each agent works in its own worktree, and `git diff` is the
authoritative account of what changed. It can't drift from reality the way a hand-updated
progress file can.

**Milestones are planned in full; tasks are not.** A task has to name real files and real
functions. For a milestone three steps out, those files don't exist yet, so anything
written now is fiction that falls apart on contact. Plan the whole road, pave one section
at a time.

**Tasks run in parallel when their file lists don't overlap.** Up to three at once, each in
its own worktree, merged one at a time with the checks re-run after each — because separate
file lists rule out conflicting edits but not conflicting behaviour.

**Agents can ask you things.** An agent that hits a choice you'd want a say in writes down
the open question along with its recommendation and stops, rather than guessing. It only
asks when the answer changes behaviour you'd notice and neither the task nor the
surrounding code settles it.

**You hear from it at every checkpoint.** After each task, each batch, each milestone, and
every blocker — summary first, plain words, no filler in between.

**Pausing lets running work finish.** `/rune:pause` stops new work starting and lets what's
already running finish and merge, so you're never left with a half-applied change. The flag
lives on disk, so nothing clears it quietly — not a new session, not a new request.

**A killed session can be picked up, not just reset.** Because changes always land before
they're recorded, the only thing that can be missing is a record — so the diff can be
matched against the task's steps to find exactly where to resume. `/rune:continue` hands
that diagnosis to a subagent instead of guessing or throwing the work away.

**Handing off is a real step, not a summary.** `/rune:handoff` sorts what's in the
conversation into what belongs on disk for good — conventions, decisions, constraints — and
what was only useful for this session, then gives you three lines to paste into a fresh
one.

**Nothing is built outside a worktree.** Agents check for one and create their own if they
weren't given one, so the guarantee doesn't depend on which tool you're running.
Coordination files still go to the main tree — they're needed before anything merges.

**It always asks before it builds.** Every run stops once to show you the plan, the
assumptions it made on your behalf, and what it's deliberately leaving out — then asks what
you'd like to add. There's no flag to skip it.

## Layout

```
.claude-plugin/
  plugin.json        the manifest
  marketplace.json   so the repo can be installed directly

skills/
  hello                                 the one command that routes to the rest
  init  vision  work                    or call these directly, as /rune:<name>
  pause  handoff  continue

  ai-taskfmt      the file formats everything else depends on
  ai-report       when to talk to the user, and how
  ai-serena       reading code without spending much context
  ai-recover      salvaging a task that stopped halfway
  ai-oracle       finding and running the pass/fail check
  ai-survey       looking around an unfamiliar codebase
  ai-decompose    milestone to tasks, and how big a task should be
  ai-bug          reproduce before planning
  ai-feature      thin end-to-end slices, open questions decided first
  ai-refactor     cover behaviour with tests first, then leave them alone
  ai-investigate  read-only, ends in an answer
  ai-drift        when the plan turns out to be wrong
  ai-verify       an independent second check
  ai-ledger       state updates, and cleaning up after a crash

agents/
  surveyor  triage  executor  verifier    sonnet
  planner                                 opus
```

That last block is about cost: most of the work runs on the cheaper model, and only the
step that splits a milestone into tasks — where a bad split ruins everything after it —
runs on the stronger one.

## Versioning

Tagged `vMAJOR.MINOR.PATCH`, matching `version` in `plugin.json`. Because that field is
set, installed copies only update when it changes — so every release bumps it.

Before 1.0, minor versions may break the `.agent/` file formats. `/rune:continue` will tell
you if it finds a layout it doesn't recognise rather than guessing.

## Status

**Untested.** `v0.1.0` is a first cut: the skills are written and consistent with each
other, and the plugin manifest validates, but this has not yet been run end to end on a
real repository. Expect to adjust:

- the 200-token limit on what subagents return (models go over it)
- how worktrees behave on Windows paths
- whether stopping for plan approval happens at the right times or just gets annoying

Start with `/rune:init` on a low-stakes repo — it only reads, and it will tell you right
away whether it can find the test command for your stack.

## License

MIT — see [LICENSE](LICENSE).
