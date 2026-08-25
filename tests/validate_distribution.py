#!/usr/bin/env python3
"""Static release gates for the public Hermes G2 distribution."""

from __future__ import annotations

import argparse
import ipaddress
import json
import re
import runpy
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_VERSION = "0.1.1"
EXPECTED_WORKFLOW_DIGEST = (
    "sha256:beab3a2170289a0f64ebeb957fd7a5c63fcaa43960c3ab293968c829eb6f9d4c"
)
EXPECTED_REFS = {
    "hermes_agent": "08f0664cdc3afe3022cc8da88f95b931651d093d",
    "bridge": "8c4f979020a21ae01fd6bc5351996e342d068136",
    "workflows": "8ecda2d984733328e4524c070386d3c1721f5c90",
    "android_app": "67989dada122ab6ce04594b11e57e742441dd2dd",
}
EXPECTED_WORKFLOW_TOOLS = frozenset(
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
EXPECTED_REPOS = {
    "hermes_agent": "https://github.com/not-benny/hermes-agent.git",
    "bridge": "https://github.com/not-benny/hermes-g2-bridge.git",
    "workflows": "https://github.com/not-benny/hermes-g2-workflows.git",
    "android_app": "https://github.com/not-benny/hermes-g2.git",
}


class ValidationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def load_yaml(path: Path) -> dict:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"{path.name} must be a YAML mapping")
    return value


def validate_manifest() -> None:
    manifest = load_yaml(ROOT / "distribution.yaml")
    require(manifest.get("name") == "even-g2", "distribution profile name changed")
    require(
        str(manifest.get("version")) == EXPECTED_VERSION,
        "distribution version changed",
    )
    require(
        manifest.get("license") == "Apache-2.0",
        "distribution license must be Apache-2.0",
    )
    require(manifest.get("hermes_requires") == ">=0.20.4", "Hermes minimum changed")
    require(
        manifest.get("distribution_owned")
        == ["SOUL.md", "config.yaml", ".env.template", "distribution.yaml"],
        "distribution-owned files must stay on the reviewed allowlist",
    )
    env = manifest.get("env_requires")
    require(
        isinstance(env, list) and len(env) == 1, "only the G2 token may be required"
    )
    require(env[0].get("name") == "HERMES_G2_TOKEN", "unexpected required secret")


def validate_locks(release: bool) -> None:
    lock = json.loads((ROOT / "sources.lock.json").read_text(encoding="utf-8"))
    require(lock.get("schema_version") == 1, "unsupported source-lock schema")
    for name, expected_repo in EXPECTED_REPOS.items():
        item = lock.get(name)
        require(isinstance(item, dict), f"missing lock entry: {name}")
        require(item.get("repo") == expected_repo, f"unexpected repository for {name}")
        ref = item.get("ref")
        if release or name != "android_app":
            require(
                isinstance(ref, str) and SHA_RE.fullmatch(ref) is not None,
                f"{name} is not exact-SHA pinned",
            )
            require(ref == EXPECTED_REFS[name], f"unexpected frozen commit for {name}")
    require(
        (lock.get("workflows") or {}).get("digest") == EXPECTED_WORKFLOW_DIGEST,
        "workflow package digest lock changed",
    )

    pack = load_yaml(ROOT / "hermes-pack.yaml")
    plugins = pack.get("plugins")
    require(
        isinstance(plugins, list) and len(plugins) == 2,
        "plugin pack must contain exactly two plugins",
    )
    expected_pack = {
        "not-benny/hermes-g2-bridge": EXPECTED_REFS["bridge"],
        "not-benny/hermes-g2-workflows": EXPECTED_REFS["workflows"],
    }
    actual_pack = {entry.get("repo"): entry.get("ref") for entry in plugins}
    require(actual_pack == expected_pack, "plugin pack and source lock differ")
    require(
        str(pack.get("version")) == EXPECTED_VERSION,
        "plugin pack version changed",
    )
    require(pack.get("config") == {}, "plugin pack must not seed authority or secrets")


def validate_persona() -> None:
    soul = (ROOT / "SOUL.md").read_text(encoding="utf-8")
    forbidden = (
        "mcp",
        "tool",
        "command",
        "weather",
        "train",
        "notification",
        "browser",
        "timer",
        "g2_",
        "glasses.",
        "retry",
        "allowlist",
        "token",
    )
    lowered = soul.lower()
    leaked = [term for term in forbidden if term in lowered]
    require(
        not leaked, f"SOUL.md contains workflow/policy language: {', '.join(leaked)}"
    )


def validate_config() -> None:
    config = load_yaml(ROOT / "config.yaml")
    require(config.get("_config_version") == 37, "unexpected config schema version")
    disabled = (config.get("agent") or {}).get("disabled_toolsets") or []
    require(
        disabled
        == [
            "browser",
            "code_execution",
            "computer_use",
            "delegation",
            "file",
            "terminal",
            "web",
        ],
        "base global toolset blocks changed",
    )
    g2 = ((config.get("gateway") or {}).get("platforms") or {}).get("g2") or {}
    require(g2.get("enabled") is False, "gateway template must install disabled")
    extra = g2.get("extra") or {}
    require(extra.get("bind") == "127.0.0.1", "template bind must be loopback")
    require(
        extra.get("allow_private_bind") is False, "private bind must require consent"
    )
    require(
        extra.get("tls_certfile") == "" and extra.get("tls_keyfile") == "",
        "TLS paths must be empty",
    )
    require(
        extra.get("proactive_tool_allowlist") == ["glasses.notify_result"],
        "proactive authority widened",
    )
    require(
        (config.get("platform_toolsets") or {}).get("g2") == [],
        "base G2 toolsets must begin empty",
    )
    plugins = config.get("plugins") or {}
    require(
        plugins.get("trusted_session_context") == [],
        "digest grants cannot ship in the template",
    )
    require(
        "mcp_servers" not in config, "personal MCP servers cannot ship in the template"
    )


def tracked_text_files() -> list[Path]:
    ignored_parts = {".git", "__pycache__", ".pytest_cache", ".ruff_cache"}
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in ignored_parts for part in path.relative_to(ROOT).parts)
    ]


def validate_no_generated_artifacts() -> None:
    generated_dirs = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
    generated_suffixes = {".pyc", ".pyo"}
    found: list[str] = []
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if ".git" in relative.parts:
            continue
        if (
            any(part in generated_dirs for part in relative.parts)
            or path.suffix in generated_suffixes
        ):
            found.append(str(relative))
    require(
        not found, f"generated cache artifact committed: {', '.join(sorted(found))}"
    )


def validate_privacy() -> None:
    private_networks = (
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("100.64.0.0/10"),
    )
    ipv4_re = re.compile(r"(?<![0-9])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9])")
    documentation_literals = {
        "10.0.0.0",
        "127.0.0.1",
        "172.16.0.0",
        "192.168.0.0",
        "100.64.0.0",
    }
    forbidden_paths = re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+/")
    secret_assignment = re.compile(
        r"(?im)^\s*(?:HERMES_G2_TOKEN|[^#\n]*(?:API_KEY|PASSWORD|SECRET|PRIVATE_KEY))\s*[=:]\s*([^\s#][^\n]*)$"
    )
    for path in tracked_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(ROOT)
        require(
            forbidden_paths.search(text) is None,
            f"personal absolute path in {relative}",
        )
        for raw in ipv4_re.findall(text):
            if raw in documentation_literals:
                continue
            try:
                address = ipaddress.ip_address(raw)
            except ValueError:
                continue
            if address.is_loopback:
                continue
            require(
                not any(address in network for network in private_networks),
                f"private address in {relative}",
            )
        if path.suffix.lower() in {
            ".yaml",
            ".yml",
            ".json",
            ".env",
            ".template",
            ".example",
        }:
            for match in secret_assignment.finditer(text):
                value = match.group(1).strip().strip("\"'")
                require(
                    value in {"", "YOUR_VALUE", "<required>"},
                    f"secret-shaped value in {relative}",
                )


def validate_public_markdown_style() -> None:
    for path in ROOT.rglob("*.md"):
        if ".git" in path.relative_to(ROOT).parts:
            continue
        text = path.read_text(encoding="utf-8")
        require(
            "\N{EM DASH}" not in text,
            f"em dash in public Markdown: {path.relative_to(ROOT)}",
        )
        require(
            "\N{EN DASH}" not in text,
            f"en dash in public Markdown: {path.relative_to(ROOT)}",
        )


def validate_workflow_surface() -> None:
    inventory_path = ROOT / "scripts" / "workflow_inventory.py"
    namespace = runpy.run_path(str(inventory_path))
    actual = namespace.get("EXPECTED_TOOLS")
    require(
        actual == EXPECTED_WORKFLOW_TOOLS,
        "workflow inventory verifier must pin the reviewed 13 tools",
    )
    require(len(actual) == 13, "workflow inventory count changed")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    lowered_readme = " ".join(readme.lower().split())
    require(
        "exposes exactly 13 intent-complete tools" in readme,
        "README must state the exact workflow count",
    )
    for name in EXPECTED_WORKFLOW_TOOLS:
        require(f"`{name}`" in readme, f"README workflow inventory is missing {name}")
    for phrase in (
        "exact case-insensitive match",
        "never falls back to the phone's Work Tasks app",
        "blocked, unassigned card",
        "does not start a worker",
        "outcome-unknown",
        "current wearer utterance",
        "one exact destination",
        "fresh wearer turn",
        "unnamed board tasks use `g2_work_task_add`",
        "mutates neither store",
    ):
        require(
            phrase.lower() in lowered_readme,
            f"README Kanban contract is missing: {phrase}",
        )


def validate_scripts() -> None:
    bootstrap = (ROOT / "scripts/bootstrap.sh").read_text(encoding="utf-8")
    lowered = bootstrap.lower()
    require("curl" not in lowered, "bootstrap must not fetch executable text with curl")
    require(
        "adb uninstall" not in lowered, "bootstrap must not uninstall the Android app"
    )
    require("pm clear" not in lowered, "bootstrap must not clear Android app data")
    require(
        "install -r" not in lowered,
        "Android replacement belongs to the reviewed app installer",
    )
    require(
        "--force-profile" in bootstrap and "profile export" in bootstrap,
        "force mode needs a backup gate",
    )
    require(
        "plugins pack install" in bootstrap, "bootstrap must use Hermes plugin packs"
    )
    require(
        "profile install" in bootstrap,
        "bootstrap must use Hermes profile distributions",
    )
    require(
        "plugins capabilities hermes-g2-workflows" in bootstrap,
        "bootstrap must verify the digest-bound workflow grant",
    )
    require(
        "agent-plugin-hermes-g2-workflows-" not in bootstrap,
        "portable MCP servers must not be treated as plugin toolsets",
    )
    require(
        '"$G2D_SCRIPT_DIR/workflow_inventory.py"' in bootstrap,
        "bootstrap must verify the exact workflow inventory",
    )
    require(
        'G2D_DEFAULT_SOURCE="$G2D_REPO_DIR"' in bootstrap,
        "bootstrap must default to the reviewed local checkout",
    )
    require(
        'G2D_DEFAULT_SOURCE="https://' not in bootstrap,
        "bootstrap must not default to a mutable remote distribution source",
    )
    require(
        "G2D_WORKFLOWS_DIGEST" in bootstrap
        and "--expected-digest" in bootstrap
        and "installed workflow package did not match its exact digest lock"
        in bootstrap,
        "bootstrap must enforce the exact workflow digest before granting authority",
    )
    require(
        "--enable-owner-tools" in bootstrap,
        "bootstrap must expose explicit owner-tool consent",
    )
    owner_match = re.search(
        r"G2D_OWNER_TOOLSETS=\(\n(?P<body>.*?)\n\)", bootstrap, re.DOTALL
    )
    owner_names = (
        tuple(re.findall(r"^\s{2}([a-z_]+)$", owner_match.group("body"), re.MULTILINE))
        if owner_match
        else ()
    )
    require(
        owner_names
        == (
            "browser",
            "terminal",
            "file",
            "skills",
            "web",
            "memory",
            "session_search",
            "cronjob",
            "computer_use",
        ),
        "owner-tool consent list changed",
    )
    require(
        "remove_global_toolset_blocks browser" in bootstrap,
        "personal browser consent must remove the base global block",
    )
    require(
        "enable_g2_toolsets_with_exact_boundary" in bootstrap
        and "G2 tool authority exceeded the consent boundary" in bootstrap
        and '--existing-json "$existing_json" --add "$@"' in bootstrap,
        "G2 owner/browser consent must reject implicit toolset widening",
    )
    require("set -x" not in lowered, "bootstrap must not enable command tracing")


def validate_release_documentation() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    lowered = " ".join(readme.lower().split())
    for phrase in (
        "git clone --branch v0.1.1 --depth 1",
        './scripts/bootstrap.sh --distribution-source "$PWD" --dry-run',
        './scripts/bootstrap.sh --distribution-source "$PWD"',
        "do not update an installed profile from a moving branch such as `main`",
        "exact workflow package digest",
        "owner-only `0600` file",
        "gateway-safe os-keyring primitive",
        "same os user can read that file",
        "public [`hermes-g2-bridge`]",
        "also apache-2.0",
    ):
        require(
            phrase.lower() in lowered,
            f"README release contract is missing: {phrase}",
        )


def validate_license() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    require(
        "Apache License" in license_text and "Version 2.0" in license_text,
        "Apache-2.0 license text missing",
    )
    require((ROOT / "NOTICE").is_file(), "NOTICE file missing")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--release",
        action="store_true",
        help="require every release lock, including Android",
    )
    args = parser.parse_args()
    checks = (
        validate_no_generated_artifacts,
        validate_manifest,
        lambda: validate_locks(args.release),
        validate_persona,
        validate_config,
        validate_privacy,
        validate_public_markdown_style,
        validate_workflow_surface,
        validate_scripts,
        validate_release_documentation,
        validate_license,
    )
    try:
        for check in checks:
            check()
    except (
        OSError,
        ValueError,
        yaml.YAMLError,
        json.JSONDecodeError,
        ValidationError,
    ) as error:
        print(f"validation failed: {error}", file=sys.stderr)
        return 1
    print("Hermes G2 distribution validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
