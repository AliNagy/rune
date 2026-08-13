# Rune

A skill set for building software without any single context window filling up.

State lives on disk, not in the conversation. Every agent is short-lived: it loads one
slice of the plan, does the work, writes the result back, and exits. Target is under ~150k
context per piece of work, on projects of any size.

## Requirements

- **git** — every task runs in its own worktree
- **[Serena](https://github.com/oraios/serena)** as an MCP server — strongly recommended;
  symbol lookup instead of whole-file reads is the single biggest context saving here
- **Claude Code** with `/plugin`, or any agent the `skills` CLI supports

## Install

**Claude Code plugin** — keeps the `rune:` namespace:

```
/plugin marketplace add AliNagy/rune
/plugin install rune@rune
```

Run `/reload-plugins` if the install summary asks for it. Then use `/rune:using-rune`.

**Any agent, via the skills CLI:**

```bash
npx skills install AliNagy/rune --all
```

`--all` installs all 28 skills to every detected agent with no prompts. Drop it and you get
a picker with nothing preselected. This path installs bare skill names, so the command is
`/using-rune` and there is no `rune:` prefix.

**From a local clone:**

```bash
claude --plugin-dir /path/to/rune
```

For OpenCode, see [docs/opencode.md](docs/opencode.md).

## Use

One command:

```
/rune:using-rune
```

Then say what you want in plain language. It reads the project state and routes you.

| You say | What happens |
|---|---|
| "set this repo up" | finds and runs the command that proves the code works, maps the codebase |
| "start a new project" | interviews you, records decisions, writes milestones |
| "add X" / "fix Y" / "clean up Z" / "why is W slow" | triages against real code, cuts tasks, builds and verifies each one |
| "stop" | finishes what is running, leaves the tree clean |
| "where were we" | reconciles state left by a dead session and picks up |
| "context is full" | writes a handoff block for a fresh session |

That is the whole interface. The other 27 skills are marked not user-invocable — the agent
loads them itself when the situation calls for one, so they stay out of your command list
and out of your context until they are needed.

## What Rune writes into your repo

```
.rune/
  rune.yml               test command, build commands, git starting point, last-checked date
  map.md                 module map, entry points, conventions, risky areas
  vision.md              the vision document
  decisions.md           decisions made and still open — open ones block milestones
  milestones.md          the road to v1
  ledger.md              task state, attempts, blockers, resume points
  drafts/M-nn/R-nnn/     protocol, planner cuts, drift replacement map
  tasks/T-nnn.md         immutable task specs; never edited or deleted
  notes/                 handoff notes, promoted investigation and research answers
  drift/                 what the plan got wrong, and which tasks that invalidates
  findings/              things noticed in passing, after a second agent checked them
  sessions/              session handoffs for fresh-context recovery
  worktrees/             disposable task checkouts; gitignore this one
```

**Commit it.** Vision, decisions, milestones, and ledger are project knowledge worth
reviewing. Add `.rune/worktrees/` to `.gitignore`.

Rune also writes a short playbook into your `CLAUDE.md` between `<!-- rune:begin -->` and
`<!-- rune:end -->`. Everything outside those markers is left alone.

Upgrading a repo with work in flight? Read
[the migration guide](docs/migrating-from-agent.md) first.

## How it works

**Set up** — find and *run* the pass/fail command that proves the codebase works. If there
isn't one, say so loudly and work in a reduced mode.

**Plan** — interview, then milestones. Every open choice becomes a written decision, and no
milestone is generated while a decision it depends on is unanswered.

**Build** — triage into bug / feature / refactor / investigation, cut the current milestone
into tasks *only when it's time to build them*, send each to its own agent, then check each
in a separate fresh context. Up to three run in parallel when their file lists don't
overlap.

**Resume** — read disk, sort out what a dead session left behind, carry on.

## Why it's built this way

- **Context is the budget.** The main session never reads source code. Subagents return 200
  tokens or less; anything longer goes to disk. One agent, one issue.
- **Interrupting is safe.** Each task is a git worktree. Unfinished work is its `git diff`;
  finished work is a commit, verified by SHA before it lands.
- **Work is checked, not claimed.** A task's test must be seen *failing* before the fix,
  with the evidence recorded. A different agent, which never saw the work, verifies it.
- **Task size is checked, not assumed.** Every new task is read cold by a fresh agent that
  answers one question: could one executor finish this with room left over?
- **A guess is not a finding.** Things noticed in passing are written down as claims, then
  checked by an agent that never saw the work. Only confirmed ones reach you.
- **A wrong plan stays legible.** Drift never patches a task spec. The obsolete task is
  retired, replacements get new ids, and the ledger records the relationship.
- **You decide the things worth deciding.** Every run stops before final task files to show
  you the plan, its assumptions, and what it leaves out. There's no flag to skip it.

## Layout

```
.claude-plugin/    plugin.json, marketplace.json

skills/
  using-rune      the only command; routes to everything below

  root            coordination-root identity and legacy migration
  taskfmt         the file formats everything else depends on
  ledger          state updates, and cleaning up after a crash
  report          when to talk to the user, and how
  serena          reading code without spending much context
  oracle          finding and running the pass/fail check
  init            establishing the oracle and mapping the codebase
  survey          looking around an unfamiliar codebase
  vision          the interview, decisions, and the milestone graph
  work            the build loop: triage, decompose, dispatch, verify, land
  triage          bug, feature, refactor, or question
  decompose       milestone to tasks, and how big a task should be
  size            could one fresh executor actually finish this
  execute         doing one task: worktree, evidence, publishing its commit
  bug             reproduce in a reserved task worktree before planning
  feature         thin end-to-end slices, open questions decided first
  refactor        cover behaviour with tests first, then leave them alone
  investigate     read-only, ends in an answer
  research        evidence from outside the repo, graded and cited
  verify          an independent second check
  verify-finding  checking a claim nobody asked for
  land            merging the exact verified commit, backing it out if checks break
  drift           when the plan turns out to be wrong
  recover         salvaging a task that stopped halfway
  pause           stop cleanly, and check whether work is stopped
  handoff         moving to a fresh session before context fills
  continue        picking up in a fresh session
```

There is no `agents/` directory. Every worker is an ordinary subagent told which skill to
follow, so a skill is the only thing Rune defines and the only thing a harness has to
understand.

## Versioning

Tagged `vMAJOR.MINOR.PATCH`, matching `version` in `plugin.json`. Installed copies only
update when that field changes, so every release bumps it. Before 1.0, minor versions may
break the `.rune/` file formats.

## Status

**Not yet production-tested.** `v0.13.0` collapses the interface to one command and drops
the `ai-` prefix from the internal skills. Rune has not been run end to end on a real
repository. Expect to adjust the 200-token subagent return limit, Windows worktree paths,
and whether the plan-approval stop lands at the right moments.

Start on a low-stakes repo. Rune does not edit source code before you approve a plan, but
it does write `.rune/` state, update the worktree ignore entry, and may migrate recognized
legacy state.

## License

MIT — see [LICENSE](LICENSE).
