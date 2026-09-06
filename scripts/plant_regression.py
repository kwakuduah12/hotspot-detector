"""Plant a synthetic serialize regression for a test PR / local proof.

Does not modify source. Runs the gate with HOTSPOT_SLOWDOWN_MS=150 so
serialize is deliberately slow. Exits 0 if the detector reports a
regression; exits 1 if it misses it.

Usage:
  python scripts/plant_regression.py
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def main() -> None:
    port = _free_port()
    env = os.environ.copy()
    env["HOTSPOT_SLOWDOWN_MS"] = "150"
    env["HOTSPOT_PORT"] = str(port)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), str(ROOT / "src"), env.get("PYTHONPATH", "")]
    )
    changed = ROOT / "results" / "synthetic-changed.txt"
    results = ROOT / "results" / "synthetic"
    changed.parent.mkdir(parents=True, exist_ok=True)
    changed.write_text("demo_service/app/ingest.py\n")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "hotspot_detector.cli",
            "gate",
            "--manifest",
            str(ROOT / "demo_service" / "hotspot-manifest.yaml"),
            "--changed-files",
            str(changed),
            "--baselines",
            str(ROOT / "demo_service" / "baselines.yaml"),
            "--results-dir",
            str(results),
            "--no-docker",
            "--strict",
        ],
        cwd=ROOT,
        env=env,
        check=False,
    )
    compare_path = results / "compare.json"
    if not compare_path.exists():
        print("gate did not write compare.json", file=sys.stderr)
        sys.exit(1)
    compare = json.loads(compare_path.read_text())
    serialize = [
        op for op in compare.get("operations", []) if op.get("operation") == "serialize"
    ]
    if serialize and serialize[0].get("status") == "regression":
        print("Synthetic regression caught.")
        sys.exit(0)
    print(f"Detector missed the planted slowdown: {compare}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
