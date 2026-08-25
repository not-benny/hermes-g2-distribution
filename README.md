# Hermes G2 Distribution

This repository turns the public Hermes G2 projects into one reviewable setup.
It installs a fresh Hermes profile, the phone/glasses transport, the fixed
13-tool workflow MCP, and, when requested, the Android app built from source.

The profile contains personality and safe defaults only. Weather, trains,
tasks, timers, apps, media, navigation, notifications, health summaries, and
calendar agenda behavior live in the pinned workflow MCP rather than in
`SOUL.md`.

## What one setup installs

- an isolated `even-g2` Hermes profile through `hermes profile install`;
- the Apache-2.0 G2 bridge and workflow MCP through one exact-SHA Hermes
  plugin pack;
- an exact digest grant, shown to the operator before the workflow package can
  receive G2 session context;
- an isolated launch check that rejects any workflow inventory other than the
  reviewed 13 tools;
- a private phone-to-Hermes token stored only in the installed profile;
- safe loopback gateway defaults, or an operator-supplied Tailscale/private
  address with TLS;
- optionally, an APK rebuilt and signed locally from an exact GitHub commit,
  then installed with Android's data-preserving replacement path.

It does not include firmware, a prebuilt APK, browser cookies, email
credentials, Home Assistant details, printer definitions, calendar account
data, personal files, private addresses, TLS keys, or signing keys.

## Before setup

The supported full host is currently Linux with:

- Hermes Agent 0.20.4 or newer, including the digest-bound portable MCP
  capability baseline pinned in [`sources.lock.json`](sources.lock.json);
- Git and Python 3;
- Playwright and websockets available in the Hermes Python environment;
- the reviewed, regular Brave ELF at `/opt/brave-bin/brave` for train and
  weather feeds;
- for a phone on another device, a Tailscale or private-LAN address plus a TLS
  certificate and key;
- for the optional Android build, the prerequisites checked by the app's own
  source installer: Node/npm, JDK 21, Android SDK build-tools 35.0.1, Android
  NDK 27.2.12479018, a compatible signing keystore, and authorized ADB.

Hermes itself is a prerequisite. This repository verifies its minimum runtime
surfaces but does not replace or modify the Hermes installation.

## Install

Clone first so the code can be reviewed. The project intentionally does not
offer a `curl | bash` shortcut.

```bash
git clone --branch v0.1.1 --depth 1 \
  https://github.com/not-benny/hermes-g2-distribution.git
cd hermes-g2-distribution
./scripts/bootstrap.sh --distribution-source "$PWD" --dry-run
./scripts/bootstrap.sh --distribution-source "$PWD"
```

The setup shows the profile and plugin review screens. It asks separately
before granting the exact workflow package access to current G2 session
context. A blank token prompt generates a strong token without printing it.
Copy that token from the installed profile's private `.env` file into the
Android app.

## Where the G2 workflow MCP appears

The workflow MCP is installed as a Hermes **Agent Plugin MCP**. It therefore
may not appear in the web dashboard's **Your MCP servers** list, which is the
inventory of MCP servers configured manually for that profile (for example,
calendar, Home Assistant, or printers). This does not mean the workflow MCP is
missing.

Use Hermes' Agent Plugin inventory as the authoritative check:

```bash
hermes --profile even-g2 plugins list --plain --no-bundled
hermes --profile even-g2 plugins show hermes-g2-workflows
hermes --profile even-g2 plugins capabilities hermes-g2-workflows
```

The workflow entry should be enabled, and the capabilities view should show a
session-capability grant for the displayed package digest.

## Fixed workflow surface

The pinned workflow MCP exposes exactly 13 intent-complete tools:

- `g2_work_task_add`, `g2_kanban_task_create`, `g2_clock_set_timer`,
  `g2_clock_set_alarm`, `g2_reminder_create`, `g2_weather_present`, and
  `g2_train_departures_present`;
- `g2_apps_manage`, `g2_media_control`, `g2_navigation`, `g2_notifications`,
  `g2_health_summary`, and `g2_calendar_agenda`.

There is no generic phone-call, rendering, discovery, or raw Kanban tool.
Setup launches the exact installed package in isolated mode and requires this
complete name set before asking for the digest-bound session grant.

`g2_kanban_task_create` accepts an exact case-insensitive match to one active
Hermes Kanban board slug or display name, and that exact board must be named in
the current wearer utterance. Every task-store call in one wearer turn stays
bound to one exact destination. A missing or ambiguous board returns a typed,
bounded list of choices, but Hermes must ask for a fresh wearer turn and must
not silently choose from that list. Requests for the onboard or local task
board, Work Tasks, ordinary unqualified tasks, and unnamed board tasks use
`g2_work_task_add`; an explicit Kanban request without an exact board mutates
neither store. The Kanban workflow never falls back to the phone's Work Tasks
app. A successful call creates one blocked, unassigned card and does not start
a worker or decomposition. The native bridge binds retries to the original
board generation and payload. A known historical mismatch is a typed conflict;
an unrecoverable possible mutation stays outcome-unknown and is not recreated.
This fail-closed behavior prevents duplicate or resurrected cards.

One-shot reminders use a bounded, profile-local outbox. Pending reminder text
and schedule metadata remain plaintext in an owner-only `0600` file because
Hermes does not yet expose a gateway-safe OS-keyring primitive. Other processes
running as the same OS user can read that file. Delivered reminder text is
removed according to the bridge's bounded tombstone policy.

Loopback is the safe default. A typical remote-phone setup supplies its own
network identity and TLS files:

```bash
./scripts/bootstrap.sh \
  --bind YOUR_TAILSCALE_IP \
  --tls-cert /path/to/your/server.crt \
  --tls-key /path/to/your/server.key \
  --start-gateway
```

The setup refuses wildcard/public binds, requires TLS off loopback, and does
not generate or publish certificates.

To build and install the frozen Android source as part of the same run:

```bash
./scripts/bootstrap.sh \
  --with-android-app \
  --adb-serial YOUR_ADB_DEVICE \
  --adb-port 5037
```

The app's own installer fetches a second clean copy of the same exact commit,
builds the unsigned release, signs it locally, verifies package/version/signer,
and uses `adb install -r`. It never uninstalls the app or clears app data.
Signing passwords are supplied through the environment names documented by
the app repository; they are not accepted as command-line arguments here.

## Existing profiles and updates

Setup stops if the chosen profile already exists. This prevents an accidental
overwrite.

- `--update` updates a profile that was installed as a distribution. Hermes
  preserves its config, memories, sessions, auth, and `.env`.
- `--force-profile` is required to replace a hand-built or otherwise existing
  profile template. Setup first creates a local, credential-free Hermes export
  with owner-only permissions. Runtime memories, sessions, auth, and `.env`
  remain user-owned and are not replaced by the distribution.

Neither mode restarts a gateway unless `--start-gateway` is also given.

An install from the commands above records the reviewed local checkout as its
profile source. To update, fetch tags, inspect the proposed release and lock
changes, check out that exact tag, then run its setup script:

```bash
git fetch --tags origin
git checkout v0.1.1
./scripts/bootstrap.sh --distribution-source "$PWD" --update
```

Replace `v0.1.1` only with a newer tag you have reviewed. Do not update an
installed profile from a moving branch such as `main`.

## Personal integrations are opt-in

The base profile starts with no G2 platform toolsets. This keeps local files,
commands, browsing, history, scheduling, and desktop control unavailable until
the operator makes a separate choice.

`--enable-personal-browser` enables the local browser toolset only after a
second consent prompt. It does not copy a browser profile or choose a Brave
profile for the user. Signed-in browser access can reveal account data and
perform website actions, so each user must configure and review that boundary
locally. Setup verifies that this option adds only `browser` to the existing
G2 selection; platform defaults cannot silently widen that consent.

`--enable-owner-tools` is the broader private-owner option. After its own
consent prompt it enables exactly `browser`, `terminal`, `file`, `skills`,
`web`, `memory`, `session_search`, `cronjob`, and `computer_use` for G2. It
does not enable code execution, delegation, optional MCP servers, or any
account credential. Because Hermes' global disabled-toolset gate must be
lifted for those approved names, review any other gateway later enabled in the
same profile. Setup preserves existing G2 selections, adds only these nine,
and fails if the stored platform boundary differs.

```bash
./scripts/bootstrap.sh --enable-owner-tools
```

The browser toolset uses the browser backend configured in Hermes. Neither
owner-access option imports cookies nor guarantees that the backend is attached
to a logged-in Brave profile.

Home Assistant, email, calendars, and printers are not in the base pack. They
need per-user accounts, endpoints, or credentials and should be added through
Hermes' normal MCP/setup screens. See
[`docs/OPTIONAL-INTEGRATIONS.md`](docs/OPTIONAL-INTEGRATIONS.md).

## Reproducibility and updates

[`hermes-pack.yaml`](hermes-pack.yaml) pins both executable plugin repositories
to exact 40-character commits. [`sources.lock.json`](sources.lock.json) records
the matching Hermes capability baseline, the exact workflow package digest,
and the Android source commit. Setup checks the workflow digest both before and
after installation, before any session-context grant is written. The
distribution repository contains source and templates only.

The setup script defaults to its own local checkout, never to a mutable remote
branch. A profile installed from a tagged local checkout therefore updates from
that reviewed checkout. Fetch, inspect, and check out a newer exact release tag
before running `--update`; plugin and Android executable sources remain
exact-SHA pinned by that tag's lock and pack.

## Validation

```bash
python3 tests/validate_distribution.py --release
bash -n scripts/bootstrap.sh
python3 -m unittest discover -s tests -p 'test_*.py'
ruff check --no-cache scripts tests
shellcheck scripts/bootstrap.sh
```

The checks reject secret-shaped committed values, private/personal paths,
non-SHA executable pins, workflow instructions in `SOUL.md`, and unsafe Android
install commands.

## License

The distribution code and templates are Apache-2.0. The public
[`hermes-g2-bridge`](https://github.com/not-benny/hermes-g2-bridge) and
[`hermes-g2-workflows`](https://github.com/not-benny/hermes-g2-workflows)
projects are also Apache-2.0 and retain their own license and notice files. No
Even firmware or proprietary binary is redistributed here.
