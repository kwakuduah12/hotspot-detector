from hotspot_detector.compare import CompareResult, OperationResult
from hotspot_detector.manifest import load_manifest
from hotspot_detector.report import (
    format_ms,
    format_pct,
    render_ab_dry_run,
    render_markdown,
)


def test_report_contains_status_and_nonblocking_note(manifest):
    compare = CompareResult(
        overall="regression",
        operations=[
            OperationResult(
                workload="ingest_bulk",
                operation="serialize",
                baseline_ms=80.0,
                current_ms=200.0,
                delta_ms=120.0,
                delta_pct=150.0,
                threshold_pct=20.0,
                threshold_ms=40.0,
                status="regression",
            )
        ],
    )
    markdown = render_markdown(
        compare,
        manifest,
        matched_files=["demo_service/app/ingest.py"],
        workloads=["ingest_bulk"],
    )
    assert "<!-- hotspot-detector-report -->" in markdown
    assert "`regression`" in markdown
    assert "does not block merge" in markdown
    assert "demo_service/app/ingest.py" in markdown


def test_ab_report_uses_last_good_headers_and_verdict(manifest):
    compare = CompareResult(
        overall="regression",
        operations=[
            OperationResult(
                workload="ingest_bulk",
                operation="serialize",
                baseline_ms=260.0,
                current_ms=410.0,
                delta_ms=150.0,
                delta_pct=57.7,
                threshold_pct=30.0,
                threshold_ms=80.0,
                status="regression",
            )
        ],
        mode="ab",
        last_good_sha="abc1234",
        first_bad_sha="def5678",
    )
    markdown = render_markdown(
        compare,
        manifest,
        matched_files=["demo_service/app/ingest.py"],
        workloads=["ingest_bulk"],
    )
    assert "Last good" in markdown
    assert "This PR" in markdown
    assert "`abc1234`" in markdown
    assert "first-bad vs last good" in markdown
    assert "does not block merge" in markdown


def test_ab_dry_run_report(manifest):
    markdown = render_ab_dry_run(
        manifest,
        matched_files=["demo_service/app/ingest.py"],
        workloads=["ingest_bulk"],
        last_good_sha="aaa",
        first_bad_sha="bbb",
    )
    assert "**Overall:** `dry_run`" in markdown
    assert "`aaa`" in markdown
    assert "would measure last good" in markdown


def test_format_helpers():
    assert format_ms(None) == "—"
    assert format_ms(12.34) == "12.3ms"
    assert format_pct(None) == "—"
    assert format_pct(12.34) == "+12.3%"
    assert format_pct(-3.0) == "-3.0%"
