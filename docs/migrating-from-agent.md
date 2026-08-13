# Migrating the legacy coordination directory

Rune 0.11 changes its durable coordination root from `.agent/` to `.rune/`. This is a
storage-format change: do not rename only the directory or update only `.gitignore`.

Rune ships no migration program. Every route follows the internal `rune-root` skill
before reading coordination state. That protocol gives the agent one consistent migration
interface while keeping Rune a skills-only instruction set.

## Skill-guided migration

After updating Rune, run `/rune:using-rune` from the orchestration checkout. Before
reading state, `rune-root` instructs the agent to:

1. check that only one coordination root exists;
2. confirm the legacy directory contains recognizable Rune state and no unsafe links;
3. inspect `git worktree list --porcelain` for a worktree registered at `.agent/` or below
   `.agent/worktrees/`;
4. acquire the migration lock, write a durable migration marker, and rename `.agent/` to
   `.rune/` in one same-filesystem rename;
5. rewrite known structured Rune pointers and the exact `.agent/worktrees/` ignore entry;
6. validate a schema-2 ledger, or preserve a recognized schema-1/schema-0 ledger for
   `rune-continue` to upgrade, and remove the marker and lock only after every rewrite succeeds.
   An unknown schema stops the migration.

Re-running the protocol is safe. If the session stops, its lock remains so a concurrent
agent cannot mistake partial state for an abandoned write. Confirm no Rune migration is
active, remove only that exact stale lock, and retry. A marker under `.rune/` resumes the
remaining rewrites; a marker under `.agent/` repeats the safety checks before the rename.
Each marker, pointer, ledger, and `.gitignore` change uses a validated sibling candidate,
preserves the target mode, and atomically renames over the unchanged target. Files beneath
`worktrees/` are never inspected or content-rewritten.

Commit the resulting rename and pointer updates together. Tasks, notes, decisions, drift
records, sessions, ledger state, configuration, and unregistered worktree directories are
preserved.

Rune refuses the migration if a coordination artifact is a symbolic link, if
`worktrees/` itself is a symbolic link, or if `.gitignore` is a symbolic link or non-file
path. Resolve those paths manually before retrying. Contents inside a real, unregistered
`worktrees/` directory are preserved byte for byte.

## Ownership checks

Rune does not claim every directory named `.agent/`. A recognizable legacy root must use
Rune's documented layout and contain an independent ownership signal such as initialized
configuration, a complete schema-2 Rune ledger, a recognizable schema-1/schema-0 Rune
ledger, an interrupted vision-and-decisions pair, a Rune map or session handoff, or a
schema-valid Rune task artifact. Unknown top-level entries make ownership ambiguous and
stop the migration. A recognized older ledger is preserved for `rune-continue` to upgrade
after root migration; it is not treated as schema 2.

Only exact absolute paths under the legacy Rune root and enumerated structured pointer
fields are rewritten. Free-form prose is preserved even when it mentions a similarly
named directory owned by another tool.

## Registered legacy worktrees

Rune refuses automatic migration while Git registers a worktree at `.agent/` or below
`.agent/worktrees/`; renaming its parent would leave Git pointing at the old location.
Finish or safely preserve the task's work, then remove each legacy registration with the
normal `git worktree remove <exact-path>` workflow. Confirm with `git worktree list`
before invoking Rune again.

Do not force-remove a worktree with uncommitted changes. Use the previous Rune version to
finish or hand off the task, or preserve its diff and commits manually before removing it.

## Both roots exist

If `.agent/` and `.rune/` both exist, Rune stops without reading, merging, renaming, or
deleting either one. Move backups of both roots outside the repository, determine which
contains the authoritative state, and restore exactly one root. If their contents
diverged, reconcile the copies manually; Rune will not guess which task or ledger state
wins.
