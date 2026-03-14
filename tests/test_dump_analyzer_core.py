from __future__ import annotations

from pathlib import Path

from windows_dump_analysis_mcp.config import ServerConfig
from windows_dump_analysis_mcp.server import DumpAnalysisMCPServer


SAMPLE_DEBUGGER_OUTPUT = """
DUMP_TYPE: minidump
PROJECT_TYPE: native_cpp
FAULTING_THREAD: 42
EXCEPTION_CODE: (NTSTATUS) 0xc0000005 - EXCEPTION_ACCESS_VIOLATION
FAULTING_IP:
myApp!InventoryComponent::UseItem+0x12 [D:\\Dev\\MyApp\\Source\\Inventory\\InventoryComponent.cpp @ 248]
STACK_TEXT:
00000000`0014f2b0 myApp!InventoryComponent::UseItem+0x12 [D:\\Dev\\MyApp\\Source\\Inventory\\InventoryComponent.cpp @ 248]
00000000`0014f300 myApp!PlayerController::Tick+0x1d [D:\\Dev\\MyApp\\Source\\Player\\PlayerController.cpp @ 102]
LOADED_MODULES:
myApp.exe | good
Engine.dll | partial
SYMBOL_STATUS: good
"""

REAL_CDB_STYLE_OUTPUT = r"""
(4ea8.654c): Access violation - code c0000005 (first/second chance not available)
cpp_crash_sample!`anonymous namespace'::TriggerAccessViolation+0x12:
0:000> cdb: Reading initial command '.sympath "C:\Sym"; .srcpath "C:\Src"; .exepath "C:\Bin"; .lines; !analyze -v; .ecxr; kL 64; lm; q'
Line number information will be loaded
ExceptionAddress: 00007ff7c2241712 (cpp_crash_sample!`anonymous namespace'::TriggerAccessViolation+0x0000000000000012)
   ExceptionCode: c0000005 (Access violation)
FAULTING_THREAD:  ffffffff
cpp_crash_sample!`anonymous namespace'::TriggerAccessViolation+12 [C:\Work\cpp-crash-sample\src\main.cpp @ 10]
00000040`7638f910 00007ff7`c22417b0     cpp_crash_sample!`anonymous namespace'::TriggerAccessViolation+0x12
C:\Work\cpp-crash-sample\src\main.cpp(10)+0x4
00000040`7638f930 00007ff7`c22439d9     cpp_crash_sample!main+0x80
start             end                 module name
00007ff7`c2240000 00007ff7`c2256000   cpp_crash_sample C (private pdb symbols)  c:\work\cpp-crash-sample\cpp_crash_sample.pdb
00007ffd`dc2e0000 00007ffd`dc3a9000   kernel32   (export symbols)       kernel32.dll
"""


class StubRunner:
    def __init__(self, output: str, *, fail: bool = False):
        self._output = output
        self._fail = fail
        self.calls: list[tuple[str, str, str, str | None]] = []

    def run(
        self,
        *,
        dump_path: str,
        symbol_root: str,
        source_root: str,
        binary_root: str | None,
    ) -> str:
        self.calls.append((dump_path, symbol_root, source_root, binary_root))
        if self._fail:
            raise RuntimeError("debugger failed")
        return self._output


def _make_registered_dump(server: DumpAnalysisMCPServer, tmp_path: Path) -> str:
    dump_file = tmp_path / "sample.dmp"
    dump_file.write_bytes(b"MZ")
    symbol_root = tmp_path / "symbols"
    source_root = tmp_path / "source"
    symbol_root.mkdir()
    source_root.mkdir()

    payload = server.call_tool(
        "register_dump",
        {
            "dump_path": str(dump_file.resolve()),
            "symbol_root": str(symbol_root.resolve()),
            "source_root": str(source_root.resolve()),
            "project_type": "native_cpp",
            "dump_type_hint": "auto",
        },
    )
    assert payload["ok"] is True
    return payload["dump_id"]


def test_analyze_dump_returns_structured_result(tmp_path: Path) -> None:
    runner = StubRunner(SAMPLE_DEBUGGER_OUTPUT)
    config = ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate()
    server = DumpAnalysisMCPServer(config=config, debugger_runner=runner)
    dump_id = _make_registered_dump(server, tmp_path)

    result = server.call_tool("analyze_dump", {"dump_id": dump_id})

    assert result["ok"] is True
    assert result["dump_id"] == dump_id
    assert result["exception_code"] == "0xC0000005"
    assert result["exception_name"] == "EXCEPTION_ACCESS_VIOLATION"
    assert result["fault_module"] == "myApp"
    assert result["fault_function"] == "InventoryComponent::UseItem"
    assert result["source_location"]["file"].endswith("InventoryComponent.cpp")
    assert result["source_location"]["line"] == 248
    assert result["crashing_thread"] == 42
    assert len(result["stack_frames"]) == 2
    assert result["symbol_quality"] == "good"
    assert len(result["loaded_modules"]) == 2


def test_get_exception_info_returns_cached_analysis_fields(tmp_path: Path) -> None:
    runner = StubRunner(SAMPLE_DEBUGGER_OUTPUT)
    config = ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate()
    server = DumpAnalysisMCPServer(config=config, debugger_runner=runner)
    dump_id = _make_registered_dump(server, tmp_path)
    server.call_tool("analyze_dump", {"dump_id": dump_id})

    result = server.call_tool("get_exception_info", {"dump_id": dump_id})
    assert result["ok"] is True
    assert result["exception_code"] == "0xC0000005"
    assert result["exception_name"] == "EXCEPTION_ACCESS_VIOLATION"
    assert result["fault_address"] == "unknown"


def test_get_stack_trace_honors_max_frames(tmp_path: Path) -> None:
    runner = StubRunner(SAMPLE_DEBUGGER_OUTPUT)
    config = ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate()
    server = DumpAnalysisMCPServer(config=config, debugger_runner=runner)
    dump_id = _make_registered_dump(server, tmp_path)
    server.call_tool("analyze_dump", {"dump_id": dump_id})

    result = server.call_tool(
        "get_stack_trace",
        {"dump_id": dump_id, "thread_id": 42, "max_frames": 1},
    )
    assert result["ok"] is True
    assert result["thread_id"] == 42
    assert len(result["stack_frames"]) == 1
    assert result["stack_frames"][0]["index"] == 0


def test_get_module_list_returns_modules_and_symbol_quality(tmp_path: Path) -> None:
    runner = StubRunner(SAMPLE_DEBUGGER_OUTPUT)
    config = ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate()
    server = DumpAnalysisMCPServer(config=config, debugger_runner=runner)
    dump_id = _make_registered_dump(server, tmp_path)
    server.call_tool("analyze_dump", {"dump_id": dump_id})

    result = server.call_tool("get_module_list", {"dump_id": dump_id})
    assert result["ok"] is True
    assert result["symbol_quality"] == "good"
    assert result["loaded_modules"][0]["module"] == "myApp.exe"


def test_analyze_dump_returns_debugger_error_when_runner_fails(tmp_path: Path) -> None:
    runner = StubRunner(SAMPLE_DEBUGGER_OUTPUT, fail=True)
    config = ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate()
    server = DumpAnalysisMCPServer(config=config, debugger_runner=runner)
    dump_id = _make_registered_dump(server, tmp_path)

    result = server.call_tool("analyze_dump", {"dump_id": dump_id})
    assert result["ok"] is False
    assert result["error"]["code"] == "debugger_invocation_failed"


def test_analyze_dump_parses_real_cdb_style_output(tmp_path: Path) -> None:
    runner = StubRunner(REAL_CDB_STYLE_OUTPUT)
    config = ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate()
    server = DumpAnalysisMCPServer(config=config, debugger_runner=runner)
    dump_id = _make_registered_dump(server, tmp_path)

    result = server.call_tool("analyze_dump", {"dump_id": dump_id})

    assert result["ok"] is True
    assert result["dump_id"] == dump_id
    assert result["exception_code"] == "0xC0000005"
    assert result["exception_name"] == "EXCEPTION_ACCESS_VIOLATION"
    assert result["fault_module"] == "cpp_crash_sample"
    assert "TriggerAccessViolation" in result["fault_function"]
    assert result["source_location"]["file"].endswith("src\\main.cpp")
    assert result["source_location"]["line"] == 10
    assert len(result["stack_frames"]) >= 2
    assert "TriggerAccessViolation" in result["stack_frames"][0]["function"]
    assert result["symbol_quality"] == "good"
