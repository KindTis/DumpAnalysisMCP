import pytest

from windows_dump_analysis_mcp.command_policy import (
    CommandExecutionPolicy,
    contains_shell_chaining,
    validate_command,
)
from windows_dump_analysis_mcp.errors import PolicyViolationError


def test_contains_shell_chaining_detects_blocked_operators() -> None:
    assert contains_shell_chaining("dotnet test && echo done")
    assert contains_shell_chaining("ctest | findstr FAIL")
    assert contains_shell_chaining("pytest ; dir")


def test_validate_command_allows_allowlisted_executable() -> None:
    policy = CommandExecutionPolicy(
        allowlist=("dotnet", "ctest"),
        timeout_seconds=1200,
        max_output_chars=10000,
    )

    normalized = validate_command('dotnet test tests/Airi.Tests.csproj -c Debug', policy)
    assert normalized == "dotnet"


def test_validate_command_rejects_non_allowlisted_executable() -> None:
    policy = CommandExecutionPolicy(
        allowlist=("dotnet", "ctest"),
        timeout_seconds=1200,
        max_output_chars=10000,
    )

    with pytest.raises(PolicyViolationError):
        validate_command("powershell -Command Get-Date", policy)
