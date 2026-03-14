from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path

from .errors import PolicyViolationError

_CHAIN_PATTERN = re.compile(r"(?:&&)|\||;")


@dataclass(frozen=True)
class CommandExecutionPolicy:
    allowlist: tuple[str, ...]
    timeout_seconds: int
    max_output_chars: int


def contains_shell_chaining(command: str) -> bool:
    return bool(_CHAIN_PATTERN.search(command))


def extract_executable(command: str) -> str:
    if not command.strip():
        raise PolicyViolationError("Command is empty.")
    parts = shlex.split(command, posix=False)
    if not parts:
        raise PolicyViolationError("Command is empty after parsing.")
    return parts[0]


def normalize_command_name(executable: str) -> str:
    raw = executable.strip().strip('"').strip("'")
    base = Path(raw).name if ("\\" in raw or "/" in raw) else raw
    return os.path.splitext(base)[0].lower()


def validate_command(command: str, policy: CommandExecutionPolicy) -> str:
    if contains_shell_chaining(command):
        raise PolicyViolationError(
            "Shell chaining operators are not allowed.",
            {"command": command},
        )

    executable = extract_executable(command)
    normalized = normalize_command_name(executable)
    allowed = {item.lower() for item in policy.allowlist}
    if normalized not in allowed:
        raise PolicyViolationError(
            "Command is not allowed by policy.",
            {
                "command": command,
                "normalized_executable": normalized,
                "allowlist": sorted(allowed),
            },
        )
    return normalized
