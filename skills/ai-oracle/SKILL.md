---
name: ai-oracle
user-invocable: false
description: Use when determining how a codebase proves itself correct, or when deciding whether a completed task actually passed. Covers the project-global oracle, per-task local checks, known-red baselines, and degraded mode when no oracle exists.
---

# The oracle

The **oracle** is whatever decides pass/fail without a human. `npm test`, `cargo test`,
a build plus a smoke script — whatever this repo actually has.

It matters because Rune executors grade their own homework. They report their own
success, in a context nobody else can see, and models are optimistic. Without an
independent check you get a ledger of green rows over a codebase that does not run.

## Two oracles

**Project-global** — "did I break anything else." Established once by `rune:init`,
recorded in `.agent/rune.yml`, run after every task.

**Task-local** — "did my specific thing work." Produced *by* the task, per
`ai-taskfmt`. Every task leaves a check behind that did not exist before.

A project with no test suite still accrues one, task by task, through the local oracles.
That is what makes degraded mode survivable rather than hopeless.

## Establishing the global oracle (init)

**Always run as a subagent.** Command output is unbounded — a failing suite can be tens of
thousands of tokens — and `rune:init` is the session every other route starts from, so it
is the worst place in Rune to absorb them. The dispatcher needs a verdict, not a log, and
cannot get one without running the command.

**Run it. Do not infer it.** A command in `package.json` proves nothing about whether it
works in this checkout, on this machine, today. Inference is what the dispatcher could
already do for free; running it is the entire reason this is a separate dispatch.

1. Look for the obvious candidates — `package.json` scripts, `Makefile`, `justfile`,
   `pyproject.toml`, `Cargo.toml`, CI workflow files. CI config is the best single
   source: it states what the project itself believes verifies it.
2. Execute the candidate on a clean tree.
3. **Return** the outcome honestly. You do not write `rune.yml` — the parent does, from
   what you hand back. You write only `.agent/notes/init-commands.md`. The canonical field
   set lives in `init` §5; do not invent a second schema for it. What the parent records
   looks like:

```yaml
oracle:
  command: npm test
  status: passing           # passing | failing | none
  duration_s: 34
  verified: 2026-08-04
  notes: 3 tests skipped in auth/ — pre-existing
```

### The three outcomes

**Passing.** Normal operation. This is the regression check for every task.

**Failing on arrival.** Do not fix it as a side effect and do not treat it as absent.
Record the exact set of failures as the **known-red baseline**. A task regresses only if
it adds a failure not in that baseline. Getting the suite green is legitimate work —
propose it as a milestone, do not smuggle it into an unrelated task.

**None found.** Say so loudly. Set `oracle.status: none` and enter degraded mode.

### Running the full command sweep

`rune:init` needs more than the oracle — build, test, lint, typecheck, and run. Same
dispatch, same discipline:

- **Run every candidate**, on a clean tree, and leave the tree clean. You do not fix
  anything you find; a failing build is a finding to report, not work to take on.
- **Time each one.** Duration is what tells the dispatcher whether the oracle is usable
  after every task or only at milestone boundaries.
- **Full output goes to `.agent/notes/init-commands.md`** — every command, its exit code,
  and enough output to diagnose a failure later. Nobody should have to re-run a 30-second
  suite to find out what broke.
- **Never summarise a failure you did not read.** The reason belongs in the note, quoted
  from the actual output.

Return ≤200 tokens:

```
build:     ok    22s
test:      ok    34s
lint:      fail  8s    14 pre-existing errors
typecheck: ok    11s
run:       none found

oracle: npm test — passing, verified on a clean tree
detail: .agent/notes/init-commands.md
```

The dispatcher acts on the verdict; the evidence stays on disk for whoever needs it.

## Degraded mode

When there is no project-global oracle:

- Mark the ledger `oracle: none (degraded)`.
- Every task's acceptance must be a **manually checkable assertion** — a command with
  observable output, a scripted check, a specific state to look at. "It works" is not an
  acceptance criterion.
- Every completion report states plainly that nothing was machine-verified.
- Task-local tests still apply and still accumulate. After a few milestones there is
  usually enough to assemble a real suite; propose that as a milestone.

Degraded mode is deliberately noisy. The point is that you feel the absence on every
single task rather than forgetting about it by task three.

## Running the oracle during verification

Run it in the task's worktree, not the main tree.

- Compare against the **known-red baseline**, not against zero failures.
- A new failure anywhere is a regression, even if the task's own test passes.
- A flaky test is not a pass. Re-run once; if it disagrees with itself, **report**
  `flaky: <test name>` in your verdict and return `unverified` for the task. You do not
  write `rune.yml` — the parent appends it to `oracle.flaky:` alongside the known-red
  baseline it belongs with.
- Timeouts are failures, not inconclusive results.

## Running the oracle after a merge

`rune:work` dispatches this after landing a verified worktree in the main tree.

Run the project oracle in the **main tree**, compare against the known-red baseline, and
return ≤200 tokens:

```
oracle: pass    # or: fail — 2 new failures not in baseline
detail: .agent/notes/merge-<T-nnn>.md    # only when it failed
```

The parent merges but never reads a suite log. That split is the whole point: merging is
bounded, running the suite is not.

## Vacuous checks

The most common way verification silently fails is a test that cannot fail.

- A test asserting nothing, or asserting `true`.
- A test whose subject is mocked so thoroughly it exercises only the mock.
- A test added *after* the change and never observed red.

The third is why `ai-taskfmt` requires red-then-green evidence in the progress
file. A verifier that cannot find that evidence must treat the task as **unverified**,
not as passed. Absence of proof is not proof.
