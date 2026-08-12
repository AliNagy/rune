---
name: ai-serena
user-invocable: false
description: Use before reading or editing any source file. Enforces symbol-level lookup over whole-file reads, and symbol-level edits over read-then-patch - the single largest lever on the context budget.
---

# Reading code without spending the budget

Rune targets under 150k context per unit of work. Reading files is where that budget
dies. Serena is symbol-addressed, so it lets you retrieve the 40 lines that matter
instead of the 900 that surround them.

**Agents do not blow budgets reading what they need. They blow them exploring.**

## The ladder

Climb only as far as the task requires. Stop at the first rung that answers the question.

1. `get_symbols_overview(file)` — what is in this file. Cheap. Almost always enough to
   orient.
2. `find_symbol(name_path)` with `include_body=false` — where a thing lives, its shape.
3. `find_symbol(name_path, include_body=true)` — the actual code, **one symbol at a
   time**.
4. `Read(file)` — last resort. Justify it. Legitimate for small config, lockfiles, and
   plain prose docs; rarely for source.

## Substitutions

| Instead of | Use | Why |
|---|---|---|
| `Read` whole file | `get_symbols_overview` then `find_symbol` | 10–50x less context |
| `grep -r` for callers | `find_referencing_symbols` | precise; no false hits in comments or strings |
| Read then `Edit` | `replace_symbol_body` | never loads the untouched remainder |
| Many small same-shape edits | `replace_in_files` (dry run first) | one call instead of N |
| Hunting a definition by eye | `find_declaration` | resolves through re-exports and aliases |
| Guessing whether it compiles | `get_diagnostics_for_file` | the language server already knows |

## Rules

**Honour the `forbidden` list.** A task's context contract names paths that are
irrelevant and expensive. Opening one is a budget violation. If the work genuinely
requires a forbidden path, that is drift — stop and report it (`ai-drift`), do not
quietly widen your reach.

**Never read a file "to get oriented."** Orientation comes from
`<main_root>/.rune/map.md`, which
already exists precisely so nobody has to re-derive it. If the map is missing or stale,
that is an `rune:init` problem, not something to solve by browsing.

**Prefer `replace_in_files` with `dry_run=True` for bulk edits.** The dry run returns
every prospective change with an occurrence id; apply only the ids you want. This costs
one extra call and removes the entire class of over-broad replacement mistakes.

**Activate the project once.** `activate_project` at session start. If the language
server is cold, the first symbol query is slow — that cost is paid once, not per query,
so do not fall back to `Read` because one lookup felt slow.

## Serena memories vs. `.rune/`

Two stores, different jobs, do not mix them.

- **Serena memories** — stable, agent-facing background knowledge about the codebase.
  Architecture notes, subsystem explanations, gotchas. Survives sessions. Written only by
  `ai-survey` workers. `rune:init`, `rune:vision`, and `handoff` dispatch those workers;
  no parent route writes a memory itself.
- **`.rune/*`** — the plan and its mutable state. Human-readable, git-tracked, edited
  by the user. Vision, milestones, tasks, ledger.

If a human needs to read and edit it, it goes in `.rune/`. If it only exists to save an
agent from re-deriving something, it goes in a Serena memory.

## Budget discipline

Check your consumption at natural boundaries. At roughly 60% of budget, stop taking on
new ground: finish the step in flight, write the handoff note, and return. An executor
that runs to exhaustion produces a truncated result and no handoff, which forces the
next one to start from nothing.

Returning early with a good handoff is a success. Running out of context is not.
