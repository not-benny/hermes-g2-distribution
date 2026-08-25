#!/usr/bin/env python3
"""Apply explicit toolset consent without discarding unrelated global blocks."""

from __future__ import annotations

import argparse
import json


def _string_list(existing_json: str, *, field: str) -> list[str]:
    value = json.loads(existing_json)
    if value is None:
        value = []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError(f"{field} must be a JSON list of strings")
    return value


def remove_disabled(existing_json: str, approved: list[str]) -> list[str]:
    """Remove only operator-approved names from a disabled-toolset JSON list."""

    value = _string_list(existing_json, field="agent.disabled_toolsets")
    approved_set = set(approved)
    return [item for item in value if item not in approved_set]


def add_enabled(existing_json: str, approved: list[str]) -> list[str]:
    """Add approved platform toolsets without widening any other authority."""

    value = _string_list(existing_json, field="platform_toolsets.g2")
    result = list(dict.fromkeys(value))
    for item in approved:
        if item not in result:
            result.append(item)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--existing-json", required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--remove", nargs="+")
    action.add_argument("--add", nargs="+")
    args = parser.parse_args()
    result = (
        remove_disabled(args.existing_json, args.remove)
        if args.remove is not None
        else add_enabled(args.existing_json, args.add)
    )
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
