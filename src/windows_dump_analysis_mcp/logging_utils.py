from __future__ import annotations

import logging
import os
from typing import Any


def configure_logging() -> None:
    level_name = os.getenv("DUMP_MCP_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def summarize_payload(payload: dict[str, Any]) -> str:
    method = payload.get("method")
    if method == "call_tool":
        return f"method=call_tool name={payload.get('name')}"
    if method == "read_resource":
        return f"method=read_resource uri={payload.get('uri')}"
    return f"method={method}"
