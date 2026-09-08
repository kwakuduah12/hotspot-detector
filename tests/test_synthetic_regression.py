"""End-to-end: a planted serialize slowdown must be reported as a regression.

This test is allowed to fail the suite if the detector misses the slowdown.
Product PRs still merge when perf.yml reports a regression.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from hotspot_detector.compare import compare_runs
from hotspot_detector.manifest import load_manifest
from hotspot_detector.runner import parse_workload_stdout, wait_for_health

PLANTED_SLOWDOWN_MS = 150
# Sleep is 150ms; leave slack for natural timing variance and cold-start effects.
MIN_PLANTED_DELTA_MS = 75


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@contextmanager
def _demo_server(repo_root, extra_env: dict[str, str] | None = None) -> Iterator[str]:
    port = _free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo_root), str(repo_root / "src"), env.get("PYTHONPATH", "")]
    )
    if extra_env:
        env.update(extra_env)
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


def _ingest_samples(base_url: str, repo_root) -> dict[str, list[float]]:
    env = os.environ.copy()
    env["HOTSPOT_BASE_URL"] = base_url
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
    samples: dict[str, list[float]] = {}
    for row in parse_workload_stdout(completed.stdout):
        samples.setdefault(row["operation"], []).append(float(row["duration_ms"]))
    return samples


@pytest.mark.integration
def test_planted_slowdown_is_regression(repo_root, manifest_path):
    with _demo_server(repo_root) as clean_url:
        clean = _ingest_samples(clean_url, repo_root)
    with _demo_server(repo_root, {"HOTSPOT_SLOWDOWN_MS": str(PLANTED_SLOWDOWN_MS)}) as slow_url:
        planted = _ingest_samples(slow_url, repo_root)

    compared = compare_runs(
        {"workloads": {"ingest_bulk": clean}},
        {"workloads": {"ingest_bulk": planted}},
        load_manifest(manifest_path),
    )
    serialize = next(op for op in compared.operations if op.operation == "serialize")
    assert serialize.status == "regression"
    assert serialize.current_ms is not None
    assert serialize.baseline_ms is not None
    assert serialize.current_ms >= serialize.baseline_ms + MIN_PLANTED_DELTA_MS
    assert compared.overall == "regression"
