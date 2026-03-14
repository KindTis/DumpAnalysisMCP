from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from windows_dump_analysis_mcp.config import ServerConfig
from windows_dump_analysis_mcp.server import DumpAnalysisMCPServer


@dataclass
class FakeRunResult:
    return_code: int
    stdout: str
    stderr: str


class FakeCommandRunner:
    def __init__(self, result: FakeRunResult | None = None, *, raise_timeout: bool = False):
        self.result = result or FakeRunResult(return_code=0, stdout="ok", stderr="")
        self.raise_timeout = raise_timeout
        self.calls: list[dict[str, object]] = []

    def run(
        self,
        *,
        args: list[str],
        cwd: str | None,
        timeout_seconds: int,
    ) -> FakeRunResult:
        self.calls.append({"args": args, "cwd": cwd, "timeout_seconds": timeout_seconds})
        if self.raise_timeout:
            raise TimeoutError("timed out")
        return self.result


def _new_server(command_runner: FakeCommandRunner) -> DumpAnalysisMCPServer:
    cfg = ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate()
    return DumpAnalysisMCPServer(config=cfg, command_runner=command_runner)


def test_build_project_requires_user_confirmation() -> None:
    server = _new_server(FakeCommandRunner())
    result = server.call_tool(
        "build_project",
        {"command": "dotnet build Airi.sln -c Debug", "user_confirmed": False},
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "policy_violation"


def test_build_project_rejects_shell_chaining() -> None:
    server = _new_server(FakeCommandRunner())
    result = server.call_tool(
        "build_project",
        {"command": "dotnet build Airi.sln -c Debug && echo done", "user_confirmed": True},
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "policy_violation"


def test_build_project_runs_allowlisted_command(tmp_path: Path) -> None:
    runner = FakeCommandRunner(result=FakeRunResult(return_code=0, stdout="build ok", stderr=""))
    server = _new_server(runner)
    result = server.call_tool(
        "build_project",
        {
            "command": "dotnet build Airi.sln -c Debug",
            "user_confirmed": True,
            "working_directory": str(tmp_path.resolve()),
        },
    )
    assert result["ok"] is True
    assert result["tool"] == "build_project"
    assert result["status"] == "passed"
    assert result["exit_code"] == 0
    assert runner.calls


def test_run_tests_returns_failure_when_exit_code_nonzero(tmp_path: Path) -> None:
    runner = FakeCommandRunner(result=FakeRunResult(return_code=1, stdout="x", stderr="failed"))
    server = _new_server(runner)
    result = server.call_tool(
        "run_tests",
        {
            "command": "dotnet test tests/Airi.Tests/Airi.Tests.csproj -c Debug",
            "user_confirmed": True,
            "working_directory": str(tmp_path.resolve()),
        },
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "test_failed"


def test_run_tests_returns_timeout_error(tmp_path: Path) -> None:
    runner = FakeCommandRunner(raise_timeout=True)
    server = _new_server(runner)
    result = server.call_tool(
        "run_tests",
        {
            "command": "dotnet test tests/Airi.Tests/Airi.Tests.csproj -c Debug",
            "user_confirmed": True,
            "working_directory": str(tmp_path.resolve()),
            "timeout_seconds": 1,
        },
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "test_failed"

