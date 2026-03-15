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

MULTI_THREAD_OUTPUT = r"""
DUMP_TYPE: minidump
PROJECT_TYPE: native_cpp
EXCEPTION_CODE: (NTSTATUS) 0xc0000005 - EXCEPTION_ACCESS_VIOLATION
FAULTING_IP:
CppConsoleApplication!DataProcessor::ConsumeData+0x23 [C:\OldRoot\CppConsoleApplication.cpp @ 95]
DUMP_MCP_BEGIN_THREAD_LIST
.  0  Id: 4ea8.654c Suspend: 1 Teb: 00000000`00001000 Unfrozen
   1  Id: 4ea8.33a0 Suspend: 1 Teb: 00000000`00002000 Unfrozen
DUMP_MCP_END_THREAD_LIST
DUMP_MCP_BEGIN_ALL_THREADS_STACK
.  0  Id: 4ea8.654c Suspend: 1 Teb: 00000000`00001000 Unfrozen
00000040`0010f910 00007ff7`c22417b0 CppConsoleApplication!DataProcessor::ConsumeData+0x23
00000040`0010f930 00007ff7`c22439d9 CppConsoleApplication!SubThreadEntry+0x80
00000040`0010f950 00007ffd`dc311234 kernel32!BaseThreadInitThunk+0x14
   1  Id: 4ea8.33a0 Suspend: 1 Teb: 00000000`00002000 Unfrozen
00000040`0011f910 00007ff7`c2241000 CppConsoleApplication!main+0x44
00000040`0011f930 00007ffd`dc311234 kernel32!BaseThreadInitThunk+0x14
DUMP_MCP_END_ALL_THREADS_STACK
DUMP_MCP_BEGIN_RUNAWAY
 User Mode Time
 Thread       Time
   0:654c     0 days 0:00:01.250
   1:33a0     0 days 0:00:09.125
DUMP_MCP_END_RUNAWAY
LOADED_MODULES:
CppConsoleApplication.exe | good
SYMBOL_STATUS: good
"""

FAULTING_THREAD_MAPPING_OUTPUT = r"""
DUMP_TYPE: minidump
PROJECT_TYPE: native_cpp
FAULTING_THREAD: ffffffff
STACK_COMMAND: ~4s; .ecxr ; kb
Last event: 3c54.35d4: Access violation - code c0000005 (first/second chance not available)
EXCEPTION_CODE: (NTSTATUS) 0xc0000005 - EXCEPTION_ACCESS_VIOLATION
FAULTING_IP:
CppConsoleApplication!DataProcessor::ConsumeData+0x3b [C:\OldRoot\CppConsoleApplication.cpp @ 95]
STACK_TEXT:
0000005c`b2efe9f0 CppConsoleApplication!DataProcessor::ConsumeData+0x3b [C:\OldRoot\CppConsoleApplication.cpp @ 95]
0000005c`b2efeb10 CppConsoleApplication!DataProcessor::ParseData+0x2c [C:\OldRoot\CppConsoleApplication.cpp @ 82]
0000005c`b2eff4b0 CppConsoleApplication!SubThreadEntry+0x66 [C:\OldRoot\CppConsoleApplication.cpp @ 155]
DUMP_MCP_BEGIN_THREAD_LIST
   0  Id: 3c54.0674 Suspend: 0 Teb: 0000005c`b29f6000 Unfrozen
.  4  Id: 3c54.35d4 Suspend: 0 Teb: 0000005c`b29fe000 Unfrozen
DUMP_MCP_END_THREAD_LIST
DUMP_MCP_BEGIN_ALL_THREADS_STACK
   0  Id: 3c54.0674 Suspend: 0 Teb: 0000005c`b29f6000 Unfrozen
0000005c`b2afecf0 ntdll!RtlDelayExecution+0x34
0000005c`b2afed20 KERNELBASE!SleepEx+0x91
0000005c`b2afef60 CppConsoleApplication!main+0x3cd
.  4  Id: 3c54.35d4 Suspend: 0 Teb: 0000005c`b29fe000 Unfrozen
0000005c`b2efba48 ntdll!NtGetContextThread+0x14
DUMP_MCP_END_ALL_THREADS_STACK
LOADED_MODULES:
CppConsoleApplication.exe | good
SYMBOL_STATUS: good
"""

WRONG_SYMBOLS_LEADING_STACK_OUTPUT = r"""
DUMP_TYPE: minidump
PROJECT_TYPE: native_cpp
FAULTING_THREAD: ffffffff
STACK_COMMAND: ~4s; .ecxr ; kb
Last event: 3c54.35d4: Access violation - code c0000005 (first/second chance not available)
EXCEPTION_CODE: (NTSTATUS) 0xc0000005 - EXCEPTION_ACCESS_VIOLATION
FAULTING_IP:
CppConsoleApplication!DataProcessor::ConsumeData+0x3b [C:\OldRoot\CppConsoleApplication.cpp @ 95]
STACK_TEXT:
0000005c`b2efe9f0 00007ff7`4d1cb6ec : 00000251`079de830 00007ff7`4d1ca7fb 0000005c`b2efecc8 00007ffb`eafcdcd5 : WRONG_SYMBOLS!WRONG_SYMBOLS+0x0

0000005c`b2efeb10 00007ff7`4d1cb69c : 00000251`079de830 00007ffb`00000000 00000000`00000000 0000005c`b2efed28 : CppConsoleApplication!DataProcessor::ConsumeData+0x3b
0000005c`b2eff4b0 00007ff7`4d1c7a48 : 00000251`079f5580 00007ffc`acf7b350 00000000`00000008 0000005c`b2eff7b8 : CppConsoleApplication!SubThreadEntry+0x66
DUMP_MCP_BEGIN_THREAD_LIST
   0  Id: 3c54.0674 Suspend: 0 Teb: 0000005c`b29f6000 Unfrozen
.  4  Id: 3c54.35d4 Suspend: 0 Teb: 0000005c`b29fe000 Unfrozen
DUMP_MCP_END_THREAD_LIST
DUMP_MCP_BEGIN_ALL_THREADS_STACK
   0  Id: 3c54.0674 Suspend: 0 Teb: 0000005c`b29f6000 Unfrozen
0000005c`b2afef60 CppConsoleApplication!main+0x3cd
.  4  Id: 3c54.35d4 Suspend: 0 Teb: 0000005c`b29fe000 Unfrozen
0000005c`b2efba48 ntdll!NtGetContextThread+0x14
DUMP_MCP_END_ALL_THREADS_STACK
LOADED_MODULES:
CppConsoleApplication.exe | good
SYMBOL_STATUS: good
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


def test_get_stack_trace_uses_crashing_thread_when_thread_id_is_none(tmp_path: Path) -> None:
    runner = StubRunner(SAMPLE_DEBUGGER_OUTPUT)
    config = ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate()
    server = DumpAnalysisMCPServer(config=config, debugger_runner=runner)
    dump_id = _make_registered_dump(server, tmp_path)
    server.call_tool("analyze_dump", {"dump_id": dump_id})

    result = server.call_tool(
        "get_stack_trace",
        {"dump_id": dump_id, "thread_id": None, "max_frames": 2},
    )
    assert result["ok"] is True
    assert result["thread_id"] == 42
    assert len(result["stack_frames"]) == 2


def test_get_stack_trace_returns_validation_error_for_invalid_thread_id(tmp_path: Path) -> None:
    runner = StubRunner(SAMPLE_DEBUGGER_OUTPUT)
    config = ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate()
    server = DumpAnalysisMCPServer(config=config, debugger_runner=runner)
    dump_id = _make_registered_dump(server, tmp_path)
    server.call_tool("analyze_dump", {"dump_id": dump_id})

    result = server.call_tool(
        "get_stack_trace",
        {"dump_id": dump_id, "thread_id": "not-an-int"},
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_request"


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


def test_analyze_dump_parses_multi_thread_sections(tmp_path: Path) -> None:
    runner = StubRunner(MULTI_THREAD_OUTPUT)
    config = ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate()
    server = DumpAnalysisMCPServer(config=config, debugger_runner=runner)
    dump_id = _make_registered_dump(server, tmp_path)

    result = server.call_tool("analyze_dump", {"dump_id": dump_id})

    assert result["ok"] is True
    assert result["thread_count"] == 2
    assert result["crashing_thread"] == 0
    assert result["fault_function"] == "DataProcessor::ConsumeData"
    assert any(pattern == "main_alive_worker_crashed" for pattern in result["suspected_patterns"])
    assert result["threads"][0]["is_faulting"] is True
    assert result["threads"][1]["thread_id"] == 1
    assert result["threads"][0]["cpu_user_time_seconds"] == 1.25
    assert result["threads"][1]["cpu_user_time_seconds"] == 9.125
    assert result["threads"][0]["cpu_user_time_text"] == "0 days 00:00:01.250"
    assert result["threads"][1]["cpu_user_time_text"] == "0 days 00:00:09.125"


def test_thread_tools_return_selected_thread_frames(tmp_path: Path) -> None:
    runner = StubRunner(MULTI_THREAD_OUTPUT)
    config = ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate()
    server = DumpAnalysisMCPServer(config=config, debugger_runner=runner)
    dump_id = _make_registered_dump(server, tmp_path)
    server.call_tool("analyze_dump", {"dump_id": dump_id})

    listed = server.call_tool("get_thread_list", {"dump_id": dump_id})
    assert listed["ok"] is True
    assert listed["thread_count"] == 2
    assert len(listed["threads"]) == 2
    assert any(item["is_faulting"] for item in listed["threads"])
    assert listed["threads"][0]["cpu_user_time_seconds"] == 1.25

    selected = server.call_tool(
        "get_thread_stack_trace",
        {"dump_id": dump_id, "thread_id": 1, "max_frames": 1},
    )
    assert selected["ok"] is True
    assert selected["thread_id"] == 1
    assert len(selected["stack_frames"]) == 1
    assert selected["stack_frames"][0]["function"] == "main"
    assert selected["cpu_user_time_seconds"] == 9.125

    legacy_selected = server.call_tool(
        "get_stack_trace",
        {"dump_id": dump_id, "thread_id": 1, "max_frames": 1},
    )
    assert legacy_selected["ok"] is True
    assert legacy_selected["thread_id"] == 1
    assert legacy_selected["stack_frames"][0]["function"] == "main"

    os_tid = next(item["os_thread_id"] for item in listed["threads"] if item["thread_id"] == 1)
    selected_by_os_tid = server.call_tool(
        "get_thread_stack_trace",
        {"dump_id": dump_id, "thread_id": os_tid, "max_frames": 1},
    )
    assert selected_by_os_tid["ok"] is True
    assert selected_by_os_tid["thread_id"] == 1

    legacy_by_os_tid = server.call_tool(
        "get_stack_trace",
        {"dump_id": dump_id, "thread_id": os_tid, "max_frames": 1},
    )
    assert legacy_by_os_tid["ok"] is True
    assert legacy_by_os_tid["thread_id"] == 1

    invalid_thread = server.call_tool(
        "get_thread_stack_trace",
        {"dump_id": dump_id, "thread_id": 999999},
    )
    assert invalid_thread["ok"] is False
    assert invalid_thread["error"]["code"] == "invalid_request"


def test_faulting_thread_mapping_prefers_deterministic_signals(tmp_path: Path) -> None:
    runner = StubRunner(FAULTING_THREAD_MAPPING_OUTPUT)
    config = ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate()
    server = DumpAnalysisMCPServer(config=config, debugger_runner=runner)
    dump_id = _make_registered_dump(server, tmp_path)

    analyzed = server.call_tool("analyze_dump", {"dump_id": dump_id})
    assert analyzed["ok"] is True
    assert analyzed["faulting_thread_confidence"] == "high"
    assert analyzed["crashing_thread"] == 4
    assert analyzed["stack_frames"][0]["function"] == "DataProcessor::ConsumeData"

    listed = server.call_tool("get_thread_list", {"dump_id": dump_id})
    assert listed["ok"] is True
    faulting_rows = [item for item in listed["threads"] if item["is_faulting"]]
    assert len(faulting_rows) == 1
    assert faulting_rows[0]["thread_id"] == 4


def test_stack_text_trims_leading_wrong_symbols_frame(tmp_path: Path) -> None:
    runner = StubRunner(WRONG_SYMBOLS_LEADING_STACK_OUTPUT)
    config = ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate()
    server = DumpAnalysisMCPServer(config=config, debugger_runner=runner)
    dump_id = _make_registered_dump(server, tmp_path)

    analyzed = server.call_tool("analyze_dump", {"dump_id": dump_id})
    assert analyzed["ok"] is True
    assert analyzed["crashing_thread"] == 4
    assert analyzed["stack_frames"][0]["module"] == "CppConsoleApplication"
    assert analyzed["stack_frames"][0]["function"] == "DataProcessor::ConsumeData"
    assert analyzed["stack_frames"][0]["function"] != "WRONG_SYMBOLS"
