from hotspot_detector.compare import CompareResult, OperationResult
from hotspot_detector.manifest import load_manifest
from hotspot_detector.report import format_ms, format_pct, render_markdown


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


def test_format_helpers():
    assert format_ms(None) == "—"
    assert format_ms(12.34) == "12.3ms"
    assert format_pct(None) == "—"
    assert format_pct(12.34) == "+12.3%"
    assert format_pct(-3.0) == "-3.0%"
