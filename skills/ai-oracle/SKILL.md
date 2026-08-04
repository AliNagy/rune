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

**Run it. Do not infer it.** A command in `package.json` proves nothing about whether it
works in this checkout, on this machine, today.

1. Look for the obvious candidates — `package.json` scripts, `Makefile`, `justfile`,
   `pyproject.toml`, `Cargo.toml`, CI workflow files. CI config is the best single
   source: it states what the project itself believes verifies it.
2. Execute the candidate on a clean tree.
3. Record the outcome honestly in `rune.yml`:

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
- A flaky test is not a pass. Re-run once; if it disagrees with itself, record it as
  flaky in `rune.yml` and treat it as uninformative for this task rather than pretending
  it verified something.
- Timeouts are failures, not inconclusive results.

## Vacuous checks

The most common way verification silently fails is a test that cannot fail.

- A test asserting nothing, or asserting `true`.
- A test whose subject is mocked so thoroughly it exercises only the mock.
- A test added *after* the change and never observed red.

The third is why `ai-taskfmt` requires red-then-green evidence in the progress
file. A verifier that cannot find that evidence must treat the task as **unverified**,
not as passed. Absence of proof is not proof.
