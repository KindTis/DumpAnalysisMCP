from __future__ import annotations

from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
from typing import Any

from .errors import ErrorCode, PolicyViolationError, ServerError, ValidationError


@dataclass(frozen=True)
class PatchChange:
    path: str
    content: str


def _is_inside_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _resolve_target(root: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    target = candidate if candidate.is_absolute() else (root / candidate)
    resolved = target.resolve()
    if not _is_inside_root(resolved, root):
        raise ServerError(
            ErrorCode.INVALID_PATH,
            "Patch target path is outside source_root.",
            {"source_root": str(root), "target": str(resolved)},
        )
    return resolved


class PatchExecutor:
    def apply_patch(
        self,
        *,
        source_root: str,
        changes: list[PatchChange],
        mode: str,
        user_confirmed: bool,
    ) -> dict[str, Any]:
        if mode not in {"preview", "apply"}:
            raise ValidationError("mode must be either 'preview' or 'apply'.", {"mode": mode})
        if mode == "apply" and not user_confirmed:
            raise PolicyViolationError(
                "apply mode requires explicit user confirmation.",
                {"required_flag": "user_confirmed"},
            )

        root = Path(source_root).resolve()
        if not root.exists() or not root.is_dir():
            raise ServerError(
                ErrorCode.SOURCE_ROOT_INVALID,
                "source_root does not exist.",
                {"source_root": str(root)},
            )

        prepared: list[tuple[Path, str, str]] = []
        for change in changes:
            target = _resolve_target(root, change.path)
            old_text = ""
            if target.exists():
                if not target.is_file():
                    raise ServerError(
                        ErrorCode.INVALID_PATH,
                        "Patch target must be a file path.",
                        {"target": str(target)},
                    )
                old_text = target.read_text(encoding="utf-8", errors="replace")
            prepared.append((target, old_text, change.content))

        diff_chunks: list[str] = []
        modified_files: list[str] = []
        for target, old_text, new_text in prepared:
            if old_text == new_text:
                continue
            modified_files.append(str(target))
            from_name = f"a/{target.name}" if old_text else "/dev/null"
            to_name = f"b/{target.name}"
            diff_chunks.extend(
                unified_diff(
                    old_text.splitlines(keepends=True),
                    new_text.splitlines(keepends=True),
                    fromfile=from_name,
                    tofile=to_name,
                )
            )

        if mode == "apply":
            for target, _old_text, new_text in prepared:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(new_text, encoding="utf-8")

        return {
            "ok": True,
            "mode": mode,
            "applied": mode == "apply",
            "modified_files": modified_files,
            "diff": "".join(diff_chunks),
        }
