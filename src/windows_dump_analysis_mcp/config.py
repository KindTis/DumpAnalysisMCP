from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .errors import InvalidPathError


def _parse_csv(value: str | None, fallback: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        return fallback
    items = [item.strip() for item in value.split(",")]
    return tuple(item for item in items if item)


@dataclass(frozen=True)
class ServerConfig:
    cdb_path: str | None = None
    analyze_timeout_seconds: int = 180
    default_build_timeout_seconds: int = 20 * 60
    default_test_timeout_seconds: int = 30 * 60
    max_output_chars: int = 200_000
    build_allowlist: tuple[str, ...] = field(
        default_factory=lambda: (
            "msbuild",
            "dotnet",
            "cmake",
            "ninja",
            "UnrealBuildTool",
            "RunUAT",
        )
    )
    test_allowlist: tuple[str, ...] = field(
        default_factory=lambda: (
            "ctest",
            "dotnet",
            "pytest",
            "UnrealEditor-Cmd",
            "RunUAT",
        )
    )

    @classmethod
    def from_env(cls) -> "ServerConfig":
        return cls(
            cdb_path=os.getenv("DUMP_MCP_CDB_PATH"),
            analyze_timeout_seconds=int(
                os.getenv("DUMP_MCP_ANALYZE_TIMEOUT_SECONDS", "180")
            ),
            default_build_timeout_seconds=int(
                os.getenv("DUMP_MCP_BUILD_TIMEOUT_SECONDS", str(20 * 60))
            ),
            default_test_timeout_seconds=int(
                os.getenv("DUMP_MCP_TEST_TIMEOUT_SECONDS", str(30 * 60))
            ),
            max_output_chars=int(os.getenv("DUMP_MCP_MAX_OUTPUT_CHARS", "200000")),
            build_allowlist=_parse_csv(
                os.getenv("DUMP_MCP_BUILD_ALLOWLIST"),
                (
                    "msbuild",
                    "dotnet",
                    "cmake",
                    "ninja",
                    "UnrealBuildTool",
                    "RunUAT",
                ),
            ),
            test_allowlist=_parse_csv(
                os.getenv("DUMP_MCP_TEST_ALLOWLIST"),
                ("ctest", "dotnet", "pytest", "UnrealEditor-Cmd", "RunUAT"),
            ),
        ).validate()

    def validate(self) -> "ServerConfig":
        if self.cdb_path:
            cdb = Path(self.cdb_path)
            if not cdb.is_absolute():
                raise InvalidPathError(
                    "Configured cdb_path must be an absolute path.",
                    {"cdb_path": self.cdb_path},
                )
        if self.default_build_timeout_seconds <= 0:
            raise InvalidPathError(
                "Build timeout must be positive.",
                {"default_build_timeout_seconds": self.default_build_timeout_seconds},
            )
        if self.analyze_timeout_seconds <= 0:
            raise InvalidPathError(
                "Analyze timeout must be positive.",
                {"analyze_timeout_seconds": self.analyze_timeout_seconds},
            )
        if self.default_test_timeout_seconds <= 0:
            raise InvalidPathError(
                "Test timeout must be positive.",
                {"default_test_timeout_seconds": self.default_test_timeout_seconds},
            )
        if self.max_output_chars <= 0:
            raise InvalidPathError(
                "Max output chars must be positive.",
                {"max_output_chars": self.max_output_chars},
            )
        return self

    def cdb_command(self) -> str:
        # Absolute path is preferred to avoid PATH/version ambiguity.
        return self.cdb_path or "cdb.exe"
