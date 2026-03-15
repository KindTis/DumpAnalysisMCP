from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import itertools
import threading
from typing import Any

from .errors import ErrorCode, ServerError


@dataclass
class DumpSession:
    dump_id: str
    dump_path: str
    symbol_root: str
    source_root: str
    binary_root: str | None
    project_type: str
    dump_type_hint: str
    log_paths: list[str]
    source_path_map: dict[str, str]
    created_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DumpSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, DumpSession] = {}
        self._counter = itertools.count(1)
        self._lock = threading.Lock()

    def _new_dump_id(self) -> str:
        now = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        with self._lock:
            sequence = next(self._counter)
        return f"crash-{now}-{sequence:03d}"

    def create(
        self,
        *,
        dump_path: str,
        symbol_root: str,
        source_root: str,
        binary_root: str | None,
        project_type: str,
        dump_type_hint: str,
        log_paths: list[str],
        source_path_map: dict[str, str],
    ) -> DumpSession:
        dump_id = self._new_dump_id()
        session = DumpSession(
            dump_id=dump_id,
            dump_path=dump_path,
            symbol_root=symbol_root,
            source_root=source_root,
            binary_root=binary_root,
            project_type=project_type,
            dump_type_hint=dump_type_hint,
            log_paths=log_paths,
            source_path_map=source_path_map,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
        )
        self._sessions[dump_id] = session
        return session

    def get(self, dump_id: str) -> DumpSession:
        session = self._sessions.get(dump_id)
        if not session:
            raise ServerError(
                ErrorCode.INVALID_REQUEST,
                f"dump_id '{dump_id}' does not exist.",
                {"dump_id": dump_id},
            )
        return session

    def list(self) -> list[DumpSession]:
        return list(self._sessions.values())


def ensure_existing_file(path: str, error_code: str) -> None:
    p = Path(path)
    if not p.is_absolute():
        raise ServerError(error_code, "Path must be absolute.", {"path": path})
    if not p.exists() or not p.is_file():
        raise ServerError(error_code, "File not found.", {"path": path})


def ensure_existing_dir(path: str, error_code: str) -> None:
    p = Path(path)
    if not p.is_absolute():
        raise ServerError(error_code, "Path must be absolute.", {"path": path})
    if not p.exists() or not p.is_dir():
        raise ServerError(error_code, "Directory not found.", {"path": path})
