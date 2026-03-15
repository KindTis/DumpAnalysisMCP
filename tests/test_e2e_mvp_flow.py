from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from windows_dump_analysis_mcp.config import ServerConfig
from windows_dump_analysis_mcp.server import DumpAnalysisMCPServer


class StubDebuggerRunner:
    def __init__(self, output: str):
        self._output = output

    def run(
        self,
        *,
        dump_path: str,
        symbol_root: str,
        source_root: str,
        binary_root: str | None,
    ) -> str:
        _ = (dump_path, symbol_root, source_root, binary_root)
        return self._output


@dataclass
class FakeRunResult:
    return_code: int
    stdout: str
    stderr: str


class FakeCommandRunner:
    def __init__(self):
        self.calls: list[list[str]] = []

    def run(
        self,
        *,
        args: list[str],
        cwd: str | None,
        timeout_seconds: int,
    ) -> FakeRunResult:
        _ = (cwd, timeout_seconds)
        self.calls.append(args)
        cmd = " ".join(args).lower()
        if "dotnet build" in cmd:
            return FakeRunResult(0, "build ok", "")
        if "dotnet test" in cmd:
            return FakeRunResult(0, "tests ok", "")
        return FakeRunResult(1, "", "unknown command")


def test_e2e_mvp_flow_native_cpp(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    target_file = source_root / "InventoryComponent.cpp"
    target_file.write_text(
        "\n".join(
            [
                "void Helper() {}",
                "void InventoryComponent::UseItem() {",
                "  int* ptr = nullptr;",
                "  *ptr = 10;",
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (source_root / "InventoryComponent.h").write_text(
        "class InventoryComponent { void UseItem(); };",
        encoding="utf-8",
    )
    dump_file = tmp_path / "sample.dmp"
    dump_file.write_bytes(b"MZ")
    symbol_root = tmp_path / "symbols"
    symbol_root.mkdir()

    debugger_output = f"""
DUMP_TYPE: minidump
PROJECT_TYPE: native_cpp
FAULTING_THREAD: 42
EXCEPTION_CODE: (NTSTATUS) 0xc0000005 - EXCEPTION_ACCESS_VIOLATION
FAULTING_IP:
myApp!InventoryComponent::UseItem+0x12 [{target_file} @ 4]
STACK_TEXT:
00000000`0014f2b0 myApp!InventoryComponent::UseItem+0x12 [{target_file} @ 4]
LOADED_MODULES:
myApp.exe | good
SYMBOL_STATUS: good
"""
    command_runner = FakeCommandRunner()
    server = DumpAnalysisMCPServer(
        config=ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate(),
        debugger_runner=StubDebuggerRunner(debugger_output),
        command_runner=command_runner,
    )

    registered = server.call_tool(
        "register_dump",
        {
            "dump_path": str(dump_file.resolve()),
            "symbol_root": str(symbol_root.resolve()),
            "source_root": str(source_root.resolve()),
            "project_type": "native_cpp",
        },
    )
    assert registered["ok"] is True
    dump_id = registered["dump_id"]

    analyzed = server.call_tool("analyze_dump", {"dump_id": dump_id})
    assert analyzed["ok"] is True
    assert analyzed["exception_name"] == "EXCEPTION_ACCESS_VIOLATION"

    threads = server.call_tool("get_thread_list", {"dump_id": dump_id})
    assert threads["ok"] is True
    assert threads["thread_count"] >= 1

    source_ctx = server.call_tool(
        "get_source_context",
        {"dump_id": dump_id, "frame_index": 0, "context_before": 1, "context_after": 1},
    )
    assert source_ctx["ok"] is True
    assert source_ctx["focus_line"] == 4

    refs = server.call_tool(
        "search_code_references",
        {"dump_id": dump_id, "query": "UseItem", "max_results": 10},
    )
    assert refs["ok"] is True
    assert refs["count"] >= 2

    preview = server.call_tool(
        "apply_patch",
        {
            "dump_id": dump_id,
            "changes": [{"path": "InventoryComponent.cpp", "content": target_file.read_text(encoding="utf-8").replace("*ptr = 10;", "if (ptr) { *ptr = 10; }")}],
        },
    )
    assert preview["ok"] is True
    assert preview["applied"] is False

    apply = server.call_tool(
        "apply_patch",
        {
            "dump_id": dump_id,
            "mode": "apply",
            "user_confirmed": True,
            "changes": [
                {
                    "path": "InventoryComponent.cpp",
                    "content": target_file.read_text(encoding="utf-8").replace(
                        "*ptr = 10;", "if (ptr) { *ptr = 10; }"
                    ),
                }
            ],
        },
    )
    assert apply["ok"] is True
    assert apply["applied"] is True
    assert "if (ptr) { *ptr = 10; }" in target_file.read_text(encoding="utf-8")

    build = server.call_tool(
        "build_project",
        {
            "command": "dotnet build Airi.sln -c Debug",
            "user_confirmed": True,
            "working_directory": str(source_root.resolve()),
        },
    )
    assert build["ok"] is True
    assert build["status"] == "passed"

    test = server.call_tool(
        "run_tests",
        {
            "command": "dotnet test tests/Airi.Tests/Airi.Tests.csproj -c Debug",
            "user_confirmed": True,
            "working_directory": str(source_root.resolve()),
        },
    )
    assert test["ok"] is True
    assert test["status"] == "passed"

    resources = server.list_resources()
    assert f"crash://{dump_id}/summary" in resources
    summary = server.read_resource(f"crash://{dump_id}/summary")
    assert summary["ok"] is True
    assert summary["resource"]["contents"]["dump_id"] == dump_id

    assert len(command_runner.calls) == 2
