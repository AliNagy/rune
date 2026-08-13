---
name: survey
user-invocable: false
description: Use when mapping an unfamiliar or in-progress codebase - stack, modules, entry points, conventions, danger zones, and what is stubbed, orphaned, or half-built. Always runs as a subagent so the caller stays clean.
---

# Surveying a codebase

The dispatch includes absolute `main_root` and absolute output pointers. Survey source at
that checkout and write coordination there; never infer the repository from the worker's
starting directory.

Produces `<main_root>/.rune/map.md` plus Serena memories. Everything downstream depends
on this, so that nobody else ever has to browse the repo to get oriented.

**Always run as a subagent.** The caller — `init`, `vision`, or `handoff` — must
not read code. Survey burns context by design; that cost is quarantined in a worker that
returns a digest and dies.

## Two modes

The dispatch names one. They are not variations on each other: the first writes the map,
the second edits it.

| `mode` | `work` | Given | Does |
|---|---|---|---|
| `full` (default) | `survey` | the checkout | surveys the codebase and writes the whole map |
| `amend` | `survey/amend` | exactly one fact | files that one fact, touching nothing else |

Everything below describes `full` until the **Amending one fact** section, which is the
complete contract for `amend`. An `amend` dispatch never surveys: it reads the map, or one
memory, and stops. Re-deriving the codebase to file a single convention is the exact cost
this mode exists to avoid.

**Read-only with respect to source.** You write `<main_root>/.rune/map.md` and Serena
memories; you never touch the codebase. Nothing enforces that — you are an ordinary
subagent with ordinary permissions — so it holds because you keep it. Surveying turns up
plenty worth fixing, and every one of those is a finding for the map, not a change to make
here.

## Order of work

Breadth before depth, always. A surveyor that starts reading files in `src/` learns a
great deal about one corner and nothing about the shape.

1. **Perimeter** — directory tree to depth 3, ignoring vendored and generated paths.
   Manifests (`package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod`). README. CI
   workflow files.
2. **Entry points** — `main`, server bootstrap, CLI registration, route tables, exported
   package surface. These anchor the map; everything else hangs off them.
3. **Module map** — for each top-level module: purpose in one line, its entry symbols,
   what it depends on. Use `get_symbols_overview`, not `Read` (see `serena`).
4. **Conventions** — sample three or four representative files and extract observed
   practice: error handling, naming, module boundaries, test structure, async style.
   Report what the code *does*, not what a style guide says it should.
5. **Danger zones** — generated files, vendored directories, lockfiles, migrations,
   anything with a "do not edit" banner.
6. **Completeness** — the pass that matters for in-progress projects. Below.

## Completeness assessment

For an in-progress codebase, the single most valuable output is an honest account of
what is *not* finished. Look for and record, each with a file reference:

- **Stubs** — functions that return a constant, `TODO`, `NotImplementedError`, `panic!`,
  empty handlers.
- **Orphans** — code with no inbound references (`find_referencing_symbols` returns
  nothing). Either dead or not yet wired.
- **Half-wired** — an implementation exists but is never called; a route is registered
  with no handler; a feature flag permanently off.
- **Contradictions** — two implementations of the same concept, a config key nothing
  reads, a migration with no corresponding model.
- **Abandoned direction** — a subsystem in a style unlike the rest, or a partial
  migration with both old and new patterns live simultaneously.

State these as observations with evidence, never as judgements. "`AuthService.refresh`
returns null and has no callers" is useful. "The auth is a mess" is not.

## Output

Write `<main_root>/.rune/map.md`:

```markdown
# Map — <project>
surveyed: 2026-08-04   commit: a3f91c2

## Stack
TypeScript · Node 20 · Fastify · Postgres via Prisma · Vitest

## Entry points
- src/server.ts        — HTTP bootstrap, registers routes
- src/worker/index.ts  — background job runner
- src/cli.ts           — admin CLI

## Modules
| path        | purpose                    | entry symbols            | depends on |
|-------------|----------------------------|--------------------------|------------|
| src/auth    | sessions, tokens           | SessionMiddleware, ...   | db, config |
| src/api     | HTTP routes                | registerRoutes           | auth, svc  |

## Conventions
- Errors: typed Result union, never thrown across module boundaries
- Tests: colocated __tests__/, vitest, one file per subject
- Async: async/await throughout; no raw promise chains

## Danger zones
- prisma/migrations/**   — generated, never hand-edit
- src/generated/**       — regenerated by `npm run codegen`

## Completeness
- STUB   src/auth/refresh.ts :: rotate — returns null, no callers
- ORPHAN src/billing/**      — no inbound references from any entry point
- HALF   /api/v2/session registered, handler throws NotImplemented
- CONTRA two user models: src/models/User.ts and src/db/user.ts
```

Then write the deep material to **Serena memories** — subsystem explanations, gotchas,
architectural reasoning. `map.md` is the index a human reads; memories are the detail an
agent pulls on demand.

## Amending one fact

`handoff` learns things from the conversation that belong in the map — a convention the
user corrected, a gotcha nobody wrote down. Each one arrives as its own dispatch:

```rune-dispatch
follow: survey
work: survey/amend
mode: amend
main_root: /workspace/acme
fact_kind: convention
fact: errors are typed Result unions, never thrown across module boundaries
pointers:
  map: /workspace/acme/.rune/map.md
```

`fact_kind` routes it. A `convention` goes to the matching `map.md` section; a `gotcha`
goes to the Serena memory for the subsystem it concerns, or a new memory if none fits.
The fact travels in the dispatch because it exists nowhere else yet — that is the whole
reason this mode exists.

**Read before you write, and preserve everything you did not come to change.** Load the
target, find where the fact belongs, and make the smallest edit that files it. Never
rewrite the map, never reformat around your edit, and never drop a section because this
dispatch had nothing to say about it. A one-line fact that replaces a whole map has
destroyed far more than it recorded.

Then decide which of four things is true:

| What you found | Return | What you write |
|---|---|---|
| the fact is not there | `amended` | add it in the right section |
| the fact is already there, in substance | `unchanged` | nothing |
| the map says something this contradicts | `conflict` | nothing |
| the target is missing or unreadable | `blocked` | nothing |

**A conflict is not yours to resolve.** You have one sentence from a conversation you did
not see; the map has a line somebody surveyed the codebase to write. Quote both and hand
it back. The parent takes it to the user, who knows which is true.

Three of those four outcomes write nothing at all, and that is normal. Filing a fact that
was already filed is not a success, and overwriting a surveyed observation to make your
dispatch look productive is the failure this mode is most likely to produce.

**You are never one of several.** The caller dispatches amendments one at a time and waits
for each. Two amend workers editing `map.md` at once would each preserve the file as they
found it and silently discard the other's edit.

## Return to caller

Keep it at or below the canonical 200-token worker budget. The map is on disk; do not
repeat it.

An `amend` return is the shorter of the two — it says what it filed and where:

```rune-return
work: survey/amend
summary: filed the typed-Result convention under Conventions in map.md
survey: amended
worktree: none
target: /workspace/acme/.rune/map.md
section: Conventions
```

For `conflict`, keep `target` and add `conflict_with:` quoting the existing line verbatim,
so the parent can show the user both without reopening the file. `unchanged` and `blocked`
carry `target` and the reason in `summary`.

A `full` return reports the survey:

```rune-return
work: survey
summary: seven modules mapped; billing is incomplete and auth confidence is high
survey: mapped | blocked
worktree: none
stack: TypeScript/Fastify/Postgres
modules: 7 mapped
oracle_candidate: npm test (vitest)
completeness: 3 stubs, 1 orphan module (billing), 1 contradiction (dual user model)
confidence: high on api/auth, low on worker/ (sparse, few tests)
flags: billing/ appears abandoned mid-implementation
serena_probe: src/server.ts#Server/start
```

Report low confidence where you have it. A surveyor that claims uniform certainty over a
codebase it sampled is worse than one that says which corners it did not reach.
`serena_probe` names one repo-relative source file and one full exact symbol name path that
this survey resolved with Serena. Return `serena_probe: unavailable` when Serena did not
resolve one; never invent a path merely to make init's confirmation pass.
