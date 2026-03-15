from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Any, Protocol

from .config import ServerConfig
from .errors import ErrorCode, ServerError
from .session_store import DumpSession

_EXCEPTION_PATTERN = re.compile(
    r"EXCEPTION_CODE:\s*(?:\(NTSTATUS\)\s*)?((?:0x)?[0-9a-fA-F]+)(?:\s*-\s*([A-Z0-9_]+))?"
)
_EXCEPTION_RECORD_PATTERN = re.compile(
    r"ExceptionCode:\s*((?:0x)?[0-9a-fA-F]+)\s*\(([^)]+)\)",
    re.IGNORECASE,
)
_EARLY_EXCEPTION_PATTERN = re.compile(
    r"\(([0-9a-fA-F]+)\.([0-9a-fA-F]+)\):\s*([^-]+)-\s*code\s*((?:0x)?[0-9a-fA-F]+)",
    re.IGNORECASE,
)
_THREAD_PATTERN = re.compile(r"FAULTING_THREAD:\s*(\d+)")
_THREAD_HEX_PATTERN = re.compile(r"FAULTING_THREAD:\s*([0-9a-fA-F]+)", re.IGNORECASE)
_FAULT_LINE_PATTERN = re.compile(
    r"(?P<symbol>[^\s\[]+)(?:\s+\[(?P<file>.+?)\s*@\s*(?P<line>\d+)\])?"
)
_STACK_LINE_PATTERN = re.compile(
    r"^\s*[0-9a-fA-F`]+\s+(?P<symbol>[^\s\[]+![^\s\[]+)(?:\s+\[(?P<file>.+?)\s*@\s*(?P<line>\d+)\])?"
)
_STACK_INDEX_LINE_PATTERN = re.compile(r"^\s*(?P<index>\d+)\s+[0-9a-fA-F`]+\s+[0-9a-fA-F`]+")
_STACK_COMPACT_PREFIX_PATTERN = re.compile(r"^\s*[0-9a-fA-F`]+\s+[0-9a-fA-F`]+\s+")
_SOURCE_LINE_PATTERN = re.compile(
    r"^(?P<file>[A-Za-z]:\\.+?)\((?P<line>\d+)\)\+0x[0-9a-fA-F]+$",
    re.IGNORECASE,
)
_MODULE_STATUS_PATTERN = re.compile(r"^(?P<module>.+?)\s*\|\s*(?P<status>\w+)\s*$")
_MODULE_LM_PATTERN = re.compile(
    r"^[0-9a-fA-F`]+\s+[0-9a-fA-F`]+\s+(?P<module>\S+)\s+\S+\s+\((?P<status>[^)]+)\)",
    re.IGNORECASE,
)
_SYMBOL_STATUS_PATTERN = re.compile(r"SYMBOL_STATUS:\s*(good|partial|poor|missing)")
_FAULT_ADDRESS_PATTERN = re.compile(r"FAULT_ADDRESS:\s*(0x[0-9a-fA-F]+)")
_EXCEPTION_ADDRESS_PATTERN = re.compile(r"ExceptionAddress:\s*([0-9a-fA-F`]+)", re.IGNORECASE)
_DUMP_TYPE_PATTERN = re.compile(r"DUMP_TYPE:\s*(\w+)")
_PROJECT_TYPE_PATTERN = re.compile(r"PROJECT_TYPE:\s*(\w+)")
_FAULT_SYMBOL_WITH_LINE_PATTERN = re.compile(
    r"(?P<symbol>[^\[]+![^\[]+?)\+(?:0x)?[0-9a-fA-F]+\s+\[(?P<file>.+?)\s*@\s*(?P<line>\d+)\]",
    re.IGNORECASE,
)
_FAULT_SYMBOL_PATTERN = re.compile(
    r"(?P<symbol>[^:\[]+![^:\[]+?)\+(?:0x)?[0-9a-fA-F]+:?",
    re.IGNORECASE,
)
_DEBUGGER_PROMPT_PATTERN = re.compile(r"^\s*\d+:\d+>\s*")
_THREAD_HEADER_PATTERN = re.compile(
    r"^\s*(?P<current>\.)?\s*(?P<index>\d+)\s+Id:\s*(?P<pid>[0-9a-fA-F]+)\.(?P<tid>[0-9a-fA-F]+)\s+Suspend:\s*(?P<suspend>\d+)\s+Teb:\s*(?P<teb>[0-9a-fA-F`]+)\s*(?P<state>.*)$",
    re.IGNORECASE,
)
_THREAD_LIST_BEGIN = "DUMP_MCP_BEGIN_THREAD_LIST"
_THREAD_LIST_END = "DUMP_MCP_END_THREAD_LIST"
_ALL_THREAD_STACK_BEGIN = "DUMP_MCP_BEGIN_ALL_THREADS_STACK"
_ALL_THREAD_STACK_END = "DUMP_MCP_END_ALL_THREADS_STACK"
_RUNAWAY_BEGIN = "DUMP_MCP_BEGIN_RUNAWAY"
_RUNAWAY_END = "DUMP_MCP_END_RUNAWAY"
_RUNAWAY_LINE_PATTERN = re.compile(
    r"^\s*(?P<index>\d+):(?P<tid>[0-9a-fA-F]+)\s+(?P<days>\d+)\s+days\s+(?P<hours>\d+):(?P<minutes>\d+):(?P<seconds>\d+)\.(?P<millis>\d+)",
    re.IGNORECASE,
)


class DebuggerRunner(Protocol):
    def run(
        self,
        *,
        dump_path: str,
        symbol_root: str,
        source_root: str,
        binary_root: str | None,
    ) -> str: ...


class CdbDebuggerRunner:
    def __init__(self, config: ServerConfig):
        self._config = config

    def run(
        self,
        *,
        dump_path: str,
        symbol_root: str,
        source_root: str,
        binary_root: str | None,
    ) -> str:
        script_parts = [
            f'.sympath "{symbol_root}"',
            f'.srcpath "{source_root}"',
        ]
        if binary_root:
            script_parts.append(f'.exepath "{binary_root}"')
        script_parts.extend(
            [
                ".lines",
                "!analyze -v",
                ".ecxr",
                ".echo DUMP_MCP_BEGIN_THREAD_LIST",
                "~",
                ".echo DUMP_MCP_END_THREAD_LIST",
                "kL 64",
                ".echo DUMP_MCP_BEGIN_ALL_THREADS_STACK",
                "~* kL 64",
                ".echo DUMP_MCP_END_ALL_THREADS_STACK",
                ".echo DUMP_MCP_BEGIN_RUNAWAY",
                "!runaway",
                ".echo DUMP_MCP_END_RUNAWAY",
                ".exr -1",
                "lm",
                "q",
            ]
        )
        script = "; ".join(script_parts)

        try:
            completed = subprocess.run(
                [self._config.cdb_command(), "-z", dump_path, "-c", script],
                capture_output=True,
                text=True,
                timeout=self._config.analyze_timeout_seconds,
                check=False,
            )
        except Exception as exc:
            raise ServerError(
                ErrorCode.DEBUGGER_INVOCATION_FAILED,
                "Failed to invoke debugger.",
                {"exception": type(exc).__name__, "message": str(exc)},
            ) from exc

        output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
        if completed.returncode != 0 and not output.strip():
            raise ServerError(
                ErrorCode.DEBUGGER_INVOCATION_FAILED,
                "Debugger exited with non-zero status.",
                {"return_code": completed.returncode},
            )
        return output


@dataclass(frozen=True)
class ParsedSymbol:
    raw_symbol: str
    module: str
    function: str


def _exception_name_from_text(text: str) -> str:
    normalized = text.strip().lower()
    mapping = {
        "access violation": "EXCEPTION_ACCESS_VIOLATION",
        "stack overflow": "EXCEPTION_STACK_OVERFLOW",
        "illegal instruction": "EXCEPTION_ILLEGAL_INSTRUCTION",
    }
    return mapping.get(normalized, "UNKNOWN_EXCEPTION")


def _normalize_exception_code(value: str) -> str:
    stripped = value.lower().removeprefix("0x")
    return f"0x{stripped.upper().zfill(8)}"


def _fault_type(exception_name: str) -> str:
    mapping = {
        "EXCEPTION_ACCESS_VIOLATION": "access_violation",
        "EXCEPTION_STACK_OVERFLOW": "stack_overflow",
        "EXCEPTION_ILLEGAL_INSTRUCTION": "illegal_instruction",
    }
    return mapping.get(exception_name, "unknown")


def _parse_symbol(raw_symbol: str) -> ParsedSymbol:
    symbol = raw_symbol.strip()
    if "!" not in symbol:
        return ParsedSymbol(raw_symbol=symbol, module="unknown", function=symbol)
    module, fn = symbol.split("!", 1)
    function = fn.split("+", 1)[0]
    return ParsedSymbol(raw_symbol=symbol, module=module, function=function)


def _extract_section(lines: list[str], header: str) -> list[str]:
    target = f"{header}:"
    start_index = -1
    for idx, line in enumerate(lines):
        if line.strip() == target:
            start_index = idx + 1
            break
    if start_index < 0:
        return []

    collected: list[str] = []
    for line in lines[start_index:]:
        stripped = line.strip()
        if stripped.endswith(":") and stripped.isupper():
            break
        if not stripped and collected:
            break
        if stripped:
            collected.append(line)
    return collected


def _normalize_module_symbol_status(raw_status: str) -> str:
    status = raw_status.strip().lower()
    if "private pdb" in status or "symbols" in status and "no symbols" not in status:
        return "good"
    if "export symbols" in status or "partial" in status:
        return "partial"
    if "deferred" in status or "no symbols" in status:
        return "missing"
    return "unknown"


def _strip_debugger_prompt(line: str) -> str:
    return _DEBUGGER_PROMPT_PATTERN.sub("", line)


def _extract_marked_section(lines: list[str], begin_marker: str, end_marker: str) -> list[str]:
    start = -1
    for idx, line in enumerate(lines):
        if _strip_debugger_prompt(line).strip() == begin_marker:
            start = idx + 1
            break
    if start < 0:
        return []

    collected: list[str] = []
    for line in lines[start:]:
        if _strip_debugger_prompt(line).strip() == end_marker:
            break
        collected.append(line)
    return collected


def _parse_stack_frames_from_lines(lines: list[str]) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for line in lines:
        stripped = _strip_debugger_prompt(line).strip()
        if not stripped:
            continue

        source_match = _SOURCE_LINE_PATTERN.match(stripped)
        if source_match and frames and not frames[-1]["file"]:
            frames[-1]["file"] = source_match.group("file")
            frames[-1]["line"] = int(source_match.group("line"))
            continue

        match = _STACK_INDEX_LINE_PATTERN.match(stripped)
        if match and " : " in stripped:
            call_site = stripped.rsplit(" : ", 1)[-1].strip()
            if "!" not in call_site:
                continue
            parsed = _parse_symbol(call_site)
            frames.append(
                {
                    "index": len(frames),
                    "module": parsed.module,
                    "function": parsed.function,
                    "file": "",
                    "line": 0,
                    "address": "",
                }
            )
            continue

        match = _STACK_LINE_PATTERN.match(stripped)
        if match:
            parsed = _parse_symbol(match.group("symbol"))
            frames.append(
                {
                    "index": len(frames),
                    "module": parsed.module,
                    "function": parsed.function,
                    "file": match.group("file") or "",
                    "line": int(match.group("line")) if match.group("line") else 0,
                    "address": "",
                }
            )
            continue

        match = _STACK_COMPACT_PREFIX_PATTERN.match(stripped)
        if match:
            symbol_text = stripped[match.end() :].strip()
            if "!" not in symbol_text:
                continue
            parsed = _parse_symbol(symbol_text)
            frames.append(
                {
                    "index": len(frames),
                    "module": parsed.module,
                    "function": parsed.function,
                    "file": "",
                    "line": 0,
                    "address": "",
                }
            )

    return frames


def _parse_thread_headers(lines: list[str]) -> dict[int, dict[str, Any]]:
    threads: dict[int, dict[str, Any]] = {}
    for line in lines:
        stripped = _strip_debugger_prompt(line).strip()
        match = _THREAD_HEADER_PATTERN.match(stripped)
        if not match:
            continue
        idx = int(match.group("index"))
        tid_hex = match.group("tid").upper()
        state_text = (match.group("state") or "").strip()
        threads[idx] = {
            "thread_id": idx,
            "os_thread_id": int(tid_hex, 16),
            "os_thread_id_hex": f"0x{tid_hex}",
            "is_current": bool(match.group("current")),
            "is_faulting": False,
            "state_hint": state_text or "unknown",
            "stack_frames": [],
            "top_frame": None,
            "cpu_user_time_seconds": None,
            "cpu_user_time_text": None,
        }
    return threads


def _parse_threads_with_stack(
    stack_lines: list[str],
    thread_index: dict[int, dict[str, Any]],
) -> None:
    current_idx: int | None = None
    bucket: dict[int, list[str]] = {}

    for line in stack_lines:
        stripped = _strip_debugger_prompt(line).strip()
        header = _THREAD_HEADER_PATTERN.match(stripped)
        if header:
            current_idx = int(header.group("index"))
            if current_idx not in thread_index:
                tid_hex = header.group("tid").upper()
                thread_index[current_idx] = {
                    "thread_id": current_idx,
                    "os_thread_id": int(tid_hex, 16),
                    "os_thread_id_hex": f"0x{tid_hex}",
                    "is_current": bool(header.group("current")),
                    "is_faulting": False,
                    "state_hint": (header.group("state") or "").strip() or "unknown",
                    "stack_frames": [],
                    "top_frame": None,
                    "cpu_user_time_seconds": None,
                    "cpu_user_time_text": None,
                }
            bucket.setdefault(current_idx, [])
            continue

        if current_idx is None:
            continue
        bucket.setdefault(current_idx, []).append(line)

    for idx, raw_lines in bucket.items():
        parsed = _parse_stack_frames_from_lines(raw_lines)
        if not parsed:
            continue
        thread = thread_index[idx]
        thread["stack_frames"] = parsed
        thread["top_frame"] = parsed[0]


def _thread_list_sorted(thread_index: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    return [thread_index[key] for key in sorted(thread_index.keys())]


def _parse_runaway_times(lines: list[str]) -> dict[int, dict[str, Any]]:
    parsed: dict[int, dict[str, Any]] = {}
    for line in lines:
        stripped = _strip_debugger_prompt(line).strip()
        match = _RUNAWAY_LINE_PATTERN.match(stripped)
        if not match:
            continue
        idx = int(match.group("index"))
        days = int(match.group("days"))
        hours = int(match.group("hours"))
        minutes = int(match.group("minutes"))
        seconds = int(match.group("seconds"))
        millis = int(match.group("millis"))
        total_seconds = (
            days * 24 * 60 * 60
            + hours * 60 * 60
            + minutes * 60
            + seconds
            + (millis / (10 ** len(match.group("millis"))))
        )
        parsed[idx] = {
            "cpu_user_time_seconds": round(total_seconds, 6),
            "cpu_user_time_text": (
                f"{days} days {hours:02d}:{minutes:02d}:{seconds:02d}.{match.group('millis')}"
            ),
        }
    return parsed


def _infer_faulting_thread(
    *,
    parsed_threads: list[dict[str, Any]],
    parsed_faulting_thread: int,
    early_exception_tid: int | None,
    fallback_stack_frames: list[dict[str, Any]],
) -> tuple[int, str]:
    if not parsed_threads:
        return parsed_faulting_thread, "low"

    by_index = {item["thread_id"]: item for item in parsed_threads}
    if early_exception_tid is not None:
        for item in parsed_threads:
            if item.get("os_thread_id") == early_exception_tid:
                return item["thread_id"], "high"

    if parsed_faulting_thread in by_index:
        return parsed_faulting_thread, "medium"

    for item in parsed_threads:
        if item.get("is_current"):
            return item["thread_id"], "medium"

    fallback_top = fallback_stack_frames[0]["function"] if fallback_stack_frames else ""
    if fallback_top:
        for item in parsed_threads:
            top = item.get("top_frame") or {}
            if top.get("function") == fallback_top:
                return item["thread_id"], "medium"

    return parsed_threads[0]["thread_id"], "low"


def _infer_suspected_patterns(
    *,
    exception_name: str,
    threads: list[dict[str, Any]],
    crashing_thread: int,
) -> list[str]:
    if exception_name != "EXCEPTION_ACCESS_VIOLATION" or not threads:
        return []

    by_index = {item["thread_id"]: item for item in threads}
    faulting = by_index.get(crashing_thread)
    if not faulting:
        return []

    patterns: list[str] = []
    fault_functions = [str(frame.get("function", "")) for frame in faulting.get("stack_frames", [])]
    other_functions: list[str] = []
    for item in threads:
        if item["thread_id"] == crashing_thread:
            continue
        other_functions.extend(
            [str(frame.get("function", "")) for frame in item.get("stack_frames", [])[:8]]
        )

    has_worker_shape = any(
        "std::thread" in fn or "BaseThreadInitThunk" in fn or "SubThread" in fn
        for fn in fault_functions
    )
    has_main_activity_elsewhere = any(fn == "main" or fn.endswith("::Run") for fn in other_functions)
    has_consume_process_style = any(
        "Consume" in fn or "Process" in fn or "Fetch" in fn for fn in fault_functions
    )

    if has_worker_shape and has_main_activity_elsewhere:
        patterns.append("main_alive_worker_crashed")
    if has_worker_shape and len(threads) > 1:
        patterns.append("use_after_free_cross_thread")
    if has_consume_process_style and len(threads) > 1:
        patterns.append("shared_raw_pointer_without_lifetime")

    return patterns


def parse_analysis_output(raw_output: str, *, fallback_project_type: str) -> dict[str, Any]:
    lines = raw_output.splitlines()

    exception_code = "0x00000000"
    exception_name = "UNKNOWN_EXCEPTION"
    early_exception_tid: int | None = None
    exception_match = _EXCEPTION_PATTERN.search(raw_output)
    if exception_match:
        exception_code = _normalize_exception_code(exception_match.group(1))
        if exception_match.group(2):
            exception_name = exception_match.group(2)
    else:
        exception_record_match = _EXCEPTION_RECORD_PATTERN.search(raw_output)
        if exception_record_match:
            exception_code = _normalize_exception_code(exception_record_match.group(1))
            exception_name = _exception_name_from_text(exception_record_match.group(2))
        else:
            early_match = _EARLY_EXCEPTION_PATTERN.search(raw_output)
            if early_match:
                exception_code = _normalize_exception_code(early_match.group(4))
                exception_name = _exception_name_from_text(early_match.group(3))
                early_exception_tid = int(early_match.group(2), 16)

    thread_id = 0
    thread_match = _THREAD_PATTERN.search(raw_output)
    if thread_match:
        thread_id = int(thread_match.group(1))
    else:
        thread_hex_match = _THREAD_HEX_PATTERN.search(raw_output)
        if thread_hex_match:
            value = thread_hex_match.group(1).lower()
            if value != "ffffffff":
                thread_id = int(value, 16)
        else:
            if early_exception_tid is not None:
                thread_id = early_exception_tid

    fault_address = "unknown"
    fault_address_match = _FAULT_ADDRESS_PATTERN.search(raw_output)
    if fault_address_match:
        fault_address = fault_address_match.group(1)
    else:
        exception_address_match = _EXCEPTION_ADDRESS_PATTERN.search(raw_output)
        if exception_address_match:
            raw_value = exception_address_match.group(1).replace("`", "")
            fault_address = f"0x{raw_value.upper()}"

    dump_type = "unknown"
    dump_type_match = _DUMP_TYPE_PATTERN.search(raw_output)
    if dump_type_match:
        dump_type = dump_type_match.group(1).lower()

    project_type = fallback_project_type
    project_type_match = _PROJECT_TYPE_PATTERN.search(raw_output)
    if project_type_match:
        project_type = project_type_match.group(1)

    fault_module = "unknown"
    fault_function = "unknown"
    source_file = "unknown"
    source_line = 0
    for line in lines:
        match = _FAULT_SYMBOL_WITH_LINE_PATTERN.search(line.strip())
        if not match:
            continue
        parsed = _parse_symbol(match.group("symbol"))
        fault_module = parsed.module
        fault_function = parsed.function
        source_file = match.group("file")
        source_line = int(match.group("line"))
        break

    if fault_module == "unknown":
        for line in lines:
            match = _FAULT_SYMBOL_PATTERN.search(line.strip())
            if not match:
                continue
            parsed = _parse_symbol(match.group("symbol"))
            fault_module = parsed.module
            fault_function = parsed.function
            break

    for line in _extract_section(lines, "FAULTING_IP"):
        match = _FAULT_LINE_PATTERN.search(line.strip())
        if not match:
            continue
        parsed = _parse_symbol(match.group("symbol"))
        fault_module = parsed.module
        fault_function = parsed.function
        if match.group("file"):
            source_file = match.group("file")
        if match.group("line"):
            source_line = int(match.group("line"))
        break

    stack_frames = _parse_stack_frames_from_lines(lines)
    if not stack_frames:
        stack_frames = _parse_stack_frames_from_lines(_extract_section(lines, "STACK_TEXT"))

    thread_list_section = _extract_marked_section(lines, _THREAD_LIST_BEGIN, _THREAD_LIST_END)
    all_thread_stack_section = _extract_marked_section(
        lines,
        _ALL_THREAD_STACK_BEGIN,
        _ALL_THREAD_STACK_END,
    )
    thread_index = _parse_thread_headers(thread_list_section)
    if all_thread_stack_section:
        _parse_threads_with_stack(all_thread_stack_section, thread_index)
    parsed_threads = _thread_list_sorted(thread_index)
    runaway_section = _extract_marked_section(lines, _RUNAWAY_BEGIN, _RUNAWAY_END)
    runaway_times = _parse_runaway_times(runaway_section)
    if runaway_times:
        for thread in parsed_threads:
            metrics = runaway_times.get(int(thread["thread_id"]))
            if metrics:
                thread.update(metrics)

    crashing_thread, faulting_thread_confidence = _infer_faulting_thread(
        parsed_threads=parsed_threads,
        parsed_faulting_thread=thread_id,
        early_exception_tid=early_exception_tid,
        fallback_stack_frames=stack_frames,
    )

    if parsed_threads:
        for thread in parsed_threads:
            thread["is_faulting"] = thread["thread_id"] == crashing_thread
        selected = next((t for t in parsed_threads if t["thread_id"] == crashing_thread), None)
        if selected and selected.get("stack_frames"):
            stack_frames = selected["stack_frames"]
        elif not selected and parsed_threads[0].get("stack_frames"):
            stack_frames = parsed_threads[0]["stack_frames"]
    else:
        parsed_threads = [
            {
                "thread_id": crashing_thread,
                "os_thread_id": crashing_thread,
                "os_thread_id_hex": f"0x{crashing_thread:X}",
                "is_current": True,
                "is_faulting": True,
                "state_hint": "unknown",
                "stack_frames": stack_frames,
                "top_frame": stack_frames[0] if stack_frames else None,
                "cpu_user_time_seconds": None,
                "cpu_user_time_text": None,
            }
        ]
        faulting_thread_confidence = "low"

    if source_file == "unknown":
        for frame in stack_frames:
            if frame["file"] and frame["line"] > 0:
                source_file = frame["file"]
                source_line = frame["line"]
                break

    loaded_modules: list[dict[str, str]] = []
    for line in _extract_section(lines, "LOADED_MODULES"):
        m = _MODULE_STATUS_PATTERN.match(line.strip())
        if not m:
            continue
        loaded_modules.append(
            {"module": m.group("module").strip(), "symbol_status": m.group("status").lower()}
        )
    if not loaded_modules:
        for line in lines:
            m = _MODULE_LM_PATTERN.match(line.strip())
            if not m:
                continue
            loaded_modules.append(
                {
                    "module": m.group("module").strip(),
                    "symbol_status": _normalize_module_symbol_status(m.group("status")),
                }
            )

    symbol_quality = "missing"
    symbol_match = _SYMBOL_STATUS_PATTERN.search(raw_output)
    if symbol_match:
        symbol_quality = symbol_match.group(1).lower()
    elif loaded_modules:
        statuses = {item["symbol_status"] for item in loaded_modules}
        if "poor" in statuses or "missing" in statuses:
            symbol_quality = "poor"
        elif "partial" in statuses:
            symbol_quality = "partial"
        else:
            symbol_quality = "good"
    elif "private pdb symbols" in raw_output.lower():
        symbol_quality = "good"
    elif "symbol loading error summary" in raw_output.lower():
        symbol_quality = "missing"

    warnings: list[str] = []
    if "symbol loading error summary" in raw_output.lower():
        warnings.append("symbol_loading_errors_detected")
    if source_file == "unknown":
        warnings.append("source_line_unresolved")
    if len(parsed_threads) > 1:
        warnings.append("multi_thread_dump_detected")

    suspected_patterns = _infer_suspected_patterns(
        exception_name=exception_name,
        threads=parsed_threads,
        crashing_thread=crashing_thread,
    )

    return {
        "dump_type": dump_type,
        "project_type": project_type,
        "exception_code": exception_code,
        "exception_name": exception_name,
        "fault_type": _fault_type(exception_name),
        "fault_address": fault_address,
        "fault_module": fault_module,
        "fault_function": fault_function,
        "source_location": {"file": source_file, "line": source_line},
        "crashing_thread": crashing_thread,
        "faulting_thread_confidence": faulting_thread_confidence,
        "thread_count": len(parsed_threads),
        "threads": parsed_threads,
        "stack_frames": stack_frames,
        "registers": {},
        "loaded_modules": loaded_modules,
        "symbol_quality": symbol_quality,
        "warnings": warnings,
        "suspected_patterns": suspected_patterns,
    }


class DumpAnalyzerCore:
    def __init__(self, config: ServerConfig, runner: DebuggerRunner | None = None):
        self._config = config
        self._runner = runner or CdbDebuggerRunner(config)

    def analyze(self, session: DumpSession) -> dict[str, Any]:
        try:
            raw = self._runner.run(
                dump_path=session.dump_path,
                symbol_root=session.symbol_root,
                source_root=session.source_root,
                binary_root=session.binary_root,
            )
        except ServerError:
            raise
        except Exception as exc:
            raise ServerError(
                ErrorCode.DEBUGGER_INVOCATION_FAILED,
                "Debugger invocation failed.",
                {"exception": type(exc).__name__, "message": str(exc)},
            ) from exc

        normalized = parse_analysis_output(raw, fallback_project_type=session.project_type)
        normalized["dump_id"] = session.dump_id
        return normalized
