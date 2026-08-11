---
name: ai-root
user-invocable: false
description: Use before any Rune coordination read or write. Resolves the canonical .rune root, initializes it when the caller permits, and safely migrates recognizable legacy .agent state without relying on a shipped runtime script.
---

# Coordination-root protocol

Rune is a skills-only instruction set. This skill is the single seam for coordination-root
identity and migration; callers follow it directly rather than launching a bundled
program. Migration callers serialize themselves with the exact lock described below.

## Interface

The caller supplies:

```text
main_root: absolute orchestration-checkout path
mode: resolve | initialize
```

On success, return the absolute `<main_root>/.rune` path and whether migration was
`none`, `completed`, or `resumed`. On ambiguity or an unsafe filesystem state, stop with a
specific diagnostic. Never guess, merge roots, or silently discard state.

`resolve` never creates an empty root. `initialize` may create one when neither root
exists. Every caller keeps `main_root` constant after this protocol returns.

## Allowed actions

This protocol may inspect the two root entries, inspect Rune coordination artifacts needed
to establish ownership, and run the bounded `git worktree list --porcelain` probe. It may
rename the legacy coordination directory, update structured Rune pointers, maintain the
one worktree ignore entry, and create or remove its migration marker, lock, and exact
atomic-write candidates. Inside a resolved canonical root it may also create the exact
`notes/open/` and `drift/open/` report-staging directories defined below.

It does not read source code, inspect task-worktree contents, run project commands, or
change anything outside those coordination paths and the exact `.gitignore` entry.

## Resolution states

Apply these cases in order:

| State | Result |
|---|---|
| both `.rune/` and `.agent/` exist | stop; report both absolute paths; change neither |
| only `.rune/` exists | resume its marked migration if needed, then return it |
| only `.agent/` exists | validate ownership and worktree safety, then migrate |
| neither exists, mode `initialize` | create `.rune/`, ensure `.rune/worktrees/` is ignored, return it |
| neither exists, mode `resolve` | return the canonical path without creating it; the caller decides whether to route to init |

A root entry that is a symbolic link or is not a directory is unsafe. A coordination
artifact that is a symbolic link, a symlinked `worktrees/` directory, or a symlinked or
non-file `.gitignore` is also unsafe. Stop without following or replacing it.

## Canonical report-staging layout

Before returning any existing, newly initialized, or migrated canonical root, ensure the
exact directories `<main_root>/.rune/notes/open/` and
`<main_root>/.rune/drift/open/` exist. Create missing `notes/`, `drift/`, or `open/`
directories idempotently. If any component already exists as a symlink or non-directory,
stop and report that exact path; never follow, replace, or merge it. This is the layout
upgrade for repositories created before report staging existed, so every `resolve` caller
gets safe destinations without a separate schema migration.

## Establish legacy ownership

The generic name may belong to another tool. Migrate only when all top-level entries fit
Rune's documented layout and at least one independent Rune signal is present:

- initialized `rune.yml` with its command/oracle structure;
- a complete schema-2 Rune ledger, or a recognizable schema-1/schema-0 Rune ledger;
- an interrupted `# Vision` plus `# Decisions` pair;
- a `# Map — <project>` survey record;
- a Rune session handoff or PAUSED record;
- a task, note, or drift artifact whose contents match the schema in `ai-taskfmt`.

Filenames alone are not ownership. Unknown top-level entries make ownership ambiguous.
Stop and tell the user to identify or move the directory manually.

Before applying the unknown-entry rule, set aside only these exact migration-control
entries: `.migration-from-agent.md`, `.rune-migration-lock/`, and sibling candidates whose
names follow the atomic rules below. They never establish ownership. Accept them only
when a separate artifact above establishes Rune ownership; otherwise stop. This lets a
recognizable root survive an interruption without letting generic temp files make a
foreign `.agent/` directory look like Rune state.

## Protect registered worktrees

Before renaming, inspect `git worktree list --porcelain`. If Git registers a worktree
exactly at the legacy root or anywhere below it, stop and list every path. Renaming its
parent would strand Git metadata and possibly live work.

Do not remove or prune those worktrees. The user must finish, preserve, relocate, or
remove them explicitly before retrying. A real but unregistered `worktrees/` directory is
preserved byte for byte and is never content-rewritten.

## Resumable migration

Migration is one protocol with a durable marker and an exclusive lock. The root that
currently exists owns the lock: `.agent/.rune-migration-lock/` before the directory rename,
or `.rune/.rune-migration-lock/` after it.

1. After establishing an independent Rune ownership signal, atomically create the lock
   directory under the current root, then create its `owner.md` exclusively with mode
   `0600` and identify the current migration invocation. If the lock directory already
   exists, stop: another invocation may be active. Never steal or age out a lock. Tell the
   user to remove that exact lock only after confirming no Rune migration is active, then
   retry.
2. After acquiring or reacquiring the lock, repeat the root, ownership, link, and
   registered-worktree checks before changing state. Then recover exact atomic-write
   candidates as described below.
3. Dispatch from the root and validated marker state:
   - sole `.agent/`, no marker: atomically create
     `.agent/.migration-from-agent.md` with `from: .agent`, `to: .rune`, and
     `phase: prepared`, following the new-file rule below;
   - sole `.agent/`, valid `phase: prepared`: keep the existing marker and continue;
   - sole `.agent/`, any other marker state: stop as inconsistent;
   - sole `.rune/`, valid `phase: prepared`: resume at the phase update in step 5;
   - sole `.rune/`, valid `phase: rewriting`: resume at the rewrites in step 6;
   - sole `.rune/`, no marker and no migration temp: remove the newly acquired lock and
     return it as the canonical root with `migration: none`;
   - any invalid marker, contradictory root, or unexplained temp: stop with the lock and
     state intact.
4. From `.agent/` with the valid prepared marker, rename the directory to `.rune/` in one
   same-filesystem rename operation. Never implement this as copy-then-delete. The lock
   moves with the directory.
5. Atomically change a `phase: prepared` marker to `phase: rewriting`. If it already says
   `phase: rewriting`, do not replace it again.
6. Rewrite only:
   - exact absolute paths rooted at `<main_root>/.agent/`;
   - relative paths in enumerated Rune pointer fields such as `latest_finding`,
     `worktree_path`, `detail`, `progress`, `artifact`, `protocol`, `milestone`, and
     `file`;
   - relative targets of Markdown links;
   - the canonical ledger's pointer columns;
   - the exact `.agent/worktrees/` line in `.gitignore`.
7. Ensure `.rune/worktrees/` is present once in `.gitignore`.
8. Handle the migrated ledger by schema:
   - schema 2: validate the complete rewritten candidate against `ai-ledger` before
     replacing it;
   - recognized schema 1 or schema 0: preserve it except for safe pointer rewrites, then
     let `continue` perform the supported schema upgrade after this protocol returns;
   - missing or unknown ownership/schema: stop without replacing the ledger.
   Preserve file permissions and every non-pointer byte that did not need rewriting.
9. Remove the marker only after all rewrites and validation succeed, then remove the
   migration lock. A failed invocation leaves both in place so partial state cannot be
   mistaken for an available migration.

Never perform a global text replacement. Free-form prose may describe another tool's
path and remains unchanged. Never inspect or rewrite files beneath `worktrees/`.

### Atomic creation and replacement rules

Never truncate a marker, coordination file, ledger, or `.gitignore` in place. Hold the
migration lock for every operation in this section.

To create a new marker that has no target yet:

1. create its sibling `.<target-name>.rune-migration-tmp` exclusively with mode `0600`;
2. write the complete candidate and validate its exact marker fields;
3. confirm the target is still absent;
4. rename the candidate to the target without replacing any path that appeared; if the
   platform cannot guarantee no-replace semantics, stop instead of risking overwrite.

For replacement of an existing target:

1. read the unchanged target and record its permission mode;
2. build the complete candidate in a sibling file named
   `.<target-name>.rune-migration-tmp`, creating it exclusively;
3. validate the candidate's syntax and, when applicable, its schema and exact intended
   pointer changes;
4. apply the target's original permission mode to the candidate;
5. rename the candidate over the target in one same-filesystem operation.

An existing lock always causes a new invocation to stop before it touches a temp. After
the user has confirmed no migration is active and removed only the stale lock, the retry
acquires a new lock and may inspect exact `.rune-migration-tmp` siblings outside
`worktrees/`. If the unchanged target plus a complete, valid temp proves the pending
operation, finish the rename. If the temp is partial or invalid, remove only that exact
temp and regenerate it from the unchanged target. A temp is never an ownership signal;
an unexpected path type or ambiguous candidate is a hard stop. Apply the same rule to the
main-root `.gitignore` candidate.

If the session stops after the rename, the marker is now under `.rune/`; after the stale
lock is safely cleared, the next caller reacquires `.rune/.rune-migration-lock/` and
dispatches from its marker phase. If it stops before the rename, the marker remains under
`.agent/`; after the stale lock is safely cleared, the next caller reacquires
`.agent/.rune-migration-lock/` and a valid prepared marker advances directly to the
rename. Repeating any completed rewrite must leave the same result; an interrupted file
write leaves the old target intact and only a lock-protected sibling temp.

## Return

```text
root: /absolute/main/.rune
migration: none | completed | resumed
```

On failure, return no root. Report the exact conflicting, ambiguous, linked, or registered
path and the safe user action required before another attempt.
