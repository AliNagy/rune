---
name: ai-refactor
user-invocable: false
description: Use when changing structure without changing behaviour - cleanup, restructure, extraction, or a library migration. Requires a characterization net first and forbids editing tests.
---

# Refactor protocol

**Governing rule: if you had to change a test, it was not a refactor.**

That is the whole discipline. Everything else is machinery for making it true.

## 1. Require a safety net first

A refactor with no test coverage over the affected code is not a refactor — it is a
rewrite with extra steps and no way to know it worked.

Before any restructuring, establish that the behaviour is pinned:

1. Identify every entry point into the code being restructured.
2. Check what tests exercise them. Coverage tooling if available; otherwise read the
   tests and map them to entry points.
3. **If coverage is absent, the first task is writing characterization tests** — tests
   that assert current behaviour, whatever it is, including behaviour that looks wrong.

Characterization tests are not quality tests. They do not judge. They record what the
system does today so you can prove you did not change it. If you find behaviour that
looks like a bug, **pin it as-is** and file it separately. Fixing it during a refactor
destroys the only signal you have.

Refuse to proceed without the net. This is the one protocol where blocking is correct —
an unverifiable refactor is indistinguishable from silent breakage, and it will be marked
`done`.

## 2. Acceptance is inverted

For features and bugs, acceptance means a new check passes. Here it means **the existing
checks pass, unmodified**.

```
- [ ] Project oracle passes — identical results to baseline
- [ ] No test file appears in `git diff <base_commit>..<artifact_commit>`
- [ ] Public API surface unchanged (or: changed exactly as declared)
```

The second line is mechanical and it is the point. If a test needed editing, one of two
things happened: behaviour changed (not a refactor), or the test was coupled to internals
(a real finding — record it, but do not quietly rewrite it mid-refactor).

Where a signature change is genuinely intended — that is the refactor — declare it in the
task up front and list every call site in the change surface. Then it is a planned
migration, not a surprise.

## 3. Mechanical over clever

Prefer transformations a tool can do and a reader can check:

- `rename_symbol` over hand-editing every reference. It is exhaustive; you are not.
- `replace_in_files` with `dry_run=True` first — inspect the prospective diff, apply the
  ids you want. This eliminates over-broad replacement entirely.
- `find_referencing_symbols` before moving anything, so you know the true blast radius
  rather than the one you assume.

**One kind of change per task.** Moving code *and* renaming it *and* changing its
signature in one task means a failure tells you nothing about which change broke it. Each
task should be describable in a single clause.

## 4. Task shape

Refactors decompose differently from features — they are naturally horizontal, because
behaviour preservation is the invariant rather than end-to-end value.

```
T-1  add characterization tests for the session path      (net)
T-2  extract TokenStore interface, no call site changes   (additive)
T-3  migrate call sites to the interface                  (mechanical)
T-4  delete the old concrete dependency                   (subtractive)
```

Additive first, mechanical middle, subtractive last. Every intermediate state compiles
and passes. **Never leave the tree broken between tasks** — a half-migrated codebase where
the oracle fails is one abandoned session away from being unrecoverable, and the next
executor cannot tell breakage from baseline.

Keep the deletion task separate and last. It is the only irreversible one, and it is the
one you want to be able to skip if something surfaces.

## 5. Migrations

A framework or library migration is a refactor with a longer tail. Same rules, plus:

- Both old and new patterns will coexist for several tasks. State explicitly which is
  authoritative during the transition, in the milestone.
- Every task must say which side of the migration it leaves its files on.
- The final task removes the old path and the compatibility shims. If that task never
  gets written, the next survey reports a contradiction — two implementations of the same
  concept — and it will be right.

## 6. When it is really something else

- Behaviour is meant to change → feature, or bug. Not this.
- "Clean this up" with no stated invariant and no coverage → route to
  `ai-investigate` first. Establish what the code actually does before agreeing to
  preserve it.
