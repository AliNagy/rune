# Working on Rune

Rune ships skills and nothing else. The skills are the product, so the rules below are
about how they are written, not about how this repository is built.

## Enforce in frontmatter, not in prose

If a rule can be enforced by the harness, it must not be written as a sentence.

| Rule type | Where it goes |
|---|---|
| this job runs in its own context | `context: fork` |
| this worker cannot touch source | `allowed-tools` |
| this must never happen | a hook |
| judgment, tradeoffs, what to look at | prose in the skill |

A sentence describing a constraint the harness could have enforced is the weakest form of
that constraint, and it costs context every time the skill loads. Rune has removed
enforcement and kept its description twice — `agents/` in `58f0f09`, the validator scripts
in `bb89985`. Do not do it a third time.

## Workers fork, references do not

- **Worker skills declare `context: fork`.** Invoking one runs it in a separate context.
  These are the jobs in `rune-taskfmt`'s dispatch table.
- **Reference skills do not fork.** `rune-root`, `rune-report`, `rune-serena`,
  `rune-taskfmt`, `rune-ledger` load into the caller and are meant to.

A worker skill without `context: fork` gets read by the parent, and the parent then does
the work itself — silently, and looking like it succeeded. `rune-oracle` and `rune-drift`
are still in this state because each is both dispatched and followed; splitting them is
open work.

## Write workers in second person, parents in second person, and keep them apart

Every worker skill opens by telling the reader it is the worker. That is correct and it is
also why an unforked worker skill is dangerous: the parent believes it.

## Length is a feature of the product

Every word in a skill is spent from the budget Rune exists to protect. Before adding a
paragraph, check whether the point is already made in the same file — most restatements
here are restatements. Before adding a rule, check whether frontmatter or a hook can carry
it instead.

`rune-report` governs everything the user reads. Its rules are as binding as any schema in
`rune-taskfmt`, and they are the ones most often lost, because the specification voice used
throughout these files is exactly the voice the user must never be shown.
