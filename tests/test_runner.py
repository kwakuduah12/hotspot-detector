import json

import pytest

from hotspot_detector.cli import app
from hotspot_detector.runner import (
    compose_recipe_digest,
    environment_fingerprint,
    parse_workload_stdout,
    resolve_command,
    wait_for_health,
)


def test_environment_fingerprint_has_runtime_python_and_machine():
    fp = environment_fingerprint("docker")
    assert fp["runtime"] == "docker"
    assert fp["python"]
    assert fp["machine"]
    assert fp["system"]
    assert "compose" not in fp


def test_environment_fingerprint_includes_compose_recipe(repo_root):
    fp = environment_fingerprint("docker", repo_root=repo_root)
    assert fp["compose"]
    assert fp["compose"] == compose_recipe_digest(repo_root)


def test_compose_recipe_digest_changes_when_dockerfile_changes(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM python:3.12-slim\n")
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    first = compose_recipe_digest(tmp_path)
    (tmp_path / "Dockerfile").write_text("FROM python:3.13-slim\n")
    assert compose_recipe_digest(tmp_path) != first


def test_resolve_command_rewrites_python():
    resolved = resolve_command(["python", "-m", "demo_service.workloads.ingest_bulk"])
    assert resolved[0] != "python"
    assert resolved[1:] == ["-m", "demo_service.workloads.ingest_bulk"]


def test_resolve_command_leaves_other_binaries():
    assert resolve_command(["uvicorn", "app:app"]) == ["uvicorn", "app:app"]


def test_parse_workload_stdout_happy_path():
    rows = parse_workload_stdout(
        '[{"operation": "serialize", "duration_ms": 12.5}]\n'
    )
    assert rows[0]["operation"] == "serialize"
    assert rows[0]["duration_ms"] == 12.5


def test_parse_workload_stdout_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        parse_workload_stdout("  \n")


def test_parse_workload_stdout_rejects_object():
    with pytest.raises(ValueError, match="JSON array"):
        parse_workload_stdout('{"operation": "serialize"}')


def test_wait_for_health_times_out():
    with pytest.raises(RuntimeError, match="did not become healthy"):
        wait_for_health("http://127.0.0.1:1", timeout=0.3)


def test_dry_run_run_command(tmp_path, runner, manifest_path, monkeypatch):
    monkeypatch.setenv("HOTSPOT_DRY_RUN", "1")
    out = tmp_path / "run.json"
    result = runner.invoke(
        app,
        [
            "run",
            "--manifest",
            str(manifest_path),
            "--workloads",
            "ingest_bulk",
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(out.read_text())
    assert payload["dry_run"] is True
    assert "ingest_bulk" in payload["workloads"]
    assert payload["plan"][0]["command"][0] == "python"


def test_run_requires_workloads_or_all(runner, manifest_path):
    result = runner.invoke(
        app,
        ["run", "--manifest", str(manifest_path), "--output", "run.json"],
    )
    assert result.exit_code != 0
