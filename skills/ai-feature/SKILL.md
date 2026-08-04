---
name: ai-feature
user-invocable: false
description: Use when the requested behaviour does not exist yet, or a request is classified as new capability. Covers vertical slicing, surfacing design decisions before building, and integration acceptance across tasks.
---

# Feature protocol

**Governing rule: vertical slices, not horizontal layers.**

## 1. Establish the boundary

Before decomposing, state in one paragraph what this feature is and — more importantly —
what it is not.

Features fail by expanding. "Add user profiles" quietly becomes avatars, then image
upload, then a CDN decision. Write the exclusions down; they become the `out:` scope on
the milestone and the `forbidden` entries on the tasks.

If the feature belongs to an existing milestone, check its scope first. If it does not
fit any milestone, that is worth saying — either it is a new milestone or the vision
needs revisiting. Do not silently graft it onto the nearest one.

## 2. Surface decisions before building

Any choice with more than one defensible answer becomes a **decision record** per
`ai-taskfmt`, and blocks decomposition until resolved.

Typical: storage shape, sync vs. async, where validation lives, what happens on partial
failure, whether this is user-configurable.

**Recommend, do not assume.** State your preference and why, then wait. A decision the
agent made silently is one nobody will find until it is load-bearing across four tasks
and expensive to reverse.

The gate is mechanical: no task may be generated that depends on an `open` decision.

## 3. Slice vertically

Each task must be independently verifiable the moment it lands.

**Horizontal — wrong:**
```
T-1  all the interfaces
T-2  all the implementations
T-3  all the tests
```
None can be verified alone. T-1 has nothing to test. T-3 has no red-then-green evidence
because the code already worked when it was written. The whole milestone is unverifiable
until the last task lands, which is exactly the failure mode the ledger exists to prevent.

**Vertical — right:**
```
T-1  store a profile record end to end, with a test
T-2  read it back through the API, with a test
T-3  edit it, with a test
```
Every task leaves something demonstrably working.

The first slice should be the **thinnest end-to-end path** — one field, one route, one
test. It validates the shape of the design against real code before you have built four
tasks on top of an assumption.

## 4. Integration acceptance

Individual task acceptance is not enough. A feature can have every task green and still
not work as a feature.

Give the milestone its own acceptance criteria, checked after the last task:

```
acceptance:
  - a user can create, read, and edit a profile through the API
  - profile data survives a restart
  - a deleted user's profile is unreachable
```

These are milestone-level and belong in `milestones.md`. They frequently catch the
seam between two individually-correct tasks.

## 5. Task shape

Per `ai-decompose`: ≤5 files, one subsystem, one checkable outcome, each with a
test that did not exist before.

Feature-specific:

- **Name the integration point** in the change surface. Most feature tasks add code *and*
  wire it in; a task that adds an unwired implementation produces an orphan, and the next
  survey will flag it as abandoned work.
- **State what happens on failure.** Features are where error paths get forgotten, and an
  untested error path is not a feature, it is a liability.
- **No task may leave the tree broken.** If a slice temporarily requires a stub to keep
  the build green, that stub is part of the task and its removal is part of a later one —
  named explicitly, not left to be noticed.

## 6. When it is really something else

- The behaviour half-exists and is broken → `ai-bug`.
- It exists and works, but the shape is wrong → `ai-refactor`.
- You cannot scope it because nobody knows what is wanted → stop. That is a vision gap,
  not a feature. Route it back to `rune:vision`.
