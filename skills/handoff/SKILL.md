---
name: handoff
user-invocable: false
description: Use when this session's context is getting large and work should move to a fresh one. Captures what is in the conversation but not on disk, files the durable parts where they belong, and produces a short block to paste into the new session.
---

# handoff

Moves work to a fresh session without losing what this one learned.

Most of the state is already on disk — that is the whole design. This skill exists for the
part that is not: everything the user said, corrected, ruled out, or preferred, which
currently lives only in a conversation that is about to end.

## When

- context above roughly 70%, or answers getting vaguer
- a long session that has drifted across several milestones
- handing the project to someone else
- before a break long enough that you would not remember the thread

Do not wait for the ceiling. A handoff written at 70% is thorough; one written at 95% is
rushed and lossy, which defeats the point.

## What you may do

**You move what this conversation knows onto disk, then get out.** This list is exhaustive:

- **Run** only the exact bounded state probes named below.
- **Follow** `root`; its narrowly scoped coordination migration is the sole write
  exception outside this route's handoff records.
- **Read** `<main_root>/.rune/` coordination files.
- **Write** `<main_root>/.rune/vision.md`, `decisions.md`, `ledger.md` while draining, and
  `sessions/<stamp>.md`.
- **Delete** only an earlier `sessions/<stamp>.md` written by this same session after the
  replacement handoff is complete and validated.
- **When draining in-flight work**, use `pause`'s exact ledger-settlement and assigned
  report-promotion and staged-question promotion permissions, including deletion of only
  the consumed `<main_root>/.rune/decisions/open/T-nnn-eN.md`; do not compose or edit
  worker-authored content.
- **Talk to the user** — the paste block at the end.
- **Dispatch subagents**, naming the skill each one must follow.

## Permitted commands and probes

This is the complete command interface for the parent route.

### State probes

```rune-commands
git rev-parse --show-toplevel
```

The probe returns exactly one line. `root` may run only its own separately bounded
migration probe while this route follows it. Drain state comes from the ledger and worker
returns.

### Mutating lifecycle commands

`none` — a drain dispatches verification and landing exactly as `pause` does; handoff
files are normal coordination-file operations, not Git lifecycle commands.

## Coordination-root preflight

Resolve `main_root` once with the bounded probe `git rev-parse --show-toplevel`, then
follow `root` with `work: coordination-root`, that absolute root, and
`mode: initialize` before reading or writing
coordination state. Stop and report any failure it returns. Resolve every coordination
path against the returned root and include `main_root` plus absolute pointers in every
dispatch. If step 1 drains task work, reuse each ledger-recorded absolute `worktree_path`
through verification and landing.

Before consuming any followed or dispatched result, validate `taskfmt`'s common
return envelope: `work` must equal the assigned token, `summary` must be one line, and
`worktree`/`worktree_path` must agree. Only then read the worker-specific outcome.

**Anything not on that list is a dispatch**, including `map.md` and Serena memories. You
are the most context-starved parent in the system by the time you run; this is the worst
possible place to start reading files.

## 1. Settle the tree first

If work is in flight, drain it exactly as `pause` does — let executors finish, promote any
staged question into a parent-assigned decision and `awaiting` row, verify, and merge.
Never hand a torn tree to a session that has no idea what caused it.

If the user wants out immediately, a running worker still cannot be interrupted — `pause`
says why. Either wait for it to return, or follow `pause` in abandon mode to discard that
task's work, and then hand off. Say which one you did.

## 2. Triage what is in your head

This is the part that matters, and the part that is easy to do badly.

Go through the conversation for things that are **not** on disk. For each, ask: *is this
durable, or is it about this session?*

**Durable → file it where it belongs.** Do not leave it in a handoff doc that nobody opens
twice.

| What you found | Where it goes |
|---|---|
| a convention the user corrected you on | **dispatch `survey` in `amend` mode** — one convention → `map.md` |
| a codebase gotcha you discovered | **dispatch `survey` in `amend` mode** — one gotcha → a Serena memory |
| a choice made verbally | you write it — `decisions.md`, `status: decided` |
| a constraint on the project | you write it — `vision.md` |
| something the user wants built later | you write it — `vision.md`, as a want |

Either survey update uses the same canonical assignment, carrying the one fact and its
kind:

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

**One fact per dispatch, and one dispatch at a time.** Send it, wait for the return, then
send the next. Never batch facts into a list and never run two of these at once — both
workers would edit `map.md` from the copy they each loaded, and the second write would
silently erase the first. Never dispatch `mode: full` from here either; a full survey
re-derives the whole codebase to file a sentence, and overwrites the map while doing it.

Act on what comes back:

- `amended` — filed. Name it in the handoff doc's *Filed elsewhere* section.
- `unchanged` — already on disk. Say nothing; there is nothing to report.
- `conflict` — **ask the user before the session ends.** The worker quotes the map line
  your fact contradicts. One of the two is wrong and only the user knows which. If they
  are gone, put both in the handoff doc as an open thread; never guess and never re-send
  the same fact hoping for a different answer.
- `blocked` — put the fact in the handoff doc verbatim so the next session can file it.

These dispatches are not ceremony. You are running at ~70% context by definition — the
worst possible moment to open `map.md`, find the right section, and check a new line does
not contradict what is already there.

A want goes to `vision.md`, **not** `milestones.md`. A passing remark is not a plan; the
next `vision` decides whether it becomes one, with the decision records that requires.

**Session-transient → the handoff doc.** Approaches tried and rejected and why. Things the
user said they would handle themselves. Threads left open that are not yet tasks. Judgement
calls you made under ambiguity that the next session should know were judgement calls.

The test: *would this still be true and useful three sessions from now?* If yes, it belongs
in a permanent file. The handoff doc is for what stops being relevant once the work moves
on.

## 3. Write the doc

`<main_root>/.rune/sessions/YYYY-MM-DD-HHMM.md`. Keep it short — a fresh session pays for every line.

```markdown
# Session handoff · 2026-08-05 14:22

## Where things stand
M-03 session lifecycle, 3 of 4 done. T-016 queued. Tests pass, tree clean.

## Not on disk anywhere else
- Tried putting rotation in the middleware directly; the user rejected it as too
  much logic in the request path. Current design puts it in TokenStore.
- The user is handling the Postgres upgrade themselves. Do not touch docker-compose.
- Open thread, not yet a task: expired sessions accumulate with no sweep. Raised, not
  decided, not urgent.

## Judgement calls made
- Named it `rotate()` rather than `refresh()` to avoid confusion with the endpoint.
  Nobody asked; reverse it freely.

## Filed elsewhere this session
- DEC-012 expired sessions -> keep flagged (decided by user)
- map.md conventions: errors are typed Result unions, never thrown across modules
```

Four sections, and the second is the one with real value. If it is empty, say so — that
means everything is genuinely on disk and the new session needs nothing but the paste
block.

## 4. Produce the paste block

Fenced, self-contained, nothing for the user to fill in. A fresh session knows nothing —
including which project this is.

````
```
Continuing work on <project> at <path>. The Rune plugin is installed.

Read <path>/.rune/sessions/2026-08-05-1422.md first — it has context from the previous
session that is not in the ledger. Then pick up where that left off.
```
````

Keep it to three lines. If it needs more, the durable material was not filed properly in
step 2 — go back and file it.

Where a specific next action is already known, name it:

```
... Then pick up where that left off, and expect to start on T-016.
```

## 5. Report

Per `report`. TL;DR, then the block.

```
TL;DR
- Handoff written. Tree clean, tests pass, nothing half-done.
- Filed 3 durable things: a decision, a convention, and a Serena note on the auth module.
- Paste the block below into a new session.
```

## Rules

**Never invent history.** If you cannot remember why something was decided, say the
decision exists and the reasoning is lost. A plausible reconstruction becomes fact the
moment the next session reads it.

**Do not summarise the ledger.** The new session reads it directly, and a stale copy in
the handoff doc will contradict the real one within a task or two. Point at state; do not
duplicate it.

**One handoff per session.** If you write a second, delete the first — two handoff docs
mean the next session has to work out which is current, and it will guess wrong.
