#!/usr/bin/env bash
set -euo pipefail

G2D_SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd -P)"
G2D_REPO_DIR="$(dirname -- "$G2D_SCRIPT_DIR")"
G2D_LOCK_FILE="$G2D_REPO_DIR/sources.lock.json"
G2D_PACK_FILE="$G2D_REPO_DIR/hermes-pack.yaml"
G2D_DEFAULT_SOURCE="https://github.com/not-benny/hermes-g2-distribution.git"

G2D_PROFILE="even-g2"
G2D_DISTRIBUTION_SOURCE="${HERMES_G2_DISTRIBUTION_SOURCE:-$G2D_DEFAULT_SOURCE}"
G2D_MODE="install"
G2D_BIND="127.0.0.1"
G2D_PORT="8790"
G2D_TLS_CERT=""
G2D_TLS_KEY=""
G2D_ALLOW_PRIVATE_BIND="false"
G2D_WITH_ANDROID="false"
G2D_ADB_SERIAL=""
G2D_ADB_PORT=""
G2D_ENABLE_BROWSER="false"
G2D_ENABLE_OWNER_TOOLS="false"
G2D_START_GATEWAY="false"
G2D_ALLOW_WITHOUT_PUBLIC_DATA="false"
G2D_DRY_RUN="false"
G2D_TEMP_DIR=""
G2D_OWNER_TOOLSETS=(
  browser
  terminal
  file
  skills
  web
  memory
  session_search
  cronjob
  computer_use
)

usage() {
  cat <<'EOF'
Install the Hermes G2 profile and its exact, source-pinned plugins.

Usage:
  ./scripts/bootstrap.sh [options]

Core options:
  --profile NAME                 Profile name (default: even-g2)
  --update                       Update an installed distribution safely
  --force-profile                Replace an existing profile template after backup
  --distribution-source SOURCE  Git URL or local distribution directory
  --bind ADDRESS                Loopback, Tailscale, or approved private address
  --port PORT                    G2 gateway port (default: 8790)
  --tls-cert FILE               TLS certificate for a non-loopback bind
  --tls-key FILE                TLS private key for a non-loopback bind
  --allow-private-bind          Allow a literal private-LAN address

Optional, explicit consent:
  --with-android-app            Build, sign, and install the pinned app source
  --adb-serial SERIAL           Select one ADB device
  --adb-port PORT               Use a non-default ADB server port
  --enable-personal-browser     Let this profile use the local browser toolset
  --enable-owner-tools          Enable nine private owner toolsets, including browser
  --start-gateway               Install/start, or restart, the profile gateway
  --allow-without-public-data   Continue without the reviewed Brave host binary

Validation:
  --dry-run                     Validate and show the plan without changing anything
  -h, --help                    Show this help

The script never uninstalls the Android app, clears app data, imports a browser
profile, or copies personal service credentials.
EOF
}

fail() {
  printf 'Setup stopped: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  if [[ -n "$G2D_TEMP_DIR" && -d "$G2D_TEMP_DIR" \
        && "$(basename -- "$G2D_TEMP_DIR")" == hermes-g2-distribution.* ]]; then
    find "$G2D_TEMP_DIR" -depth -delete 2>/dev/null || true
  fi
}
trap cleanup EXIT

need_value() {
  [[ $# -ge 2 && -n "$2" ]] || fail "$1 needs a value"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      need_value "$1" "${2:-}"
      G2D_PROFILE="$2"
      shift 2
      ;;
    --update)
      [[ "$G2D_MODE" == "install" ]] || fail "choose only one update mode"
      G2D_MODE="update"
      shift
      ;;
    --force-profile)
      [[ "$G2D_MODE" == "install" ]] || fail "choose only one update mode"
      G2D_MODE="force"
      shift
      ;;
    --distribution-source)
      need_value "$1" "${2:-}"
      G2D_DISTRIBUTION_SOURCE="$2"
      shift 2
      ;;
    --bind)
      need_value "$1" "${2:-}"
      G2D_BIND="$2"
      shift 2
      ;;
    --port)
      need_value "$1" "${2:-}"
      G2D_PORT="$2"
      shift 2
      ;;
    --tls-cert)
      need_value "$1" "${2:-}"
      G2D_TLS_CERT="$2"
      shift 2
      ;;
    --tls-key)
      need_value "$1" "${2:-}"
      G2D_TLS_KEY="$2"
      shift 2
      ;;
    --allow-private-bind)
      G2D_ALLOW_PRIVATE_BIND="true"
      shift
      ;;
    --with-android-app)
      G2D_WITH_ANDROID="true"
      shift
      ;;
    --adb-serial)
      need_value "$1" "${2:-}"
      G2D_ADB_SERIAL="$2"
      shift 2
      ;;
    --adb-port)
      need_value "$1" "${2:-}"
      G2D_ADB_PORT="$2"
      shift 2
      ;;
    --enable-personal-browser)
      G2D_ENABLE_BROWSER="true"
      shift
      ;;
    --enable-owner-tools)
      G2D_ENABLE_OWNER_TOOLS="true"
      shift
      ;;
    --start-gateway)
      G2D_START_GATEWAY="true"
      shift
      ;;
    --allow-without-public-data)
      G2D_ALLOW_WITHOUT_PUBLIC_DATA="true"
      shift
      ;;
    --dry-run)
      G2D_DRY_RUN="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown option: $1"
      ;;
  esac
done

command -v hermes >/dev/null 2>&1 || fail "Hermes Agent is not installed"
command -v git >/dev/null 2>&1 || fail "Git is not installed"
command -v python3 >/dev/null 2>&1 || fail "Python 3 is not installed"

[[ "$G2D_PROFILE" =~ ^[a-z0-9][a-z0-9_-]{0,63}$ ]] \
  || fail "profile names use lowercase letters, numbers, dashes, or underscores"
if [[ ! "$G2D_PORT" =~ ^[0-9]+$ ]] \
    || ((G2D_PORT < 1 || G2D_PORT > 65535)); then
  fail "gateway port must be between 1 and 65535"
fi
if [[ -n "$G2D_ADB_PORT" ]]; then
  if [[ ! "$G2D_ADB_PORT" =~ ^[0-9]+$ ]] \
      || ((G2D_ADB_PORT < 1 || G2D_ADB_PORT > 65535)); then
    fail "ADB server port must be between 1 and 65535"
  fi
fi

python3 - "$G2D_BIND" "$G2D_ALLOW_PRIVATE_BIND" <<'PY'
import ipaddress
import sys

raw, allow_private = sys.argv[1], sys.argv[2] == "true"
try:
    address = ipaddress.ip_address(raw)
except ValueError as error:
    raise SystemExit(f"Setup stopped: bind address must be a literal IP address: {error}")
tailscale = address in ipaddress.ip_network("100.64.0.0/10") or address in ipaddress.ip_network("fd7a:115c:a1e0::/48")
safe = address.is_loopback or tailscale
if not safe and allow_private:
    safe = address.is_private and not address.is_unspecified
if not safe:
    raise SystemExit("Setup stopped: bind address is not loopback, Tailscale, or an explicitly approved private address")
PY

G2D_IS_LOOPBACK="$(python3 - "$G2D_BIND" <<'PY'
import ipaddress
import sys
print("true" if ipaddress.ip_address(sys.argv[1]).is_loopback else "false")
PY
)"

if [[ "$G2D_IS_LOOPBACK" != "true" ]]; then
  [[ -n "$G2D_TLS_CERT" && -n "$G2D_TLS_KEY" ]] \
    || fail "a non-loopback G2 gateway needs both --tls-cert and --tls-key"
fi
if [[ -n "$G2D_TLS_CERT" || -n "$G2D_TLS_KEY" ]]; then
  [[ -f "$G2D_TLS_CERT" && ! -L "$G2D_TLS_CERT" ]] \
    || fail "TLS certificate must be a regular, non-symlink file"
  [[ -f "$G2D_TLS_KEY" && ! -L "$G2D_TLS_KEY" ]] \
    || fail "TLS key must be a regular, non-symlink file"
fi

G2D_HERMES_VERSION_OUTPUT="$(hermes --version)"
G2D_HERMES_VERSION="$(printf '%s\n' "$G2D_HERMES_VERSION_OUTPUT" | sed -n '1s/.*v\([0-9][0-9.]*\).*/\1/p')"
[[ -n "$G2D_HERMES_VERSION" ]] || fail "could not read the Hermes version"
python3 - "$G2D_HERMES_VERSION" <<'PY'
import sys

def parts(value: str) -> tuple[int, int, int]:
    pieces = value.split(".")[:3]
    pieces += ["0"] * (3 - len(pieces))
    return tuple(int(piece) for piece in pieces)

if parts(sys.argv[1]) < (0, 20, 4):
    raise SystemExit("Setup stopped: Hermes Agent 0.20.4 or newer is required")
PY

G2D_HERMES_DIR="$(printf '%s\n' "$G2D_HERMES_VERSION_OUTPUT" | sed -n 's/^Install directory:[[:space:]]*//p' | head -n 1)"
[[ -d "$G2D_HERMES_DIR" ]] || fail "could not locate the Hermes installation"
for G2D_REQUIRED_FILE in \
  "$G2D_HERMES_DIR/hermes_cli/profile_distribution.py" \
  "$G2D_HERMES_DIR/hermes_cli/plugin_packs.py" \
  "$G2D_HERMES_DIR/hermes_cli/agent_plugins.py" \
  "$G2D_HERMES_DIR/tools/mcp_tool.py"; do
  [[ -f "$G2D_REQUIRED_FILE" ]] \
    || fail "this Hermes installation lacks the required profile/MCP capability support"
done
grep -q 'trusted_session_context' "$G2D_HERMES_DIR/hermes_cli/agent_plugins.py" \
  2>/dev/null \
  || grep -q 'sessionCapability' "$G2D_HERMES_DIR/hermes_cli/agent_plugins.py" \
  || fail "this Hermes installation lacks digest-bound workflow capability support"
grep -q '_prepare_session_capability' "$G2D_HERMES_DIR/tools/mcp_tool.py" \
  || fail "this Hermes installation lacks MCP session capability injection"

G2D_HERMES_PYTHON=""
for G2D_CANDIDATE in "$G2D_HERMES_DIR/venv/bin/python" "$G2D_HERMES_DIR/.venv/bin/python"; do
  if [[ -x "$G2D_CANDIDATE" ]]; then
    G2D_HERMES_PYTHON="$G2D_CANDIDATE"
    break
  fi
done
[[ -n "$G2D_HERMES_PYTHON" ]] \
  || fail "could not locate the Hermes Python environment"
"$G2D_HERMES_PYTHON" -c 'import playwright, websockets' \
  || fail "the Hermes Python environment needs Playwright and websockets before G2 setup"

if [[ "$G2D_ALLOW_WITHOUT_PUBLIC_DATA" != "true" ]]; then
  [[ -f /opt/brave-bin/brave && ! -L /opt/brave-bin/brave && -x /opt/brave-bin/brave ]] \
    || fail "train and weather need the reviewed Brave binary at /opt/brave-bin/brave; use --allow-without-public-data to install without those feeds"
fi

python3 "$G2D_REPO_DIR/tests/validate_distribution.py"
hermes plugins pack show "$G2D_PACK_FILE" >/dev/null

lock_value() {
  python3 - "$G2D_LOCK_FILE" "$1" "$2" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    lock = json.load(handle)
value = lock[sys.argv[2]][sys.argv[3]]
print(value or "")
PY
}

G2D_TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/hermes-g2-distribution.XXXXXXXX")"

verify_pinned_plugin() {
  local name=$1
  local repo=$2
  local ref=$3
  local checkout="$G2D_TEMP_DIR/preflight-$name"
  mkdir -p -- "$checkout"
  git -C "$checkout" init -q
  git -C "$checkout" remote add origin "$repo"
  git -C "$checkout" fetch --quiet --depth 1 --no-tags origin "$ref"
  git -C "$checkout" checkout --quiet --detach FETCH_HEAD
  [[ "$(git -C "$checkout" rev-parse HEAD)" == "$ref" ]] \
    || fail "$name source checkout did not match its exact lock"
  PYTHONPATH="$G2D_HERMES_DIR" "$G2D_HERMES_PYTHON" - "$checkout" "$name" <<'PY'
import sys
from pathlib import Path
from tools.plugin_guard import format_scan_report, scan_plugin, should_allow_plugin_install

root = Path(sys.argv[1])
name = sys.argv[2]
result = scan_plugin(root, source=f"locked:{name}")
allowed, reason = should_allow_plugin_install(result)
if allowed is not True:
    print(format_scan_report(result), file=sys.stderr)
    raise SystemExit(f"Setup stopped: locked {name} source did not pass Hermes Plugin Guard: {reason}")
PY
}

G2D_BRIDGE_REPO="$(lock_value bridge repo)"
G2D_BRIDGE_REF="$(lock_value bridge ref)"
G2D_WORKFLOWS_REPO="$(lock_value workflows repo)"
G2D_WORKFLOWS_REF="$(lock_value workflows ref)"
verify_pinned_plugin bridge "$G2D_BRIDGE_REPO" "$G2D_BRIDGE_REF"
verify_pinned_plugin workflows "$G2D_WORKFLOWS_REPO" "$G2D_WORKFLOWS_REF"

G2D_APP_REPO="$(lock_value android_app repo)"
G2D_APP_REF="$(lock_value android_app ref)"
if [[ "$G2D_WITH_ANDROID" == "true" ]]; then
  [[ "$G2D_APP_REF" =~ ^[0-9a-f]{40}$ ]] \
    || fail "the Android source lock is not finalized yet"
fi

G2D_PROFILE_EXISTS="false"
if hermes profile show "$G2D_PROFILE" >/dev/null 2>&1; then
  G2D_PROFILE_EXISTS="true"
fi
case "$G2D_MODE:$G2D_PROFILE_EXISTS" in
  install:true)
    fail "profile '$G2D_PROFILE' already exists; use --update or --force-profile"
    ;;
  update:false)
    fail "profile '$G2D_PROFILE' does not exist, so it cannot be updated"
    ;;
esac

printf '\nHermes G2 setup plan\n'
printf '  Profile: %s\n' "$G2D_PROFILE"
printf '  Mode: %s\n' "$G2D_MODE"
printf '  Gateway: %s:%s\n' "$G2D_BIND" "$G2D_PORT"
printf '  Android app: %s\n' "$G2D_WITH_ANDROID"
printf '  Personal browser-only option: %s\n' "$G2D_ENABLE_BROWSER"
printf '  Private owner tool access: %s\n' "$G2D_ENABLE_OWNER_TOOLS"
printf '  Start gateway: %s\n\n' "$G2D_START_GATEWAY"

if [[ "$G2D_DRY_RUN" == "true" ]]; then
  printf 'Dry run complete. No profile, plugin, service, or Android state changed.\n'
  exit 0
fi

[[ -t 0 && -t 1 ]] \
  || fail "interactive review is required for plugin and workflow consent"

G2D_BACKUP_PATH=""
if [[ "$G2D_PROFILE_EXISTS" == "true" ]]; then
  G2D_BACKUP_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/hermes-g2-distribution/backups"
  mkdir -p -- "$G2D_BACKUP_DIR"
  chmod 700 "$G2D_BACKUP_DIR"
  G2D_BACKUP_PATH="$G2D_BACKUP_DIR/${G2D_PROFILE}-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
  hermes profile export "$G2D_PROFILE" --output "$G2D_BACKUP_PATH"
  chmod 600 "$G2D_BACKUP_PATH"
  printf 'A credential-free rollback snapshot was saved locally.\n'
fi

if [[ "$G2D_MODE" == "update" ]]; then
  hermes profile update "$G2D_PROFILE"
else
  G2D_PROFILE_INSTALL_ARGS=(profile install "$G2D_DISTRIBUTION_SOURCE" --name "$G2D_PROFILE" --alias)
  if [[ "$G2D_MODE" == "force" ]]; then
    G2D_PROFILE_INSTALL_ARGS+=(--force)
  fi
  hermes "${G2D_PROFILE_INSTALL_ARGS[@]}"
fi

G2D_PROFILE_SHOW="$(hermes profile show "$G2D_PROFILE")"
G2D_PROFILE_HOME="$(printf '%s\n' "$G2D_PROFILE_SHOW" | sed -n 's/^Path:[[:space:]]*//p' | head -n 1)"
[[ -d "$G2D_PROFILE_HOME" ]] || fail "could not resolve the installed profile directory"

python3 "$G2D_SCRIPT_DIR/profile_secret.py" "$G2D_PROFILE_HOME"

G2D_PACK_ARGS=(--profile "$G2D_PROFILE" plugins pack install "$G2D_PACK_FILE")
if [[ "$G2D_MODE" != "install" ]]; then
  G2D_PACK_ARGS+=(--force)
fi
hermes "${G2D_PACK_ARGS[@]}"

hermes --profile "$G2D_PROFILE" plugins doctor hermes-g2-bridge --ci
hermes --profile "$G2D_PROFILE" plugins doctor hermes-g2-workflows --ci

G2D_WORKFLOW_ROOT="$G2D_PROFILE_HOME/plugins/hermes-g2-workflows"
[[ -d "$G2D_WORKFLOW_ROOT" ]] || fail "the pinned workflow package was not installed"
"$G2D_HERMES_PYTHON" "$G2D_SCRIPT_DIR/workflow_inventory.py" \
  "$G2D_WORKFLOW_ROOT" --python "$G2D_HERMES_PYTHON"
printf '\nAllow the exact installed workflow package to receive the current G2\n'
printf 'conversation context and call its fixed device relay? [y/N] '
IFS= read -r G2D_GRANT_ANSWER
case "$G2D_GRANT_ANSWER" in
  y|Y|yes|YES|Yes)
    ;;
  *)
    fail "workflow context was not granted; the package remains installed but cannot control the glasses"
    ;;
esac

G2D_EXISTING_GRANTS="$(
  hermes --profile "$G2D_PROFILE" config get --json plugins.trusted_session_context \
    2>/dev/null || printf '[]'
)"
G2D_MERGED_GRANTS="$(
  python3 "$G2D_SCRIPT_DIR/package_grant.py" "$G2D_WORKFLOW_ROOT" \
    --existing-json "$G2D_EXISTING_GRANTS"
)"
hermes --profile "$G2D_PROFILE" config set \
  plugins.trusted_session_context "$G2D_MERGED_GRANTS"

# An enabled Agent Plugin MCP is included in platform sessions automatically.
# It is an MCP server, not a plugin toolset, so persisting it through
# `hermes tools enable` would be both unnecessary and rejected by Hermes.
G2D_WORKFLOW_CAPABILITIES="$(
  hermes --profile "$G2D_PROFILE" plugins capabilities hermes-g2-workflows
)"
printf '%s\n' "$G2D_WORKFLOW_CAPABILITIES"
printf '%s\n' "$G2D_WORKFLOW_CAPABILITIES" \
  | grep -Fq 'session capability hermes-g2-workflows:workflows: granted for this digest' \
  || fail "the installed workflow package did not receive its exact digest grant"

hermes --profile "$G2D_PROFILE" config set gateway.platforms.g2.extra.bind "$G2D_BIND"
hermes --profile "$G2D_PROFILE" config set gateway.platforms.g2.extra.port "$G2D_PORT"
hermes --profile "$G2D_PROFILE" config set gateway.platforms.g2.extra.allow_private_bind "$G2D_ALLOW_PRIVATE_BIND"
hermes --profile "$G2D_PROFILE" config set gateway.platforms.g2.extra.hello_profile "$G2D_PROFILE"
if [[ -n "$G2D_TLS_CERT" ]]; then
  hermes --profile "$G2D_PROFILE" config set gateway.platforms.g2.extra.tls_certfile "$G2D_TLS_CERT"
  hermes --profile "$G2D_PROFILE" config set gateway.platforms.g2.extra.tls_keyfile "$G2D_TLS_KEY"
fi
hermes --profile "$G2D_PROFILE" config set gateway.platforms.g2.enabled true

remove_global_toolset_blocks() {
  local current_json
  local filtered_json
  current_json="$(
    hermes --profile "$G2D_PROFILE" config get --json agent.disabled_toolsets \
      2>/dev/null || printf '[]'
  )"
  filtered_json="$(
    python3 "$G2D_SCRIPT_DIR/toolset_policy.py" \
      --existing-json "$current_json" --remove "$@"
  )"
  hermes --profile "$G2D_PROFILE" config set agent.disabled_toolsets "$filtered_json"
}

if [[ "$G2D_ENABLE_OWNER_TOOLS" == "true" ]]; then
  printf '\nOwner tools expose local files, commands, browser sessions, history,\n'
  printf 'scheduled actions, and desktop control to this private profile.\n'
  printf 'Enable all nine reviewed owner toolsets for G2? [y/N] '
  IFS= read -r G2D_OWNER_ANSWER
  case "$G2D_OWNER_ANSWER" in
    y|Y|yes|YES|Yes)
      remove_global_toolset_blocks "${G2D_OWNER_TOOLSETS[@]}"
      hermes --profile "$G2D_PROFILE" tools enable \
        --platform g2 "${G2D_OWNER_TOOLSETS[@]}"
      ;;
    *)
      fail "private owner tool access was not enabled"
      ;;
  esac
elif [[ "$G2D_ENABLE_BROWSER" == "true" ]]; then
  printf '\nPersonal browser access can expose signed-in pages and account actions.\n'
  printf 'Enable it for this G2 profile? [y/N] '
  IFS= read -r G2D_BROWSER_ANSWER
  case "$G2D_BROWSER_ANSWER" in
    y|Y|yes|YES|Yes)
      remove_global_toolset_blocks browser
      hermes --profile "$G2D_PROFILE" tools enable --platform g2 browser
      ;;
    *)
      fail "personal browser access was not enabled"
      ;;
  esac
fi

if [[ "$G2D_WITH_ANDROID" == "true" ]]; then
  G2D_ANDROID_CHECKOUT="$G2D_TEMP_DIR/android"
  mkdir -p -- "$G2D_ANDROID_CHECKOUT"
  git -C "$G2D_ANDROID_CHECKOUT" init -q
  git -C "$G2D_ANDROID_CHECKOUT" remote add origin "$G2D_APP_REPO"
  git -C "$G2D_ANDROID_CHECKOUT" fetch --depth 1 origin "$G2D_APP_REF"
  git -C "$G2D_ANDROID_CHECKOUT" checkout --detach -q FETCH_HEAD
  [[ "$(git -C "$G2D_ANDROID_CHECKOUT" rev-parse HEAD)" == "$G2D_APP_REF" ]] \
    || fail "Android source checkout did not match the lock"
  G2D_ANDROID_INSTALLER="$G2D_ANDROID_CHECKOUT/scripts/build-sign-install-from-github.sh"
  [[ -f "$G2D_ANDROID_INSTALLER" ]] \
    || fail "the pinned Android source does not contain its safe installer"
  G2D_ANDROID_ARGS=(--ref "$G2D_APP_REF")
  if [[ -n "$G2D_ADB_SERIAL" ]]; then
    G2D_ANDROID_ARGS+=(--serial "$G2D_ADB_SERIAL")
  fi
  if [[ -n "$G2D_ADB_PORT" ]]; then
    G2D_ANDROID_ARGS+=(--adb-port "$G2D_ADB_PORT")
  fi
  bash "$G2D_ANDROID_INSTALLER" "${G2D_ANDROID_ARGS[@]}"
fi

if [[ "$G2D_START_GATEWAY" == "true" ]]; then
  if [[ "$G2D_PROFILE_EXISTS" == "true" ]]; then
    hermes --profile "$G2D_PROFILE" gateway restart
  else
    hermes --profile "$G2D_PROFILE" gateway install --start-now --start-on-login
  fi
fi

printf '\nHermes G2 is installed from pinned source.\n'
printf 'Profile: %s\n' "$G2D_PROFILE"
if [[ -n "$G2D_BACKUP_PATH" ]]; then
  printf 'Rollback snapshot: %s\n' "$G2D_BACKUP_PATH"
fi
if [[ "$G2D_START_GATEWAY" != "true" ]]; then
  printf 'The gateway was not started. Start it when ready with:\n'
  printf '  hermes --profile %q gateway install --start-now --start-on-login\n' "$G2D_PROFILE"
fi
printf 'Copy the private G2 token from the installed profile .env into the phone app.\n'
