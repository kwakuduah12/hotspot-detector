import pytest

from hotspot_detector.compare import (
    baselines_from_run,
    classify,
    compare_run,
    compare_runs,
    median,
)
from hotspot_detector.manifest import BaselineCapture, Manifest, OperationSpec, WorkloadSpec


def _manifest(
    threshold_pct=20.0,
    threshold_ms=40.0,
    baseline_ms: float | None = 100.0,
) -> Manifest:
    return Manifest(
        version=1,
        service_area="demo",
        hotspots=[],
        workloads={
            "w": WorkloadSpec(
                command=["true"],
                repeats=5,
                operations=[
                    OperationSpec(
                        name="op",
                        baseline_ms=baseline_ms,
                        threshold_pct=threshold_pct,
                        threshold_ms=threshold_ms,
                    )
                ],
            )
        },
    )


def test_median_odd_and_even():
    assert median([3, 1, 2]) == 2
    assert median([1, 2, 3, 4]) == 2.5


def test_median_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        median([])


@pytest.mark.parametrize(
    ("current", "baseline", "threshold_pct", "threshold_ms", "expected"),
    [
        (105, 100, 20, 40, "ok"),
        (50, 100, 20, 40, "ok"),
        (111, 100, 20, 40, "warning"),
        (120, 100, 20, 40, "warning"),
        (121, 100, 20, 40, "regression"),
        (141, 100, 50, 40, "regression"),
        (100, 0, 20, 40, "error"),
        (100, -1, 20, 40, "error"),
    ],
)
def test_classify_boundaries(current, baseline, threshold_pct, threshold_ms, expected):
    assert classify(current, baseline, threshold_pct, threshold_ms) == expected


def test_compare_run_ok():
    run = {"workloads": {"w": {"op": [98.0, 100.0, 102.0]}}}
    result = compare_run(run, _manifest())
    assert result.overall == "ok"
    assert result.operations[0].status == "ok"
    assert result.operations[0].current_ms == 100.0


def test_compare_run_warning_overall():
    run = {"workloads": {"w": {"op": [111.0]}}}
    result = compare_run(run, _manifest())
    assert result.overall == "warning"


def test_compare_run_regression():
    run = {"workloads": {"w": {"op": [150.0, 160.0, 155.0]}}}
    result = compare_run(run, _manifest())
    assert result.overall == "regression"


def test_compare_prefers_baselines_file():
    run = {"workloads": {"w": {"op": [100.0]}}}
    baselines = BaselineCapture(
        operations={"w": {"op": {"baseline_ms": 50.0}}},
    )
    result = compare_run(run, _manifest(baseline_ms=1000.0), baselines)
    assert result.operations[0].baseline_ms == 50.0
    assert result.overall == "regression"


def test_missing_operation_is_error():
    run = {"workloads": {"w": {}}}
    result = compare_run(run, _manifest())
    assert result.overall == "error"
    assert result.operations[0].status == "error"


def test_unknown_workload_is_error():
    run = {"workloads": {"other": {"op": [1.0]}}}
    result = compare_run(run, _manifest())
    assert result.overall == "error"


def test_unexpected_operation_is_error():
    run = {"workloads": {"w": {"op": [100.0], "extra": [9.0]}}}
    result = compare_run(run, _manifest())
    assert result.overall == "error"
    names = {op.operation for op in result.operations}
    assert "extra" in names


def test_missing_baseline_is_error():
    run = {"workloads": {"w": {"op": [100.0]}}}
    result = compare_run(run, _manifest(baseline_ms=None))
    assert result.overall == "error"


def test_empty_run_is_error():
    result = compare_run({"workloads": {}}, _manifest())
    assert result.overall == "error"
    assert result.operations == []


def test_baselines_from_run_uses_medians():
    captured = baselines_from_run(
        {"medians": {"w": {"op": 50.0}}, "environment": "docker"}
    )
    assert captured.operations["w"]["op"]["baseline_ms"] == 50.0
    assert captured.environment["runtime"] == "docker"


def test_baselines_from_run_falls_back_to_samples():
    captured = baselines_from_run({"workloads": {"w": {"op": [10.0, 20.0, 30.0]}}})
    assert captured.operations["w"]["op"]["baseline_ms"] == 20.0


def test_compare_runs_marks_first_bad_regression():
    last_good = {"workloads": {"w": {"op": [100.0, 100.0, 100.0]}}, "git_sha": "aaa"}
    first_bad = {"workloads": {"w": {"op": [160.0, 155.0, 150.0]}}, "git_sha": "bbb"}
    result = compare_runs(last_good, first_bad, _manifest())
    assert result.mode == "ab"
    assert result.overall == "regression"
    assert result.last_good_sha == "aaa"
    assert result.first_bad_sha == "bbb"
    assert result.operations[0].baseline_ms == 100.0
    assert result.operations[0].current_ms == 155.0


def test_compare_runs_ok_when_pr_matches_last_good():
    run = {"workloads": {"w": {"op": [98.0, 100.0, 102.0]}}}
    result = compare_runs(run, run, _manifest(), last_good_sha="g", first_bad_sha="b")
    assert result.overall == "ok"
    assert result.last_good_sha == "g"
    assert result.first_bad_sha == "b"
