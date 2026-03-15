from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import ErrorCode, ServerError, ValidationError

_TEXT_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
    ".inl",
    ".ixx",
    ".cs",
    ".py",
    ".txt",
    ".ini",
    ".json",
    ".uplugin",
    ".uproject",
}


def _is_inside_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _windows_norm(value: str) -> str:
    return value.replace("/", "\\").rstrip("\\").lower()


def _apply_source_path_map(source_file: str, source_path_map: dict[str, str]) -> Path | None:
    if not source_file:
        return None

    normalized = _windows_norm(source_file)
    best_from: str | None = None
    best_to: str | None = None
    for src_prefix, dst_prefix in source_path_map.items():
        src_norm = _windows_norm(src_prefix)
        if not src_norm:
            continue
        if normalized == src_norm or normalized.startswith(src_norm + "\\"):
            if best_from is None or len(src_norm) > len(best_from):
                best_from = src_norm
                best_to = dst_prefix

    if best_from is None or best_to is None:
        return None

    suffix = normalized[len(best_from) :].lstrip("\\")
    mapped_base = Path(best_to)
    return mapped_base / suffix if suffix else mapped_base


class CodeContextProvider:
    def get_source_context(
        self,
        *,
        source_root: str,
        source_file: str,
        focus_line: int,
        context_before: int,
        context_after: int,
        source_path_map: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if context_before < 0 or context_after < 0:
            raise ValidationError("context_before/context_after must be >= 0.")
        if focus_line <= 0:
            raise ServerError(
                ErrorCode.SOURCE_MAPPING_FAILED,
                "Source line is not available for requested frame.",
                {"focus_line": focus_line},
            )

        root = Path(source_root).resolve()
        file_candidate = Path(source_file)
        target = file_candidate if file_candidate.is_absolute() else (root / file_candidate)
        target = target.resolve()

        # If source path from symbols points outside source_root, try explicit remap.
        if source_path_map and (not _is_inside_root(target, root) or not target.exists()):
            remapped = _apply_source_path_map(source_file, source_path_map)
            if remapped is not None:
                target = remapped.resolve()

        if not _is_inside_root(target, root):
            raise ServerError(
                ErrorCode.INVALID_PATH,
                "Resolved source file is outside source_root.",
                {"source_root": str(root), "source_file": str(target)},
            )
        if not target.exists() or not target.is_file():
            raise ServerError(
                ErrorCode.SOURCE_MAPPING_FAILED,
                "Resolved source file does not exist.",
                {"source_file": str(target)},
            )

        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        if not lines:
            return {
                "file": str(target),
                "start_line": 1,
                "end_line": 0,
                "focus_line": focus_line,
                "lines": [],
            }

        clamped_focus = min(max(focus_line, 1), len(lines))
        start_line = max(1, clamped_focus - context_before)
        end_line = min(len(lines), clamped_focus + context_after)
        selected = [
            {"line": idx + 1, "text": lines[idx]}
            for idx in range(start_line - 1, end_line)
        ]
        return {
            "file": str(target),
            "start_line": start_line,
            "end_line": end_line,
            "focus_line": clamped_focus,
            "lines": selected,
        }

    def search_code_references(
        self,
        *,
        source_root: str,
        query: str,
        max_results: int,
        ignore_case: bool = False,
    ) -> list[dict[str, Any]]:
        if not query.strip():
            raise ValidationError("query must be non-empty.")
        if max_results <= 0:
            raise ValidationError("max_results must be positive.")

        root = Path(source_root).resolve()
        if not root.exists() or not root.is_dir():
            raise ServerError(
                ErrorCode.SOURCE_ROOT_INVALID,
                "source_root does not exist.",
                {"source_root": str(root)},
            )

        needle = query.lower() if ignore_case else query
        results: list[dict[str, Any]] = []
        for path in root.rglob("*"):
            if len(results) >= max_results:
                break
            if not path.is_file():
                continue
            if path.suffix.lower() not in _TEXT_EXTENSIONS:
                continue
            if not _is_inside_root(path, root):
                continue

            try:
                content = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue

            for idx, line in enumerate(content, start=1):
                hay = line.lower() if ignore_case else line
                if needle in hay:
                    results.append(
                        {
                            "file": str(path.resolve()),
                            "line": idx,
                            "match": line.strip(),
                        }
                    )
                    if len(results) >= max_results:
                        break
        return results
