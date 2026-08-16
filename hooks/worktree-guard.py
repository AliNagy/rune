#!/usr/bin/env python3
"""Block a Rune worker from editing source outside its task worktree.

Wired from the frontmatter of the worker skills that touch source, so it is active only
while one of those skills is driving. It fails open: anything it cannot determine with
certainty is allowed through, because a guard that blocks legitimate work gets removed.

Rune states this rule twice in prose (`rune-work`, `rune-execute`) and explains why it is
stated twice. This file is what makes it true.
"""

import json
import os
import sys

WRITE_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}


def target_path(payload):
    tool = payload.get("tool_name")
    if tool not in WRITE_TOOLS:
        return None
    args = payload.get("tool_input") or {}
    for key in ("file_path", "notebook_path", "path"):
        value = args.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    path = target_path(payload)
    if not path:
        return 0

    abs_path = os.path.abspath(path)
    parts = abs_path.split(os.sep)

    # Coordination state and task worktrees both live under .rune/. Writing either is the
    # worker's job; writing anything else in the main checkout is not.
    if ".rune" in parts:
        return 0

    # Outside any checkout Rune knows about — not this guard's business.
    if not inside_rune_project(abs_path):
        return 0

    sys.stderr.write(
        "Blocked: {}\n\n"
        "This path is outside the task worktree. A Rune worker edits source only inside\n"
        "the worktree_path it was dispatched with, under .rune/worktrees/.\n\n"
        "If you are the coordinator, you have followed a worker skill instead of\n"
        "dispatching it — stop and dispatch the worker.\n".format(abs_path)
    )
    return 2


def inside_rune_project(abs_path):
    """True when abs_path sits under a directory tree that contains a .rune/ root."""
    directory = os.path.dirname(abs_path)
    while True:
        if os.path.isdir(os.path.join(directory, ".rune")):
            return True
        parent = os.path.dirname(directory)
        if parent == directory:
            return False
        directory = parent


if __name__ == "__main__":
    sys.exit(main())
