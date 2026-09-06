from pathlib import Path

import pytest

from hotspot_detector.manifest import load_baselines, load_manifest


def test_operation_map(manifest):
    ops = manifest.operation_map("ingest_bulk")
    assert set(ops) == {"serialize", "index"}
    assert ops["serialize"].threshold_pct == 30


def test_load_baselines(baselines_path):
    captured = load_baselines(baselines_path)
    assert captured.service_area == "demo-platform"
    assert "ingest_bulk" in captured.operations
    assert captured.operations["ingest_bulk"]["serialize"]["baseline_ms"] > 0


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
