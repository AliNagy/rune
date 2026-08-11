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
        if (phase, followed, work_id) == ("plan-graph", "ai-decompose", "vision"):
            valid = outcome.startswith("graph: /") and outcome.endswith("/.rune/milestones.md")
        elif (phase, followed, work_id) == ("survey", "ai-survey", "—"):
            valid = outcome == "map.md written"
        elif (phase, followed, work_id) == ("commands", "ai-oracle", "—"):
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
        ("plan-graph", "ai-decompose", "vision", "graph: /repo/.rune/milestones.md"),
        ("survey", "ai-survey", "—", "map.md written"),
        ("commands", "ai-oracle", "—", "oracle: npm test"),
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
    task_match = re.fullmatch(r"T-(\d{3})", returned.get("task", ""))
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
                f"status: question\ntask: T-{task:03d}\nattempt: {attempt}\n"
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
        "status: question\ntask: T-014\nattempt: 2\ndecision: pending-id\n"
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
    check_public_interfaces()
    check_writer_and_lifecycle_contracts()
    check_vision_lifecycle()
    check_decision_allocation_and_returns()
    check_pre_reconciliation_decision_gate()
    check_scaffold_behavior()
    print("skill contracts and scaffold behavior: ok")


if __name__ == "__main__":
    main()
