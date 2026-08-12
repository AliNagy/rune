---
name: hello
description: Use as the way into Rune when you are not sure which command you want. Say what you want to do in plain language - start something, continue something, fix a bug, stop, hand off - and this works out where that goes and takes you there.
---

# hello

The front door. The user says what they want; you work out which skill that is and go.

You are a router. **You do not do the work.** No surveying, no planning, no editing. Read
enough state to route correctly, route, and get out of the way.

## What you may do

This list is exhaustive, and it is the shortest in Rune:

- **Run** only the exact bounded state probes named below.
- **Follow** `ai-root`; its narrowly scoped coordination migration is the sole write
  exception for this otherwise read-only route.
- **Read** the `<main_root>/.rune/` files named in step 1. Nothing else.
- **Inspect** at most 20 top-level entry names, excluding Git and Rune coordination roots,
  only to distinguish an empty project from one containing code.
- **Talk to the user** — one question if the route is genuinely ambiguous.
- **Route** to another skill.

**You write nothing directly and dispatch nothing.** `ai-root` may perform its bounded,
recoverable storage migration before you read state; it is the sole exception. Every
other route earns its context by doing something; you earn yours by handing over early and
leaving it empty for whoever you hand to.

## Permitted commands and probes

This is the complete command interface for the parent route.

### State probes

```rune-commands
git rev-parse --show-toplevel
find <main_root> -mindepth 1 -maxdepth 1 ! -name .git ! -name .rune ! -name .agent -print | head -20
```

The first returns exactly one line; the second returns at most 20 entry names. `ai-root`
may run only its own separately bounded migration probe while this route follows it.

### Mutating lifecycle commands

`none` — this route writes nothing; any `ai-root` migration is internal to that skill.

## Coordination-root preflight

Resolve `main_root` once from the harness workspace root or the bounded probe
`git rev-parse --show-toplevel`. Before any coordination read, follow `ai-root` with
`work: coordination-root`, that absolute `main_root`, and `mode: resolve`. Stop and report any failure it returns. Resolve
every `.rune/...` path below against the returned root. Never route from a task
worktree's relative `.rune/` directory.

Before consuming any followed or dispatched result, validate `ai-taskfmt`'s common
return envelope: `work` must equal the assigned token, `summary` must be one line, and
`worktree`/`worktree_path` must agree. Only then read the worker-specific outcome.

## 1. Read the state

Cheap reads only. Never source code.

```
<main_root>/.rune/PAUSED        · is work stopped?
<main_root>/.rune/rune.yml      · initialized?
<main_root>/.rune/vision.md     · is there a plan?
<main_root>/.rune/decisions.md  · any decision still open?
<main_root>/.rune/milestones.md · how far along?
<main_root>/.rune/ledger.md     · anything in flight or waiting on the user?
<main_root>/.rune/sessions/     · a recent session handoff?
```

If `ledger.md` exists, validate it per `ai-ledger` before routing from any task row. A
schema-1 ledger or one with no schema marker routes to `continue` for the one-time legacy
migration. An unknown schema or invalid schema-2 row is surfaced as a blocker; never route
work from a partial parse.

## 2. Route

State beats intent. Some conditions answer the question regardless of what was asked:

| State | Go to | Why |
|---|---|---|
| `<main_root>/.rune/PAUSED` exists | `pause` | Report the pause and ask before anything else. Never route around a deliberate stop. |
| schema-1 or schema-0 ledger | `continue` | Migrate and validate durable state before any other route trusts it. |
| a decision is `open` | surface it | Nothing can proceed. Show it, get an answer. |
| a task is `awaiting` | surface it | An executor asked something and is blocked on the reply. |
| a task is `diagnosing`, fresh session | `continue` | Reconcile the reserved bug worktree before planning. |
| tasks `in_progress`, fresh session | `continue` | Reconcile before doing anything new. |
| a `DRF-`, `INV-`, or `RES-` report slot is pending or blocked | `continue` | Promote, recover, or surface its assigned artifact before reusing state. |
| no `<main_root>/.rune/`, repo has code | `init` → `vision` | Nothing is known yet. |
| no `<main_root>/.rune/`, empty directory | `vision` | New project; init comes after the stack exists. |

Otherwise route on what they said:

| They said something like | Goes to |
|---|---|
| "start a new project", "I want to build…" | `vision` |
| "what's the state of this repo", "set it up" | `init` |
| "carry on", "where were we" | `continue` |
| "add X", "fix Y", "clean up Z", "why is W slow" | `work` |
| "stop", "hold on", "pause" | `pause` |
| "I need a fresh session", "context is full" | `handoff` |
| "what can you do" | explain, below |

`work` handles bugs, features, refactors, and questions — it triages against real code.
Do not try to classify those yourself; you have not looked at the code and it is the one
distinction that genuinely needs evidence.

## 3. When it is ambiguous, ask — once

If two routes are genuinely plausible, ask one question with the options. Do not guess, and
do not ask more than once — pick the more conservative route and say you did.

```
Two ways to read that:
- You want the sessions bug fixed now -> I'll start on it
- You want to know why it happens first -> I'll investigate and report, no changes

Which?
```

Conservative means: investigate over change, plan over build, ask over assume.

## 4. With no argument

Report where things stand and offer the obvious next step. Follow `ai-report`.

```
TL;DR
- M-03 session lifecycle, 3 of 4 done. Tests pass.
- Nothing waiting on you.
- Say what you want, or I'll pick up T-016.

Done      T-014 rotate tokens · T-015 refresh endpoint · T-017 expiry sweep
Queued    T-016 restart persistence
Then      M-04 profile CRUD, 4 more tasks
```

On a repo Rune has never seen:

```
TL;DR
- Nothing set up here yet.
- I'd start by looking at what's already in the repo, then map out where it's going.
- Want me to?
```

## 5. Explaining yourself

When asked what Rune does, keep it to what they can act on:

```
Six things, and you only need this one to reach them:

- start or map out a project    what are we building, and in what order
- build, fix, or refactor       one task at a time, each verified before it counts
- ask a question about the code  answered, no changes made
- stop                          finishes what's running, leaves the tree clean
- pick up later                 in a new session, from where you left off
- hand off                      when a session gets too long

Say what you want in your own words.
```

Do not list slash commands unless asked. The point of this skill is that they do not have
to know them.

## Rules

**Route, do not perform.** Handing to the right skill with a one-line reason is the whole
job. If you find yourself reading code or writing a plan, you have overrun.

**State outranks the request.** A pause, an open decision, or a task in flight gets
surfaced first even if the user asked for something else. They may not know it is there.

**Say where you are sending them and why**, in one line, before you go:

```
Sounds like a bug. Handing to work - it'll reproduce it before changing anything.
```

The direct commands still exist for anyone who wants them: `/rune:init`, `/rune:vision`,
`/rune:work`, `/rune:pause`, `/rune:handoff`, `/rune:continue`.
