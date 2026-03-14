from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex
import subprocess
from typing import Protocol

from .command_policy import CommandExecutionPolicy, validate_command
from .config import ServerConfig
from .errors import ErrorCode, PolicyViolationError, ServerError, ValidationError


@dataclass(frozen=True)
class CommandRunResult:
    return_code: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(
        self,
        *,
        args: list[str],
        cwd: str | None,
        timeout_seconds: int,
    ) -> CommandRunResult: ...


class SubprocessCommandRunner:
    def run(
        self,
        *,
        args: list[str],
        cwd: str | None,
        timeout_seconds: int,
    ) -> CommandRunResult:
        completed = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return CommandRunResult(
            return_code=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n...[truncated {len(text) - max_chars} chars]"


class BuildTestExecutor:
    def __init__(self, config: ServerConfig, runner: CommandRunner | None = None):
        self._config = config
        self._runner = runner or SubprocessCommandRunner()

    def run_build(
        self,
        *,
        command: str,
        user_confirmed: bool,
        working_directory: str | None,
        timeout_seconds: int | None,
    ) -> dict:
        return self._run(
            tool_name="build_project",
            command=command,
            user_confirmed=user_confirmed,
            working_directory=working_directory,
            timeout_seconds=timeout_seconds,
            policy=CommandExecutionPolicy(
                allowlist=self._config.build_allowlist,
                timeout_seconds=self._config.default_build_timeout_seconds,
                max_output_chars=self._config.max_output_chars,
            ),
            error_code=ErrorCode.BUILD_FAILED,
        )

    def run_tests(
        self,
        *,
        command: str,
        user_confirmed: bool,
        working_directory: str | None,
        timeout_seconds: int | None,
    ) -> dict:
        return self._run(
            tool_name="run_tests",
            command=command,
            user_confirmed=user_confirmed,
            working_directory=working_directory,
            timeout_seconds=timeout_seconds,
            policy=CommandExecutionPolicy(
                allowlist=self._config.test_allowlist,
                timeout_seconds=self._config.default_test_timeout_seconds,
                max_output_chars=self._config.max_output_chars,
            ),
            error_code=ErrorCode.TEST_FAILED,
        )

    def _run(
        self,
        *,
        tool_name: str,
        command: str,
        user_confirmed: bool,
        working_directory: str | None,
        timeout_seconds: int | None,
        policy: CommandExecutionPolicy,
        error_code: str,
    ) -> dict:
        if not user_confirmed:
            raise PolicyViolationError(
                f"{tool_name} requires explicit user confirmation.",
                {"required_flag": "user_confirmed"},
            )
        if not isinstance(command, str) or not command.strip():
            raise ValidationError(f"{tool_name} requires non-empty 'command'.")

        normalized = validate_command(command, policy)
        args = shlex.split(command, posix=False)
        if not args:
            raise ValidationError("Command cannot be empty after parsing.")

        cwd = None
        if working_directory:
            wd = Path(working_directory)
            if not wd.is_absolute():
                raise ServerError(
                    ErrorCode.INVALID_PATH,
                    "working_directory must be absolute.",
                    {"working_directory": working_directory},
                )
            if not wd.exists() or not wd.is_dir():
                raise ServerError(
                    ErrorCode.INVALID_PATH,
                    "working_directory does not exist.",
                    {"working_directory": working_directory},
                )
            cwd = str(wd)

        timeout = timeout_seconds or policy.timeout_seconds
        if timeout <= 0:
            raise ValidationError("timeout_seconds must be positive.", {"timeout_seconds": timeout})

        try:
            result = self._runner.run(args=args, cwd=cwd, timeout_seconds=timeout)
        except TimeoutError as exc:
            raise ServerError(
                error_code,
                f"{tool_name} timed out.",
                {"command": command, "timeout_seconds": timeout, "timed_out": True},
            ) from exc
        except Exception as exc:
            raise ServerError(
                error_code,
                f"{tool_name} execution failed.",
                {"command": command, "exception": type(exc).__name__, "message": str(exc)},
            ) from exc

        stdout = _truncate(result.stdout, policy.max_output_chars)
        stderr = _truncate(result.stderr, policy.max_output_chars)
        if result.return_code != 0:
            raise ServerError(
                error_code,
                f"{tool_name} command failed.",
                {
                    "command": command,
                    "exit_code": result.return_code,
                    "stdout": stdout,
                    "stderr": stderr,
                    "normalized_executable": normalized,
                },
            )

        return {
            "ok": True,
            "tool": tool_name,
            "status": "passed",
            "command": command,
            "normalized_executable": normalized,
            "exit_code": result.return_code,
            "stdout": stdout,
            "stderr": stderr,
            "timeout_seconds": timeout,
        }
