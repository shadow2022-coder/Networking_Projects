# Networking_Projects
This repo contains the network releated projects
# Async Network Log & Event Monitor

## Overview

A Python `asyncio`-based tool that tails infrastructure log/syslog files in real time, extracts network events using regular expressions, tracks stateful patterns within a sliding time window (e.g. repeated interface flaps, bursts of authentication failures), and writes structured alerts to a JSON Lines file for downstream dashboarding or alerting.

Built with the standard library only — no external frameworks — to demonstrate the underlying async and pattern-matching mechanics directly.

## Why this design

- **`asyncio` instead of threads**: the tail loop is I/O-bound (waiting on new log lines), which is exactly the case asyncio is built for. In a real deployment this coroutine would run alongside other monitoring tasks (health checks, metric polling) inside one event loop without the overhead of separate threads.
- **Sliding window via `deque`**: each tracked key (interface name, source IP) has its own deque of event timestamps. Old timestamps outside the window are dropped from the left in O(1), which is cheaper than rescanning a list of all events on every check — matters when this runs continuously against a busy log.
- **JSON Lines output**: alerts are appended one JSON object per line rather than rewriting a JSON array each time. This lets the file be tailed/streamed by a dashboard process without re-parsing the whole file on every write.

## What it detects

| Pattern | Trigger | Window |
|---|---|---|
| Port flap | An interface transitions up/down 4+ times | 30 seconds |
| Auth failure burst | 3+ failed logins from the same source IP | 30 seconds |

Thresholds and window size are configured as constants at the top of `log_monitor.py` — change them to match your actual log volume and tolerance.

## Usage

**Live tailing (production mode):**
```
python3 log_monitor.py --file /var/log/syslog
```
This waits at the end of the file and processes new lines as they're written — this is the real-world mode.

**Replay mode (for testing against a static sample log):**
```
python3 log_monitor.py --file sample_logs/test.log --replay
```
Reads the whole file once and exits. Use this to validate behavior without needing a live growing log.

## Verified test run

Ran against `sample_logs/test.log`, which contains 5 up/down transitions on one interface within 14 seconds, and 3 auth failures from the same source IP within 8 seconds. Actual output:

```
ALERT  port_flap  {"type": "port_flap", "iface": "GigabitEthernet0/1", "count": 4, "window_s": 30, "detected_at": "2026-07-08T14:02:22"}
ALERT  port_flap  {"type": "port_flap", "iface": "GigabitEthernet0/1", "count": 5, "window_s": 30, "detected_at": "2026-07-08T14:02:25"}
ALERT  auth_failure_burst  {"type": "auth_failure_burst", "src": "10.4.2.9", "count": 3, "window_s": 30, "detected_at": "2026-07-08T14:03:09"}
```
Correctly fired once the 4th flap crossed the threshold, again on the 5th (see Known Limitations), and once on the 3rd auth failure.

## Known limitations (documented honestly, not hidden)

- **No alert de-duplication**: once a threshold is crossed, every subsequent event in the same window re-fires an alert (see the two `port_flap` alerts above from one burst). A production version would suppress repeat alerts for the same key until the window resets, or use a cooldown timer. This is a deliberate scoping decision for v1 — call it out if asked in an interview rather than pretending it's not there.
- **Regex assumes specific log formats**: patterns are tuned to Cisco-style `%LINK-3-UPDOWN` interface messages and Linux `sshd` failure messages. Real environments use varied formats across vendors; this would need per-source regex profiles for production use.
- **Timestamp parsing assumes current year**: standard syslog format omits the year. This will misparse logs from a previous year if replayed later — a real fix would pull the year from file metadata or require ISO 8601 timestamps upstream.
- **No log rotation handling**: if the log file is rotated (renamed and a new file created) while tailing, this script keeps reading the old file handle. Production tools like `logrotate`-aware tails reopen the file by inode change detection — not implemented here.

## Possible extensions (not built, listed for interview discussion)

- De-duplicate alerts per key with a cooldown window
- Config file for thresholds/patterns instead of hardcoded constants
- Send alerts to a real sink (webhook, Slack, PagerDuty) instead of just a JSON file
- Multi-file tailing for monitoring several devices at once

## Repository Structure

```
net-log-monitor/
├── README.md
├── log_monitor.py
├── sample_logs/
│   └── test.log
└── alerts.json          (generated on run — do not commit if it contains real data)
```

## Requirements

- Python 3.9+ (uses `dict[str, deque]` type hint syntax)
- No external packages required