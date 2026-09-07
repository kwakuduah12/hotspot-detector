"""Provision a test environment and execute matched workloads."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

from hotspot_detector.compare import median
from hotspot_detector.manifest import Manifest

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def is_dry_run() -> bool:
    return os.environ.get("HOTSPOT_DRY_RUN", "").strip() in {"1", "true", "TRUE", "yes"}


def docker_available() -> bool:
    return shutil.which("docker") is not None


def wait_for_health(base_url: str, timeout: float = 40.0) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            response = httpx.get(f"{base_url.rstrip('/')}/health", timeout=1.0)
            if response.status_code == 200:
                return
            last_error = f"status {response.status_code}"
        except Exception as exc:  # noqa: BLE001 — probe until timeout
            last_error = str(exc)
        time.sleep(0.25)
    raise RuntimeError(f"service at {base_url} did not become healthy: {last_error}")


def _compose_env(project: str) -> dict[str, str]:
    env = os.environ.copy()
    env["COMPOSE_PROJECT_NAME"] = project
    return env


def _compose_up(repo_root: Path, project: str = "hotspot") -> None:
    subprocess.run(
        ["docker", "compose", "up", "-d", "--build"],
        cwd=repo_root,
        env=_compose_env(project),
        check=True,
    )


def _compose_down(repo_root: Path, project: str = "hotspot") -> None:
    subprocess.run(
        ["docker", "compose", "down"],
        cwd=repo_root,
        env=_compose_env(project),
        check=False,
    )


def _start_local(repo_root: Path, port: int) -> subprocess.Popen:
    env = os.environ.copy()
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
    return proc


def parse_workload_stdout(stdout: str) -> list[dict]:
    text = stdout.strip()
    if not text:
        raise ValueError("workload produced empty stdout")
    payload = json.loads(text)
    if not isinstance(payload, list):
        raise ValueError("workload stdout must be a JSON array")
    return payload


def resolve_command(command: list[str]) -> list[str]:
    if command and command[0] in {"python", "python3"}:
        return [sys.executable, *command[1:]]
    return command


def run_workload_command(
    command: list[str],
    *,
    repo_root: Path,
    base_url: str,
    repeats: int,
) -> dict[str, list[float]]:
    samples: dict[str, list[float]] = {}
    env = os.environ.copy()
    env["HOTSPOT_BASE_URL"] = base_url
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo_root), str(repo_root / "src"), env.get("PYTHONPATH", "")]
    )
    for _ in range(repeats):
        completed = subprocess.run(
            resolve_command(command),
            cwd=repo_root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        for row in parse_workload_stdout(completed.stdout):
            name = row["operation"]
            samples.setdefault(name, []).append(float(row["duration_ms"]))
    return samples


def run_workloads(
    manifest: Manifest,
    workload_ids: list[str],
    *,
    repo_root: Path,
    output_path: Path,
    prefer_docker: bool = True,
    harness_root: Path | None = None,
    compose_project: str = "hotspot",
    role: str | None = None,
    git_sha: str | None = None,
) -> dict:
    """Run workloads against *repo_root* (the service under test).

    *harness_root* is the tree that supplies workload commands. For last-good
    vs first-bad, pass the merge-base worktree so a PR cannot shrink N.
    """
    base_url = os.environ.get("HOTSPOT_BASE_URL", DEFAULT_BASE_URL)
    port = int(os.environ.get("HOTSPOT_PORT", "8000"))
    if "HOTSPOT_BASE_URL" not in os.environ:
        base_url = f"http://127.0.0.1:{port}"

    plan = []
    for workload_id in workload_ids:
        spec = manifest.workloads[workload_id]
        plan.append(
            {
                "id": workload_id,
                "command": spec.command,
                "repeats": spec.repeats,
            }
        )

    command_root = harness_root or repo_root

    def _annotate(payload: dict) -> dict:
        if role:
            payload["role"] = role
        if git_sha:
            payload["git_sha"] = git_sha
        payload["sut_root"] = str(repo_root)
        payload["harness_root"] = str(command_root)
        return payload

    if is_dry_run():
        payload = _annotate(
            {
                "dry_run": True,
                "service_area": manifest.service_area,
                "base_url": base_url,
                "would_provision": "docker" if prefer_docker and docker_available() else "local",
                "workloads": {item["id"]: {} for item in plan},
                "plan": plan,
            }
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2) + "\n")
        return payload

    used_docker = prefer_docker and docker_available()
    local_proc: subprocess.Popen | None = None
    try:
        if used_docker:
            _compose_up(repo_root, compose_project)
        else:
            local_proc = _start_local(repo_root, port)
        wait_for_health(base_url)

        run_payload: dict = _annotate(
            {
                "dry_run": False,
                "service_area": manifest.service_area,
                "base_url": base_url,
                "environment": "docker" if used_docker else "local",
                "workloads": {},
                "medians": {},
            }
        )
        for item in plan:
            samples = run_workload_command(
                item["command"],
                repo_root=command_root,
                base_url=base_url,
                repeats=item["repeats"],
            )
            run_payload["workloads"][item["id"]] = samples
            run_payload["medians"][item["id"]] = {
                name: median(values) for name, values in samples.items()
            }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(run_payload, indent=2) + "\n")
        return run_payload
    finally:
        if used_docker:
            _compose_down(repo_root, compose_project)
        if local_proc is not None:
            local_proc.terminate()
            try:
                local_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                local_proc.kill()
