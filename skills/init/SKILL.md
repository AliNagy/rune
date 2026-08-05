---
name: init
description: Use when starting Rune on a repository for the first time, or re-running after the codebase has changed substantially. Establishes the pass/fail oracle, verifies build and test commands, maps modules and conventions, flags danger zones, and scaffolds .agent/.
---

# rune:init

Establishes ground truth so nothing downstream has to re-derive it. Mechanical, no
interview. Re-runnable.

**You do not read source code.** Survey runs as a subagent (`ai-survey`) and returns
a digest. Your context stays small and clean.

## When it runs

- First use of Rune on a repo
- `rune:vision` finds no `.agent/rune.yml` and triggers it automatically
- Re-run after major change, or when `rune.yml` is stale (commit differs substantially
  from the recorded one)

For a **new project with no code**, init runs *after* vision — there is nothing to
inspect until the stack is chosen. Vision knows this and orders it correctly.

## Procedure

### 1. Git baseline

```
git status --porcelain     # must be clean, or the user must accept the dirt
git rev-parse HEAD
git worktree list
```

Rune isolates every executor in a worktree, so a repo that is not under git loses its
rollback story. If there is no git, say so plainly and offer to `git init` — this is the
first thing to fix, before anything else.

Uncommitted changes are not fatal but must be surfaced: they will show up in every task's
`git diff` and corrupt the record of what each task actually changed.

### 2. Serena

`activate_project` on the repo root. Confirm the language server comes up and one symbol
query returns. A cold or broken language server silently degrades every downstream agent
into whole-file reading, which is precisely what the budget cannot absorb.

Record whether it worked. If Serena is unavailable, note it — `ai-serena` fallbacks
apply and the effective budget per task drops considerably.

### 3. Survey

Dispatch `ai-survey` as a subagent. It writes `.agent/map.md` and
Serena memories, and returns a ≤300 token digest.

### 4. Commands

From the survey digest and manifests, identify build, test, lint, typecheck, and run.
**Execute each one.** A script in `package.json` proves nothing about whether it works
here, today.

Record real outcomes, including failures and durations.

### 5. The oracle

The most important output. Per `ai-oracle`:

- **Passing** → normal operation.
- **Failing on arrival** → record the exact known-red baseline. Do not fix it as a side
  effect; propose it as a milestone.
- **None found** → `oracle.status: none`, degraded mode, and say so loudly.

### 6. Write `.agent/rune.yml`

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
  build:     { cmd: npm run build,     status: ok,   duration_s: 22 }
  test:      { cmd: npm test,          status: ok,   duration_s: 34 }
  lint:      { cmd: npm run lint,      status: fail, note: 14 pre-existing errors }
  typecheck: { cmd: npx tsc --noEmit,  status: ok,   duration_s: 11 }
oracle:
  command: npm test
  status: passing
  known_red: []
  verified: 2026-08-04
confidence:
  map: high
  conventions: medium      # sampled 4 files
  oracle: high
```

Scaffold the rest of `.agent/` per `ai-taskfmt`: `tasks/`, `notes/`, `drift/`, and
an empty `ledger.md`.

Add `.agent/worktrees/` to `.gitignore` if worktrees will live inside the repo.

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
