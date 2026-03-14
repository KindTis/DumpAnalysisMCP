from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ErrorCode:
    INVALID_REQUEST = "invalid_request"
    INVALID_PATH = "invalid_path"
    DUMP_FILE_NOT_FOUND = "dump_file_not_found"
    SYMBOL_PATH_INVALID = "symbol_path_invalid"
    SOURCE_ROOT_INVALID = "source_root_invalid"
    SOURCE_MAPPING_FAILED = "source_mapping_failed"
    DEBUGGER_INVOCATION_FAILED = "debugger_invocation_failed"
    BUILD_FAILED = "build_failed"
    TEST_FAILED = "test_failed"
    POLICY_VIOLATION = "policy_violation"
    TOOL_NOT_IMPLEMENTED = "tool_not_implemented"
    INTERNAL_ERROR = "internal_error"
    UNKNOWN_TOOL = "unknown_tool"


@dataclass
class ServerError(Exception):
    code: str
    message: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
            },
        }
        if self.details:
            payload["error"]["details"] = self.details
        return payload


class ValidationError(ServerError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(ErrorCode.INVALID_REQUEST, message, details)


class InvalidPathError(ServerError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(ErrorCode.INVALID_PATH, message, details)


class PolicyViolationError(ServerError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(ErrorCode.POLICY_VIOLATION, message, details)


class ToolNotImplementedError(ServerError):
    def __init__(self, tool_name: str):
        super().__init__(
            ErrorCode.TOOL_NOT_IMPLEMENTED,
            f"Tool '{tool_name}' is not implemented yet.",
            {"tool_name": tool_name},
        )


class UnknownToolError(ServerError):
    def __init__(self, tool_name: str):
        super().__init__(
            ErrorCode.UNKNOWN_TOOL,
            f"Unknown tool '{tool_name}'.",
            {"tool_name": tool_name},
        )
