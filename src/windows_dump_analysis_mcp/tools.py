from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .analyzer import DumpAnalyzerCore
from .code_context import CodeContextProvider
from .config import ServerConfig
from .errors import (
    ErrorCode,
    ServerError,
    ToolNotImplementedError,
    UnknownToolError,
    ValidationError,
)
from .execution import BuildTestExecutor
from .patching import PatchChange, PatchExecutor
from .session_store import DumpSessionStore, ensure_existing_dir, ensure_existing_file


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class ToolContext:
    config: ServerConfig
    session_store: DumpSessionStore
    analyzer: DumpAnalyzerCore
    code_context: CodeContextProvider
    patch_executor: PatchExecutor
    build_test_executor: BuildTestExecutor


class ToolRegistry:
    def __init__(self, ctx: ToolContext):
        self._ctx = ctx
        self._analysis_cache: dict[str, dict[str, Any]] = {}
        self._handlers: dict[str, ToolHandler] = {
            "register_dump": self._register_dump,
            "analyze_dump": self._analyze_dump,
            "get_exception_info": self._get_exception_info,
            "get_stack_trace": self._get_stack_trace,
            "get_module_list": self._get_module_list,
            "get_source_context": self._get_source_context,
            "search_code_references": self._search_code_references,
            "apply_patch": self._apply_patch,
            "build_project": self._build_project,
            "run_tests": self._run_tests,
        }

    def list_tool_names(self) -> list[str]:
        return sorted(self._handlers.keys())

    def list_resource_uris(self) -> list[str]:
        uris = [
            "project://symbols/status",
            "project://source/root",
        ]
        for session in self._ctx.session_store.list():
            dump_id = session.dump_id
            uris.extend(
                [
                    f"crash://{dump_id}/summary",
                    f"crash://{dump_id}/exception",
                    f"crash://{dump_id}/stack",
                    f"crash://{dump_id}/modules",
                    f"crash://{dump_id}/warnings",
                    f"crash://{dump_id}/source/main-frame",
                ]
            )
        return uris

    def read_resource(self, uri: str) -> dict[str, Any]:
        if uri == "project://source/root":
            return {
                "uri": uri,
                "contents": {
                    "sessions": [
                        {"dump_id": s.dump_id, "source_root": s.source_root}
                        for s in self._ctx.session_store.list()
                    ]
                },
            }

        if uri == "project://symbols/status":
            rows: list[dict[str, Any]] = []
            for session in self._ctx.session_store.list():
                try:
                    analyzed = self._get_or_analyze(session.dump_id)
                    rows.append(
                        {
                            "dump_id": session.dump_id,
                            "symbol_quality": analyzed["symbol_quality"],
                        }
                    )
                except ServerError as err:
                    rows.append(
                        {
                            "dump_id": session.dump_id,
                            "symbol_quality": "unknown",
                            "error": err.to_dict()["error"],
                        }
                    )
            return {"uri": uri, "contents": {"sessions": rows}}

        if not uri.startswith("crash://"):
            raise ValidationError("Unsupported resource URI.", {"uri": uri})

        rest = uri.removeprefix("crash://")
        if "/" not in rest:
            raise ValidationError("Invalid crash resource URI.", {"uri": uri})
        dump_id, view = rest.split("/", 1)
        analyzed = self._get_or_analyze(dump_id)

        if view == "summary":
            return {
                "uri": uri,
                "contents": {
                    "dump_id": dump_id,
                    "dump_type": analyzed["dump_type"],
                    "project_type": analyzed["project_type"],
                    "exception_code": analyzed["exception_code"],
                    "exception_name": analyzed["exception_name"],
                    "fault_module": analyzed["fault_module"],
                    "fault_function": analyzed["fault_function"],
                    "source_location": analyzed["source_location"],
                    "symbol_quality": analyzed["symbol_quality"],
                    "warnings": analyzed["warnings"],
                },
            }
        if view == "exception":
            return {
                "uri": uri,
                "contents": {
                    "dump_id": dump_id,
                    "exception_code": analyzed["exception_code"],
                    "exception_name": analyzed["exception_name"],
                    "fault_type": analyzed["fault_type"],
                    "fault_address": analyzed["fault_address"],
                    "fault_module": analyzed["fault_module"],
                    "fault_function": analyzed["fault_function"],
                },
            }
        if view == "stack":
            return {
                "uri": uri,
                "contents": {
                    "dump_id": dump_id,
                    "crashing_thread": analyzed["crashing_thread"],
                    "stack_frames": analyzed["stack_frames"],
                },
            }
        if view == "modules":
            return {
                "uri": uri,
                "contents": {
                    "dump_id": dump_id,
                    "loaded_modules": analyzed["loaded_modules"],
                    "symbol_quality": analyzed["symbol_quality"],
                },
            }
        if view == "warnings":
            return {
                "uri": uri,
                "contents": {
                    "dump_id": dump_id,
                    "warnings": analyzed["warnings"],
                    "suspected_patterns": analyzed["suspected_patterns"],
                },
            }
        if view == "source/main-frame":
            session = self._ctx.session_store.get(dump_id)
            source_location = analyzed["source_location"]
            payload = self._ctx.code_context.get_source_context(
                source_root=session.source_root,
                source_file=source_location["file"],
                focus_line=int(source_location["line"]),
                context_before=20,
                context_after=20,
            )
            return {"uri": uri, "contents": payload}

        raise ValidationError("Unsupported crash resource view.", {"uri": uri, "view": view})

    def call(self, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
        handler = self._handlers.get(name)
        if handler is None:
            raise UnknownToolError(name)
        return handler(arguments or {})

    def _register_dump(self, args: dict[str, Any]) -> dict[str, Any]:
        required = ["dump_path", "symbol_root", "source_root", "project_type"]
        missing = [key for key in required if not args.get(key)]
        if missing:
            raise ValidationError(
                "register_dump requires mandatory fields.",
                {"missing_fields": missing},
            )

        dump_path = str(args["dump_path"])
        symbol_root = str(args["symbol_root"])
        source_root = str(args["source_root"])
        project_type = str(args["project_type"])
        binary_root = str(args["binary_root"]) if args.get("binary_root") else None
        dump_type_hint = str(args.get("dump_type_hint", "auto"))
        log_paths = [str(item) for item in args.get("log_paths", [])]

        if project_type not in {"native_cpp", "unreal_engine"}:
            raise ValidationError(
                "project_type must be one of: native_cpp, unreal_engine.",
                {"project_type": project_type},
            )

        ensure_existing_file(dump_path, ErrorCode.DUMP_FILE_NOT_FOUND)
        ensure_existing_dir(symbol_root, ErrorCode.SYMBOL_PATH_INVALID)
        ensure_existing_dir(source_root, ErrorCode.SOURCE_ROOT_INVALID)
        if binary_root:
            ensure_existing_dir(binary_root, ErrorCode.INVALID_PATH)
        for log_path in log_paths:
            ensure_existing_file(log_path, ErrorCode.INVALID_PATH)

        session = self._ctx.session_store.create(
            dump_path=dump_path,
            symbol_root=symbol_root,
            source_root=source_root,
            binary_root=binary_root,
            project_type=project_type,
            dump_type_hint=dump_type_hint,
            log_paths=log_paths,
        )
        return {"ok": True, "dump_id": session.dump_id, "status": "registered"}

    def _require_dump_id(self, args: dict[str, Any]) -> str:
        dump_id = args.get("dump_id")
        if not isinstance(dump_id, str) or not dump_id.strip():
            raise ValidationError("Tool requires 'dump_id'.")
        return dump_id

    def _get_or_analyze(self, dump_id: str) -> dict[str, Any]:
        cached = self._analysis_cache.get(dump_id)
        if cached:
            return cached
        session = self._ctx.session_store.get(dump_id)
        analyzed = self._ctx.analyzer.analyze(session)
        self._analysis_cache[dump_id] = analyzed
        return analyzed

    def _analyze_dump(self, args: dict[str, Any]) -> dict[str, Any]:
        dump_id = self._require_dump_id(args)
        analyzed = self._get_or_analyze(dump_id)
        return {"ok": True, **analyzed}

    def _get_exception_info(self, args: dict[str, Any]) -> dict[str, Any]:
        dump_id = self._require_dump_id(args)
        analyzed = self._get_or_analyze(dump_id)
        return {
            "ok": True,
            "dump_id": dump_id,
            "exception_code": analyzed["exception_code"],
            "exception_name": analyzed["exception_name"],
            "fault_address": analyzed["fault_address"],
            "fault_type": analyzed["fault_type"],
        }

    def _get_stack_trace(self, args: dict[str, Any]) -> dict[str, Any]:
        dump_id = self._require_dump_id(args)
        analyzed = self._get_or_analyze(dump_id)

        max_frames_value = args.get("max_frames", 30)
        try:
            max_frames = int(max_frames_value)
        except (TypeError, ValueError):
            raise ValidationError("max_frames must be an integer.")
        if max_frames <= 0:
            raise ValidationError("max_frames must be positive.")

        raw_thread_id = args.get("thread_id")
        if raw_thread_id is None:
            thread_id = int(analyzed["crashing_thread"])
        else:
            try:
                thread_id = int(raw_thread_id)
            except (TypeError, ValueError):
                raise ValidationError("thread_id must be an integer.")
        frames = analyzed["stack_frames"][:max_frames]
        return {
            "ok": True,
            "dump_id": dump_id,
            "thread_id": thread_id,
            "stack_frames": frames,
        }

    def _get_module_list(self, args: dict[str, Any]) -> dict[str, Any]:
        dump_id = self._require_dump_id(args)
        analyzed = self._get_or_analyze(dump_id)
        return {
            "ok": True,
            "dump_id": dump_id,
            "symbol_quality": analyzed["symbol_quality"],
            "loaded_modules": analyzed["loaded_modules"],
        }

    def _get_source_context(self, args: dict[str, Any]) -> dict[str, Any]:
        dump_id = self._require_dump_id(args)
        analyzed = self._get_or_analyze(dump_id)
        session = self._ctx.session_store.get(dump_id)

        frame_index = int(args.get("frame_index", 0))
        context_before = int(args.get("context_before", 20))
        context_after = int(args.get("context_after", 20))
        if frame_index < 0:
            raise ValidationError("frame_index must be >= 0.")

        frames = analyzed["stack_frames"]
        if frame_index >= len(frames):
            raise ValidationError(
                "frame_index is out of range.",
                {"frame_index": frame_index, "stack_size": len(frames)},
            )

        frame = frames[frame_index]
        source_file = frame.get("file") or analyzed["source_location"]["file"]
        source_line = int(frame.get("line") or analyzed["source_location"]["line"] or 0)
        if not source_file or source_file == "unknown":
            raise ServerError(
                ErrorCode.SOURCE_MAPPING_FAILED,
                "No source file is mapped to requested frame.",
                {"dump_id": dump_id, "frame_index": frame_index},
            )

        payload = self._ctx.code_context.get_source_context(
            source_root=session.source_root,
            source_file=source_file,
            focus_line=source_line,
            context_before=context_before,
            context_after=context_after,
        )
        return {"ok": True, "dump_id": dump_id, "frame_index": frame_index, **payload}

    def _search_code_references(self, args: dict[str, Any]) -> dict[str, Any]:
        query = args.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValidationError("search_code_references requires non-empty 'query'.")

        dump_id = args.get("dump_id")
        source_root = args.get("source_root")
        if source_root:
            source_root = str(source_root)
            ensure_existing_dir(source_root, ErrorCode.SOURCE_ROOT_INVALID)
        elif dump_id:
            dump_id = str(dump_id)
            source_root = self._ctx.session_store.get(dump_id).source_root
        else:
            raise ValidationError(
                "search_code_references requires either 'source_root' or 'dump_id'."
            )

        max_results = int(args.get("max_results", 50))
        ignore_case = bool(args.get("ignore_case", False))
        results = self._ctx.code_context.search_code_references(
            source_root=source_root,
            query=query,
            max_results=max_results,
            ignore_case=ignore_case,
        )
        return {
            "ok": True,
            "dump_id": dump_id,
            "source_root": source_root,
            "query": query,
            "count": len(results),
            "results": results,
        }

    def _apply_patch(self, args: dict[str, Any]) -> dict[str, Any]:
        source_root: str | None = None
        dump_id = args.get("dump_id")
        if dump_id:
            source_root = self._ctx.session_store.get(str(dump_id)).source_root
        elif args.get("source_root"):
            source_root = str(args["source_root"])
            ensure_existing_dir(source_root, ErrorCode.SOURCE_ROOT_INVALID)
        else:
            raise ValidationError("apply_patch requires either 'dump_id' or 'source_root'.")

        raw_changes = args.get("changes")
        if not isinstance(raw_changes, list) or not raw_changes:
            raise ValidationError("apply_patch requires non-empty 'changes' list.")

        changes: list[PatchChange] = []
        for idx, item in enumerate(raw_changes):
            if not isinstance(item, dict):
                raise ValidationError("Each change must be an object.", {"index": idx})
            path = item.get("path")
            content = item.get("content")
            if not isinstance(path, str) or not path.strip():
                raise ValidationError("Change 'path' must be non-empty string.", {"index": idx})
            if not isinstance(content, str):
                raise ValidationError("Change 'content' must be string.", {"index": idx})
            changes.append(PatchChange(path=path, content=content))

        mode = str(args.get("mode", "preview")).lower()
        user_confirmed = bool(args.get("user_confirmed", False))
        return self._ctx.patch_executor.apply_patch(
            source_root=source_root,
            changes=changes,
            mode=mode,
            user_confirmed=user_confirmed,
        )

    def _resolve_working_directory(
        self, *, dump_id: str | None, working_directory: str | None
    ) -> str | None:
        if working_directory:
            ensure_existing_dir(working_directory, ErrorCode.INVALID_PATH)
            return working_directory
        if dump_id:
            return self._ctx.session_store.get(dump_id).source_root
        return None

    def _build_project(self, args: dict[str, Any]) -> dict[str, Any]:
        command = args.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValidationError("build_project requires non-empty 'command'.")
        dump_id = str(args.get("dump_id")) if args.get("dump_id") else None
        working_directory = (
            str(args.get("working_directory")) if args.get("working_directory") else None
        )
        timeout_seconds = int(args["timeout_seconds"]) if args.get("timeout_seconds") else None
        user_confirmed = bool(args.get("user_confirmed", False))
        return self._ctx.build_test_executor.run_build(
            command=command,
            user_confirmed=user_confirmed,
            working_directory=self._resolve_working_directory(
                dump_id=dump_id, working_directory=working_directory
            ),
            timeout_seconds=timeout_seconds,
        )

    def _run_tests(self, args: dict[str, Any]) -> dict[str, Any]:
        command = args.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValidationError("run_tests requires non-empty 'command'.")
        dump_id = str(args.get("dump_id")) if args.get("dump_id") else None
        working_directory = (
            str(args.get("working_directory")) if args.get("working_directory") else None
        )
        timeout_seconds = int(args["timeout_seconds"]) if args.get("timeout_seconds") else None
        user_confirmed = bool(args.get("user_confirmed", False))
        return self._ctx.build_test_executor.run_tests(
            command=command,
            user_confirmed=user_confirmed,
            working_directory=self._resolve_working_directory(
                dump_id=dump_id, working_directory=working_directory
            ),
            timeout_seconds=timeout_seconds,
        )

    def _make_stub(self, tool_name: str) -> ToolHandler:
        def _stub(args: dict[str, Any]) -> dict[str, Any]:
            _ = args
            raise ToolNotImplementedError(tool_name)

        return _stub
