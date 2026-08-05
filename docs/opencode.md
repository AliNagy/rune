# Running Rune under OpenCode

Rune is authored for Claude Code. OpenCode support is generated from that canonical
source by `scripts/sync-opencode.mjs`, because the two harnesses differ in ways that a
straight copy cannot bridge.

## Install

```bash
git clone https://github.com/AliNagy/rune
cd rune
node scripts/sync-opencode.mjs
```

Restart OpenCode. The skills are auto-discovered — there is nothing to register.

```
/rune-init        establishes the oracle, maps the codebase
/rune-vision      surveys, interviews you, emits milestones
/rune-work        decomposes and executes
/rune-continue    resume in a fresh session
```

### Options

| Flag | Default | Purpose |
|---|---|---|
| `--provider <id>` | `opencode` | Model provider prefix. Use `anthropic` for a direct API key, `amazon-bedrock` for Bedrock. Run `opencode models` to see what you have. |
| `--target <dir>` | `~/.config/opencode` | Write somewhere else — e.g. `.opencode` in a project for a repo-local install. |
| `--dry-run` | | Report what would be written, touch nothing. |

Re-run it after pulling changes. It overwrites, so delete the generated `skills/rune-*`
and `agents/rune-*` first if you want a clean slate.

### Serena

Rune leans on Serena heavily. Add it to `opencode.json` if it isn't there:

```json
{
  "mcp": {
    "serena": {
      "type": "local",
      "command": ["serena", "start-mcp-server", "--context=ide", "--project-from-cwd"],
      "enabled": true,
      "timeout": 120000
    }
  }
}
```

## What the generator changes, and why

**Everything gets a literal `rune-` prefix.** Claude Code namespaces plugin skills as
`/rune:init`. OpenCode has no plugin namespace — a skill directory named `init` would
simply be `/init`, which is both generic and likely to collide. So directories become
`rune-init`, `rune-ai-taskfmt`, and so on, and every cross-reference inside skill bodies
is rewritten to match.

**Agent frontmatter is rewritten, not copied.** Claude Code agents declare
`model: sonnet` and an explicit tool list including `mcp__serena__*` names. OpenCode wants
`provider/model-id`, a `mode`, and a `tools` object — and its MCP tools are named
differently, so enumerating them by Claude Code's names would silently disable them. The
generator emits coarse `write` / `edit` gates instead, leaving read and search tools
available without naming them.

**Model tiering is preserved.** `planner` gets the strong model, everything else the fast
one — that split is the whole reason the agents exist as separate definitions.

## Known gaps

**No harness-level worktree isolation — handled in the executor instead.** Claude Code's
Agent tool takes an `isolation: "worktree"` flag; OpenCode's subagents have no equivalent.

This used to be the significant gap. It no longer is: executors verify they are in a
worktree before touching source and run `git worktree add` themselves if not, so the
guarantee holds on either harness. The flag is now a convenience rather than the
mechanism.

What you lose is automatic cleanup. Claude Code removes an unchanged worktree on its own;
under OpenCode, abandoned worktrees accumulate under `.agent/worktrees/`. `/rune-continue`
prunes ones with no matching ledger row, but check occasionally:

```bash
git worktree list
git worktree prune
```

**All the `rune-ai-*` skills are visible.** `user-invocable: false` is a Claude Code field;
OpenCode ignores unknown frontmatter, so the twelve `rune-ai-*` skills appear in the
palette alongside the four you actually invoke. They still work correctly if invoked by
the model — they're just not hidden. Ignore anything starting with `rune-ai-`.

**Skill permissions are the OpenCode way to restrict access.** If the visible `rune-ai-*`
entries bother you, `opencode.json` supports pattern-based skill permissions:

```json
{ "permission": { "skills": { "rune-ai-*": "deny" } } }
```

Be aware that `deny` hides a skill from agents entirely, not just from you — which would
break the system. Prefer living with the clutter.

## Staying in sync

The Claude Code source under `skills/` and `agents/` is canonical. Never edit the
generated files under `~/.config/opencode/` — they are overwritten on every sync. Fix the
source, re-run the generator.
