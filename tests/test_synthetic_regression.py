"""End-to-end: a planted serialize slowdown must be reported as a regression.

This test is allowed to fail the suite if the detector misses the slowdown.
Product PRs still merge when perf.yml reports a regression.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys

import pytest

from hotspot_detector.compare import compare_runs
from hotspot_detector.manifest import load_manifest
from hotspot_detector.runner import parse_workload_stdout, wait_for_health


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture
def slow_server(repo_root):
    port = _free_port()
    env = os.environ.copy()
    env["HOTSPOT_SLOWDOWN_MS"] = "150"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo_root), str(repo_root / "src"), env.get("PYTHONPATH", "")]
    )
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "demo_service.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=repo_root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        wait_for_health(url, timeout=20)
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.mark.integration
def test_planted_slowdown_is_regression(slow_server, repo_root, manifest_path):
    env = os.environ.copy()
    env["HOTSPOT_BASE_URL"] = slow_server
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo_root), str(repo_root / "src"), env.get("PYTHONPATH", "")]
    )
    completed = subprocess.run(
        [sys.executable, "-m", "demo_service.workloads.ingest_bulk"],
        cwd=repo_root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    rows = parse_workload_stdout(completed.stdout)
    samples: dict[str, list[float]] = {}
    for row in rows:
        samples.setdefault(row["operation"], []).append(float(row["duration_ms"]))

    run = {"workloads": {"ingest_bulk": samples}}
    last_good = {
        "workloads": {
            "ingest_bulk": {
                "serialize": [100.0, 100.0, 100.0],
                "index": samples.get("index", [50.0]),
            }
        }
    }
    compared = compare_runs(last_good, run, load_manifest(manifest_path))
    serialize = next(op for op in compared.operations if op.operation == "serialize")
    assert serialize.status == "regression"
    assert serialize.current_ms is not None
    assert serialize.current_ms >= 150
    assert compared.overall == "regression"
