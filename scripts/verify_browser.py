"""Run a disposable API and isolated Chrome tests. No user credentials are used."""

import os
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.chdir(ROOT)
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", 8001))
        except OSError:
            raise SystemExit("Port 8001 is already in use; no existing process was changed.") from None
    cache = ROOT / ".cache"
    (cache / "tmp").mkdir(parents=True, exist_ok=True)
    (ROOT / "artifacts").mkdir(exist_ok=True)
    # SQLite backup is a consistent snapshot, including WAL writes.
    with sqlite3.connect(ROOT / "database" / "finops.db") as source:
        with sqlite3.connect(cache / "e2e.db") as target:
            source.backup(target)
    source.close()
    target.close()
    environment = os.environ | {
        "DATABASE_URL": f"sqlite:///{(cache / 'e2e.db').as_posix()}",
        "FINOPS_ADMIN_KEY": "disposable-e2e-only-key-not-a-user-secret",
        "FINOPS_E2E_KEY": "disposable-e2e-only-key-not-a-user-secret",
        "E2E_BASE_URL": "http://127.0.0.1:8001",
        "GEMINI_API_KEY": "",
        "NOTIFICATION_MODE": "simulated",
        "TEMP": str(cache / "tmp"),
        "TMP": str(cache / "tmp"),
    }
    with (ROOT / "artifacts" / "e2e-server.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8001",
            ],
            env=environment,
            stdout=log,
            stderr=log,
        )
        try:
            for _ in range(80):
                if server.poll() is not None:
                    raise RuntimeError("Test API did not start. See artifacts/e2e-server.log.")
                try:
                    with urlopen("http://127.0.0.1:8001/api/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    time.sleep(0.25)
            else:
                raise RuntimeError("Test API readiness timeout")
            npm = "npm.cmd" if os.name == "nt" else "npm"
            result = subprocess.run(
                [npm, "run", "test:e2e", "--", *sys.argv[1:]],
                cwd=ROOT / "frontend",
                env=environment,
                check=False,
            )
            return result.returncode
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


if __name__ == "__main__":
    raise SystemExit(main())
