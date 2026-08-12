#!/usr/bin/env python3
"""Parsed contract checks and a filesystem model for Rune's skills-only scaffold."""

from __future__ import annotations

import os
import re
import stat
import tempfile
from dataclasses import dataclass, field
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

WORKTREE_OUTCOMES = {"none", "kept", "discarded"}
COMMAND_OUTCOMES = {"passing", "failing", "unavailable"}
ORACLE_OUTCOMES = {"passing", "failing", "none"}
TASK_TYPES = {"feature", "bug", "refactor", "characterization", "chore"}
RETURN_SCHEMAS: dict[str, dict[str, set[str]]] = {
    "ai-bug": {"diagnosis": {"reproduced", "not_reproduced", "reclassified", "blocked"}},
    "ai-decompose": {"plan": {"graph", "drafted", "reconciled", "blocked"}},
    "ai-drift": {"status": {"drifted", "recorded", "quiesced", "abandoned", "discarded", "refused", "budget", "question"}},
    "ai-execute": {"status": {"done", "drifted", "budget", "blocked", "question"}},
    "ai-investigate": {"investigation": {"answered", "blocked"}},
    "ai-land": {"landing": {"landed", "refused", "conflict", "reverted", "stuck", "not_landed", "cleaned"}},
    "ai-oracle": {"oracle": ORACLE_OUTCOMES},
    "ai-recover": {"verdict": {"salvage", "discard", "partial"}},
    "ai-research": {"research": {"answered", "blocked"}},
    "ai-root": {"migration": {"none", "completed", "resumed", "blocked"}},
    "ai-survey": {"survey": {"mapped", "blocked"}},
    "ai-taskfmt": {"status": {"done", "drifted", "budget", "blocked", "question"}},
    "ai-triage": {"type": {"bug", "feature", "refactor", "investigation"}},
    "ai-verify": {"verdict": {"pass", "fail", "unverified"}},
    "work": {
        "status": {"done", "drifted", "budget", "blocked", "question"},
        "type": {"bug", "feature", "refactor", "investigation"},
    },
}
PRIMARY_OUTCOME_FIELDS = {
    field_name
    for schema in RETURN_SCHEMAS.values()
    for field_name in schema
}
EXPECTED_RETURN_EXAMPLES = {
    "ai-bug": 1, "ai-decompose": 1, "ai-drift": 3, "ai-execute": 1,
    "ai-investigate": 1, "ai-land": 2, "ai-oracle": 1, "ai-recover": 1,
    "ai-research": 1, "ai-root": 1, "ai-survey": 1, "ai-taskfmt": 2,
    "ai-triage": 1, "ai-verify": 1, "work": 2,
}
EXPECTED_DISPATCH_EXAMPLES = {
    "ai-bug": 1,
    "ai-root": 1,
    "ai-taskfmt": 4,
    "handoff": 1,
    "init": 2,
    "vision": 2,
    "work": 1,
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


def top_level_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if not line or line[0].isspace():
            continue
        match = re.fullmatch(r"([a-z_]+):\s*(.*)", line)
        if not match:
            raise ValueError(f"invalid top-level return line: {line}")
        key, value = match.groups()
        if key in fields:
            raise ValueError(f"duplicate return field: {key}")
        fields[key] = value.split(" #", 1)[0].strip()
    return fields


def enum_values(value: str) -> set[str]:
    values: set[str] = set()
    for raw in value.split("|"):
        item = raw.strip()
        if not item:
            raise ValueError("empty enum value")
        values.add(item.split(maxsplit=1)[0])
    return values


def validate_return_budget_paragraph(paragraph: str) -> None:
    for budget in re.findall(r"\b(\d+)\s*(?:-|\s)?tokens?\b", paragraph):
        if int(budget) != 200:
            raise ValueError(f"contradictory return budget: {budget} tokens")


def normalize_return_fields(
    fields: dict[str, str], *, allow_historical_task: bool = False
) -> dict[str, str]:
    normalized = dict(fields)
    if "work" in normalized and "task" in normalized:
        raise ValueError("return contains both work and legacy task")
    if "work" not in normalized and "task" in normalized:
        if not allow_historical_task:
            raise ValueError("canonical return uses legacy task field")
        normalized["work"] = normalized.pop("task")
    return normalized


def validate_return_fields(
    fields: dict[str, str],
    schemas: dict[str, set[str]],
    *,
    allow_historical_task: bool = False,
) -> dict[str, str]:
    fields = normalize_return_fields(
        fields, allow_historical_task=allow_historical_task
    )
    for key in ("work", "summary", "worktree"):
        if not fields.get(key):
            raise ValueError(f"missing common return field: {key}")
    if (
        "\n" in fields["summary"]
        or "\r" in fields["summary"]
        or re.search(r"(?i)\btwo lines\b", fields["summary"])
    ):
        raise ValueError("summary must be exactly one line")
    outcome_keys = set(fields).intersection(PRIMARY_OUTCOME_FIELDS)
    if len(outcome_keys) != 1:
        raise ValueError("return must contain exactly one primary outcome")
    outcome_key = next(iter(outcome_keys))
    if outcome_key not in schemas:
        raise ValueError(f"outcome field is not valid for this worker: {outcome_key}")
    if not enum_values(fields[outcome_key]).issubset(schemas[outcome_key]):
        raise ValueError(f"invalid {outcome_key} enum")
    worktrees = enum_values(fields["worktree"])
    if not worktrees.issubset(WORKTREE_OUTCOMES):
        raise ValueError("invalid worktree enum")
    if worktrees == {"none"} and "worktree_path" in fields:
        raise ValueError("non-task return invented a worktree path")
    if worktrees != {"none"} and not fields.get("worktree_path"):
        raise ValueError("task-bound return omitted worktree path")
    if "oracle" in fields and not enum_values(fields["oracle"]).issubset(ORACLE_OUTCOMES):
        raise ValueError("invalid oracle enum")
    if "oracle_result" in fields and not enum_values(fields["oracle_result"]).issubset(
        ORACLE_OUTCOMES
    ):
        raise ValueError("invalid oracle result enum")
    return fields


def validate_dispatch_fields(
    fields: dict[str, str], *, allow_historical_task: bool = False
) -> dict[str, str]:
    normalized = dict(fields)
    if "work" in normalized and "task" in normalized:
        raise ValueError("dispatch contains both work and legacy task")
    if "work" not in normalized and "task" in normalized:
        if not allow_historical_task:
            raise ValueError("canonical dispatch uses legacy task field")
        normalized["work"] = normalized.pop("task")
    for key in ("follow", "work", "main_root"):
        if not normalized.get(key):
            raise ValueError(f"missing common dispatch field: {key}")
    return normalized


def check_dispatch_examples_and_callers() -> None:
    counts: dict[str, int] = {}
    bindings: dict[str, list[tuple[str, str]]] = {}
    for relative in sorted((ROOT / "skills").glob("*/SKILL.md")):
        skill = relative.parent.name
        markdown = relative.read_text(encoding="utf-8")
        for info, block in fenced_blocks(markdown):
            if info != "rune-dispatch":
                continue
            counts[skill] = counts.get(skill, 0) + 1
            try:
                fields = validate_dispatch_fields(top_level_fields(block))
            except ValueError as error:
                fail(f"{skill}: invalid canonical dispatch example: {error}")
            bindings.setdefault(skill, []).append((fields["follow"], fields["work"]))
    if counts != EXPECTED_DISPATCH_EXAMPLES:
        fail(f"explicit dispatch-example inventory drifted: {counts}")

    try:
        validate_dispatch_fields(
            {"follow": "ai-execute", "task": "T-001", "main_root": "/repo"}
        )
    except ValueError:
        pass
    else:
        fail("canonical dispatch validator accepted legacy task")
    historical = validate_dispatch_fields(
        {"follow": "ai-execute", "task": "T-001", "main_root": "/repo"},
        allow_historical_task=True,
    )
    if historical.get("work") != "T-001" or "task" in historical:
        fail("historical dispatch did not normalize task to work")

    for route in PUBLIC_ROUTES:
        markdown = read(f"skills/{route}/SKILL.md")
        caller_paragraphs = [
            paragraph
            for paragraph in re.split(r"\n\s*\n", markdown)
            if "Before consuming any followed or dispatched result" in paragraph
        ]
        if len(caller_paragraphs) != 1 or not all(
            token in caller_paragraphs[0]
            for token in ("common", "return envelope", "`work`", "`summary`", "`worktree`/`worktree_path`", "Only then")
        ):
            fail(f"{route}: caller consumes an outcome before the common envelope")
        if "work: coordination-root" not in markdown:
            fail(f"{route}: ai-root caller omitted its canonical work token")

    direct_bindings = {
        "ai-bug": [("ai-bug", "T-nnn")],
        "handoff": [("ai-survey", "survey")],
        "init": [("ai-survey", "survey"), ("ai-oracle", "init/commands")],
        "vision": [("ai-survey", "survey"), ("ai-decompose", "vision/graph")],
        "work": [("ai-bug", "T-nnn")],
    }
    for skill, expected in direct_bindings.items():
        if bindings.get(skill) != expected:
            fail(f"{skill}: parsed caller bindings drifted: {bindings.get(skill)}")

    ledger = read("skills/ai-ledger/SKILL.md")
    tables = re.findall(
        r"(?ms)^\|\s*phase\s*\|\s*followed\s*\|\s*work\s*\|\s*outcome\s*\|\n"
        r"^\|[-|\s]+\|\n(?P<body>(?:^\|[^\n]*\|\n)+)",
        ledger,
    )
    if not tables:
        fail("ledger dispatch log has no canonical work table")
    rows = [
        tuple(cell.strip() for cell in line.strip().strip("|").split("|"))
        for table in tables
        for line in table.splitlines()
    ]
    for row in rows:
        if (
            len(row) != 4
            or not row[2]
            or row[2] == "—"
            or re.search(r"/e\d+$", row[2])
        ):
            fail(f"ledger dispatch row has an invalid work binding: {row}")
    for expected in (
        ("plan-graph", "ai-decompose", "vision/graph"),
        ("survey", "ai-survey", "survey"),
        ("commands", "ai-oracle", "init/commands"),
    ):
        if not any(row[:3] == expected for row in rows):
            fail(f"ledger pre-init dispatch omitted canonical binding: {expected}")

    init = read("skills/init/SKILL.md")
    if "| phase | followed | work | outcome |" not in init:
        fail("init scaffold still creates the legacy dispatch header")


def check_return_examples_and_budgets() -> None:
    counts: dict[str, int] = {}
    for relative in sorted((ROOT / "skills").glob("*/SKILL.md")):
        skill = relative.parent.name
        markdown = relative.read_text(encoding="utf-8")
        for info, block in fenced_blocks(markdown):
            if info != "rune-return":
                continue
            counts[skill] = counts.get(skill, 0) + 1
            if skill not in RETURN_SCHEMAS:
                fail(f"{skill}: rune-return has no parsed schema")
            try:
                validate_return_fields(top_level_fields(block), RETURN_SCHEMAS[skill])
            except ValueError as error:
                fail(f"{skill}: invalid rune-return example: {error}")

        for paragraph in re.split(r"\n\s*\n", markdown):
            if not re.search(r"(?i)\b(return|digest|worker budget)\b", paragraph):
                continue
            try:
                validate_return_budget_paragraph(paragraph)
            except ValueError as error:
                fail(f"{skill}: {error}")
            for outcome_key, allowed in RETURN_SCHEMAS.get(skill, {}).items():
                mentioned = set(
                    re.findall(rf"`{re.escape(outcome_key)}: ([a-z_]+)`", paragraph)
                )
                unknown = mentioned - allowed
                if unknown:
                    fail(
                        f"{skill}: prose return outcomes are outside the parsed schema: "
                        f"{sorted(unknown)}"
                    )
    if counts != EXPECTED_RETURN_EXAMPLES:
        fail(f"explicit return-example inventory drifted: {counts}")

    taskfmt = read("skills/ai-taskfmt/SKILL.md")
    if "There are no per-job\nexceptions" not in taskfmt:
        fail("canonical return budget still permits undocumented exceptions")

    invalid_examples = (
        ({"work": "T-001", "status": "done", "worktree": "kept", "worktree_path": "/repo/T-001"}, "missing summary"),
        ({"work": "T-001", "task": "T-001", "summary": "done", "status": "done", "worktree": "kept", "worktree_path": "/repo/T-001"}, "dual id"),
        ({"work": "survey", "summary": "mapped", "survey": "mapped", "worktree": "none", "worktree_path": "/invented"}, "non-task path"),
        ({"work": "T-001", "summary": "done", "status": "finished", "worktree": "kept", "worktree_path": "/repo/T-001"}, "invalid outcome"),
        ({"work": "T-001", "summary": "done", "status": "done", "worktree": "work", "worktree_path": "/repo/T-001"}, "invalid worktree"),
        ({"work": "T-001", "summary": "done", "status": "done", "worktree": "kept", "oracle": "pass", "worktree_path": "/repo/T-001"}, "invalid oracle"),
        ({"work": "T-001", "summary": "line one\nline two", "status": "done", "worktree": "kept", "worktree_path": "/repo/T-001"}, "multiline summary"),
        ({"work": "T-001", "summary": "done", "status": "done", "verdict": "pass", "worktree": "kept", "worktree_path": "/repo/T-001"}, "second global outcome"),
        ({"task": "T-001", "summary": "done", "status": "done", "worktree": "kept", "worktree_path": "/repo/T-001"}, "canonical legacy task"),
    )
    for fields, label in invalid_examples:
        try:
            validate_return_fields(fields, RETURN_SCHEMAS["ai-taskfmt"])
        except ValueError:
            pass
        else:
            fail(f"return validator accepted {label}")

    legacy = validate_return_fields(
        {
            "task": "T-001",
            "summary": "historical return",
            "status": "done",
            "worktree": "kept",
            "worktree_path": "/repo/T-001",
        },
        RETURN_SCHEMAS["ai-taskfmt"],
        allow_historical_task=True,
    )
    if legacy.get("work") != "T-001" or "task" in legacy:
        fail("legacy task field did not normalize deterministically")
    try:
        validate_return_fields(
            {"task": "T-001", "status": "done", "worktree": "kept", "worktree_path": "/repo/T-001"},
            RETURN_SCHEMAS["ai-taskfmt"],
            allow_historical_task=True,
        )
    except ValueError:
        pass
    else:
        fail("legacy return without summary was accepted")

    try:
        validate_return_budget_paragraph("Return digest under 300 tokens")
    except ValueError:
        pass
    else:
        fail("return-budget lint accepted a 300-token exception")


def validate_command_outcome(value: str) -> None:
    if value not in COMMAND_OUTCOMES:
        raise ValueError(f"invalid command outcome: {value}")


def normalize_legacy_command_outcome(value: str) -> str:
    mapping = {"ok": "passing", "fail": "failing", "none found": "unavailable"}
    if value in COMMAND_OUTCOMES:
        return value
    if value in mapping:
        return mapping[value]
    raise ValueError(f"unknown legacy command outcome: {value}")


def validate_oracle_outcome(value: str) -> None:
    if value not in ORACLE_OUTCOMES:
        raise ValueError(f"invalid oracle outcome: {value}")


def validate_landing_oracle(
    landing: str, oracle: str | None, *, oracle_configured: bool
) -> None:
    if landing == "landed":
        if oracle == "passing":
            return
        if oracle == "none" and not oracle_configured:
            return
        raise ValueError("landed has contradictory oracle verdict")
    if landing == "reverted":
        if oracle != "failing":
            raise ValueError("reverted must report the failed merge oracle")
        return
    if landing == "stuck":
        if oracle not in {None, "failing"}:
            raise ValueError("stuck has impossible oracle evidence")
        return
    if landing in {"refused", "conflict", "not_landed", "cleaned"}:
        if oracle is not None:
            raise ValueError("pre-oracle landing outcome invented oracle evidence")
        return
    raise ValueError("unknown landing outcome")


def check_command_and_oracle_enums() -> None:
    init = read("skills/init/SKILL.md")
    manifests = [
        block
        for info, block in fenced_blocks(init)
        if info == "yaml" and "commands:" in block and "oracle:" in block
    ]
    if len(manifests) != 1:
        fail(f"expected one parsed rune.yml example, found {len(manifests)}")
    manifest = manifests[0]
    command_match = re.search(r"(?ms)^commands:\n(?P<body>.*?)^oracle:\n", manifest)
    oracle_match = re.search(r"(?ms)^oracle:\n(?P<body>.*?)(?:^[a-z_]+:|\Z)", manifest)
    if not command_match or not oracle_match:
        fail("could not parse command/oracle sections from rune.yml example")
    command_statuses = re.findall(
        r"(?m)^  [a-z_]+:\s*\{[^\n]*\bstatus:\s*([a-z_]+)", command_match["body"]
    )
    if len(command_statuses) < 4:
        fail("rune.yml example omitted command statuses")
    try:
        for status in command_statuses:
            validate_command_outcome(status)
    except ValueError as error:
        fail(str(error))
    stored_oracle = re.search(r"(?m)^  status:\s*([a-z_]+)\s*$", oracle_match["body"])
    if not stored_oracle:
        fail("rune.yml example omitted oracle status")
    try:
        validate_oracle_outcome(stored_oracle[1])
    except ValueError as error:
        fail(str(error))

    oracle_skill = read("skills/ai-oracle/SKILL.md")
    return_blocks = [body for info, body in fenced_blocks(oracle_skill) if info == "rune-return"]
    if len(return_blocks) != 1:
        fail("ai-oracle must expose one parsed return example")
    digest = return_blocks[0]
    transient_commands = re.findall(
        r"(?m)^  [a-z_]+:\s*(passing|failing|unavailable)(?:\s|$)", digest
    )
    if len(transient_commands) < 5:
        fail("ai-oracle return omitted parsed command verdicts")
    try:
        for status in transient_commands:
            validate_command_outcome(status)
        validate_oracle_outcome(top_level_fields(digest)["oracle"])
    except ValueError as error:
        fail(str(error))

    for invalid in ("ok", "fail", "none"):
        try:
            validate_command_outcome(invalid)
        except ValueError:
            pass
        else:
            fail(f"command enum accepted legacy synonym: {invalid}")
    if [normalize_legacy_command_outcome(value) for value in ("ok", "fail", "none found")] != [
        "passing", "failing", "unavailable"
    ]:
        fail("legacy command outcomes did not normalize deterministically")
    try:
        normalize_legacy_command_outcome("skipped")
    except ValueError:
        pass
    else:
        fail("unknown legacy command outcome was guessed")
    for invalid in ("ok", "pass", "fail", "unavailable"):
        try:
            validate_oracle_outcome(invalid)
        except ValueError:
            pass
        else:
            fail(f"oracle enum accepted noncanonical value: {invalid}")

    validate_landing_oracle("landed", "passing", oracle_configured=True)
    validate_landing_oracle("landed", "none", oracle_configured=False)
    validate_landing_oracle("reverted", "failing", oracle_configured=True)
    validate_landing_oracle("conflict", None, oracle_configured=True)
    for landing, oracle, configured in (
        ("landed", "failing", True),
        ("landed", "none", True),
        ("reverted", "passing", True),
        ("reverted", None, True),
        ("conflict", "passing", True),
        ("refused", "none", False),
        ("not_landed", "passing", True),
        ("stuck", "passing", True),
    ):
        try:
            validate_landing_oracle(landing, oracle, oracle_configured=configured)
        except ValueError:
            pass
        else:
            fail(f"landing/oracle mapping accepted {landing}/{oracle}")

    taskfmt = section(read("skills/ai-taskfmt/SKILL.md"), "Check-result vocabulary", 3)
    for token in (
        "stored/transient mapping is identity",
        "`passing \\| failing \\| unavailable`",
        "`passing \\| failing \\| none`",
        "Post-merge landing uses the same oracle enum",
    ):
        if token not in taskfmt:
            fail(f"check vocabulary mapping is incomplete: {token}")
    if "`ok -> passing`, `fail -> failing`, and `none found -> unavailable`" not in read(
        "skills/init/SKILL.md"
    ):
        fail("init lacks deterministic command-enum migration")
    if "route through `init` before task dispatch" not in read("skills/continue/SKILL.md"):
        fail("continue bypasses the manifest enum owner during migration")


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
        "work": (
            "**Write**",
            "decisions.md",
            "**delete**",
            "decisions/open/T-nnn-eN.md",
            "source: planning",
            "pre-reconciliation gate",
        ),
        "pause": (
            "**Delete**",
            ".rune/PAUSED",
            "decisions.md",
            "decisions/open/T-nnn-eN.md",
        ),
        "handoff": (
            "ledger.md",
            "**Delete**",
            "sessions/<stamp>.md",
            "decisions/open/T-nnn-eN.md",
        ),
        "continue": ("**Write**", "decisions.md", "**delete**", "decisions/open/T-nnn-eN.md"),
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


def recover_vision_phase(
    phase: str, *, required_topics_complete: bool, milestones_exist: bool = False
) -> str:
    """Reference recovery at the ledger-owned vision-phase seam."""
    if phase not in {"absent", "drafting", "complete"}:
        raise ValueError("invalid vision phase")
    if milestones_exist and phase != "complete":
        raise ValueError("milestones before completed vision")
    if phase == "drafting" and required_topics_complete:
        return "complete"
    return phase


def transition_vision_phase(
    current: str, target: str, *, required_topics_complete: bool = False
) -> str:
    allowed = {("absent", "drafting"), ("drafting", "drafting"), ("drafting", "complete")}
    if (current, target) not in allowed:
        raise ValueError("invalid vision transition")
    if target == "complete" and not required_topics_complete:
        raise ValueError("vision completed before required topics")
    return target


def start_vision_interview(phase: str) -> str:
    return transition_vision_phase(phase, "drafting")


VISION_TOPICS = (
    "What and why",
    "V1 line",
    "Shape",
    "Data",
    "Stack",
    "Constraints",
    "Done",
)


def vision_topics_complete(markdown: str, decision_ids: set[str]) -> bool:
    mode_match = re.search(r"(?m)^mode: (new|in-progress)$", markdown)
    if not mode_match:
        return False
    expected = list(VISION_TOPICS)
    if mode_match[1] == "in-progress":
        expected.extend(("Survey reality", "Discrepancies"))
    headings = list(re.finditer(r"(?m)^## ([^\n]+)$", markdown))
    if [match[1] for match in headings] != expected:
        return False
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(markdown)
        lines = [line.strip() for line in markdown[heading.end() : end].splitlines() if line.strip()]
        if len(lines) < 3 or lines[0] != "status: settled":
            return False
        decisions_match = re.fullmatch(
            r"decisions: \[((?:DEC-\d{3}(?:, DEC-\d{3})*)?)\]", lines[1]
        )
        if decisions_match is None:
            return False
        listed = set(decisions_match[1].split(", ")) if decisions_match[1] else set()
        if not listed.issubset(decision_ids):
            return False
        if heading[1] == "Discrepancies":
            content = lines[2:]
            table_rows = [line for line in content if line.startswith("|") and line.endswith("|")]
            if len(table_rows) < 2 or not any(re.fullmatch(r"\|(?:\s*:?-+:?\s*\|)+", line) for line in table_rows):
                return False
    return True


def preinit_dispatches_valid(rows: list[tuple[str, str, str, str]]) -> bool:
    for phase, followed, work_id, outcome in rows:
        if (phase, followed, work_id) == ("plan-graph", "ai-decompose", "vision/graph"):
            valid = outcome.startswith("graph: /") and outcome.endswith("/.rune/milestones.md")
        elif (phase, followed, work_id) == ("survey", "ai-survey", "survey"):
            valid = outcome == "map.md written"
        elif (phase, followed, work_id) == ("commands", "ai-oracle", "init/commands"):
            valid = outcome.startswith("oracle: ") and len(outcome) > len("oracle: ")
        else:
            valid = False
        if not valid:
            return False
    return True


def init_recovery_state(
    *, oracle: str, rune_yml_exists: bool, task_count: int, dispatches_valid: bool
) -> str:
    if task_count or not dispatches_valid:
        raise ValueError("ambiguous init state")
    if rune_yml_exists and oracle == "—":
        raise ValueError("rune.yml preceded ledger initialization")
    if not rune_yml_exists and oracle == "—":
        return "bootstrap"
    if not rune_yml_exists:
        return "ledger-persisted"
    return "initialized"


def check_vision_lifecycle() -> None:
    ledger = read("skills/ai-ledger/SKILL.md")
    lifecycle = section(ledger, "Vision phase", level=3)
    for token in (
        "only authoritative vision phase",
        "`absent | drafting | complete`",
        "sole writer is the parent",
        "`absent` | `drafting`",
        "`drafting` | `complete`",
        "final answer is durable",
        "`oracle: —` is valid only",
        "coordination-only pre-init rows",
        "No diagnose, plan-draft, reconcile, execute, verify, land",
        "post-init/pre-manifest state",
    ):
        if token not in lifecycle:
            fail(f"vision lifecycle contract is incomplete: {token}")

    vision = read("skills/vision/SKILL.md")
    capabilities = section(vision, "What you may do")
    if "empty-project" not in capabilities or "schema-2 ledger" not in capabilities:
        fail("vision cannot write its parent-owned phase/bootstrap")
    if "oracle: —" not in vision or "vision: absent" not in vision:
        fail("empty-project vision bootstrap is undefined")
    continue_skill = read("skills/continue/SKILL.md")
    reconcile_vision = section(continue_skill, "Reconcile the vision phase", level=3)
    if "legacy `drafting` vision" not in reconcile_vision or "never auto-completes" not in reconcile_vision:
        fail("legacy drafting vision has no safe normalization path")
    init_skill = read("skills/init/SKILL.md")
    init_capabilities = section(init_skill, "What you may do")
    if "ledger.md" not in init_capabilities or "bootstrap update" not in init_capabilities:
        fail("init cannot finalize the pre-init vision ledger bootstrap")
    persist_state = init_skill[
        init_skill.index("### 5. Persist initialized state") : init_skill.index("## Report")
    ]
    ledger_write = persist_state.find("Persist that validated\nledger replacement")
    rune_write = persist_state.find("atomically installing the validated `rune.yml` candidate")
    if ledger_write < 0 or rune_write < 0 or ledger_write > rune_write:
        fail("init does not persist the authoritative ledger before rune.yml")
    if "next init recognizes exactly this\nrecovery state" not in persist_state:
        fail("init does not recover a ledger-first initialization crash")
    milestones = section(vision, "Milestones")
    if milestones.find("`vision: complete`") > milestones.find("Dispatch a subagent"):
        fail("vision dispatches the graph before persisting completion")

    taskfmt = read("skills/ai-taskfmt/SKILL.md")
    vision_schema = taskfmt[taskfmt.index("## Vision document") : taskfmt.index("## Planner draft")]
    for token in ("status: settled", "decisions: []", "nonempty answer content", "status: open"):
        if token not in vision_schema:
            fail(f"vision document recovery shape is incomplete: {token}")

    complete_new = "# Vision\n\nmode: new\n\n" + "\n\n".join(
        f"## {topic}\nstatus: settled\ndecisions: []\nanswer for {topic}"
        for topic in VISION_TOPICS
    )
    if not vision_topics_complete(complete_new, set()):
        fail("canonical complete new-project vision did not validate")
    if vision_topics_complete(complete_new.replace("status: settled", "status: open", 1), set()):
        fail("vision with an open topic validated as complete")
    if vision_topics_complete(complete_new.replace("answer for Done", ""), set()):
        fail("vision with an empty topic validated as complete")
    dangling = complete_new.replace("decisions: []", "decisions: [DEC-999]", 1)
    if vision_topics_complete(dangling, set()):
        fail("vision with a dangling decision id validated as complete")
    if not vision_topics_complete(dangling, {"DEC-999"}):
        fail("vision rejected an existing durable decision id")
    incomplete_existing = complete_new.replace("mode: new", "mode: in-progress")
    if vision_topics_complete(incomplete_existing, set()):
        fail("in-progress vision omitted its survey/discrepancy sections")
    complete_existing = incomplete_existing + (
        "\n\n## Survey reality\nstatus: settled\ndecisions: []\nmap and survey digest"
        "\n\n## Discrepancies\nstatus: settled\ndecisions: []"
        "\n| intended | actual | gap |\n|---|---|---|\n| sessions persist | memory only | build |"
    )
    if not vision_topics_complete(complete_existing, set()):
        fail("canonical complete in-progress vision did not validate")
    no_table = complete_existing.replace(
        "| intended | actual | gap |\n|---|---|---|\n| sessions persist | memory only | build |",
        "intended versus actual prose",
    )
    if vision_topics_complete(no_table, set()):
        fail("in-progress vision without discrepancy table validated as complete")
    preinit_rows = [
        ("plan-graph", "ai-decompose", "vision/graph", "graph: /repo/.rune/milestones.md"),
        ("survey", "ai-survey", "survey", "map.md written"),
        ("commands", "ai-oracle", "init/commands", "oracle: npm test"),
    ]
    if not preinit_dispatches_valid(preinit_rows):
        fail("valid coordination-only pre-init dispatches were rejected")
    if preinit_dispatches_valid(
        preinit_rows + [("execute", "ai-execute", "T-001", "done")]
    ):
        fail("task-bound dispatch was allowed before oracle initialization")
    if init_recovery_state(
        oracle="—", rune_yml_exists=False, task_count=0, dispatches_valid=True
    ) != "bootstrap":
        fail("empty vision bootstrap was not recognized")
    if init_recovery_state(
        oracle="npm test", rune_yml_exists=False, task_count=0, dispatches_valid=True
    ) != "ledger-persisted":
        fail("crash after ledger initialization was not recoverable")
    for invalid in (
        {"oracle": "—", "rune_yml_exists": True, "task_count": 0, "dispatches_valid": True},
        {"oracle": "npm test", "rune_yml_exists": False, "task_count": 1, "dispatches_valid": True},
        {"oracle": "npm test", "rune_yml_exists": False, "task_count": 0, "dispatches_valid": False},
    ):
        try:
            init_recovery_state(**invalid)
        except ValueError:
            pass
        else:
            fail("accepted an ambiguous init crash state")

    # Crash before the first transition: a stray vision file does not change authority.
    if recover_vision_phase("absent", required_topics_complete=True) != "absent":
        fail("absent vision inferred progress from non-authoritative content")
    if start_vision_interview("absent") != "drafting":
        fail("vision did not persist drafting before the interview")
    if transition_vision_phase("drafting", "drafting") != "drafting":
        fail("settled interview progress did not preserve drafting")
    if transition_vision_phase(
        "drafting", "complete", required_topics_complete=True
    ) != "complete":
        fail("complete interview could not persist completion")
    for current, target in (
        ("absent", "complete"),
        ("complete", "drafting"),
        ("complete", "absent"),
        ("drafting", "absent"),
    ):
        try:
            transition_vision_phase(
                current, target, required_topics_complete=True
            )
        except ValueError:
            pass
        else:
            fail(f"accepted invalid vision transition: {current} -> {target}")
    try:
        transition_vision_phase("drafting", "complete")
    except ValueError:
        pass
    else:
        fail("vision completed before required topics were durable")
    # Crash before the final answer: resume drafting at the first missing topic.
    if recover_vision_phase("drafting", required_topics_complete=False) != "drafting":
        fail("partial interview did not remain drafting")
    # Crash after the final answer but before the phase write: recovery completes it.
    if recover_vision_phase(
        "drafting", required_topics_complete=vision_topics_complete(complete_new, set())
    ) != "complete":
        fail("durable final interview answer was not recoverable")
    # Crash after completion: never restart the interview.
    if recover_vision_phase("complete", required_topics_complete=True) != "complete":
        fail("complete vision regressed during recovery")
    for bad_phase in ("", "done", "partial"):
        try:
            recover_vision_phase(bad_phase, required_topics_complete=False)
        except ValueError:
            pass
        else:
            fail(f"accepted invalid vision phase: {bad_phase!r}")
    try:
        recover_vision_phase(
            "drafting", required_topics_complete=True, milestones_exist=True
        )
    except ValueError:
        pass
    else:
        fail("accepted a milestone graph before authoritative vision completion")


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    milestone: str
    task_type: str
    remediation: str
    root_cause_followup: str


def normalize_task_contract(record: dict[str, str]) -> tuple[TaskContract, bool]:
    task_type = record.get("type", "")
    remediation = record.get("remediation")
    legacy_kind = record.get("kind")
    legacy_repair = False
    if remediation is None:
        if task_type == "bug" and legacy_kind == "mitigation":
            remediation = "mitigation"
            legacy_repair = record.get("root_cause_followup", "none") == "none"
        elif task_type == "bug":
            remediation = "root_cause"
        else:
            remediation = "not_applicable"
    elif legacy_kind == "mitigation" and remediation != "mitigation":
        raise ValueError("legacy mitigation was reclassified as root cause")
    return (
        TaskContract(
            task_id=record.get("id", ""),
            milestone=record.get("milestone", ""),
            task_type=task_type,
            remediation=remediation,
            root_cause_followup=record.get("root_cause_followup", "none"),
        ),
        legacy_repair,
    )


def validate_task_contracts(
    records: list[dict[str, str]], *, allow_legacy: bool = False
) -> list[TaskContract]:
    normalized: list[TaskContract] = []
    for record in records:
        if not allow_legacy and (
            "remediation" not in record or "root_cause_followup" not in record
        ):
            raise ValueError("canonical task omitted remediation fields")
        task, legacy_repair = normalize_task_contract(record)
        if legacy_repair:
            raise ValueError("legacy mitigation requires reconciliation repair")
        if not re.fullmatch(r"[TD]-\d{3}", task.task_id) or not re.fullmatch(
            r"M-\d{2}", task.milestone
        ):
            raise ValueError("invalid task identity")
        if task.task_type not in TASK_TYPES:
            raise ValueError("invalid task type")
        if task.task_type == "bug":
            if task.remediation not in {"root_cause", "mitigation"}:
                raise ValueError("bug has invalid remediation")
        elif task.remediation != "not_applicable":
            raise ValueError("non-bug has bug remediation")
        if task.remediation != "mitigation" and task.root_cause_followup != "none":
            raise ValueError("non-mitigation has root-cause follow-up")
        normalized.append(task)
    by_id = {task.task_id: task for task in normalized}
    if len(by_id) != len(normalized):
        raise ValueError("duplicate task id")
    for task in normalized:
        if task.remediation != "mitigation":
            continue
        target = by_id.get(task.root_cause_followup)
        if (
            target is None
            or target.task_id == task.task_id
            or target.task_id[0] != task.task_id[0]
            or target.milestone != task.milestone
            or target.task_type != "bug"
            or target.remediation != "root_cause"
            or target.root_cause_followup != "none"
        ):
            raise ValueError("invalid mitigation root-cause follow-up")
    return normalized


@dataclass
class RepairAssignment:
    work: str
    legacy_mitigation: str
    reserved_root_cause: str
    protocol: str
    task_path: str
    artifact: str
    outcome: str = "pending"
    blocker: str | None = None
    detail: str | None = None
    unblocks_when: str | None = None


@dataclass
class LegacyRepairState:
    schema: int
    tasks: dict[str, dict[str, str]]
    statuses: dict[str, str]
    protocols: dict[str, dict[str, str]] = field(default_factory=dict)
    repairs: dict[str, RepairAssignment] = field(default_factory=dict)
    artifacts: dict[str, dict[str, str]] = field(default_factory=dict)
    dispatched: set[str] = field(default_factory=set)
    events: list[str] = field(default_factory=list)


REPAIR_ROW = re.compile(
    r"^\| mitigation-repair \| ai-decompose \| (?P<work>M-\d{2}/R-\d{3}) \| "
    r"(?P<outcome>pending|linked|blocked) (?P<legacy>T-\d{3}) -> (?P<root>T-\d{3}): "
    r"protocol (?P<protocol>/[^;|]+); task (?P<task>/[^;|]+); repair (?P<repair>/[^;|]+)"
    r"(?:; blocker (?P<blocker>[a-z0-9-]+); detail (?P<detail>[^;|\s]+); "
    r"unblocks_when (?P<unblocks_when>[^;|\s]+))? \|$"
)


def parse_repair_dispatch_row(row: str) -> RepairAssignment:
    match = REPAIR_ROW.fullmatch(row)
    if not match:
        raise ValueError("invalid mitigation-repair row")
    fields = match.groupdict()
    blocked_fields = (fields["blocker"], fields["detail"], fields["unblocks_when"])
    if fields["outcome"] == "blocked":
        if not all(blocked_fields):
            raise ValueError("blocked repair omitted durable unblock fields")
    elif any(blocked_fields):
        raise ValueError("non-blocked repair invented unblock fields")
    return RepairAssignment(
        work=fields["work"],
        legacy_mitigation=fields["legacy"],
        reserved_root_cause=fields["root"],
        protocol=fields["protocol"],
        task_path=fields["task"],
        artifact=fields["repair"],
        outcome=fields["outcome"],
        blocker=fields["blocker"],
        detail=fields["detail"],
        unblocks_when=fields["unblocks_when"],
    )


def validate_repair_binding(assignment: RepairAssignment) -> None:
    main_root, separator, protocol_suffix = assignment.protocol.partition("/.rune/drafts/")
    if not separator or protocol_suffix != f"{assignment.work}/protocol.md":
        raise ValueError("repair protocol path does not match work")
    if assignment.task_path != (
        f"{main_root}/.rune/tasks/{assignment.reserved_root_cause}.md"
    ):
        raise ValueError("reserved root id and task path disagree")
    if assignment.artifact != (
        f"{main_root}/.rune/drafts/{assignment.work}/mitigation-repair.md"
    ):
        raise ValueError("repair artifact path does not match work")


def validate_repair_protocol(record: dict[str, str]) -> None:
    required = {
        "run",
        "repair",
        "legacy_mitigation",
        "reserved_root_cause",
        "legacy_task",
        "root_cause_task",
        "repair_artifact",
    }
    if set(record) != required:
        raise ValueError("repair protocol fields are incomplete or unknown")
    if record["repair"] != "completed_legacy_mitigation":
        raise ValueError("repair protocol has an unknown repair enum")
    if not re.fullmatch(r"M-\d{2}/R-\d{3}", record["run"]):
        raise ValueError("repair protocol has an invalid run")
    if not re.fullmatch(r"T-\d{3}", record["legacy_mitigation"]) or not re.fullmatch(
        r"T-\d{3}", record["reserved_root_cause"]
    ):
        raise ValueError("repair protocol has invalid task ids")
    main_root, separator, legacy_suffix = record["legacy_task"].partition(
        "/.rune/tasks/"
    )
    if (
        not separator
        or not main_root.startswith("/")
        or legacy_suffix != f"{record['legacy_mitigation']}.md"
        or record["root_cause_task"]
        != f"{main_root}/.rune/tasks/{record['reserved_root_cause']}.md"
        or record["repair_artifact"]
        != f"{main_root}/.rune/drafts/{record['run']}/mitigation-repair.md"
    ):
        raise ValueError("repair protocol absolute paths disagree with its ids or run")


def publish_repair_protocol(
    state: LegacyRepairState, record: dict[str, str]
) -> None:
    validate_repair_protocol(record)
    work = record["run"]
    legacy = state.tasks.get(record["legacy_mitigation"])
    if (
        legacy is None
        or legacy.get("type") != "bug"
        or legacy.get("kind") != "mitigation"
        or state.statuses.get(record["legacy_mitigation"]) != "done"
    ):
        raise ValueError("repair protocol does not target a completed legacy mitigation")
    if record["reserved_root_cause"] in state.tasks:
        raise ValueError("repair protocol reserved an already-used task id")
    if work in state.protocols:
        if state.protocols[work] == record:
            return
        raise ValueError("repair protocol path contains conflicting bytes")
    if any(
        existing["legacy_mitigation"] == record["legacy_mitigation"]
        or existing["reserved_root_cause"] == record["reserved_root_cause"]
        or existing["root_cause_task"] == record["root_cause_task"]
        or existing["repair_artifact"] == record["repair_artifact"]
        for existing in state.protocols.values()
    ):
        raise ValueError("repair protocol collides with an existing reservation")
    state.protocols[work] = dict(record)
    state.events.append(f"protocol:{work}")


def assignment_from_protocol(record: dict[str, str], protocol_path: str) -> RepairAssignment:
    validate_repair_protocol(record)
    return RepairAssignment(
        work=record["run"],
        legacy_mitigation=record["legacy_mitigation"],
        reserved_root_cause=record["reserved_root_cause"],
        protocol=protocol_path,
        task_path=record["root_cause_task"],
        artifact=record["repair_artifact"],
    )


def stage_completed_mitigation_repair(
    state: LegacyRepairState, assignment: RepairAssignment
) -> None:
    if state.schema != 2:
        raise ValueError("repair assignment requires durable schema 2")
    if assignment.outcome != "pending":
        raise ValueError("new repair assignment is not pending")
    validate_repair_binding(assignment)
    protocol = state.protocols.get(assignment.work)
    if protocol is None:
        raise ValueError("pending repair row preceded its durable protocol")
    expected_assignment = assignment_from_protocol(protocol, assignment.protocol)
    if expected_assignment != assignment:
        raise ValueError("pending repair row disagrees with its durable protocol")
    legacy = state.tasks.get(assignment.legacy_mitigation)
    if (
        legacy is None
        or legacy.get("type") != "bug"
        or legacy.get("kind") != "mitigation"
        or state.statuses.get(assignment.legacy_mitigation) != "done"
    ):
        raise ValueError("repair assignment is not for a completed legacy mitigation")
    if assignment.reserved_root_cause in state.tasks:
        raise ValueError("reserved root-cause id is already used")
    if assignment.work in state.repairs or any(
        existing.legacy_mitigation == assignment.legacy_mitigation
        or existing.reserved_root_cause == assignment.reserved_root_cause
        or assignment.protocol in {existing.protocol, existing.task_path, existing.artifact}
        or assignment.task_path in {existing.protocol, existing.task_path, existing.artifact}
        or assignment.artifact in {existing.protocol, existing.task_path, existing.artifact}
        for existing in state.repairs.values()
    ):
        raise ValueError("duplicate mitigation repair assignment")
    state.repairs[assignment.work] = assignment
    state.events.append(f"pending:{assignment.work}")


def dispatch_mitigation_repair(state: LegacyRepairState, work: str) -> None:
    if state.schema != 2 or work not in state.protocols:
        raise ValueError("repair dispatch preceded durable schema or protocol")
    assignment = state.repairs.get(work)
    if assignment is None or assignment.outcome != "pending":
        raise ValueError("repair dispatch preceded its pending ledger row")
    if work in state.dispatched:
        raise ValueError("repair assignment is already dispatched")
    state.dispatched.add(work)
    state.events.append(f"dispatch:{work}")


def migrate_and_stage_completed_mitigation_repair(
    state: LegacyRepairState, assignment: RepairAssignment
) -> None:
    if state.schema not in {0, 1}:
        raise ValueError("not a predecessor ledger")
    predecessor = state.schema
    state.schema = 2
    try:
        stage_completed_mitigation_repair(state, assignment)
    except ValueError:
        state.schema = predecessor
        raise


def recover_orphan_repair_protocol(
    state: LegacyRepairState, work: str, protocol_path: str
) -> RepairAssignment:
    protocol = state.protocols.get(work)
    if protocol is None:
        raise ValueError("orphan recovery has no durable protocol")
    if work in state.repairs:
        raise ValueError("protocol already has a ledger assignment")
    assignment = assignment_from_protocol(protocol, protocol_path)
    stage_completed_mitigation_repair(state, assignment)
    return assignment


def expected_repair_artifact(
    state: LegacyRepairState, assignment: RepairAssignment
) -> dict[str, str]:
    legacy, _ = normalize_task_contract(state.tasks[assignment.legacy_mitigation])
    main_root = assignment.task_path.partition("/.rune/tasks/")[0]
    return {
        "legacy_mitigation": legacy.task_id,
        "root_cause_followup": assignment.reserved_root_cause,
        "milestone": legacy.milestone,
        "run": assignment.work,
        "legacy_task": f"{main_root}/.rune/tasks/{legacy.task_id}.md",
        "root_cause_task": assignment.task_path,
    }


def complete_mitigation_repair(
    state: LegacyRepairState,
    *,
    work: str,
    artifact_record: dict[str, str],
    root_task: dict[str, str],
) -> list[TaskContract]:
    assignment = state.repairs.get(work)
    if assignment is None or assignment.outcome != "pending":
        raise ValueError("repair return has no pending assignment")
    legacy_record = state.tasks[assignment.legacy_mitigation]
    legacy, needs_repair = normalize_task_contract(legacy_record)
    if not needs_repair or state.statuses.get(legacy.task_id) != "done":
        raise ValueError("repair return does not target an unresolved completed mitigation")
    root_id = root_task.get("id", "")
    if root_id != assignment.reserved_root_cause:
        raise ValueError("repair used a root id other than its reservation")
    existing_task = state.tasks.get(root_id)
    if existing_task is not None and (
        root_id in state.statuses or existing_task != root_task
    ):
        raise ValueError("reserved task path collides with another task")
    existing_artifact = state.artifacts.get(work)
    if existing_artifact is not None and existing_artifact != artifact_record:
        raise ValueError("repair artifact path contains conflicting bytes")
    if artifact_record != expected_repair_artifact(state, assignment):
        raise ValueError("repair artifact disagrees with its assignment or task files")
    overlaid_legacy = {
        "id": legacy.task_id,
        "milestone": legacy.milestone,
        "type": legacy.task_type,
        "remediation": "mitigation",
        "root_cause_followup": root_id,
    }
    canonical = validate_task_contracts([overlaid_legacy, root_task])

    state.tasks[root_id] = dict(root_task)
    state.statuses[root_id] = "pending"
    state.artifacts[work] = dict(artifact_record)
    assignment.outcome = "linked"
    state.dispatched.discard(work)
    return canonical


def record_repair_blocked(
    state: LegacyRepairState,
    work: str,
    *,
    blocker: str,
    detail: str,
    unblocks_when: str,
) -> None:
    assignment = state.repairs[work]
    if assignment.outcome == "blocked":
        existing = (assignment.blocker, assignment.detail, assignment.unblocks_when)
        replay = (blocker, detail, unblocks_when)
        if existing == replay:
            return
        raise ValueError("blocked repair replay conflicts with durable outcome")
    if assignment.outcome != "pending":
        raise ValueError("linked repair cannot become blocked")
    if (
        not re.fullmatch(r"[a-z0-9-]+", blocker)
        or not detail
        or not unblocks_when
        or any(re.search(r"[\s|;]", value) for value in (detail, unblocks_when))
    ):
        raise ValueError("blocked repair has unstable detail or condition")
    assignment.outcome = "blocked"
    assignment.blocker = blocker
    assignment.detail = detail
    assignment.unblocks_when = unblocks_when
    state.dispatched.discard(work)


def unblock_repair(
    state: LegacyRepairState, work: str, *, condition_observed: bool
) -> None:
    assignment = state.repairs[work]
    if assignment.outcome != "blocked":
        raise ValueError("repair is not blocked")
    if not condition_observed:
        return
    assignment.outcome = "pending"
    assignment.blocker = None
    assignment.detail = None
    assignment.unblocks_when = None


def recover_mitigation_repair(state: LegacyRepairState, work: str) -> str:
    assignment = state.repairs[work]
    if assignment.outcome == "blocked":
        return "blocked"
    if assignment.outcome == "linked":
        resolve_legacy_mitigation_overlay(state, assignment.legacy_mitigation)
        return "linked"
    if work not in state.dispatched:
        return "dispatch"
    root_task = state.tasks.get(assignment.reserved_root_cause)
    artifact = state.artifacts.get(work)
    if root_task is None and artifact is None:
        return "redispatch-both"
    if root_task is None:
        record_repair_blocked(
            state,
            work,
            blocker="artifact-without-task",
            detail="publication-order-violation",
            unblocks_when=f"task:{assignment.reserved_root_cause}:restored",
        )
        return "blocked"
    overlaid_legacy = {
        "id": assignment.legacy_mitigation,
        "milestone": state.tasks[assignment.legacy_mitigation]["milestone"],
        "type": "bug",
        "remediation": "mitigation",
        "root_cause_followup": assignment.reserved_root_cause,
    }
    try:
        validate_task_contracts([overlaid_legacy, root_task])
    except ValueError:
        record_repair_blocked(
            state,
            work,
            blocker="reserved-task-mismatch",
            detail="reserved-task-contract-invalid",
            unblocks_when=f"task:{assignment.reserved_root_cause}:restored",
        )
        return "blocked"
    if artifact is None:
        return "redispatch-repair-only"
    try:
        complete_mitigation_repair(
            state,
            work=work,
            artifact_record=artifact,
            root_task=root_task,
        )
    except ValueError:
        record_repair_blocked(
            state,
            work,
            blocker="repair-output-mismatch",
            detail="task-and-repair-disagree",
            unblocks_when="repair-outputs-restored",
        )
        return "blocked"
    return "linked"


def resolve_legacy_mitigation_overlay(
    state: LegacyRepairState, legacy_mitigation: str
) -> dict[str, str]:
    matches = [
        assignment
        for assignment in state.repairs.values()
        if assignment.legacy_mitigation == legacy_mitigation
        and assignment.outcome == "linked"
    ]
    if len(matches) != 1:
        raise ValueError("legacy mitigation has no unique linked repair")
    assignment = matches[0]
    artifact = state.artifacts.get(assignment.work)
    root_id = assignment.reserved_root_cause
    root_task = state.tasks.get(root_id)
    if (
        artifact is None
        or artifact != expected_repair_artifact(state, assignment)
        or root_task is None
        or root_id not in state.statuses
    ):
        raise ValueError("linked repair has no matching immutable artifact")
    legacy, _ = normalize_task_contract(state.tasks[legacy_mitigation])
    overlaid = {
        "id": legacy.task_id,
        "milestone": legacy.milestone,
        "type": legacy.task_type,
        "remediation": "mitigation",
        "root_cause_followup": root_id,
    }
    validate_task_contracts([overlaid, root_task])
    return overlaid


def parse_frontmatter(block: str) -> dict[str, str]:
    match = re.match(r"(?ms)^---\n(.*?)\n---", block)
    if not match:
        raise ValueError("missing frontmatter")
    return top_level_fields(match[1])


def check_mitigation_contracts() -> None:
    taskfmt = read("skills/ai-taskfmt/SKILL.md")
    task_section = taskfmt[taskfmt.index("## Task file") : taskfmt.index("### Sizing")]
    final_examples = [
        block
        for info, block in fenced_blocks(task_section)
        if info == "markdown" and re.search(r"(?m)^id: T-\d{3}$", block)
    ]
    if len(final_examples) != 1:
        fail(f"expected one parsed final task example, found {len(final_examples)}")
    final_record = parse_frontmatter(final_examples[0])
    try:
        validate_task_contracts([final_record])
    except ValueError as error:
        fail(f"canonical final task example is invalid: {error}")

    draft_examples = [
        block
        for info, block in fenced_blocks(taskfmt)
        if info == "markdown" and "# Candidate cut" in block
    ]
    if len(draft_examples) != 1:
        fail(f"expected one parsed planner draft, found {len(draft_examples)}")
    draft_records: list[dict[str, str]] = []
    for match in re.finditer(
        r"(?ms)^## (D-\d{3}) ·[^\n]+\n(.*?)(?=^### |^## D-|^## Cut notes)",
        draft_examples[0],
    ):
        field_lines = "\n".join(
            line
            for line in match[2].splitlines()
            if re.match(r"^(type|remediation|root_cause_followup|verification|blocked_by):", line)
        )
        fields = top_level_fields(field_lines)
        fields.update({"id": match[1], "milestone": "M-03"})
        draft_records.append(fields)
    if len(draft_records) != 2:
        fail("planner draft tasks were not parsed")
    try:
        validate_task_contracts(draft_records)
    except ValueError as error:
        fail(f"canonical draft task example is invalid: {error}")

    mitigation = {
        "id": "T-020", "milestone": "M-03", "type": "bug",
        "remediation": "mitigation", "root_cause_followup": "T-021",
    }
    root_cause = {
        "id": "T-021", "milestone": "M-03", "type": "bug",
        "remediation": "root_cause", "root_cause_followup": "none",
    }
    validate_task_contracts([mitigation, root_cause])
    invalid_sets = (
        [dict(mitigation, root_cause_followup="T-020"), root_cause],
        [mitigation],
        [mitigation, dict(root_cause, milestone="M-04")],
        [mitigation, dict(root_cause, type="feature", remediation="not_applicable")],
        [mitigation, dict(root_cause, remediation="mitigation", root_cause_followup="T-020")],
        [dict(mitigation, root_cause_followup="none"), root_cause],
        [dict(root_cause, remediation="not_applicable")],
        [dict(mitigation, root_cause_followup="D-021"), dict(root_cause, id="D-021")],
        [dict(root_cause, type="patch")],
    )
    for invalid in invalid_sets:
        try:
            validate_task_contracts(invalid)
        except ValueError:
            pass
        else:
            fail("mitigation validator accepted an invalid task relationship")

    legacy_bug, repair = normalize_task_contract(
        {"id": "T-030", "milestone": "M-03", "type": "bug"}
    )
    if repair or legacy_bug.remediation != "root_cause" or legacy_bug.root_cause_followup != "none":
        fail("legacy root-cause bug did not normalize deterministically")
    try:
        validate_task_contracts(
            [{"id": "T-030", "milestone": "M-03", "type": "bug"}]
        )
    except ValueError:
        pass
    else:
        fail("strict canonical task validation accepted missing remediation fields")
    legacy_allowed = validate_task_contracts(
        [{"id": "T-030", "milestone": "M-03", "type": "bug"}],
        allow_legacy=True,
    )
    if legacy_allowed[0].remediation != "root_cause":
        fail("legacy-mode task validation did not normalize the old root-cause contract")
    legacy_mitigation, repair = normalize_task_contract(
        {"id": "T-031", "milestone": "M-03", "type": "bug", "kind": "mitigation"}
    )
    if not repair or legacy_mitigation.remediation != "mitigation":
        fail("legacy mitigation was silently normalized as a root-cause fix")

    repair_examples = [
        top_level_fields(block)
        for info, block in fenced_blocks(taskfmt)
        if info == "rune-mitigation-repair"
    ]
    if len(repair_examples) != 1:
        fail(f"expected one parsed mitigation-repair artifact, found {len(repair_examples)}")

    protocol_examples = [
        top_level_fields(block)
        for info, block in fenced_blocks(taskfmt)
        if info == "rune-mitigation-repair-protocol"
    ]
    if len(protocol_examples) != 1:
        fail(f"expected one parsed mitigation-repair protocol, found {len(protocol_examples)}")
    row_blocks = [
        block
        for info, block in fenced_blocks(taskfmt)
        if info == "rune-mitigation-repair-rows"
    ]
    if len(row_blocks) != 1:
        fail(f"expected one parsed mitigation-repair row set, found {len(row_blocks)}")
    parsed_rows = [
        parse_repair_dispatch_row(line)
        for line in row_blocks[0].splitlines()
        if line.strip()
    ]
    if [row.outcome for row in parsed_rows] != ["pending", "linked", "blocked"]:
        fail("documented repair rows omitted a canonical outcome")
    pending_assignment, linked_example, blocked_example = parsed_rows
    protocol = protocol_examples[0]
    try:
        validate_repair_protocol(protocol)
    except ValueError as error:
        fail(f"canonical mitigation-repair protocol is invalid: {error}")
    if (
        protocol.get("run") != pending_assignment.work
        or protocol.get("legacy_mitigation") != pending_assignment.legacy_mitigation
        or protocol.get("reserved_root_cause") != pending_assignment.reserved_root_cause
        or protocol.get("root_cause_task") != pending_assignment.task_path
        or protocol.get("repair_artifact") != pending_assignment.artifact
        or linked_example.reserved_root_cause != pending_assignment.reserved_root_cause
        or not all((blocked_example.blocker, blocked_example.detail, blocked_example.unblocks_when))
    ):
        fail("repair protocol and parsed row bindings disagree")
    for invalid_protocol in (
        dict(protocol, repair="legacy_patch"),
        dict(protocol, legacy_task="relative/tasks/T-031.md"),
        dict(protocol, legacy_task="/workspace/acme/.rune/tasks/T-030.md"),
        dict(protocol, root_cause_task="/workspace/acme/.rune/tasks/T-034.md"),
        dict(protocol, repair_artifact="/workspace/acme/.rune/drafts/M-03/R-006/mitigation-repair.md"),
        {key: value for key, value in protocol.items() if key != "legacy_task"},
    ):
        try:
            validate_repair_protocol(invalid_protocol)
        except ValueError:
            pass
        else:
            fail("repair protocol validator accepted an enum, field, or path regression")
    for invalid_row in (
        row_blocks[0].splitlines()[0].replace("pending", "queued", 1),
        row_blocks[0].splitlines()[2].replace("; unblocks_when decision:DEC-004:decided", ""),
        row_blocks[0].splitlines()[0].replace("T-033.md", "T-034.md", 1),
    ):
        try:
            parsed = parse_repair_dispatch_row(invalid_row)
            validate_repair_binding(parsed)
        except ValueError:
            pass
        else:
            fail("repair-row parser accepted an invalid outcome, blocker, or path")

    legacy_record = {
        "id": "T-031", "milestone": "M-03", "type": "bug", "kind": "mitigation"
    }
    second_legacy = {
        "id": "T-032", "milestone": "M-03", "type": "bug", "kind": "mitigation"
    }
    original_bytes_model = dict(legacy_record)
    second_protocol = {
        "run": "M-03/R-006",
        "repair": "completed_legacy_mitigation",
        "legacy_mitigation": "T-032",
        "reserved_root_cause": "T-034",
        "legacy_task": "/workspace/acme/.rune/tasks/T-032.md",
        "root_cause_task": "/workspace/acme/.rune/tasks/T-034.md",
        "repair_artifact": "/workspace/acme/.rune/drafts/M-03/R-006/mitigation-repair.md",
    }
    second_assignment = assignment_from_protocol(
        second_protocol, "/workspace/acme/.rune/drafts/M-03/R-006/protocol.md"
    )

    row_before_protocol = LegacyRepairState(
        schema=2,
        tasks={"T-031": dict(legacy_record)},
        statuses={"T-031": "done"},
    )
    try:
        stage_completed_mitigation_repair(row_before_protocol, pending_assignment)
    except ValueError:
        pass
    else:
        fail("pending repair row was persisted before its protocol")

    orphan_protocol = LegacyRepairState(
        schema=2,
        tasks={"T-031": dict(legacy_record)},
        statuses={"T-031": "done"},
    )
    publish_repair_protocol(orphan_protocol, protocol)
    try:
        dispatch_mitigation_repair(orphan_protocol, "M-03/R-005")
    except ValueError:
        pass
    else:
        fail("repair worker was dispatched before its pending row")
    recovered_assignment = recover_orphan_repair_protocol(
        orphan_protocol,
        "M-03/R-005",
        "/workspace/acme/.rune/drafts/M-03/R-005/protocol.md",
    )
    if recover_mitigation_repair(orphan_protocol, "M-03/R-005") != "dispatch":
        fail("recovered orphan protocol skipped the pending-before-dispatch boundary")
    dispatch_mitigation_repair(orphan_protocol, "M-03/R-005")
    if (
        recovered_assignment != orphan_protocol.repairs["M-03/R-005"]
        or orphan_protocol.events
        != ["protocol:M-03/R-005", "pending:M-03/R-005", "dispatch:M-03/R-005"]
    ):
        fail("orphan repair protocol did not recover in durable order")

    repair_state = LegacyRepairState(
        schema=1,
        tasks={"T-031": legacy_record, "T-032": second_legacy},
        statuses={"T-031": "done", "T-032": "done"},
    )
    publish_repair_protocol(repair_state, protocol)
    publish_repair_protocol(repair_state, second_protocol)
    try:
        stage_completed_mitigation_repair(repair_state, pending_assignment)
    except ValueError:
        pass
    else:
        fail("mitigation repair was dispatched against a predecessor ledger")
    migrate_and_stage_completed_mitigation_repair(repair_state, pending_assignment)
    stage_completed_mitigation_repair(repair_state, second_assignment)
    dispatch_mitigation_repair(repair_state, "M-03/R-005")
    dispatch_mitigation_repair(repair_state, "M-03/R-006")
    if repair_state.schema != 2 or repair_state.repairs["M-03/R-005"].outcome != "pending":
        fail("predecessor migration did not durably stage schema-2 repair")
    if {
        assignment.reserved_root_cause for assignment in repair_state.repairs.values()
    } != {"T-033", "T-034"}:
        fail("simultaneous repairs did not reserve distinct root-cause ids")
    if repair_state.events != [
        "protocol:M-03/R-005",
        "protocol:M-03/R-006",
        "pending:M-03/R-005",
        "pending:M-03/R-006",
        "dispatch:M-03/R-005",
        "dispatch:M-03/R-006",
    ]:
        fail(f"simultaneous repair publication order drifted: {repair_state.events}")

    for collision_protocol in (
        dict(
            second_protocol,
            run="M-03/R-007",
            reserved_root_cause="T-033",
            root_cause_task="/workspace/acme/.rune/tasks/T-033.md",
            repair_artifact="/workspace/acme/.rune/drafts/M-03/R-007/mitigation-repair.md",
        ),
        dict(second_protocol, reserved_root_cause="T-035", root_cause_task="/workspace/acme/.rune/tasks/T-035.md"),
    ):
        try:
            publish_repair_protocol(repair_state, collision_protocol)
        except ValueError:
            pass
        else:
            fail("simultaneous repair allocator accepted an id or path collision")
    used_id_state = LegacyRepairState(
        schema=2,
        tasks={
            "T-031": dict(original_bytes_model),
            "T-033": {
                "id": "T-033", "milestone": "M-02", "type": "feature",
                "remediation": "not_applicable", "root_cause_followup": "none",
            },
        },
        statuses={"T-031": "done", "T-033": "pending"},
    )
    try:
        publish_repair_protocol(used_id_state, protocol)
    except ValueError:
        pass
    else:
        fail("repair allocator reserved an id already owned by a task")

    repaired_root = {
        "id": "T-033", "milestone": "M-03", "type": "bug",
        "remediation": "root_cause", "root_cause_followup": "none",
    }

    def fresh_repair_state() -> LegacyRepairState:
        state = LegacyRepairState(
            schema=2,
            tasks={"T-031": dict(original_bytes_model)},
            statuses={"T-031": "done"},
        )
        assignment = parse_repair_dispatch_row(row_blocks[0].splitlines()[0])
        publish_repair_protocol(state, protocol)
        stage_completed_mitigation_repair(state, assignment)
        dispatch_mitigation_repair(state, assignment.work)
        return state

    neither_state = fresh_repair_state()
    if recover_mitigation_repair(neither_state, "M-03/R-005") != "redispatch-both":
        fail("empty repair publication was not safely redispatched")

    task_only_state = fresh_repair_state()
    task_only_state.tasks["T-033"] = dict(repaired_root)
    if recover_mitigation_repair(task_only_state, "M-03/R-005") != "redispatch-repair-only":
        fail("task-only repair crash was not attributed to its reservation")
    if task_only_state.repairs["M-03/R-005"].outcome != "pending":
        fail("task-only recovery lost the pending reservation")

    artifact_only_state = fresh_repair_state()
    artifact_only_state.artifacts["M-03/R-005"] = dict(repair_examples[0])
    if recover_mitigation_repair(artifact_only_state, "M-03/R-005") != "blocked":
        fail("artifact-only publication did not become durably blocked")
    blocked_snapshot = vars(artifact_only_state.repairs["M-03/R-005"]).copy()
    if (
        recover_mitigation_repair(artifact_only_state, "M-03/R-005") != "blocked"
        or vars(artifact_only_state.repairs["M-03/R-005"]) != blocked_snapshot
    ):
        fail("blocked repair was not idempotent across recovery")
    unblock_repair(
        artifact_only_state, "M-03/R-005", condition_observed=False
    )
    if artifact_only_state.repairs["M-03/R-005"].outcome != "blocked":
        fail("blocked repair retried before its condition was observed")
    artifact_only_state.tasks["T-033"] = dict(repaired_root)
    unblock_repair(
        artifact_only_state, "M-03/R-005", condition_observed=True
    )
    dispatch_mitigation_repair(artifact_only_state, "M-03/R-005")
    if recover_mitigation_repair(artifact_only_state, "M-03/R-005") != "linked":
        fail("observably unblocked repair did not finish its original reservation")

    both_state = fresh_repair_state()
    both_state.tasks["T-033"] = dict(repaired_root)
    both_state.artifacts["M-03/R-005"] = dict(repair_examples[0])
    if recover_mitigation_repair(both_state, "M-03/R-005") != "linked":
        fail("valid two-output repair was not linked")
    if recover_mitigation_repair(both_state, "M-03/R-005") != "linked":
        fail("already-linked repair was not idempotent")

    mismatch_state = fresh_repair_state()
    mismatch_state.tasks["T-033"] = dict(repaired_root, milestone="M-04")
    if recover_mitigation_repair(mismatch_state, "M-03/R-005") != "blocked":
        fail("mismatched reserved task did not become durably blocked")

    no_output_blocked = fresh_repair_state()
    record_repair_blocked(
        no_output_blocked,
        "M-03/R-005",
        blocker="evidence-insufficient",
        detail="diagnosis-does-not-identify-causal-boundary",
        unblocks_when="decision:DEC-004:decided",
    )
    recorded_block = no_output_blocked.repairs["M-03/R-005"]
    if (
        recorded_block.blocker,
        recorded_block.detail,
        recorded_block.unblocks_when,
    ) != (
        blocked_example.blocker,
        blocked_example.detail,
        blocked_example.unblocks_when,
    ):
        fail("modeled blocked outcome drifted from the parsed canonical row")
    if recover_mitigation_repair(no_output_blocked, "M-03/R-005") != "blocked":
        fail("no-output plan: blocked would be endlessly redispatched")
    replay_snapshot = vars(no_output_blocked.repairs["M-03/R-005"]).copy()
    record_repair_blocked(
        no_output_blocked,
        "M-03/R-005",
        blocker="evidence-insufficient",
        detail="diagnosis-does-not-identify-causal-boundary",
        unblocks_when="decision:DEC-004:decided",
    )
    if vars(no_output_blocked.repairs["M-03/R-005"]) != replay_snapshot:
        fail("identical blocked repair replay was not a no-op")
    try:
        record_repair_blocked(
            no_output_blocked,
            "M-03/R-005",
            blocker="evidence-insufficient",
            detail="different-detail",
            unblocks_when="decision:DEC-004:decided",
        )
    except ValueError:
        pass
    else:
        fail("conflicting blocked repair replay was accepted")
    if vars(no_output_blocked.repairs["M-03/R-005"]) != replay_snapshot:
        fail("conflicting blocked repair replay mutated durable state")
    unblock_repair(no_output_blocked, "M-03/R-005", condition_observed=True)
    dispatch_mitigation_repair(no_output_blocked, "M-03/R-005")
    if recover_mitigation_repair(no_output_blocked, "M-03/R-005") != "redispatch-both":
        fail("observed blocked condition did not safely re-enable the same reservation")

    repair_state.tasks["T-033"] = dict(repaired_root)
    repair_state.artifacts["M-03/R-005"] = dict(repair_examples[0])
    if recover_mitigation_repair(repair_state, "M-03/R-005") != "linked":
        fail("post-migration repair state did not link")
    resolved_legacy = resolve_legacy_mitigation_overlay(repair_state, "T-031")
    validate_task_contracts([resolved_legacy, repair_state.tasks["T-033"]])
    if repair_state.tasks["T-031"] != original_bytes_model:
        fail("repair rewrote immutable legacy task bytes")
    if (
        repair_state.repairs["M-03/R-005"].outcome != "linked"
        or repair_state.statuses["T-033"] != "pending"
    ):
        fail("post-repair state did not link and register the root-cause task")

    try:
        normalize_task_contract(
            {
                "id": "T-032", "milestone": "M-03", "type": "bug",
                "kind": "mitigation", "remediation": "root_cause",
            }
        )
    except ValueError:
        pass
    else:
        fail("known legacy mitigation was reclassified as root cause")

    ledger = read("skills/ai-ledger/SKILL.md")
    report = read("skills/ai-report/SKILL.md")
    verify = read("skills/ai-verify/SKILL.md")
    continue_skill = read("skills/continue/SKILL.md")
    for token, markdown in (
        ("mitigation T-nnn → root-cause T-mmm", ledger),
        ("mitigation T-020 → root-cause T-021", report),
        ("different id in the same milestone", verify),
        ("mitigation-repair pending assignment", continue_skill),
        ("linked mitigation-repair ledger row", verify),
        ("matching immutable repair artifact", report),
    ):
        if token not in markdown:
            fail(f"mitigation lifecycle coverage is incomplete: {token}")


@dataclass(frozen=True)
class StagedQuestion:
    task: int
    attempt: int
    path: str

    @property
    def source(self) -> str:
        return f"T-{self.task:03d}/e{self.attempt}"


@dataclass
class DecisionState:
    records: dict[str, int] = field(default_factory=dict)
    awaiting: dict[int, int] = field(default_factory=dict)
    staged: set[str] = field(default_factory=set)
    attempts: dict[int, int] = field(default_factory=dict)


def parse_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for key, value in re.findall(r"(?m)^([a-z_]+):\s*(.+)$", text):
        if key in fields:
            raise ValueError(f"duplicate field: {key}")
        fields[key] = value.strip()
    return fields


def parse_staged_question(
    *,
    main_root: str,
    staging_path: str,
    staged_record: str,
    worker_return: str,
    current_attempt: int,
) -> StagedQuestion:
    staged = parse_fields(staged_record)
    returned = parse_fields(worker_return)
    if staged.get("status") != "open" or returned.get("status") != "question":
        raise ValueError("question status mismatch")
    if returned.get("decision") != "pending-id":
        raise ValueError("worker assigned or omitted decision id")
    task_match = re.fullmatch(r"T-(\d{3})", returned.get("work", ""))
    attempt_match = re.fullmatch(r"e(\d+)", staged.get("source_attempt", ""))
    returned_attempt = returned.get("attempt", "")
    if not task_match or not attempt_match or not returned_attempt.isdigit():
        raise ValueError("invalid task or attempt")
    task, attempt = int(task_match[1]), int(attempt_match[1])
    expected_path = f"{main_root}/.rune/decisions/open/T-{task:03d}-e{attempt}.md"
    if (
        staged.get("raised_by") != f"T-{task:03d}"
        or int(returned_attempt) != attempt
        or attempt != current_attempt
        or staging_path != expected_path
        or returned.get("decision_artifact") != expected_path
    ):
        raise ValueError("question record, return, path, root, or ledger mismatch")
    return StagedQuestion(task, attempt, staging_path)


def decision_sources_valid(records: list[tuple[str, int]]) -> bool:
    seen: set[str] = set()
    for source, _decision in records:
        if re.fullmatch(r"T-\d{3}/e\d+", source) is None:
            continue
        if source in seen:
            return False
        seen.add(source)
    return True


def validate_question(question: StagedQuestion, current_attempt: int | None = None) -> None:
    expected_suffix = f"/.rune/decisions/open/T-{question.task:03d}-e{question.attempt}.md"
    if not question.path.endswith(expected_suffix):
        raise ValueError("question path does not match task attempt")
    if current_attempt is not None and question.attempt != current_attempt:
        raise ValueError("question attempt is stale against ledger")


def reconcile_question(
    state: DecisionState, question: StagedQuestion, crash_after: str | None = None
) -> None:
    """Reference decisions -> ledger -> delete transaction, with crash injection."""
    if question.task not in state.attempts:
        raise ValueError("question task has no current ledger attempt")
    validate_question(question, state.attempts.get(question.task))
    if question.path not in state.staged:
        return
    source = question.source
    if source in state.records:
        decision = state.records[source]
    else:
        decision = max(state.records.values(), default=0) + 1
        state.records[source] = decision
    if crash_after == "decision":
        return
    existing = state.awaiting.get(question.task)
    if existing not in {None, decision}:
        raise ValueError("conflicting awaiting row")
    state.awaiting[question.task] = decision
    if crash_after == "ledger":
        return
    state.staged.remove(question.path)


def reconcile_question_batch(
    state: DecisionState, questions: list[StagedQuestion]
) -> None:
    for question in sorted(questions, key=lambda item: (item.task, item.attempt)):
        reconcile_question(state, question)


def check_decision_allocation_and_returns() -> None:
    taskfmt = read("skills/ai-taskfmt/SKILL.md")
    decisions = taskfmt[taskfmt.index("## Decision record") : taskfmt.index("## Handoff note")]
    for token in (
        "T-nnn-eN.md",
        "decision: pending-id",
        "decision_artifact:",
        "sorts simultaneously observed questions",
        "only then deletes",
        "unique `source`",
        "source: vision",
        "vision | planning | T-nnn/eN",
    ):
        if token not in decisions:
            fail(f"decision allocation contract is incomplete: {token}")

    for skill in ("ai-execute", "ai-drift", "work"):
        markdown = read(f"skills/{skill}/SKILL.md")
        if "decision: pending-id" not in markdown or "decision_artifact:" not in markdown:
            fail(f"{skill}: question return lacks pending id and staging pointer")
        if re.search(r"(?m)^decision: DEC-", markdown):
            fail(f"{skill}: worker-facing example still invents a DEC id")

    def parsed_question(root: str, task: int, attempt: int) -> StagedQuestion:
        path = f"{root}/.rune/decisions/open/T-{task:03d}-e{attempt}.md"
        return parse_staged_question(
            main_root=root,
            staging_path=path,
            staged_record=(
                f"status: open\nraised_by: T-{task:03d}\nsource_attempt: e{attempt}\n"
            ),
            worker_return=(
                f"work: T-{task:03d}\nsummary: decision required\nstatus: question\n"
                f"worktree: kept\nworktree_path: {root}/.rune/worktrees/T-{task:03d}\n"
                f"attempt: {attempt}\n"
                f"decision: pending-id\ndecision_artifact: {path}\n"
            ),
            current_attempt=attempt,
        )

    q20 = parsed_question("/workspace/acme", 20, 2)
    q03 = parsed_question("/workspace/acme", 3, 4)
    state = DecisionState(
        records={"vision": 5},
        staged={q20.path, q03.path},
        attempts={20: 2, 3: 4},
    )
    reconcile_question_batch(state, [q20, q03])
    if state.records[q03.source] != 6 or state.records[q20.source] != 7:
        fail("concurrent questions did not receive deterministic parent ids")
    if state.staged or state.awaiting != {3: 6, 20: 7}:
        fail("concurrent question batch did not complete every transaction")

    # Crash after decisions.md: retry reuses the id before updating the ledger.
    q11 = parsed_question("/repo", 11, 3)
    crash = DecisionState(records={"old": 8}, staged={q11.path}, attempts={11: 3})
    reconcile_question(crash, q11, crash_after="decision")
    assigned = crash.records[q11.source]
    reconcile_question(crash, q11)
    if crash.records[q11.source] != assigned or crash.awaiting[11] != assigned:
        fail("decision-write crash allocated a duplicate id")

    # Crash after ledger.md: retry only consumes the remaining staging file.
    q12 = parsed_question("/repo", 12, 1)
    crash = DecisionState(records={"old": 9}, staged={q12.path}, attempts={12: 1})
    reconcile_question(crash, q12, crash_after="ledger")
    record_count = len(crash.records)
    reconcile_question(crash, q12)
    if len(crash.records) != record_count or q12.path in crash.staged:
        fail("ledger-write crash was not idempotently cleaned up")

    stale = parsed_question("/repo", 12, 2)
    try:
        validate_question(stale, current_attempt=3)
    except ValueError:
        pass
    else:
        fail("accepted a stale attempt's decision staging path")

    valid_path = "/repo/.rune/decisions/open/T-014-e2.md"
    staged_record = "status: open\nraised_by: T-014\nsource_attempt: e2\n"
    worker_return = (
        "work: T-014\nsummary: decision required\nstatus: question\nworktree: kept\n"
        "worktree_path: /repo/.rune/worktrees/T-014\nattempt: 2\ndecision: pending-id\n"
        f"decision_artifact: {valid_path}\n"
    )
    invalid_inputs = (
        ("/other", valid_path, staged_record, worker_return, 2),
        ("/repo", valid_path, staged_record.replace("T-014", "T-015"), worker_return, 2),
        ("/repo", valid_path, staged_record.replace("e2", "e3"), worker_return, 2),
        ("/repo", valid_path, staged_record, worker_return.replace("attempt: 2", "attempt: 3"), 2),
        ("/repo", valid_path, staged_record, worker_return.replace(valid_path, "/repo/wrong"), 2),
        ("/repo", valid_path, staged_record, worker_return, 3),
    )
    for main_root, path, staged, returned, current in invalid_inputs:
        try:
            parse_staged_question(
                main_root=main_root,
                staging_path=path,
                staged_record=staged,
                worker_return=returned,
                current_attempt=current,
            )
        except ValueError:
            pass
        else:
            fail("accepted mismatched staged question inputs")
    if decision_sources_valid([("T-014/e2", 8), ("T-014/e2", 9)]):
        fail("accepted duplicate durable ids for one worker-question source")
    if decision_sources_valid([("T-014/e2", 8), ("T-014/e2", 8)]):
        fail("accepted a repeated worker-question source")


def check_pre_reconciliation_decision_gate() -> None:
    work = read("skills/work/SKILL.md")
    decompose = section(work, "2. Decompose")
    gate_at = decompose.find("Run the pre-reconciliation gate")
    reconcile_at = decompose.find("dispatch one fresh\n   reconciler")
    if gate_at < 0 or reconcile_at < 0 or gate_at > reconcile_at:
        fail("work does not gate user decisions before final reconciliation")
    for token in ("harmless implementation assumption", "behaviour/scope decision"):
        if token not in decompose:
            fail(f"work decision gate lacks classification: {token}")
    if "fresh run whose protocol lists that id" not in decompose:
        fail("settled decisions are not made durable inputs to fresh planners")

    taskfmt = read("skills/ai-taskfmt/SKILL.md")
    if "decisions: [DEC-004, DEC-007]" not in taskfmt:
        fail("protocol schema lacks durable decided inputs")
    ai_decompose = read("skills/ai-decompose/SKILL.md")
    for token in ("`decisions: [...]`", "require `status: decided`", "nonempty `decision_candidates`"):
        if token not in ai_decompose:
            fail(f"decomposer does not consume the decision seam: {token}")


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
    check_dispatch_examples_and_callers()
    check_return_examples_and_budgets()
    check_command_and_oracle_enums()
    check_public_interfaces()
    check_writer_and_lifecycle_contracts()
    check_vision_lifecycle()
    check_decision_allocation_and_returns()
    check_pre_reconciliation_decision_gate()
    check_mitigation_contracts()
    check_scaffold_behavior()
    print("skill contracts and scaffold behavior: ok")


if __name__ == "__main__":
    main()
