from pathlib import Path

import pytest

from hotspot_detector.manifest import load_baselines, load_manifest, merge_manifests
from hotspot_detector.matcher import evaluate_pr_diff


def test_operation_map(manifest):
    ops = manifest.operation_map("ingest_bulk")
    assert set(ops) == {"serialize", "index"}
    assert ops["serialize"].threshold_pct == 30


def test_load_baselines(baselines_path):
    captured = load_baselines(baselines_path)
    assert captured.service_area == "demo-platform"
    assert "ingest_bulk" in captured.operations
    assert captured.operations["ingest_bulk"]["serialize"]["baseline_ms"] > 0
    assert captured.operations["export_jsonl"]["materialize"]["baseline_ms"] > 100


def test_load_baselines_rejects_non_mapping(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text("- nope\n")
    with pytest.raises(ValueError, match="not a mapping"):
        load_baselines(path)


def test_checked_in_manifest_is_valid(manifest_path):
    loaded = load_manifest(manifest_path)
    assert loaded.version == 1
    assert loaded.hotspots
    for hotspot in loaded.hotspots:
        assert hotspot.workloads
        assert hotspot.paths


def test_merge_keeps_base_hotspot_when_pr_deletes_it(manifest):
    pr = manifest.model_copy(
        update={"hotspots": [h for h in manifest.hotspots if h.id != "ingest-path"]}
    )
    merged = merge_manifests(manifest, pr)
    result = evaluate_pr_diff(["demo_service/app/ingest.py"], merged)
    assert result.trigger is True
    assert result.workloads == ["ingest_bulk"]


def test_merge_runs_hotspot_added_on_pr(manifest):
    base = manifest.model_copy(
        update={
            "hotspots": [h for h in manifest.hotspots if h.id != "export-path"],
            "workloads": {
                key: spec for key, spec in manifest.workloads.items() if key != "export_jsonl"
            },
        }
    )
    assert evaluate_pr_diff(["demo_service/app/export.py"], base).trigger is False
    merged = merge_manifests(base, manifest)
    result = evaluate_pr_diff(["demo_service/app/export.py"], merged)
    assert result.trigger is True
    assert result.workloads == ["export_jsonl"]
    assert result.hotspots == ["export-path"]


def test_merge_keeps_base_repeats_when_pr_shrinks_n(manifest):
    shrunk = manifest.workloads["ingest_bulk"].model_copy(update={"repeats": 1})
    pr = manifest.model_copy(
        update={"workloads": {**dict(manifest.workloads), "ingest_bulk": shrunk}}
    )
    merged = merge_manifests(manifest, pr)
    assert merged.workloads["ingest_bulk"].repeats == manifest.workloads["ingest_bulk"].repeats
    assert merged.workloads["ingest_bulk"].repeats != 1
