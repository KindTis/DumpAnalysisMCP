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
                "kL 64",
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


def _parse_stack_frames_from_lines(lines: list[str]) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for line in lines:
        stripped = line.strip()
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


def parse_analysis_output(raw_output: str, *, fallback_project_type: str) -> dict[str, Any]:
    lines = raw_output.splitlines()

    exception_code = "0x00000000"
    exception_name = "UNKNOWN_EXCEPTION"
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
            early_match = _EARLY_EXCEPTION_PATTERN.search(raw_output)
            if early_match:
                thread_id = int(early_match.group(2), 16)

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
        "crashing_thread": thread_id,
        "stack_frames": stack_frames,
        "registers": {},
        "loaded_modules": loaded_modules,
        "symbol_quality": symbol_quality,
        "warnings": warnings,
        "suspected_patterns": [],
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
