
import argparse
import asyncio
import json
import re
import sys
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
WINDOW_SECONDS = 30
PORT_FLAP_THRESHOLD = 4       
AUTH_FAILURE_THRESHOLD = 3   
ALERTS_OUTPUT = Path("alerts.json")

# Regex patterns for the two event types we care about.
# Real syslog formats vary by vendor -- these match common Cisco-style
# and Linux sshd-style lines. Document any format you actually test against.
IFACE_TRANSITION_RE = re.compile(
    r"(?P<ts>\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2}).*?"
    r"(?:Interface|iface)\s+(?P<iface>[\w/]+)\W*?.*?(?P<state>up|down)",
    re.IGNORECASE,
)

AUTH_FAILURE_RE = re.compile(
    r"(?P<ts>\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2}).*?"
    r"(?:sshd|auth).*?(?:failed|failure).*?"
    r"(?:user=)?(?P<user>\S+)?\s*(?:src=|from\s+)(?P<src>\d{1,3}(?:\.\d{1,3}){3})",
    re.IGNORECASE,
)

CURRENT_YEAR = datetime.now().year


def parse_syslog_timestamp(ts_str: str) -> datetime:
    """Parse a 'Mon DD HH:MM:SS' syslog timestamp, assuming current year."""
    return datetime.strptime(f"{CURRENT_YEAR} {ts_str}", "%Y %b %d %H:%M:%S")


class EventTracker:
    """
    Tracks timestamps of events per key (e.g. per interface, per source IP)
    inside a sliding time window, and reports when a threshold is crossed.
    """

    def __init__(self, window_seconds: int):
        self.window = timedelta(seconds=window_seconds)
        self._events: dict[str, deque] = defaultdict(deque)

    def record(self, key: str, timestamp: datetime) -> int:
        """Record an event and return the current count within the window."""
        dq = self._events[key]
        dq.append(timestamp)
        cutoff = timestamp - self.window
        while dq and dq[0] < cutoff:
            dq.popleft()
        return len(dq)


class AlertWriter:
    """Appends structured alerts to a JSON file, one JSON object per line
    (JSON Lines format) so the file can be tailed/streamed by a dashboard
    without re-parsing the whole file on every write."""

    def __init__(self, path: Path):
        self.path = path
        self.path.touch(exist_ok=True)

    def write(self, alert: dict) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps(alert) + "\n")
        print(f"ALERT  {alert['type']:<20} {json.dumps(alert)}")


async def tail_file(path: Path, replay: bool = False):
    """
    Async generator that yields new lines appended to a file.
    If replay=True, reads the whole existing file first (useful for
    testing against a static sample log instead of a live growing one).
    """
    with path.open("r") as f:
        if not replay:
            f.seek(0, 2)  # jump to end -- only new lines from here
        while True:
            line = f.readline()
            if line:
                yield line.rstrip("\n")
            else:
                if replay:
                    return
                await asyncio.sleep(0.5)


async def monitor(path: Path, replay: bool = False):
    iface_tracker = EventTracker(WINDOW_SECONDS)
    auth_tracker = EventTracker(WINDOW_SECONDS)
    writer = AlertWriter(ALERTS_OUTPUT)

    async for line in tail_file(path, replay=replay):
        iface_match = IFACE_TRANSITION_RE.search(line)
        if iface_match:
            ts = parse_syslog_timestamp(iface_match.group("ts"))
            iface = iface_match.group("iface")
            count = iface_tracker.record(iface, ts)
            if count >= PORT_FLAP_THRESHOLD:
                writer.write({
                    "type": "port_flap",
                    "iface": iface,
                    "count": count,
                    "window_s": WINDOW_SECONDS,
                    "detected_at": ts.isoformat(),
                })
            continue

        auth_match = AUTH_FAILURE_RE.search(line)
        if auth_match:
            ts = parse_syslog_timestamp(auth_match.group("ts"))
            src = auth_match.group("src")
            count = auth_tracker.record(src, ts)
            if count >= AUTH_FAILURE_THRESHOLD:
                writer.write({
                    "type": "auth_failure_burst",
                    "src": src,
                    "count": count,
                    "window_s": WINDOW_SECONDS,
                    "detected_at": ts.isoformat(),
                })
            continue


def main():
    parser = argparse.ArgumentParser(description="Async network log monitor")
    parser.add_argument("--file", required=True, help="Path to log file to monitor")
    parser.add_argument("--replay", action="store_true",
                         help="Read existing file once and exit, instead of tailing live")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        print(f"ERROR: log file not found: {path}", file=sys.stderr)
        sys.exit(1)

    try:
        asyncio.run(monitor(path, replay=args.replay))
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()