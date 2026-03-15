from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .logging_utils import configure_logging, get_logger
from .server import DumpAnalysisMCPServer

LOGGER = get_logger("windows_dump_analysis_mcp.mcp")


def _call_tool(server: DumpAnalysisMCPServer, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return server.call_tool(name, arguments)


def _read_resource(server: DumpAnalysisMCPServer, uri: str) -> dict[str, Any]:
    response = server.read_resource(uri)
    if response.get("ok") is True:
        return response["resource"]

    error = response.get("error", {})
    code = error.get("code", "internal_error")
    message = error.get("message", "Resource read failed.")
    raise RuntimeError(f"{code}: {message}")


def create_mcp_app(server: DumpAnalysisMCPServer | None = None) -> FastMCP:
    backend = server or DumpAnalysisMCPServer()
    app = FastMCP(name="dump-analysis")

    @app.tool(
        name="register_dump",
        description="Register a dump session (dump/symbol/source paths, project_type, optional source_path_map) and return dump_id.",
    )
    def register_dump(
        dump_path: str,
        symbol_root: str,
        source_root: str,
        project_type: str,
        binary_root: str | None = None,
        dump_type_hint: str = "auto",
        log_paths: list[str] | None = None,
        source_path_map: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return _call_tool(
            backend,
            "register_dump",
            {
                "dump_path": dump_path,
                "symbol_root": symbol_root,
                "source_root": source_root,
                "project_type": project_type,
                "binary_root": binary_root,
                "dump_type_hint": dump_type_hint,
                "log_paths": log_paths or [],
                "source_path_map": source_path_map or {},
            },
        )

    @app.tool(
        name="analyze_dump",
        description="Run analysis for a registered dump_id and return normalized crash data (exception, stack, threads, modules, warnings).",
    )
    def analyze_dump(dump_id: str) -> dict[str, Any]:
        return _call_tool(backend, "analyze_dump", {"dump_id": dump_id})

    @app.tool(
        name="get_exception_info",
        description="Get exception summary for a dump_id (code, name, type, fault address).",
    )
    def get_exception_info(dump_id: str) -> dict[str, Any]:
        return _call_tool(backend, "get_exception_info", {"dump_id": dump_id})

    @app.tool(
        name="get_stack_trace",
        description="Get stack frames for a selected thread in dump_id (default: crashing thread; thread_id uses WinDbg index first, OS TID fallback).",
    )
    def get_stack_trace(
        dump_id: str,
        max_frames: int = 30,
        thread_id: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "dump_id": dump_id,
            "max_frames": max_frames,
        }
        if thread_id is not None:
            payload["thread_id"] = thread_id
        return _call_tool(
            backend,
            "get_stack_trace",
            payload,
        )

    @app.tool(
        name="get_thread_list",
        description="List threads for dump_id with faulting metadata, top frame, and CPU user time.",
    )
    def get_thread_list(dump_id: str) -> dict[str, Any]:
        return _call_tool(backend, "get_thread_list", {"dump_id": dump_id})

    @app.tool(
        name="get_thread_stack_trace",
        description="Get stack frames for a specific thread (thread_id required; WinDbg index first, OS TID fallback).",
    )
    def get_thread_stack_trace(
        dump_id: str,
        thread_id: int,
        max_frames: int = 30,
    ) -> dict[str, Any]:
        return _call_tool(
            backend,
            "get_thread_stack_trace",
            {
                "dump_id": dump_id,
                "thread_id": thread_id,
                "max_frames": max_frames,
            },
        )

    @app.tool(
        name="get_module_list",
        description="Get loaded modules and overall symbol quality for a dump_id.",
    )
    def get_module_list(dump_id: str) -> dict[str, Any]:
        return _call_tool(backend, "get_module_list", {"dump_id": dump_id})

    @app.tool(
        name="get_source_context",
        description="Get source context around a selected frame/thread for dump_id (uses source_path_map remap when provided at register_dump).",
    )
    def get_source_context(
        dump_id: str,
        frame_index: int = 0,
        context_before: int = 20,
        context_after: int = 20,
        thread_id: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "dump_id": dump_id,
            "frame_index": frame_index,
            "context_before": context_before,
            "context_after": context_after,
        }
        if thread_id is not None:
            payload["thread_id"] = thread_id
        return _call_tool(
            backend,
            "get_source_context",
            payload,
        )

    @app.tool(
        name="search_code_references",
        description="Search code references by query under source_root (explicit) or source_root from dump_id.",
    )
    def search_code_references(
        query: str,
        dump_id: str | None = None,
        source_root: str | None = None,
        max_results: int = 50,
        ignore_case: bool = False,
    ) -> dict[str, Any]:
        return _call_tool(
            backend,
            "search_code_references",
            {
                "query": query,
                "dump_id": dump_id,
                "source_root": source_root,
                "max_results": max_results,
                "ignore_case": ignore_case,
            },
        )

    @app.tool(
        name="apply_patch",
        description="Preview or apply file changes using dump_id or source_root (apply mode requires user_confirmed=true).",
    )
    def apply_patch(
        changes: list[dict[str, str]],
        dump_id: str | None = None,
        source_root: str | None = None,
        mode: str = "preview",
        user_confirmed: bool = False,
    ) -> dict[str, Any]:
        return _call_tool(
            backend,
            "apply_patch",
            {
                "changes": changes,
                "dump_id": dump_id,
                "source_root": source_root,
                "mode": mode,
                "user_confirmed": user_confirmed,
            },
        )

    @app.tool(
        name="build_project",
        description="Run a guarded build command (allowlist/timeout; user_confirmed=true required) and return build result.",
    )
    def build_project(
        command: str,
        dump_id: str | None = None,
        working_directory: str | None = None,
        timeout_seconds: int | None = None,
        user_confirmed: bool = False,
    ) -> dict[str, Any]:
        return _call_tool(
            backend,
            "build_project",
            {
                "command": command,
                "dump_id": dump_id,
                "working_directory": working_directory,
                "timeout_seconds": timeout_seconds,
                "user_confirmed": user_confirmed,
            },
        )

    @app.tool(
        name="run_tests",
        description="Run a guarded test command (allowlist/timeout; user_confirmed=true required) and return test result.",
    )
    def run_tests(
        command: str,
        dump_id: str | None = None,
        working_directory: str | None = None,
        timeout_seconds: int | None = None,
        user_confirmed: bool = False,
    ) -> dict[str, Any]:
        return _call_tool(
            backend,
            "run_tests",
            {
                "command": command,
                "dump_id": dump_id,
                "working_directory": working_directory,
                "timeout_seconds": timeout_seconds,
                "user_confirmed": user_confirmed,
            },
        )

    @app.resource("project://symbols/status")
    def project_symbols_status() -> dict[str, Any]:
        return _read_resource(backend, "project://symbols/status")

    @app.resource("project://source/root")
    def project_source_root() -> dict[str, Any]:
        return _read_resource(backend, "project://source/root")

    @app.resource("crash://{dump_id}/summary")
    def crash_summary(dump_id: str) -> dict[str, Any]:
        return _read_resource(backend, f"crash://{dump_id}/summary")

    @app.resource("crash://{dump_id}/exception")
    def crash_exception(dump_id: str) -> dict[str, Any]:
        return _read_resource(backend, f"crash://{dump_id}/exception")

    @app.resource("crash://{dump_id}/stack")
    def crash_stack(dump_id: str) -> dict[str, Any]:
        return _read_resource(backend, f"crash://{dump_id}/stack")

    @app.resource("crash://{dump_id}/modules")
    def crash_modules(dump_id: str) -> dict[str, Any]:
        return _read_resource(backend, f"crash://{dump_id}/modules")

    @app.resource("crash://{dump_id}/threads")
    def crash_threads(dump_id: str) -> dict[str, Any]:
        return _read_resource(backend, f"crash://{dump_id}/threads")

    @app.resource("crash://{dump_id}/warnings")
    def crash_warnings(dump_id: str) -> dict[str, Any]:
        return _read_resource(backend, f"crash://{dump_id}/warnings")

    @app.resource("crash://{dump_id}/source/main-frame")
    def crash_main_frame_source(dump_id: str) -> dict[str, Any]:
        return _read_resource(backend, f"crash://{dump_id}/source/main-frame")

    return app


def main() -> int:
    configure_logging()
    app = create_mcp_app()
    LOGGER.info("Starting MCP stdio server")
    app.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
