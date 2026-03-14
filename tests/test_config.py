from pathlib import Path

import pytest

from windows_dump_analysis_mcp.config import ServerConfig
from windows_dump_analysis_mcp.errors import InvalidPathError


def test_config_prefers_absolute_cdb_path() -> None:
    cfg = ServerConfig(cdb_path="C:\\Program Files\\WindowsApps\\Microsoft.WinDbg\\amd64\\cdb.exe").validate()
    assert cfg.cdb_command().lower().endswith("cdb.exe")
    assert cfg.cdb_command().startswith("C:\\")


def test_config_rejects_relative_cdb_path() -> None:
    with pytest.raises(InvalidPathError):
        ServerConfig(cdb_path="amd64\\cdb.exe").validate()


def test_config_falls_back_to_executable_name_if_cdb_not_set() -> None:
    cfg = ServerConfig(cdb_path=None).validate()
    assert cfg.cdb_command() == "cdb.exe"
