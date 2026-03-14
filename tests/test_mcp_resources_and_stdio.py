from __future__ import annotations

import os
import sys
from pathlib import Path

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

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


def _setup_server_with_session(tmp_path: Path) -> tuple[DumpAnalysisMCPServer, str]:
    source_root = tmp_path / "source"
    source_root.mkdir()
    src = source_root / "InventoryComponent.cpp"
    src.write_text("\n".join([f"line {idx}" for idx in range(1, 11)]), encoding="utf-8")
    dump_file = tmp_path / "sample.dmp"
    dump_file.write_bytes(b"MZ")
    symbol_root = tmp_path / "symbols"
    symbol_root.mkdir()

    output = f"""
DUMP_TYPE: minidump
PROJECT_TYPE: native_cpp
FAULTING_THREAD: 42
EXCEPTION_CODE: (NTSTATUS) 0xc0000005 - EXCEPTION_ACCESS_VIOLATION
FAULTING_IP:
myApp!InventoryComponent::UseItem+0x12 [{src} @ 5]
STACK_TEXT:
00000000`0014f2b0 myApp!InventoryComponent::UseItem+0x12 [{src} @ 5]
LOADED_MODULES:
myApp.exe | good
SYMBOL_STATUS: good
"""
    server = DumpAnalysisMCPServer(
        config=ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate(),
        debugger_runner=StubRunner(output),
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
    return server, dump_id


def test_server_lists_resources_for_registered_dump(tmp_path: Path) -> None:
    server, dump_id = _setup_server_with_session(tmp_path)
    resources = server.list_resources()

    assert f"crash://{dump_id}/summary" in resources
    assert f"crash://{dump_id}/source/main-frame" in resources
    assert "project://symbols/status" in resources


def test_server_reads_crash_summary_and_source_resource(tmp_path: Path) -> None:
    server, dump_id = _setup_server_with_session(tmp_path)

    summary = server.read_resource(f"crash://{dump_id}/summary")
    assert summary["ok"] is True
    assert summary["resource"]["uri"] == f"crash://{dump_id}/summary"
    assert summary["resource"]["contents"]["exception_code"] == "0xC0000005"

    source = server.read_resource(f"crash://{dump_id}/source/main-frame")
    assert source["ok"] is True
    assert source["resource"]["contents"]["focus_line"] == 5
    assert len(source["resource"]["contents"]["lines"]) > 0


async def _run_stdio_handshake_test() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["DUMP_MCP_LOG_LEVEL"] = "WARNING"

    existing_pythonpath = env.get("PYTHONPATH", "")
    src_path = str((repo_root / "src").resolve())
    env["PYTHONPATH"] = src_path if not existing_pythonpath else f"{src_path}{os.pathsep}{existing_pythonpath}"

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "windows_dump_analysis_mcp"],
        env=env,
        cwd=str(repo_root),
    )

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            tool_names = {tool.name for tool in tools_result.tools}
            assert "register_dump" in tool_names
            assert "analyze_dump" in tool_names

            resources_result = await session.list_resources()
            resource_uris = {str(resource.uri) for resource in resources_result.resources}
            assert "project://symbols/status" in resource_uris
            assert "project://source/root" in resource_uris

            templates_result = await session.list_resource_templates()
            template_uris = {str(template.uriTemplate) for template in templates_result.resourceTemplates}
            assert "crash://{dump_id}/summary" in template_uris
            assert "crash://{dump_id}/source/main-frame" in template_uris


def test_stdio_server_completes_mcp_initialize_handshake() -> None:
    anyio.run(_run_stdio_handshake_test)
