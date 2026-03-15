from __future__ import annotations

from pathlib import Path

from windows_dump_analysis_mcp.config import ServerConfig
from windows_dump_analysis_mcp.server import DumpAnalysisMCPServer


class StubRunner:
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


def _register(
    server: DumpAnalysisMCPServer,
    tmp_path: Path,
    source_root: Path,
    *,
    source_path_map: dict[str, str] | None = None,
) -> str:
    dump_file = tmp_path / "sample.dmp"
    dump_file.write_bytes(b"MZ")
    symbol_root = tmp_path / "symbols"
    symbol_root.mkdir()

    payload = server.call_tool(
        "register_dump",
        {
            "dump_path": str(dump_file.resolve()),
            "symbol_root": str(symbol_root.resolve()),
            "source_root": str(source_root.resolve()),
            "project_type": "native_cpp",
            "source_path_map": source_path_map or {},
        },
    )
    assert payload["ok"] is True
    return payload["dump_id"]


def test_get_source_context_returns_frame_window(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    file_a = source_root / "InventoryComponent.cpp"
    file_a.write_text("\n".join([f"line {idx}" for idx in range(1, 11)]), encoding="utf-8")

    file_b = source_root / "PlayerController.cpp"
    file_b.write_text("a\nb\nc\nd\n", encoding="utf-8")

    output = f"""
DUMP_TYPE: minidump
PROJECT_TYPE: native_cpp
FAULTING_THREAD: 42
EXCEPTION_CODE: (NTSTATUS) 0xc0000005 - EXCEPTION_ACCESS_VIOLATION
FAULTING_IP:
myApp!InventoryComponent::UseItem+0x12 [{file_a} @ 5]
STACK_TEXT:
00000000`0014f2b0 myApp!InventoryComponent::UseItem+0x12 [{file_a} @ 5]
00000000`0014f300 myApp!PlayerController::Tick+0x1d [{file_b} @ 3]
LOADED_MODULES:
myApp.exe | good
SYMBOL_STATUS: good
"""
    server = DumpAnalysisMCPServer(
        config=ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate(),
        debugger_runner=StubRunner(output),
    )
    dump_id = _register(server, tmp_path, source_root)
    server.call_tool("analyze_dump", {"dump_id": dump_id})

    result = server.call_tool(
        "get_source_context",
        {"dump_id": dump_id, "frame_index": 0, "context_before": 2, "context_after": 1},
    )
    assert result["ok"] is True
    assert result["focus_line"] == 5
    assert result["start_line"] == 3
    assert result["end_line"] == 6
    assert len(result["lines"]) == 4
    assert result["lines"][0]["text"] == "line 3"


def test_get_source_context_rejects_path_outside_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    file_inside = source_root / "InventoryComponent.cpp"
    file_inside.write_text("inside\n", encoding="utf-8")

    outside_file = tmp_path / "outside.cpp"
    outside_file.write_text("outside\n", encoding="utf-8")

    output = f"""
DUMP_TYPE: minidump
PROJECT_TYPE: native_cpp
FAULTING_THREAD: 42
EXCEPTION_CODE: (NTSTATUS) 0xc0000005 - EXCEPTION_ACCESS_VIOLATION
FAULTING_IP:
myApp!InventoryComponent::UseItem+0x12 [{file_inside} @ 1]
STACK_TEXT:
00000000`0014f2b0 myApp!InventoryComponent::UseItem+0x12 [{outside_file} @ 1]
LOADED_MODULES:
myApp.exe | good
SYMBOL_STATUS: good
"""
    server = DumpAnalysisMCPServer(
        config=ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate(),
        debugger_runner=StubRunner(output),
    )
    dump_id = _register(server, tmp_path, source_root)
    server.call_tool("analyze_dump", {"dump_id": dump_id})

    result = server.call_tool("get_source_context", {"dump_id": dump_id, "frame_index": 0})
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_path"


def test_get_source_context_applies_source_path_map(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    local_file = source_root / "CppConsoleApplication.cpp"
    local_file.write_text("\n".join([f"line {idx}" for idx in range(1, 121)]), encoding="utf-8")

    external_source = Path(r"C:\OldRoot\CppConsoleApplication.cpp")
    output = f"""
DUMP_TYPE: minidump
PROJECT_TYPE: native_cpp
FAULTING_THREAD: 0
EXCEPTION_CODE: (NTSTATUS) 0xc0000005 - EXCEPTION_ACCESS_VIOLATION
FAULTING_IP:
CppConsoleApplication!DataProcessor::ConsumeData+0x23 [{external_source} @ 95]
STACK_TEXT:
00000000`0014f2b0 CppConsoleApplication!DataProcessor::ConsumeData+0x23 [{external_source} @ 95]
LOADED_MODULES:
CppConsoleApplication.exe | good
SYMBOL_STATUS: good
"""
    server = DumpAnalysisMCPServer(
        config=ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate(),
        debugger_runner=StubRunner(output),
    )
    dump_id = _register(
        server,
        tmp_path,
        source_root,
        source_path_map={r"C:\OldRoot": str(source_root.resolve())},
    )
    server.call_tool("analyze_dump", {"dump_id": dump_id})

    result = server.call_tool("get_source_context", {"dump_id": dump_id, "frame_index": 0})
    assert result["ok"] is True
    assert result["focus_line"] == 95
    assert result["file"].endswith("CppConsoleApplication.cpp")


def test_search_code_references_uses_dump_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "A.cpp").write_text("void UseItem();\nvoid x(){UseItem();}\n", encoding="utf-8")
    (source_root / "B.h").write_text("int UseItemCount = 0;\n", encoding="utf-8")
    (source_root / "Ignore.bin").write_bytes(b"\x00\x01\x02")

    output = """
DUMP_TYPE: minidump
PROJECT_TYPE: native_cpp
FAULTING_THREAD: 1
EXCEPTION_CODE: (NTSTATUS) 0xc0000005 - EXCEPTION_ACCESS_VIOLATION
FAULTING_IP:
myApp!InventoryComponent::UseItem+0x12
STACK_TEXT:
00000000`0014f2b0 myApp!InventoryComponent::UseItem+0x12
LOADED_MODULES:
myApp.exe | good
SYMBOL_STATUS: good
"""
    server = DumpAnalysisMCPServer(
        config=ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate(),
        debugger_runner=StubRunner(output),
    )
    dump_id = _register(server, tmp_path, source_root)
    result = server.call_tool(
        "search_code_references",
        {"dump_id": dump_id, "query": "UseItem", "max_results": 10},
    )

    assert result["ok"] is True
    assert result["count"] >= 2
    assert any(item["file"].endswith("A.cpp") for item in result["results"])
    assert any(item["file"].endswith("B.h") for item in result["results"])


def test_search_code_references_requires_source_root_or_dump_id(tmp_path: Path) -> None:
    _ = tmp_path
    server = DumpAnalysisMCPServer(config=ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate())
    result = server.call_tool("search_code_references", {"query": "UseItem"})
    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_request"
