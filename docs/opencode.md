# Running Rune under OpenCode

Rune is authored as a Claude Code plugin, but its product is only the `SKILL.md` files.
There is no generator, executable adapter, or runtime package in this repository.

## Install

Copy this repository's `skills/` directory into OpenCode's skill directory. The names
already carry the `rune-` prefix, so nothing has to be rewritten — keep the directory
names, the frontmatter `name` fields, and `user-invocable: false` exactly as they are,
even though OpenCode currently displays skills marked that way.

The canonical source remains this repository's `skills/` directory. After updating the
repository, repeat the same copy.

There is one user-facing command:

```text
/using-rune
```

`rune-root` performs the coordination-root protocol as agent instructions. It does not
invoke a bundled resolver.

## Serena

Rune leans on Serena heavily. Add it to `opencode.json` if it is not already available:

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

## Harness differences

### No harness-level worktree allocation

The parent assigns every task one absolute worktree path before its first task-bound
worker. For a bug, `rune-bug` creates that exact checkout before writing its
reproduction; for other tasks, the first executor creates it. Every later executor,
verifier, recoverer, and lander receives and validates the same path.

All coordination reads and writes use the separately supplied absolute main-checkout path.
Neither harness may substitute the worker's starting directory or a fresh anonymous
checkout. A successful lander removes the worktree; abandoned paths remain under
`.rune/worktrees/` until the next reconciliation run.

### Internal skills remain visible

OpenCode may display all twenty-seven internal skills even though their frontmatter says
`user-invocable: false`. They are model-facing protocols and should not be called directly
by the user; `using-rune` reaches them all.

Do not deny them through skill permissions merely to hide them: that would also prevent
`using-rune` from loading the protocols it routes to.
