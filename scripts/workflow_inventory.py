#!/usr/bin/env python3
"""Verify the exact, fixed tool surface of an installed G2 workflow package."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any


EXPECTED_TOOLS = frozenset(
    {
        "g2_apps_manage",
        "g2_calendar_agenda",
        "g2_clock_set_alarm",
        "g2_clock_set_timer",
        "g2_health_summary",
        "g2_kanban_task_create",
        "g2_media_control",
        "g2_navigation",
        "g2_notifications",
        "g2_reminder_create",
        "g2_train_departures_present",
        "g2_weather_present",
        "g2_work_task_add",
    }
)


def _message(
    method: str, *, request_id: int | None = None, params: dict[str, Any] | None = None
) -> str:
    value: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        value["id"] = request_id
    if params is not None:
        value["params"] = params
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def validate_responses(responses: list[dict[str, Any]]) -> None:
    by_id = {response.get("id"): response for response in responses if "id" in response}
    initialized = by_id.get(1, {}).get("result", {})
    if (initialized.get("serverInfo") or {}).get("name") != "hermes-g2-workflows":
        raise RuntimeError("workflow MCP identity did not match hermes-g2-workflows")

    raw_tools = (by_id.get(2, {}).get("result", {}) or {}).get("tools")
    if not isinstance(raw_tools, list) or not all(
        isinstance(tool, dict) for tool in raw_tools
    ):
        raise RuntimeError("workflow MCP did not return a tools list")
    names = [tool.get("name") for tool in raw_tools]
    if not all(isinstance(name, str) for name in names) or len(names) != len(
        set(names)
    ):
        raise RuntimeError("workflow MCP returned missing or duplicate tool names")
    if set(names) != EXPECTED_TOOLS:
        missing = sorted(EXPECTED_TOOLS - set(names))
        extra = sorted(set(names) - EXPECTED_TOOLS)
        raise RuntimeError(
            f"workflow inventory changed (missing={missing}, extra={extra})"
        )

    kanban = next(
        tool for tool in raw_tools if tool.get("name") == "g2_kanban_task_create"
    )
    description = str(kanban.get("description") or "").lower()
    required_phrases = (
        "existing hermes kanban board",
        "blocked",
        "no assignee",
        "never starts a worker",
    )
    if not all(phrase in description for phrase in required_phrases):
        raise RuntimeError(
            "Kanban workflow description lost its parked-card safety contract"
        )
    schema = kanban.get("inputSchema") or {}
    if schema.get("required") != ["title", "board"]:
        raise RuntimeError("Kanban workflow must require exactly title and board")
    properties = schema.get("properties") or {}
    if set(properties) != {"title", "board", "body"}:
        raise RuntimeError("Kanban workflow input surface changed")


def inspect_package(plugin_root: Path, interpreter: Path) -> None:
    root = plugin_root.resolve(strict=True)
    server = root / "server.py"
    if server.is_symlink() or not server.is_file():
        raise RuntimeError("workflow server must be a regular, non-symlink file")
    resolved_interpreter = interpreter.resolve(strict=True)
    if not resolved_interpreter.is_file() or not os.access(
        resolved_interpreter, os.X_OK
    ):
        raise RuntimeError(
            "workflow interpreter must resolve to an executable regular file"
        )
    executable_caches = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}
    ]
    if executable_caches:
        raise RuntimeError(
            f"workflow package contains executable cache: {executable_caches[0]}"
        )

    payload = (
        "\n".join(
            (
                _message(
                    "initialize",
                    request_id=1,
                    params={
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {
                            "name": "hermes-g2-distribution",
                            "version": "1",
                        },
                    },
                ),
                _message("notifications/initialized"),
                _message("tools/list", request_id=2, params={}),
            )
        )
        + "\n"
    )
    env = {
        "HERMES_G2_WORKFLOW_RELAY": str(root / ".inventory-check.sock"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    try:
        completed = subprocess.run(
            [str(resolved_interpreter), "-I", "-S", "-B", str(server)],
            cwd=root,
            env=env,
            input=payload,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("workflow MCP inventory check timed out") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip()[:240]
        raise RuntimeError(f"workflow MCP inventory check failed: {detail}")
    try:
        responses = [
            json.loads(line) for line in completed.stdout.splitlines() if line.strip()
        ]
    except json.JSONDecodeError as error:
        raise RuntimeError("workflow MCP inventory returned invalid JSON") from error
    validate_responses(responses)
    if any(
        path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}
        for path in root.rglob("*")
    ):
        raise RuntimeError("workflow MCP inventory check created executable cache")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin_root", type=Path)
    parser.add_argument("--python", type=Path, required=True)
    args = parser.parse_args()
    inspect_package(args.plugin_root, args.python)
    print(f"Verified workflow inventory: {len(EXPECTED_TOOLS)} fixed tools.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
