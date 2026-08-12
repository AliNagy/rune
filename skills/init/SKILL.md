---
name: init
description: Use when starting Rune on a repository for the first time, or re-running once recorded setup measures stale against the current commit. Establishes the pass/fail oracle, verifies build and test commands, maps modules and conventions, flags danger zones, and scaffolds .rune/.
---

# rune:init

Establishes ground truth so nothing downstream has to re-derive it. Mechanical, no
interview. Re-runnable.

## What you may do

**You establish ground truth and report it.** Everything you are allowed to do follows
from that, and this list is exhaustive:

- **Follow** `ai-root`; its root rename, migration marker, pointer rewrites, and exact
  `.gitignore` update are part of initialization.
- **Read** coordination files under `<main_root>/.rune/`, and manifests small enough to
  name a command from.
- **Write** `<main_root>/.rune/rune.yml`, the canonical empty or bootstrap update to
  `<main_root>/.rune/ledger.md`, the `<main_root>/.rune/` scaffolding, and one line in
  `<main_root>/.gitignore`.
- **Run** only the exact state probes and conditionally authorized lifecycle command named
  below.
- **Talk to the user** — the report at the end.
- **Dispatch subagents**, naming the skill each one must follow. The dispatch table in
  `ai-taskfmt` says which skill does which job.

**Anything not on that list is a dispatch**, including reading source code and running any
command that is not one of the **bounded state probes named below**. Unbounded output is
exactly what this skill exists to keep out of the session everything else starts from.

## Permitted commands and probes

This is the complete command interface for the parent route. Replace placeholders with
the already-resolved absolute value; do not add flags or substitute a broader command.

### State probes

```rune-commands
git rev-parse --show-toplevel
git status --porcelain | head -20
git rev-parse HEAD
git worktree list --porcelain | awk '/^worktree / { n++ } END { print n }'
git -C <main_root> cat-file -e <recorded_commit>^{commit}
git -C <main_root> rev-list --count <recorded_commit>..HEAD
git -C <main_root> diff --name-only <recorded_commit>..HEAD | wc -l
serena.activate_project(project="<main_root>")
serena.find_symbol(relative_path="<probe_file>", name_path="<exact_name_path>", include_body=false)
```

The Git bounds are, in order: exactly one line, at most 20 lines, exactly one line, one
count line, a silent existence test, one count line, and one count line. Serena activation
returns one status. The last three run only for the staleness rule below, against the
commit `rune.yml` recorded. The survey supplies one
repo-relative `probe_file` and one full, exact `name_path`; `find_symbol` uses the fixed
parameters above and must return zero or one signature-only symbol. More than one result
is a failed probe, not permission to broaden or repeat it. Anything else, including any
build or test command, is a dispatch.

### Mutating lifecycle commands

```rune-commands
git -C <main_root> init --quiet
```

This is permitted only after `git rev-parse --show-toplevel` proves no repository exists
and the user explicitly accepts initialization. It emits no normal output. Coordination
creation and the `.gitignore` update are file operations; migration is internal to
`ai-root`, and Git task lifecycle belongs to task-bound workers.

## When it runs

- First use of Rune on a repo
- `rune:vision` finds no `.rune/rune.yml` and triggers it automatically
- Re-run when setup has gone stale, measured by the rule below

For a **new project with no code**, init runs *after* vision — there is nothing to
inspect until the stack is chosen. Vision knows this and orders it correctly.

### When setup is stale

Stale is measured, never judged, so two sessions looking at the same repository reach the
same answer. Compare the `commit` recorded in `rune.yml` against `HEAD` using the last
three state probes above.

Setup is stale when **any one** of these is true:

| Measure | Stale at |
|---|---|
| the recorded commit | it no longer resolves in this repository |
| commits since it | 50 or more |
| files changed since it | 25 or more |
| the recorded oracle command | no longer present in the project manifests |

Under every threshold, setup is current. There is no middle verdict and no judgement call
about how big a change felt.

Record what you measured, so the next reader inherits the numbers instead of re-deriving
them. This block is part of the `rune.yml` candidate below:

```yaml
staleness:
  checked: 2026-08-04
  commits_since: 0
  files_changed_since: 0
  verdict: current        # current | stale
```

A `stale` verdict is a recommendation, never an automatic re-run. Show the numbers and let
the user decide.

## Procedure

### 1. Coordination-root preflight

First resolve `main_root`, keep it constant, and capture the working-tree baseline before
any repository write or coordination read:

```rune-commands
git rev-parse --show-toplevel       # stable main_root for dispatches and coordination
git status --porcelain | head -20   # clean, or the user must accept the dirt
```

Then follow `ai-root` with `work: coordination-root`, the absolute `main_root`, and
`mode: initialize`. It creates a
fresh `.rune/`, migrates recognizable legacy state when safe, or fails closed with a
diagnostic you report before doing anything else.

Before consuming any followed or dispatched result, validate `ai-taskfmt`'s common
return envelope: `work` must equal the assigned token, `summary` must be one line, and
`worktree`/`worktree_path` must agree. Only then read the worker-specific outcome.

After it succeeds, finish the remaining bounded probes:

```rune-commands
git rev-parse HEAD
git worktree list --porcelain | awk '/^worktree / { n++ } END { print n }'
```

These four, and nothing else. The `head -20` is the bound: a repo with 500 dirty files is
itself the finding, and you only need to know it is not clean.

Rune isolates every executor in a worktree, so a repo that is not under git loses its
rollback story. If there is no git, use the harness workspace root as `main_root`, say so
plainly, and offer the exact `git -C <main_root> init --quiet` lifecycle command above.
Run it only on a clear yes. A newly initialized repository has no `HEAD`, so stop after
success and ask the user to create its initial commit; do not restart step 1 or run
`git rev-parse HEAD` against an unborn branch. The next init invocation begins normally
after that commit exists. A decline stops init before `ai-root`.

Uncommitted changes are not fatal but must be surfaced: they will show up in every task's
`git diff` and corrupt the record of what each task actually changed.

### 2. Serena

Run the exact `serena.activate_project` operation above. The signature-only symbol probe
runs after the survey supplies its fixed file and full name path. A cold or broken
language server silently degrades every downstream agent into whole-file reading, which
is precisely what the budget cannot absorb.

Record whether it worked. If Serena is unavailable, note it — `ai-serena` fallbacks
apply and the effective budget per task drops considerably.

### 3. Survey

Dispatch a subagent that follows `ai-survey` with `work: survey`, `main_root`, and absolute
output pointers.

```rune-dispatch
follow: ai-survey
work: survey
main_root: /workspace/acme
pointers:
  map: /workspace/acme/.rune/map.md
```

It writes `<main_root>/.rune/map.md` and Serena memories, and returns a digest within the
canonical ≤200-token worker budget.
Accept only `survey: mapped`; `survey: blocked` stops initialization with its summary.
Require a mapped return to include
`serena_probe: <repo-relative-file>#<full-name-path>` for one
symbol it resolved while surveying, or `serena_probe: unavailable`. For a supplied probe,
run the exact `serena.find_symbol` operation above once and record whether it returned that
one signature. Do not choose another symbol or retry with fuzzy matching. If unavailable
or unsuccessful, record Serena as degraded and continue with `ai-serena` fallbacks.

### 4. Commands and the oracle

**Dispatch a subagent that follows `ai-oracle`. You do not run these commands
yourself.** Build and test output is unbounded — a failing suite is tens of thousands of
tokens — and this is the session every other route starts from, so it is the worst
possible place to absorb them.

Pass it `work: init/commands`, `main_root`, absolute pointers, and the candidates you can
name from the survey digest and manifests. It runs each one on that clean checkout, writes the full output to
`<main_root>/.rune/notes/init-commands.md`, and returns a
per-command verdict with durations plus the oracle result, in ≤200 tokens.

```rune-dispatch
follow: ai-oracle
work: init/commands
main_root: /workspace/acme
pointers:
  output: /workspace/acme/.rune/notes/init-commands.md
```

The rule it enforces on your behalf, per `ai-oracle`: **run it, do not infer it.** Then
record what came back:

- **Passing** → normal operation.
- **Failing on arrival** → record the exact known-red baseline. Do not fix it as a side
  effect; propose it as a milestone.
- **None found** → `oracle.status: none`, degraded mode, and say so loudly.

A `none` or a red baseline is a real result. Do not re-run anything yourself to check —
that is the leak this dispatch exists to close, and the evidence is already on disk.

### 5. Persist initialized state

Build the complete `<main_root>/.rune/rune.yml` candidate below, but do not install it
yet. The ledger transition is persisted first so `rune.yml` can never claim initialization
while the authoritative ledger still has `oracle: —`.

```yaml
initialized: 2026-08-04
commit: a3f91c2
git:
  clean: true
  worktrees_supported: true
serena:
  active: true
  language_server: typescript-language-server
commands:
  build:     { cmd: npm run build,     status: passing, duration_s: 22 }
  test:      { cmd: npm test,          status: passing, duration_s: 34 }
  lint:      { cmd: npm run lint,      status: failing, note: 14 pre-existing errors }
  typecheck: { cmd: npx tsc --noEmit,  status: passing, duration_s: 11 }
oracle:
  command: npm test
  status: passing
  known_red: []
  verified: 2026-08-04
confidence:
  map: high
  conventions: medium      # sampled 4 files
  oracle: high
staleness:
  checked: 2026-08-04
  commits_since: 0
  files_changed_since: 0
  verdict: current
```

These enums are exact. Each `commands.<name>.status` is
`passing | failing | unavailable`; `oracle.status` is `passing | failing | none`. Copy the
transient `ai-oracle` verdicts without translating `passing` to `ok` or `failing` to
`fail`. `unavailable` means that candidate command could not be run, while `none` is
reserved for the absence of any project oracle.

When an existing manifest uses the legacy command statuses, normalize only the exact map
`ok -> passing`, `fail -> failing`, and `none found -> unavailable`. Validate the complete
candidate, then atomically replace `rune.yml` once under this parent's existing ownership.
Unknown command or oracle values stop initialization; never widen the map by analogy.

Ensure every entry in `ai-root`'s authoritative `rune-directory-manifest` exists. This is
create-if-missing and idempotent: accept an existing real directory, never clear its
contents, and stop on a symbolic link or non-directory at any required path. Only when no
ledger exists, write this valid empty schema-2 ledger (fill the top-level values from the
init result rather than leaving placeholders). For a new project whose `vision` route
already created the validated bootstrap, preserve it and replace only `oracle` and `main`
from init's result; never reset `vision`:

```markdown
# Ledger

schema: 2
vision: absent
current_milestone: —
oracle: npm test
main: green

## Tasks

| id | milestone | title | status | blocked_by | worktree | attempts | failures | latest_finding | blocker | resume_at | replaced_by |
|---|---|---|---|---|---|---|---|---|---|---|---|

## Drift

## Dispatches
| phase | followed | work | outcome |
|---|---|---|---|
```

Validate the complete candidate per `ai-ledger` before writing it. On a re-run, validate
and preserve an existing schema-2 ledger. The sole narrow exception is the pre-init vision
bootstrap: `rune.yml` is absent, `oracle: —`, no task row exists, and every dispatch row is
one of `ai-ledger`'s exact coordination-only pre-init graph/survey/commands shapes. Replace
only its `oracle` and `main` values from the init result, preserving `vision` and those
dispatch rows, then validate and replace the complete ledger once. Persist that validated
ledger replacement **before** atomically installing the validated `rune.yml` candidate.

If a crash lands the ledger but not `rune.yml`, the next init recognizes exactly this
recovery state: `rune.yml` absent, schema-2 ledger with `oracle != —`, no Tasks, and only
the allowed pre-init coordination rows. Re-run the bounded ground probes and idempotent
survey/oracle discovery, preserve the vision phase and history, update `oracle`/`main` if
ground truth changed, validate both complete candidates, persist the ledger first again,
then install `rune.yml`. Do not reset to `oracle: —` or treat the missing file as a fresh
ledger. Any task row or other dispatch shape makes this ambiguous and stops init.

A schema-0 or schema-1 ledger routes through
`continue` for migration, and init never resets task history. Run and
planner-specific directories beneath `drafts/` are created only when `work` assigns a new
decomposition run, writes its protocol record, and assigns distinct planner slots.

Add `.rune/worktrees/` to `<main_root>/.gitignore` if worktrees will live inside the repo.

## Report

Follow `ai-report`. TL;DR first, plain words, detail stays on disk.

```
TL;DR
- Ready. TypeScript/Fastify/Postgres, 7 modules mapped.
- `npm test` passes in 34s — that is what every task will be checked against.
- Found 3 unfinished things worth knowing about before you plan.

Checks     tests pass (34s) · build ok · typecheck ok · lint has 14 pre-existing errors
Setup      Serena active · git clean · worktrees available

Unfinished
- src/auth/refresh.ts — rotate() returns null and nothing calls it
- src/billing/ — nothing anywhere imports it
- two user models: src/models/User.ts and src/db/user.ts

Confidence  module map high · conventions medium (sampled 4 files)

Next: /rune:vision to map the road, or /rune:work if you already know what you want.
```

Say "tests pass", never "the oracle is green". The internal vocabulary is for the skills,
not the user.

## Rules

**Never invent an oracle.** If nothing verifies this codebase, that is the finding. A
plausible-looking command that was never run is worse than admitting there is none,
because everything downstream will trust it.

**Report confidence per item.** "Conventions: medium, sampled 4 files" tells the next
agent how much weight to put on the map. Uniform claimed certainty is not credible and
hides exactly the corners that will produce drift.

**Never fix anything.** Init observes. A failing lint, a broken build, a stub — these are
recorded, not repaired. Repairs are work, work goes through `rune:work`, and work needs
acceptance criteria that init has no mandate to invent.
