from __future__ import annotations

from pathlib import Path

from windows_dump_analysis_mcp.config import ServerConfig
from windows_dump_analysis_mcp.server import DumpAnalysisMCPServer


def _new_server() -> DumpAnalysisMCPServer:
    return DumpAnalysisMCPServer(config=ServerConfig(cdb_path="C:\\Debuggers\\cdb.exe").validate())


def test_apply_patch_defaults_to_preview_and_does_not_write_file(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    target = source_root / "A.cpp"
    target.write_text("int a = 1;\n", encoding="utf-8")

    server = _new_server()
    result = server.call_tool(
        "apply_patch",
        {
            "source_root": str(source_root.resolve()),
            "changes": [{"path": "A.cpp", "content": "int a = 2;\n"}],
        },
    )

    assert result["ok"] is True
    assert result["mode"] == "preview"
    assert result["applied"] is False
    assert target.read_text(encoding="utf-8") == "int a = 1;\n"
    assert "int a = 1;" in result["diff"]
    assert "int a = 2;" in result["diff"]


def test_apply_patch_requires_explicit_confirmation_for_apply_mode(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "A.cpp").write_text("int a = 1;\n", encoding="utf-8")

    server = _new_server()
    result = server.call_tool(
        "apply_patch",
        {
            "source_root": str(source_root.resolve()),
            "mode": "apply",
            "changes": [{"path": "A.cpp", "content": "int a = 2;\n"}],
            "user_confirmed": False,
        },
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "policy_violation"


def test_apply_patch_writes_when_apply_mode_and_confirmed(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    target = source_root / "A.cpp"
    target.write_text("int a = 1;\n", encoding="utf-8")

    server = _new_server()
    result = server.call_tool(
        "apply_patch",
        {
            "source_root": str(source_root.resolve()),
            "mode": "apply",
            "user_confirmed": True,
            "changes": [{"path": "A.cpp", "content": "int a = 3;\n"}],
        },
    )

    assert result["ok"] is True
    assert result["mode"] == "apply"
    assert result["applied"] is True
    assert len(result["modified_files"]) == 1
    assert target.read_text(encoding="utf-8") == "int a = 3;\n"


def test_apply_patch_rejects_path_escape_outside_source_root(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()

    server = _new_server()
    result = server.call_tool(
        "apply_patch",
        {
            "source_root": str(source_root.resolve()),
            "changes": [{"path": "..\\escape.cpp", "content": "bad\n"}],
        },
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_path"
