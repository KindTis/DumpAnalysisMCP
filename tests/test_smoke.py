from windows_dump_analysis_mcp.config import ServerConfig
from windows_dump_analysis_mcp.server import DumpAnalysisMCPServer


def test_server_starts_and_exposes_expected_tools() -> None:
    config = ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate()
    server = DumpAnalysisMCPServer(config=config)
    tools = server.list_tools()

    assert "register_dump" in tools
    assert "analyze_dump" in tools
    assert "run_tests" in tools
