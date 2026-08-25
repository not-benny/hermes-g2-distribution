#!/usr/bin/env python3
"""Store the G2 bridge token in one profile without printing it."""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
import stat
import tempfile
from pathlib import Path


KEY = "HERMES_G2_TOKEN"


def _current_value(lines: list[str]) -> str | None:
    prefix = f"{KEY}="
    for line in reversed(lines):
        if line.startswith(prefix):
            value = line[len(prefix) :].strip()
            return value or None
    return None


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f"Refusing unsafe profile environment path: {path}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise RuntimeError(
            f"Refusing {path}: permissions must not allow group or other access"
        )
    return path.read_text(encoding="utf-8").splitlines()


def _token_from_operator(non_interactive: bool) -> tuple[str, bool]:
    supplied = os.environ.get(KEY, "").strip()
    if supplied:
        return supplied, False
    if non_interactive:
        raise RuntimeError(f"Set {KEY} in the setup process environment")
    entered = getpass.getpass(
        "Create or paste the phone-to-Hermes token (leave blank to generate one): "
    ).strip()
    return (entered, False) if entered else (secrets.token_urlsafe(36), True)


def _validate_token(value: str) -> None:
    if len(value) < 32:
        raise RuntimeError("The G2 token must be at least 32 characters")
    if any(character in value for character in "\r\n\x00"):
        raise RuntimeError("The G2 token contains an invalid character")


def _replace_value(lines: list[str], value: str) -> list[str]:
    prefix = f"{KEY}="
    kept = [line for line in lines if not line.startswith(prefix)]
    if kept and kept[-1] != "":
        kept.append("")
    kept.append(f"{KEY}={value}")
    return kept


def _atomic_write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.is_symlink():
        raise RuntimeError(f"Refusing symlinked profile directory: {path.parent}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines).rstrip("\n") + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile_home", type=Path)
    parser.add_argument("--non-interactive", action="store_true")
    args = parser.parse_args()

    profile_home = args.profile_home.expanduser().resolve(strict=True)
    env_path = profile_home / ".env"
    lines = _read_lines(env_path)
    if _current_value(lines):
        print("The G2 token is already stored; keeping it unchanged.")
        return 0

    token, generated = _token_from_operator(args.non_interactive)
    _validate_token(token)
    _atomic_write(env_path, _replace_value(lines, token))
    if generated:
        print(
            "A strong token was generated and stored privately. Copy it from "
            "the installed profile's .env file into the Android app."
        )
    else:
        print("The G2 token was stored privately and was not displayed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError) as error:
        raise SystemExit(f"Token setup failed: {error}") from error
