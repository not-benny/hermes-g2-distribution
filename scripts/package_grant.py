#!/usr/bin/env python3
"""Calculate and merge an exact portable-package context grant."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
)
EXCLUDED_FILES = frozenset({".DS_Store"})
BINDING = "hermes-g2-workflows:workflows"


def verify_expected_digest(digest: str, expected_digest: str | None) -> None:
    if expected_digest is not None and digest != expected_digest:
        raise RuntimeError("workflow package digest does not match the release lock")


def canonical_digest(plugin_root: Path) -> str:
    root = plugin_root.resolve(strict=True)
    if not root.is_dir():
        raise RuntimeError("workflow package root is not a directory")
    entries: list[tuple[str, Path]] = []
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        kept: list[str] = []
        for name in sorted(directories):
            path = current_path / name
            if name in EXCLUDED_DIRS:
                continue
            if path.is_symlink():
                entries.append((path.relative_to(root).as_posix(), path))
                continue
            kept.append(name)
        directories[:] = kept
        for name in sorted(files):
            path = current_path / name
            if name in EXCLUDED_FILES or name.endswith((".pyc", ".pyo")):
                continue
            if not path.is_symlink() and not path.is_file():
                raise RuntimeError("workflow package contains a special file")
            entries.append((path.relative_to(root).as_posix(), path))

    digest = hashlib.sha256(b"hermes-agent-plugin-package-v1\0")
    for relative, path in sorted(entries):
        encoded_name = relative.encode("utf-8")
        content = (
            b"symlink-v1\0" + os.readlink(path).encode("utf-8")
            if path.is_symlink()
            else b"file-v1\0" + path.read_bytes()
        )
        digest.update(len(encoded_name).to_bytes(8, "big"))
        digest.update(encoded_name)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return f"sha256:{digest.hexdigest()}"


def merged_grants(raw: str, digest: str) -> list[dict[str, str]]:
    try:
        current = json.loads(raw) if raw.strip() else []
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "existing trusted-session grants are not valid JSON"
        ) from error
    if current is None:
        current = []
    if not isinstance(current, list):
        raise RuntimeError("existing trusted-session grants are not a list")

    result: list[dict[str, str]] = []
    for item in current:
        if not isinstance(item, dict):
            raise RuntimeError("existing trusted-session grant has an invalid shape")
        if item.get("binding") == BINDING:
            continue
        if set(item) != {"binding", "digest"}:
            raise RuntimeError("existing trusted-session grant has an invalid shape")
        if not all(isinstance(item[key], str) for key in ("binding", "digest")):
            raise RuntimeError("existing trusted-session grant has an invalid value")
        result.append({"binding": item["binding"], "digest": item["digest"]})
    result.append({"binding": BINDING, "digest": digest})
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("plugin_root", type=Path)
    parser.add_argument("--existing-json", default="[]")
    parser.add_argument("--digest-only", action="store_true")
    parser.add_argument("--expected-digest")
    args = parser.parse_args()

    digest = canonical_digest(args.plugin_root)
    verify_expected_digest(digest, args.expected_digest)
    if args.digest_only:
        print(digest)
    else:
        print(
            json.dumps(merged_grants(args.existing_json, digest), separators=(",", ":"))
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError) as error:
        raise SystemExit(f"Workflow grant preparation failed: {error}") from error
