#!/usr/bin/env python3
"""Auto-approve permission requests for Parliament pipeline work.

Reads a PermissionRequest hook payload on stdin and prints a decision on stdout.

Policy: allow by default. The pipelines are long unattended runs made of curl
downloads, python3 scripts, and CSV writes inside the repo — prompting on each
one costs hours of wall-clock waiting for a human to click "yes".

Fall through to a normal permission prompt (print "{}") only for actions that
are destructive or reach outside this project:

  - deleting/moving/overwriting paths outside the project root
  - privilege escalation (sudo, su, chmod on system paths)
  - disk/system level commands (dd, mkfs, shutdown, killall)
  - piping a download straight into a shell
  - history-rewriting or remote-destroying git commands
  - dropping or truncating database tables

Everything else — every curl, python3, unzip, csv write, git add/commit,
WebFetch of any government domain — is approved silently.
"""

import json
import os
import re
import shlex
import sys

PROJECT_ROOT = os.path.realpath(
    os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "..")
)

# Extra roots the pipelines legitimately write to outside the repo.
EXTRA_WRITE_ROOTS = [
    os.path.realpath(os.path.expanduser("~/.claude/jobs")),
    os.path.realpath("/tmp"),
    os.path.realpath("/var/folders"),  # macOS $TMPDIR
]

ALLOW = {
    "hookSpecificOutput": {
        "hookEventName": "PermissionRequest",
        "permissionDecision": "allow",
    }
}
ASK = {}

# Commands that always warrant a human, wherever they point.
HARD_PATTERNS = [
    r"(^|[;&|]\s*)sudo\b",
    r"(^|[;&|]\s*)su\b",
    r"(^|[;&|]\s*)dd\b.*\bof=",
    r"\bmkfs\b",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bkillall\b",
    r"\bdiskutil\b",
    r":\(\)\s*\{.*\};\s*:",                     # fork bomb
    r"(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba)?sh",  # pipe download into shell
    r"\bchmod\b[^;|&]*\s/(usr|etc|bin|sbin|var|System)\b",
    r"\bgit\b[^;|&]*\bpush\b[^;|&]*(--force\b|--force-with-lease\b|\s-f\b)",
    r"\bgit\b[^;|&]*\breset\b[^;|&]*--hard\b",
    r"\bgit\b[^;|&]*\bfilter-branch\b",
    r"\bgit\b[^;|&]*\bpush\b[^;|&]*--delete\b",
    r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b",
    r"\bTRUNCATE\s+(TABLE\s+)?\w",
]

# Commands whose path arguments must stay inside the project.
PATH_SCOPED = {"rm", "rmdir", "mv", "cp", "shred", "trash", "chmod", "chown", "ln"}


def inside_allowed_roots(path: str) -> bool:
    """True if path resolves inside the project or another sanctioned root."""
    expanded = os.path.expanduser(os.path.expandvars(path))
    if not os.path.isabs(expanded):
        expanded = os.path.join(PROJECT_ROOT, expanded)
    resolved = os.path.realpath(expanded)
    roots = [PROJECT_ROOT] + EXTRA_WRITE_ROOTS
    return any(resolved == r or resolved.startswith(r + os.sep) for r in roots)


def bash_is_safe(command: str) -> bool:
    for pattern in HARD_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return False

    # Check path arguments of destructive commands. Parse failures (heredocs,
    # unbalanced quotes) fall back to the pattern check above.
    try:
        tokens = shlex.split(command)
    except ValueError:
        return True

    for i, token in enumerate(tokens):
        base = os.path.basename(token)
        if base not in PATH_SCOPED:
            continue
        for arg in tokens[i + 1:]:
            if arg in {";", "&&", "||", "|"}:
                break
            if arg.startswith("-"):
                continue
            if arg in {"/", "~", "$HOME", "~/"} or not inside_allowed_roots(arg):
                return False
    return True


def decide(payload: dict) -> dict:
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    if tool in {"Bash", "BashOutput"}:
        command = tool_input.get("command", "")
        return ALLOW if bash_is_safe(command) else ASK

    if tool in {"Write", "Edit", "NotebookEdit"}:
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        return ALLOW if path and inside_allowed_roots(path) else ASK

    # Read, Glob, Grep, WebFetch, WebSearch and the rest are non-destructive.
    return ALLOW


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print(json.dumps(ASK))
        return
    print(json.dumps(decide(payload)))


if __name__ == "__main__":
    main()
