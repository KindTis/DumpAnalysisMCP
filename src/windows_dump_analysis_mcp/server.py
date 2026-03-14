from __future__ import annotations

from typing import Any

from .analyzer import DebuggerRunner, DumpAnalyzerCore
from .code_context import CodeContextProvider
from .config import ServerConfig
from .errors import ErrorCode, ServerError
from .execution import BuildTestExecutor, CommandRunner
from .patching import PatchExecutor
from .session_store import DumpSessionStore
from .tools import ToolContext, ToolRegistry


class DumpAnalysisMCPServer:
    def __init__(
        self,
        config: ServerConfig | None = None,
        debugger_runner: DebuggerRunner | None = None,
        command_runner: CommandRunner | None = None,
    ):
        self.config = (config or ServerConfig.from_env()).validate()
        self.session_store = DumpSessionStore()
        self.analyzer = DumpAnalyzerCore(self.config, runner=debugger_runner)
        self.code_context = CodeContextProvider()
        self.patch_executor = PatchExecutor()
        self.build_test_executor = BuildTestExecutor(self.config, runner=command_runner)
        self.registry = ToolRegistry(
            ToolContext(
                config=self.config,
                session_store=self.session_store,
                analyzer=self.analyzer,
                code_context=self.code_context,
                patch_executor=self.patch_executor,
                build_test_executor=self.build_test_executor,
            )
        )

    def list_tools(self) -> list[str]:
        return self.registry.list_tool_names()

    def list_resources(self) -> list[str]:
        return self.registry.list_resource_uris()

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            return self.registry.call(name, arguments)
        except ServerError as err:
            return err.to_dict()
        except Exception as err:  # pragma: no cover - safety net
            return ServerError(
                ErrorCode.INTERNAL_ERROR,
                "Unhandled server error.",
                {"exception": type(err).__name__, "message": str(err)},
            ).to_dict()

    def read_resource(self, uri: str) -> dict[str, Any]:
        try:
            payload = self.registry.read_resource(uri)
            return {"ok": True, "resource": payload}
        except ServerError as err:
            return err.to_dict()
        except Exception as err:  # pragma: no cover - safety net
            return ServerError(
                ErrorCode.INTERNAL_ERROR,
                "Unhandled server error.",
                {"exception": type(err).__name__, "message": str(err)},
            ).to_dict()
