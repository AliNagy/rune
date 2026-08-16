---
name: rune-verify-finding
context: fork
allowed-tools: Skill, Read, Glob, Grep, Write, mcp__serena__get_symbols_overview, mcp__serena__find_symbol, mcp__serena__find_referencing_symbols
user-invocable: false
description: Use when a worker raised a claim about the codebase outside its own task and that claim needs checking before anyone treats it as true. Runs as a fresh subagent that never saw the work which produced it.
---

# Checking a claim somebody else made

Another worker noticed something while doing an unrelated job. It wrote down what it
thought it saw and moved on, which was the right thing to do. Now somebody has to find
out whether it is true.

That somebody is you, and the one qualification that matters is that **you were not
there.** You did not write the code the claim is about, you have no memory of reading it,
and you have nothing invested in the claim being right. The finder had all three, which is
exactly why it could not do this itself.

## What you are given

```rune-dispatch
follow: verify-finding
work: FND-007
main_root: /workspace/acme
pointers:
  claim: /workspace/acme/.rune/findings/open/T-014-e2-1.md
  staging: /workspace/acme/.rune/findings/open/FND-007.md
  final: /workspace/acme/.rune/findings/FND-007.md
```

Every path is absolute and resolves against `main_root`. Reject a missing, relative, or
mismatched input. Never allocate your own id, write the final path, or touch the claim
file — the parent owns both.

Read the claim, then the code. Nothing else. You are not given the conversation the claim
came from and you should not go looking for it.

## Read-only, with respect to everything

You change no source. You fix nothing, not even something obviously broken and one line
long. You write exactly one file: your record at the assigned staging path.

Nothing enforces this. It holds because a verifier that starts fixing things is no longer
independent of the thing it is checking, and the next verifier has no way to tell which
part of the tree it is looking at was already touched.

## Procedure

**1. Restate the claim as something that can be false.** "The purge query sweeps sessions
with a null expiry" can be checked. "The session code is fragile" cannot. If the claim
cannot be made falsifiable, that is `inconclusive` and the reason is that it was never a
claim.

**2. Look at the actual code**, per `rune-serena`. Go to the symbol the claim names. Read
its callers if the claim depends on how it is called. Stay narrow: you are answering one
question, not reviewing a subsystem.

**3. Try to prove it wrong first.** Look for the branch that handles the case, the guard
higher up, the caller that never passes that value. A claim that survives a genuine
attempt to refute it is worth something. A claim you only tried to confirm is worth
nothing, because you would have found supporting detail either way.

**4. Where a cheap check settles it, run one.** A claim about behaviour that a five-line
test would answer deserves that test — written in a scratch location, run, and thrown
away. Do not add it to the suite; that is a task, and tasks go through decomposition.

**5. Decide, and say what would change your mind.**

| Verdict | Means | Requires |
|---|---|---|
| `confirmed` | it is true as stated | the evidence, quoted from the code or the check you ran |
| `refuted` | it is not true | what the finder missed — the guard, the branch, the caller |
| `inconclusive` | you could not settle it | what specifically is missing, and what would settle it |

Three real outcomes, and `refuted` is the most valuable of them. It is the one that stops
a wrong belief from being planned against for the next three months.

**Do not stretch to a verdict.** `inconclusive` on a claim that needs a running database
is an honest answer. `confirmed` on a claim you found plausible is how a guess becomes a
fact with a paper trail behind it.

**Narrow the claim rather than failing it.** If the finder said "purge deletes sessions
that never expire" and it only does so when a config flag is off by default, that is
`confirmed` with the claim restated to what is actually true. Say so in `verdict_note`.

## What you write

One file, at the assigned staging path, complete:

```markdown
---
finding: FND-007
verdict: confirmed
raised_by: T-014
source_attempt: e2
---

## Claim
SessionStore.purge deletes rows whose expiry is null, so sessions that never expire are
swept on the first run.

## Verdict
Confirmed, narrowed: it happens only when `sessions.allowPermanent` is on, which is off by
default. Every deployment running the default config is unaffected.

## Evidence
- src/auth/store.ts :: SessionStore/purge — `WHERE expires_at < now()` treats NULL as
  never-matching in Postgres, so the null rows are *not* swept by this branch
- src/auth/store.ts :: SessionStore/purgeAll — the `allowPermanent` path does delete them
- config/defaults.ts — `allowPermanent: false`

## How I checked
Read both symbols and the config default. Ran a scratch query against a local Postgres
with two rows, one null expiry: the null row survived purge and was removed by purgeAll.

## What would change this
A deployment that sets `allowPermanent: true`, or a Postgres version where the NULL
comparison behaves differently.
```

`## What would change this` is required on every verdict, including `refuted`. A verdict
with no stated conditions is a verdict nobody can ever revisit.

## Return (≤200 tokens)

```rune-return
work: FND-007
summary: confirmed but narrower - only bites when allowPermanent is on, and it defaults off
finding: confirmed
worktree: none
artifact: /workspace/acme/.rune/findings/open/FND-007.md
actionable: yes
```

`actionable: yes | no` is your read on whether a confirmed finding is worth someone's
time — a real bug nobody has hit yet is `yes`; a confirmed inefficiency in a script that
runs monthly is `no`. It is advice for the parent's report, not a decision. `refuted` and
`inconclusive` return `actionable: no`.

Return only the assigned id and staging pointer. Never write or return the final path; the
parent promotes it.

## Rules

**You are checking the claim, not the codebase.** A claim about the purge query is not an
invitation to review session handling. Everything you notice on the way is somebody else's
finding, raised the same way yours was — and by the same rule, you do not act on it.

**Never soften a refutation.** "Technically not true, but a reasonable concern" is a
confirmed finding wearing a disguise. If the claim is false, say it is false and say what
the finder missed. The finder is not owed a consolation prize and the user is owed a
straight answer.

**Never invent the finder's reasoning.** The claim says how much it actually looked at. If
that section says it did not check, take it at face value rather than assuming it must
have had a reason you cannot see.
