"""Triage Report a problem submissions in the live Realtime Database.

Uses an access token of the owner's personal Google account, which bypasses the
database rules, so it can read, mark and delete reports the app may only create.

    python src/reports.py                  # unmarked reports, screenshots to --shots
    python src/reports.py --all
    python src/reports.py mark ID issue --issue 142
    python src/reports.py mark ID noise
    python src/reports.py clean            # delete noise, and the rest 30 days after marking
"""

import argparse
import base64
import json
import subprocess
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATABASE = "https://ksv-volleyball-xszpo-default-rtdb.europe-west1.firebasedatabase.app"
ACCOUNT = "daniel.szponar@gmail.com"
STATUSES = ("issue", "duplicate", "noise")
KEEP_DAYS = 30


def token() -> str:
    """Returns an access token for the owner's personal account, never the work one."""
    out = subprocess.run(
        ["gcloud", "auth", "print-access-token", f"--account={ACCOUNT}"], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def call(method: str, path: str, auth: str, body: object = None, query: str = "") -> Any:
    """Sends one REST request to the database and returns the decoded JSON."""
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        f"{DATABASE}/{path}.json{query}", data=data, method=method, headers={"Authorization": f"Bearer {auth}"}
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read() or b"null")


def when(ms: float) -> str:
    """Formats a Firebase millisecond timestamp in UTC."""
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%d %H:%M")


def show(auth: str, everything: bool, shots: Path) -> None:
    """Prints the reports and saves their screenshots as <id>.jpg in shots."""
    ids = sorted(call("GET", "reports", auth, query="?shallow=true") or {})
    shown = 0
    for report_id in ids:
        report = call("GET", f"reports/{report_id}", auth)
        if not report or (report.get("status") and not everything):
            continue
        shown += 1
        image = report.pop("image", "")
        if image:
            shots.mkdir(parents=True, exist_ok=True)
            (shots / f"{report_id}.jpg").write_bytes(base64.b64decode(image.split(",", 1)[1]))
        mark = (
            f" [{report['status']}{' #' + str(report['issue']) if report.get('issue') else ''}]"
            if report.get("status")
            else ""
        )
        print(f"{report_id}{mark}  {when(report['createdAt'])}  {report.get('tab')} · {report.get('view')}")
        print(f"  role {report.get('role')} · {report.get('rules')} · {report.get('theme')} · {report.get('viewport')}")
        print(f"  ua {report.get('ua', '')}")
        print(f"  screenshot {shots / (report_id + '.jpg') if image else 'none'}")
        print(f"  comment: {report.get('comment', '')}")
    print(f"{shown} report(s){'' if everything else ' unmarked'} of {len(ids)}")


def mark(auth: str, report_id: str, status: str, issue: int | None) -> None:
    """Sets the triage status of one report."""
    if call("GET", f"reports/{report_id}/createdAt", auth) is None:
        sys.exit(f"no report {report_id}")
    fields: dict[str, object] = {"status": status, "markedAt": int(time.time() * 1000)}
    if issue is not None:
        fields["issue"] = issue
    call("PATCH", f"reports/{report_id}", auth, fields)
    print(f"{report_id} marked {status}{f' #{issue}' if issue else ''}")


def clean(auth: str) -> None:
    """Deletes noise at once and other marked reports KEEP_DAYS after marking."""
    cutoff = time.time() * 1000 - KEEP_DAYS * 86400000
    for report_id in sorted(call("GET", "reports", auth, query="?shallow=true") or {}):
        status = call("GET", f"reports/{report_id}/status", auth)
        marked = call("GET", f"reports/{report_id}/markedAt", auth) or 0
        if status == "noise" or (status and marked < cutoff):
            call("DELETE", f"reports/{report_id}", auth)
            print(f"{report_id} deleted ({status})")


def main() -> None:
    """Parses the command line and runs one command."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="list marked reports too")
    parser.add_argument("--shots", type=Path, default=Path("/tmp/ksv-reports"), help="where screenshots go")
    commands = parser.add_subparsers(dest="command")
    marker = commands.add_parser("mark")
    marker.add_argument("id")
    marker.add_argument("status", choices=STATUSES)
    marker.add_argument("--issue", type=int)
    commands.add_parser("clean")
    args = parser.parse_args()
    auth = token()
    if args.command == "mark":
        mark(auth, args.id, args.status, args.issue)
    elif args.command == "clean":
        clean(auth)
    else:
        show(auth, args.all, args.shots)


if __name__ == "__main__":
    main()
