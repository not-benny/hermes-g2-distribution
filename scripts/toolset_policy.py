#!/usr/bin/env python3
"""Apply explicit toolset consent without discarding unrelated global blocks."""

from __future__ import annotations

import argparse
import json


def remove_disabled(existing_json: str, approved: list[str]) -> list[str]:
    """Remove only operator-approved names from a disabled-toolset JSON list."""

    value = json.loads(existing_json)
    if value is None:
        value = []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError("agent.disabled_toolsets must be a JSON list of strings")
    approved_set = set(approved)
    return [item for item in value if item not in approved_set]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--existing-json", required=True)
    parser.add_argument("--remove", nargs="+", required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            remove_disabled(args.existing_json, args.remove), separators=(",", ":")
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
