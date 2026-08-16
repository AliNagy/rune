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

`--all` installs all 28 skills to every detected agent with no prompts; drop it and you get
a picker where one keystroke on the **Rune** group selects the set. Here the command is
`/using-rune`, without the `rune:` prefix.

Note that `--all` skips the overwrite confirmation. The 27 internal skills are named
`rune-*` so they cannot collide, but `using-rune` will replace any skill of yours by that
name.

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

### Optional: two lines in your CLAUDE.md

Rune needs nothing in `CLAUDE.md` to work. If you want sessions to reach for it without
being told, this is all that belongs there — it is loaded into every context, so keep it
to what is true in all of them:

```
This project uses Rune. Start with the using-rune skill.
Never hand-edit files under .rune/.
```

Do not copy Rune's rules into `CLAUDE.md`. They are role-specific — the coordinator must
not edit source, its workers must — and a file loaded everywhere would hand both halves to
every agent at once.

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
hooks/             worktree-guard.py, wired from the skills that edit source

skills/
  using-rune           the only command; routes to everything below

  rune-root            coordination-root identity and legacy migration
  rune-taskfmt         the file formats everything else depends on
  rune-ledger          state updates, and cleaning up after a crash
  rune-report          when to talk to the user, and how
  rune-serena          reading code without spending much context
  rune-oracle          finding and running the pass/fail check
  rune-init            establishing the oracle and mapping the codebase
  rune-survey          looking around an unfamiliar codebase
  rune-vision          the interview, decisions, and the milestone graph
  rune-work            the build loop: triage, decompose, dispatch, verify, land
  rune-triage          bug, feature, refactor, or question
  rune-decompose       milestone to tasks, and how big a task should be
  rune-size            could one fresh executor actually finish this
  rune-execute         doing one task: worktree, evidence, publishing its commit
  rune-bug             reproduce in a reserved task worktree before planning
  rune-feature         thin end-to-end slices, open questions decided first
  rune-refactor        cover behaviour with tests first, then leave them alone
  rune-investigate     read-only, ends in an answer
  rune-research        evidence from outside the repo, graded and cited
  rune-verify          an independent second check
  rune-verify-finding  checking a claim nobody asked for
  rune-land            merging the exact verified commit, backing it out if checks break
  rune-drift           when the plan turns out to be wrong
  rune-recover         salvaging a task that stopped halfway
  rune-pause           stop cleanly, and check whether work is stopped
  rune-handoff         moving to a fresh session before context fills
  rune-continue        picking up in a fresh session
```

The `rune-` prefix is what keeps a plain `npx skills install` from colliding with your own
skills, or with Claude Code's bundled ones. Under the plugin the namespace does that job
already, so the prefix is only ever visible to the agent.

There is no `agents/` directory. Every worker is an ordinary subagent told which skill to
follow, so a skill is the only thing Rune defines and the only thing a harness has to
understand.

## Versioning

Tagged `vMAJOR.MINOR.PATCH`, matching `version` in `plugin.json`. Installed copies only
update when that field changes, so every release bumps it. Before 1.0, minor versions may
break the `.rune/` file formats.

## Status

**Not yet production-tested.** `v0.14.0` collapses the interface to one command and renames
the 27 internal skills to `rune-*` so a non-plugin install cannot collide with anything. Rune has not been run end to end on a real
repository. Expect to adjust the 200-token subagent return limit, Windows worktree paths,
and whether the plan-approval stop lands at the right moments.

Start on a low-stakes repo. Rune does not edit source code before you approve a plan, but
it does write `.rune/` state, update the worktree ignore entry, and may migrate recognized
legacy state.

## License

MIT — see [LICENSE](LICENSE).
