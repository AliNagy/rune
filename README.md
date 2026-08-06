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

The fifteen `ai-*` skills load themselves when they're needed and stay out of your
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

You invoke one skill; it loads the others.

Rune is 22 skills, but only seven can be called by name — `hello`, `init`, `vision`,
`work`, `pause`, `handoff`, `continue` — and `hello` picks between those for you. The other
fifteen are marked as not user-invocable. The agent loads them itself when the situation
calls for one: `/rune:work` triages a request as a bug and pulls in `ai-bug`; the agent it
sends off to write the code pulls in `ai-taskfmt` and `ai-serena`.

The reason is the same one behind everything else here. Instructions for all 22 skills in
one context window would crowd out your actual code, and most of them are irrelevant at any
given moment. Loading them on demand means each agent carries only the rules for the job in
front of it — and you only have to remember one command.

Four phases:

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

## Why it's built this way

**Context is the budget.** The main session never reads source code — it holds the ledger
and short reports, nothing else. One "just checking" file read would bring back the exact
cost the design exists to avoid. Subagents return 200 tokens or less; anything longer goes
to disk. Each one carries exactly one issue — one bug, one task, one question, never a
batch — so three reported bugs get three agents, running at the same time if they can;
that keeps evidence from one out of the reading of another, and keeps one agent from
holding three working sets. And an agent in trouble writes a handoff note and exits rather
than pausing,
because resuming an agent keeps its context, which is the opposite of what you want here. A
fresh one starts again from the task file — with Serena, about 10k to get back up to speed.

**Interrupting it is safe.** Every task runs in its own git worktree, and `git diff` is the
authoritative record of what changed; it can't drift from reality the way a hand-updated
progress file can. Changes are always made *before* they're recorded, so the only thing
that can go missing is a record — and that fixes itself, because the next agent finds the
step already done. The other order would leave a record with no change behind it, and real
work would get skipped. That ordering is also what makes a killed session recoverable
rather than merely resettable: the diff can be matched against the task's steps to find
where to resume. `/rune:pause` stops new work but lets what's running finish and merge, so
you're never left with a half-applied change, and the flag lives on disk so nothing clears
it quietly.

**Work is checked, not claimed.** A task's test must be seen *failing* before the change is
made, with the evidence recorded — a test written after the fix and never seen failing
proves nothing, and a reviewer in a fresh context can't tell the two apart. Each finished
task is then checked by a different agent that never saw the work. Tasks are self-contained
— goal, files it may touch, what counts as done, its test — so any one can be run, retried,
or reviewed without knowing about the others, and up to three run in parallel when their
file lists don't overlap, merged one at a time with the checks re-run after each. Milestones
are planned in full, but tasks only when it's time to build them: a task has to name real
files, and for a milestone three steps out those files don't exist yet.

**You decide the things worth deciding.** Every run stops once before writing code to show
you the plan, the assumptions it made on your behalf, and what it's deliberately leaving
out — then asks what you'd like to add. There's no flag to skip it. An agent that hits a
choice you'd want a say in writes down the question and its recommendation and stops rather
than guessing, but only when the answer changes behaviour you'd notice and neither the task
nor the surrounding code settles it. You get an update after each task, batch, milestone,
and blocker: summary first, plain words.

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
  ai-research     evidence from outside the repo, graded and cited
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
