# Optional personal integrations

The public base profile stops at the glasses/app bridge and its fixed workflow
MCP. Personal services are deliberately added after installation so the
repository never needs a copy of anyone's accounts, addresses, cookies, or
device names.

## Private owner tools

`--enable-owner-tools` is an explicit, non-default choice for a locally owned
profile. After a second consent prompt it enables these nine G2 toolsets:

- `browser`, `terminal`, `file`, `skills`, and `web`;
- `memory`, `session_search`, `cronjob`, and `computer_use`.

This option does not enable code execution, delegation, email, Home Assistant,
calendar servers, printer servers, or any account credential. It removes the
global block only for those nine approved names, so review any other gateway
later enabled in the same Hermes profile. The default remains an empty G2
toolset list.

## Signed-in browser

Run setup with `--enable-personal-browser` only if you want the G2 profile to
use Hermes' local browser tools. The flag enables the toolset after an explicit
consent prompt; it does not import a browser profile.

Configure the browser through Hermes on the installed machine. Review which
local profile it uses before allowing access: a signed-in profile may expose
email, purchases, messages, saved addresses, and any website action available
to that login. Browser output is untrusted web content and should not silently
authorize a later device or account mutation.

The browser flag and the broader owner-tools flag only enable Hermes' browser
toolset. They do not copy cookies, select a Brave profile, or guarantee that
Hermes is attached to an already logged-in browser session.

The experimental `hermes-public-web` package is not included. Its current
resource and prompt-injection boundaries are not sufficient for the privileged
G2 profile.

## Conversate cues

The bridge exposes a fast, tool-free auxiliary model slot for opt-in question
and topic cues. The public config leaves provider selection on `auto` and sends
nothing until the phone enables the feature.

Choose a local model in the profile's Hermes settings if transcripts must stay
on the machine. Choosing a remote provider sends the bounded recent transcript
to that provider under its data policy. This cue lane cannot use device tools
or launch a full agent turn.

## Home Assistant

Add Home Assistant through Hermes' standard setup or MCP screen. Use a
least-privilege token and review exposed entities/tools. The distribution does
not know or ship a server address, token, entity aliases, or home-specific
automation policy.

## Email

Email access is not in the public pack. Configure an independently licensed
email connector through Hermes and grant only the mailboxes/actions wanted.
No email password, OAuth token, watch database, or personal filtering rule is
copied from the distribution author.

## Calendar

The G2 workflow can read the phone's bounded calendar agenda after phone-side
consent. A separate host calendar MCP is optional and is not required for that
workflow. Add a host calendar connector only when users want that second data
source and have reviewed its account permissions.

## Printers

Printer scripts and addresses are machine-specific and are not included. Add a
printer MCP locally, then expose only the operations and devices wanted on the
G2 platform.

## Firmware

Firmware, OTA images, custom firmware builds, and flashing tools are outside
this distribution. The Android app and Hermes integration do not require the
repository to redistribute Even firmware.
