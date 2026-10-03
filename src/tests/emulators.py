"""Runs a test script under the Firebase Auth and Realtime Database emulators.

The ports come from KSV_EMU_DB_PORT and KSV_EMU_AUTH_PORT (default 9000 and 9099); the emulator hub and
logging take the auth port + 1 and + 2. They go into a temporary copy of infra/firebase.json, so worktrees on
other ports can run their emulators at the same time. ``firebase emulators:exec`` passes the hosts to the
script in FIREBASE_DATABASE_EMULATOR_HOST and FIREBASE_AUTH_EMULATOR_HOST.
"""

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INFRA = ROOT / "infra"
PROJECT = "ksv-volleyball-xszpo"


def ports() -> dict[str, int]:
    """The emulator ports by emulator name, from the environment or the defaults."""
    auth = int(os.environ.get("KSV_EMU_AUTH_PORT", "9099"))
    return {
        "database": int(os.environ.get("KSV_EMU_DB_PORT", "9000")),
        "auth": auth,
        "hub": auth + 1,
        "logging": auth + 2,
    }


def config(directory: Path) -> Path:
    """Writes infra/firebase.json with this run's ports into directory and returns its path."""
    settings = json.loads((INFRA / "firebase.json").read_text())
    settings["database"]["rules"] = str(INFRA / settings["database"]["rules"])
    for name, port in ports().items():
        settings["emulators"][name] = {"host": "127.0.0.1", "port": port}
    path = directory / "firebase.json"
    path.write_text(json.dumps(settings, indent=2))
    return path


def run_under_emulators(script: str) -> None:
    """Restarts script inside ``firebase emulators:exec`` and always stops the emulators afterwards."""
    busy = []
    for port in ports().values():
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                busy.append(port)
    if busy:
        sys.exit(
            f"Port(s) {busy} are in use, probably by an emulator left from an earlier run. "
            f"Stop it first, for example: lsof -ti :{busy[0]} | xargs kill"
        )
    env = dict(os.environ)
    env["PATH"] = "/opt/homebrew/opt/openjdk/bin:" + env.get("PATH", "")
    firebase = shutil.which("firebase", path=env["PATH"])
    assert firebase, "Firebase CLI not found; install it with npm install -g firebase-tools"
    command = " ".join(f'"{arg}"' for arg in (sys.executable, Path(script).resolve(), *sys.argv[1:]))
    with tempfile.TemporaryDirectory(prefix="ksv-emulators-") as directory:
        process = subprocess.Popen(
            [
                firebase,
                "emulators:exec",
                "--only",
                "auth,database",
                "--project",
                PROJECT,
                "--config",
                str(config(Path(directory))),
                command,
            ],
            cwd=INFRA,
            env=env,
            start_new_session=True,
        )
        try:
            code = process.wait()
        except KeyboardInterrupt:
            code = 130
        finally:
            # The emulators run as Java children in the same session; kill the whole group so none is left behind.
            try:
                os.killpg(process.pid, signal.SIGTERM)
                time.sleep(1)
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            (INFRA / "database-debug.log").unlink(missing_ok=True)
    sys.exit(code)
