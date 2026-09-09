import json

import yaml

from hotspot_detector.cli import app


def test_match_cli_empty_file(tmp_path, runner, manifest_path):
    changed = tmp_path / "changed.txt"
    changed.write_text("")
    result = runner.invoke(
        app,
        ["match", "--manifest", str(manifest_path), "--changed-files", str(changed)],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["trigger"] is False


def test_run_all_dry_run(tmp_path, runner, manifest_path, monkeypatch):
    monkeypatch.setenv("HOTSPOT_DRY_RUN", "1")
    out = tmp_path / "run.json"
    result = runner.invoke(
        app,
        ["run", "--manifest", str(manifest_path), "--all", "--output", str(out)],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(out.read_text())
    assert set(payload["workloads"]) == {"ingest_bulk", "query_filter", "export_jsonl"}
    assert payload["fingerprint"]["runtime"] in {"docker", "local"}


def test_run_rejects_unknown_workload(runner, manifest_path):
    result = runner.invoke(
        app,
        [
            "run",
            "--manifest",
            str(manifest_path),
            "--workloads",
            "does_not_exist",
            "--output",
            "run.json",
        ],
    )
    assert result.exit_code != 0


def test_match_cli_hotspot(tmp_path, runner, manifest_path):
    changed = tmp_path / "changed.txt"
    changed.write_text("demo_service/app/ingest.py\n")
    result = runner.invoke(
        app,
        [
            "match",
            "--manifest",
            str(manifest_path),
            "--changed-files",
            str(changed),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["trigger"] is True
    assert "ingest_bulk" in payload["workloads"]


def test_match_cli_docs_quiet_skip(tmp_path, runner, manifest_path):
    changed = tmp_path / "changed.txt"
    changed.write_text("docs/adoption-guide.md\n")
    result = runner.invoke(
        app,
        [
            "match",
            "--manifest",
            str(manifest_path),
            "--changed-files",
            str(changed),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["trigger"] is False
    assert payload["workloads"] == []


def test_match_cli_json_array(tmp_path, runner, manifest_path):
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(["demo_service/app/query.py"]))
    out = tmp_path / "match.json"
    result = runner.invoke(
        app,
        [
            "match",
            "--manifest",
            str(manifest_path),
            "--changed-files",
            str(changed),
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(out.read_text())
    assert payload["workloads"] == ["query_filter"]


def test_gate_comment_only_hotspot_skips(tmp_path, runner, manifest_path):
    changed = tmp_path / "changed.txt"
    changed.write_text("demo_service/app/ingest.py\n")
    results_dir = tmp_path / "results"
    result = runner.invoke(
        app,
        [
            "gate",
            "--manifest",
            str(manifest_path),
            "--changed-files",
            str(changed),
            "--base-ref",
            "HEAD",
            "--results-dir",
            str(results_dir),
            "--no-docker",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "comments, docstrings, or whitespace" in result.output
    match = json.loads((results_dir / "match.json").read_text())
    assert match["trigger"] is False
    assert "demo_service/app/ingest.py" in match["cosmetic_files"]
    assert not (results_dir / "run.json").exists()


def test_gate_docs_only_skips_without_running(tmp_path, runner, manifest_path):
    changed = tmp_path / "changed.txt"
    changed.write_text("README.md\n")
    results_dir = tmp_path / "results"
    result = runner.invoke(
        app,
        [
            "gate",
            "--manifest",
            str(manifest_path),
            "--changed-files",
            str(changed),
            "--results-dir",
            str(results_dir),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "skipping" in result.output.lower()
    assert (results_dir / "match.json").exists()
    assert not (results_dir / "run.json").exists()


def test_gate_dry_run_hotspot_writes_report(
    tmp_path, runner, manifest_path, baselines_path, monkeypatch
):
    monkeypatch.setenv("HOTSPOT_DRY_RUN", "1")
    changed = tmp_path / "changed.txt"
    changed.write_text("demo_service/app/ingest.py\n")
    results_dir = tmp_path / "results"
    result = runner.invoke(
        app,
        [
            "gate",
            "--manifest",
            str(manifest_path),
            "--changed-files",
            str(changed),
            "--baselines",
            str(baselines_path),
            "--results-dir",
            str(results_dir),
            "--no-docker",
        ],
    )
    assert result.exit_code == 0, result.output
    run_payload = json.loads((results_dir / "run.json").read_text())
    assert run_payload["dry_run"] is True
    assert (results_dir / "compare.json").exists()
    assert (results_dir / "report.md").exists()


def test_gate_base_ref_dry_run(tmp_path, runner, manifest_path, monkeypatch):
    monkeypatch.setenv("HOTSPOT_DRY_RUN", "1")
    monkeypatch.setattr(
        "hotspot_detector.cli.is_cosmetic_path",
        lambda *_args, **_kwargs: False,
    )
    changed = tmp_path / "changed.txt"
    changed.write_text("demo_service/app/ingest.py\n")
    results_dir = tmp_path / "results"
    result = runner.invoke(
        app,
        [
            "gate",
            "--manifest",
            str(manifest_path),
            "--changed-files",
            str(changed),
            "--base-ref",
            "HEAD",
            "--results-dir",
            str(results_dir),
            "--no-docker",
        ],
    )
    assert result.exit_code == 0, result.output
    last_good = json.loads((results_dir / "last_good.json").read_text())
    first_bad = json.loads((results_dir / "run.json").read_text())
    assert last_good["role"] == "last_good"
    assert first_bad["role"] == "first_bad"
    assert last_good["harness_root"] == last_good["sut_root"]
    assert first_bad["harness_root"] != first_bad["sut_root"]
    assert last_good["harness_by_workload"]["ingest_bulk"] == last_good["sut_root"]
    report = (results_dir / "report.md").read_text()
    assert "last good" in report.lower()
    assert "dry_run" in report


def test_compare_cli_last_good(tmp_path, runner, manifest_path):
    last_good = tmp_path / "last_good.json"
    last_good.write_text(
        json.dumps({"workloads": {"ingest_bulk": {"serialize": [260.0], "index": [58.0]}}})
    )
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "workloads": {
                    "ingest_bulk": {
                        "serialize": [410.0, 400.0, 405.0],
                        "index": [54.0, 55.0, 53.0],
                    }
                }
            }
        )
    )
    compare_path = tmp_path / "compare.json"
    result = runner.invoke(
        app,
        [
            "compare",
            "--run",
            str(run_path),
            "--last-good",
            str(last_good),
            "--manifest",
            str(manifest_path),
            "--output",
            str(compare_path),
        ],
    )
    assert result.exit_code == 0, result.output
    compared = json.loads(compare_path.read_text())
    assert compared["mode"] == "ab"
    assert compared["overall"] == "regression"
    serialize = next(op for op in compared["operations"] if op["operation"] == "serialize")
    assert serialize["baseline_ms"] == 260.0
    assert compared["golden_overall"] is None


def test_compare_cli_last_good_with_golden(tmp_path, runner, manifest_path, baselines_path):
    last_good = tmp_path / "last_good.json"
    last_good.write_text(
        json.dumps({"workloads": {"ingest_bulk": {"serialize": [260.0], "index": [58.0]}}})
    )
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "workloads": {
                    "ingest_bulk": {
                        "serialize": [262.0, 261.0, 260.0],
                        "index": [54.0, 55.0, 53.0],
                    }
                }
            }
        )
    )
    compare_path = tmp_path / "compare.json"
    result = runner.invoke(
        app,
        [
            "compare",
            "--run",
            str(run_path),
            "--last-good",
            str(last_good),
            "--baselines",
            str(baselines_path),
            "--manifest",
            str(manifest_path),
            "--output",
            str(compare_path),
        ],
    )
    assert result.exit_code == 0, result.output
    compared = json.loads(compare_path.read_text())
    assert compared["overall"] == "ok"
    assert compared["golden_overall"] == "ok"


def test_compare_and_report_cli(tmp_path, runner, manifest_path, baselines_path):
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "workloads": {
                    "ingest_bulk": {
                        "serialize": [400.0, 410.0, 405.0],
                        "index": [40.0, 41.0, 39.0],
                    }
                }
            }
        )
    )
    compare_path = tmp_path / "compare.json"
    result = runner.invoke(
        app,
        [
            "compare",
            "--run",
            str(run_path),
            "--manifest",
            str(manifest_path),
            "--baselines",
            str(baselines_path),
            "--output",
            str(compare_path),
        ],
    )
    assert result.exit_code == 0, result.output
    compared = json.loads(compare_path.read_text())
    assert compared["overall"] == "regression"

    report_path = tmp_path / "report.md"
    report = runner.invoke(
        app,
        [
            "report",
            "--run",
            str(run_path),
            "--compare",
            str(compare_path),
            "--manifest",
            str(manifest_path),
            "--output",
            str(report_path),
        ],
    )
    assert report.exit_code == 0, report.output
    body = report_path.read_text()
    assert "<!-- hotspot-detector-report -->" in body
    assert "does not block merge" in body


def test_capture_dry_run_writes_snapshot(tmp_path, runner, manifest_path, monkeypatch):
    monkeypatch.setenv("HOTSPOT_DRY_RUN", "1")
    out = tmp_path / "baselines.yaml"
    result = runner.invoke(
        app,
        [
            "capture",
            "--manifest",
            str(manifest_path),
            "--output",
            str(out),
            "--no-docker",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = yaml.safe_load(out.read_text())
    assert payload["service_area"] == "demo-platform"
    assert "operations" in payload


def test_capture_from_run_writes_snapshot(tmp_path, runner, manifest_path):
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "environment": "docker",
                "base_url": "http://127.0.0.1:8000",
                "fingerprint": {
                    "runtime": "docker",
                    "python": "3.12.11",
                    "machine": "x86_64",
                    "system": "Linux",
                },
                "medians": {"export_jsonl": {"materialize": 137.1}},
            }
        )
    )
    out = tmp_path / "baselines.yaml"
    result = runner.invoke(
        app,
        [
            "capture",
            "--manifest",
            str(manifest_path),
            "--from-run",
            str(run_path),
            "--output",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = yaml.safe_load(out.read_text())
    assert payload["operations"]["export_jsonl"]["materialize"]["baseline_ms"] == 137.1
    assert payload["environment"]["python"] == "3.12.11"


def test_gate_strict_dry_run_exits_nonzero(
    tmp_path, runner, manifest_path, baselines_path, monkeypatch
):
    monkeypatch.setenv("HOTSPOT_DRY_RUN", "1")
    changed = tmp_path / "changed.txt"
    changed.write_text("demo_service/app/ingest.py\n")
    result = runner.invoke(
        app,
        [
            "gate",
            "--manifest",
            str(manifest_path),
            "--changed-files",
            str(changed),
            "--baselines",
            str(baselines_path),
            "--results-dir",
            str(tmp_path / "results"),
            "--no-docker",
            "--strict",
        ],
    )
    assert result.exit_code == 1
