---
name: handoff
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

- **Run** `git rev-parse --show-toplevel` and the bounded probes owned by `ai-root`.
- **Follow** `ai-root`; its narrowly scoped coordination migration is the sole write
  exception outside this route's handoff records.
- **Read** `<main_root>/.rune/` coordination files.
- **Write** `<main_root>/.rune/vision.md`, `decisions.md`, and `sessions/<stamp>.md`.
- **When draining in-flight work**, use `pause`'s exact ledger-settlement and assigned
  report-promotion permissions; do not compose or edit report content.
- **Talk to the user** — the paste block at the end.
- **Dispatch subagents**, naming the skill each one must follow.

## Coordination-root preflight

Resolve `main_root` once with the bounded probe `git rev-parse --show-toplevel`, then
follow `ai-root` with that absolute root and `mode: initialize` before reading or writing
coordination state. Stop and report any failure it returns. Resolve every coordination
path against the returned root and include `main_root` plus absolute pointers in every
dispatch. If step 1 drains task work, reuse each ledger-recorded absolute `worktree_path`
through verification and landing.

**Anything not on that list is a dispatch**, including `map.md` and Serena memories. You
are the most context-starved parent in the system by the time you run; this is the worst
possible place to start reading files.

## 1. Settle the tree first

If work is in flight, drain it exactly as `pause` does — let executors finish, verify,
merge. Never hand a torn tree to a session that has no idea what caused it.

If the user wants out immediately, that is `/rune:pause stop` first, then handoff. Say
which you did.

## 2. Triage what is in your head

This is the part that matters, and the part that is easy to do badly.

Go through the conversation for things that are **not** on disk. For each, ask: *is this
durable, or is it about this session?*

**Durable → file it where it belongs.** Do not leave it in a handoff doc that nobody opens
twice.

| What you found | Where it goes |
|---|---|
| a convention the user corrected you on | **dispatch `ai-survey` with `main_root`** — one convention → `map.md` |
| a codebase gotcha you discovered | **dispatch `ai-survey` with `main_root`** — one gotcha → a Serena memory |
| a choice made verbally | you write it — `decisions.md`, `status: decided` |
| a constraint on the project | you write it — `vision.md` |
| something the user wants built later | you write it — `vision.md`, as a want |

The two dispatches are not ceremony. You are running at ~70% context by definition — the
worst possible moment to open `map.md`, find the right section, and check a new line does
not contradict what is already there. One dispatch per item, never a list.

A want goes to `vision.md`, **not** `milestones.md`. A passing remark is not a plan; the
next `rune:vision` decides whether it becomes one, with the decision records that requires.

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
means everything is genuinely on disk and the new session needs nothing but
`/rune:continue`.

## 4. Produce the paste block

Fenced, self-contained, nothing for the user to fill in. A fresh session knows nothing —
including which project this is.

````
```
Continuing work on <project> at <path>. The Rune plugin is installed.

Read <path>/.rune/sessions/2026-08-05-1422.md first — it has context from the previous
session that is not in the ledger. Then run /rune:continue.
```
````

Keep it to three lines. If it needs more, the durable material was not filed properly in
step 2 — go back and file it.

Where a specific next action is already known, name it:

```
... Then run /rune:continue, and expect to pick up T-016.
```

## 5. Report

Per `ai-report`. TL;DR, then the block.

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
