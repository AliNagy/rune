#!/usr/bin/env python3
"""Parsed contract checks and a filesystem model for Rune's skills-only scaffold."""

from __future__ import annotations

import os
import re
import stat
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ROUTES = ("hello", "vision", "work", "pause", "handoff", "continue", "init")
SHELL_TOKENS = {
    "bash", "bun", "cargo", "cat", "chmod", "chown", "cmake", "cp", "curl", "dd",
    "docker", "echo", "find", "git", "go", "grep", "head", "install", "kill",
    "kubectl", "ln", "make", "mkdir", "mv", "node", "npm", "npx", "pkill", "pnpm",
    "printf", "python", "python3", "rg", "rm", "rmdir", "sed", "sh", "sudo", "tail",
    "tee", "terraform", "touch", "truncate", "wget", "xargs", "yarn", "zsh",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def section(markdown: str, heading: str, level: int = 2) -> str:
    marker = f"{'#' * level} {heading}"
    matches = list(re.finditer(rf"(?m)^{re.escape(marker)}\s*$", markdown))
    if len(matches) != 1:
        fail(f"expected one {marker!r}, found {len(matches)}")
    start = matches[0].end()
    end_match = re.search(rf"(?m)^#{{1,{level}}} (?!#)", markdown[start:])
    end = start + end_match.start() if end_match else len(markdown)
    return markdown[start:end]


def fenced_blocks(markdown: str) -> list[tuple[str, str]]:
    pattern = re.compile(
        r"(?ms)^(?P<fence>`{3,})(?P<info>[^\n]*)\n(?P<body>.*?)^(?P=fence)\s*$"
    )
    return [(match["info"].strip(), match["body"]) for match in pattern.finditer(markdown)]


def command_lines(markdown: str) -> list[str]:
    lines: list[str] = []
    for info, block in fenced_blocks(markdown):
        if info != "rune-commands":
            continue
        for raw in block.splitlines():
            command = raw.split(" #", 1)[0].strip()
            if command and not command.startswith("#"):
                lines.append(command)
    return lines


def reject_hidden_shell(markdown: str, route: str) -> None:
    for info, block in fenced_blocks(markdown):
        if info == "rune-commands":
            continue
        if info in {"bash", "sh", "shell", "zsh"}:
            fail(f"{route}: executable fence must use rune-commands, not {info}")
        for raw in block.splitlines():
            line = raw.strip()
            token_match = re.match(
                r"^(?:serena\.[A-Za-z0-9_.-]+(?=\(|\s|$)|[A-Za-z0-9_.-]+(?=\s|$))",
                line,
            )
            if not token_match:
                continue
            token = token_match.group(0)
            if token.startswith("serena.") or token in SHELL_TOKENS or line.startswith("#!"):
                fail(f"{route}: shell-looking line outside rune-commands fence: {line}")


def assert_bounded(command: str) -> None:
    bounded = (
        re.match(r"^git(?: -C \S+)? rev-parse ", command) is not None
        or (" status --porcelain | head -" in command)
        or " cat-file -e " in command
        or " merge-base " in command
        or " rev-list --count " in command
        or (
            " worktree list --porcelain | awk " in command
            and ("END { print" in command or "registered_worktrees=" in command)
        )
        or (command.startswith("find ") and " | head -" in command)
        or command == 'serena.activate_project(project="<main_root>")'
        or command
        == 'serena.find_symbol(relative_path="<probe_file>", name_path="<exact_name_path>", include_body=false)'
    )
    if not bounded:
        fail(f"unbounded or unknown state probe: {command}")


def check_public_interfaces() -> None:
    convention = section(read("skills/ai-taskfmt/SKILL.md"), "Bounded state probes", 3)
    for token in ("`rune-commands`", "match one admitted command", "Static validation rejects"):
        if token not in convention:
            fail(f"command-fence convention is incomplete: {token}")
    for route in PUBLIC_ROUTES:
        markdown = read(f"skills/{route}/SKILL.md")
        capabilities = section(markdown, "What you may do")
        if "**Run** only the exact" not in capabilities:
            fail(f"{route}: exhaustive capability list does not bind the command interface")

        interface = section(markdown, "Permitted commands and probes")
        state = section(interface, "State probes", level=3)
        lifecycle = section(interface, "Mutating lifecycle commands", level=3)
        commands = command_lines(state)
        if not commands:
            fail(f"{route}: no explicit state probe")
        for command in commands:
            assert_bounded(command)

        lifecycle_commands = command_lines(lifecycle)
        if route == "init":
            if lifecycle_commands != ["git -C <main_root> init --quiet"]:
                fail("init: lifecycle interface must contain only quiet git init")
            if "explicitly accepts initialization" not in lifecycle:
                fail("init: git init is not gated on explicit user acceptance")
            for token in ("unborn branch", "do not restart step 1", "initial commit"):
                if token not in markdown:
                    fail(f"init: post-git-init stop contract is missing: {token}")
        elif lifecycle_commands or "`none`" not in lifecycle:
            fail(f"{route}: unexpected parent lifecycle command")

        # Executable commands shown in procedure code blocks must be admitted verbatim.
        reject_hidden_shell(markdown, route)
        for command in command_lines(markdown):
            if command not in commands and command not in lifecycle_commands:
                fail(f"{route}: procedure command is outside its interface: {command}")

    expected_capabilities = {
        "work": ("**Write**", "decisions.md", "**delete**", "decisions/open/T-nnn.md"),
        "pause": ("**Delete**", ".rune/PAUSED"),
        "handoff": ("ledger.md", "**Delete**", "sessions/<stamp>.md"),
        "continue": ("**Write**", "decisions.md", "**delete**", "decisions/open/T-nnn.md"),
    }
    for route, tokens in expected_capabilities.items():
        capabilities = section(read(f"skills/{route}/SKILL.md"), "What you may do")
        missing = [token for token in tokens if token not in capabilities]
        if missing:
            fail(f"{route}: procedure capability missing from exhaustive list: {missing}")
    hello = read("skills/hello/SKILL.md")
    if "files named in step 1" not in section(hello, "What you may do") or "decisions.md" not in section(hello, "1. Read the state"):
        fail("hello: decision-state read is not covered by its exhaustive capability")


def parse_writer_table(markdown: str) -> dict[str, str]:
    body = section(markdown, "Single-writer rule")
    rows: dict[str, str] = {}
    for line in body.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 2 or cells[0] in {"File", "---"} or set(cells[0]) == {"-"}:
            continue
        if cells[0] in rows:
            fail(f"duplicate writer-table row: {cells[0]}")
        rows[cells[0]] = cells[1]
    return rows


def check_writer_and_lifecycle_contracts() -> None:
    taskfmt = read("skills/ai-taskfmt/SKILL.md")
    rows = parse_writer_table(taskfmt)
    writer = rows.get("`milestones.md`", "")
    if "ai-decompose" not in writer or "one worker" not in writer:
        fail("milestones.md does not have one ai-decompose writer")
    if any("milestones.md" in key and key != "`milestones.md`" for key in rows):
        fail("milestones.md appears in more than one writer-table row")

    vision_capabilities = section(read("skills/vision/SKILL.md"), "What you may do")
    if "milestones.md" in vision_capabilities:
        fail("vision parent still claims milestone write capability")
    graph_job = section(read("skills/ai-decompose/SKILL.md"), "Which job you were given")
    if "You are the sole writer for that file." not in graph_job:
        fail("milestone graph job does not implement sole-writer ownership")

    lifecycle = section(taskfmt, "Worktree container lifecycle")
    for owner in ("`ai-bug`", "`ai-drift`", "`ai-land`"):
        if owner not in lifecycle:
            fail(f"worktree lifecycle omits {owner}")
    checkout = section(taskfmt, "Checkout identity contract")
    if "only a successful lander may remove" in checkout:
        fail("obsolete lander-only worktree rule remains")
    for owner in ("`ai-bug`", "`ai-drift`", "`ai-land`"):
        if owner not in checkout:
            fail(f"checkout identity rules omit {owner}")

    continue_skill = read("skills/continue/SKILL.md")
    probe = section(section(continue_skill, "Permitted commands and probes"), "State probes", 3)
    if 'path "\\t" branch' not in probe or "branch-ref-or-detached" not in probe:
        fail("continue worktree probe does not return bounded path+branch records")
    reconcile = section(continue_skill, "2. Reconcile")
    if "`discard-empty` mode" not in reconcile:
        fail("continue still lacks delegated empty-worktree discard")

    drift_modes = section(read("skills/ai-drift/SKILL.md"), "Modes")
    if "**discard-empty**" not in drift_modes or "zero commits" not in drift_modes:
        fail("ai-drift discard-empty safety interface is incomplete")

    land = read("skills/ai-land/SKILL.md")
    cleanup = section(land, "Cleanup mode")
    returns = section(land, "Return")
    if "landing: cleaned | refused" not in returns or "`refused` keeps" not in returns:
        fail("ai-land cleanup return/retention contract is incomplete")
    if "failed worktree removal returns `landing: refused`" not in cleanup:
        fail("ai-land cleanup refusal is ambiguous")
    if "In cleanup mode, `refused` keeps it and `cleaned` proves it was" not in returns:
        fail("ai-land global retention rule conflicts with cleanup mode")


def canonical_manifest() -> tuple[str, ...]:
    root_skill = read("skills/ai-root/SKILL.md")
    blocks = re.findall(r"```rune-directory-manifest\n(.*?)```", root_skill, flags=re.S)
    if len(blocks) != 1:
        fail(f"expected one canonical directory manifest, found {len(blocks)}")
    entries = tuple(line.strip() for line in blocks[0].splitlines() if line.strip())
    if len(entries) != len(set(entries)):
        fail("canonical directory manifest contains duplicates")
    for entry in entries:
        path = Path(entry)
        if not entry.endswith("/") or path.is_absolute() or ".." in path.parts:
            fail(f"unsafe canonical manifest entry: {entry}")
    required = {"decisions/open/", "sessions/", "worktrees/"}
    if not required.issubset(entries):
        fail(f"canonical manifest misses issue #22 paths: {sorted(required - set(entries))}")
    for entry in entries:
        parent = str(Path(entry.rstrip("/")).parent)
        if parent != "." and f"{parent}/" not in entries:
            fail(f"manifest child lacks explicit parent: {entry}")
    return entries


def scaffold_semantics() -> dict[str, bool]:
    root_skill = read("skills/ai-root/SKILL.md")
    blocks = re.findall(r"```rune-scaffold-semantics\n(.*?)```", root_skill, flags=re.S)
    if len(blocks) != 1:
        fail(f"expected one scaffold-semantics block, found {len(blocks)}")
    semantics: dict[str, bool] = {}
    for line in blocks[0].splitlines():
        key, separator, value = line.strip().partition("=")
        if not separator or value not in {"true", "false"} or key in semantics:
            fail(f"invalid scaffold semantic: {line}")
        semantics[key] = value == "true"
    required = {
        "create_missing",
        "preserve_existing_directory",
        "preserve_existing_content",
        "reject_symlink",
        "reject_non_directory",
        "never_clear",
        "never_remove_container",
    }
    if set(semantics) != required or not all(semantics.values()):
        fail("scaffold semantics must define every required safety property as true")
    return semantics


def ensure_scaffold(
    root: Path, entries: tuple[str, ...], semantics: dict[str, bool]
) -> None:
    """Reference execution of ai-root's documented create-if-missing contract."""
    for entry in entries:
        target = root / entry.rstrip("/")
        if os.path.lexists(target):
            mode = target.lstat().st_mode
            if semantics["reject_symlink"] and stat.S_ISLNK(mode):
                raise ValueError(str(target))
            if semantics["reject_non_directory"] and not stat.S_ISDIR(mode):
                raise ValueError(str(target))
            continue
        if semantics["create_missing"]:
            target.mkdir()


def check_scaffold_behavior() -> None:
    entries = canonical_manifest()
    semantics = scaffold_semantics()
    init = read("skills/init/SKILL.md")
    if "authoritative `rune-directory-manifest`" not in init:
        fail("init duplicates or fails to consume ai-root's canonical manifest")

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / ".rune"
        root.mkdir()
        root_inode = root.stat().st_ino
        root_sentinel = root / "preserve-root.md"
        root_sentinel.write_text("keep root", encoding="utf-8")
        ensure_scaffold(root, entries, semantics)
        if any(not (root / entry).is_dir() for entry in entries):
            fail("first scaffold run did not create the manifest")
        sentinel = root / "decisions/open/preserve.md"
        sentinel.write_text("keep", encoding="utf-8")
        inodes = {entry: (root / entry).stat().st_ino for entry in entries}
        ensure_scaffold(root, entries, semantics)
        if root.stat().st_ino != root_inode or root_sentinel.read_text(encoding="utf-8") != "keep root":
            fail("scaffold cleared or replaced the container")
        if sentinel.read_text(encoding="utf-8") != "keep":
            fail("scaffold rerun did not preserve existing content")
        if inodes != {entry: (root / entry).stat().st_ino for entry in entries}:
            fail("scaffold rerun replaced an existing directory")

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / ".rune"
        outside = Path(temp) / "outside"
        root.mkdir()
        outside.mkdir()
        os.symlink(outside, root / "notes")
        try:
            ensure_scaffold(root, entries, semantics)
        except ValueError as error:
            if Path(str(error)) != root / "notes":
                fail("symlink rejection reported the wrong path")
        else:
            fail("scaffold followed a symlinked manifest directory")

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / ".rune"
        root.mkdir()
        (root / "worktrees").write_text("not a directory", encoding="utf-8")
        try:
            ensure_scaffold(root, entries, semantics)
        except ValueError as error:
            if Path(str(error)) != root / "worktrees":
                fail("non-directory rejection reported the wrong path")
        else:
            fail("scaffold accepted a non-directory manifest entry")


def main() -> None:
    check_public_interfaces()
    check_writer_and_lifecycle_contracts()
    check_scaffold_behavior()
    print("skill contracts and scaffold behavior: ok")


if __name__ == "__main__":
    main()
