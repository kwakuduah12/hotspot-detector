"""Render comparison results as markdown and JSON."""

from __future__ import annotations

from hotspot_detector.compare import CompareResult
from hotspot_detector.manifest import Manifest

VERDICTS = {
    "ok": "This PR matches last good on the merge-base.",
    "warning": "This PR is slower than last good, below the regression bar.",
    "regression": (
        "This PR is first-bad vs last good. Review the delta before merge; "
        "this check does not block."
    ),
    "error": "The compare did not finish (missing samples or a workload crash).",
}


def format_ms(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}ms"


def format_pct(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def render_ab_dry_run(
    manifest: Manifest,
    *,
    matched_files: list[str],
    workloads: list[str],
    last_good_sha: str | None,
    first_bad_sha: str | None,
) -> str:
    lines = [
        "<!-- hotspot-detector-report -->",
        "## Performance regression report",
        "",
        f"**Service area:** `{manifest.service_area}`",
        "**Overall:** `dry_run`",
        "**Mode:** last good (merge-base) vs this PR",
    ]
    if last_good_sha:
        lines.append(f"**Last good:** `{last_good_sha}`")
    if first_bad_sha:
        lines.append(f"**This PR:** `{first_bad_sha}`")
    if workloads:
        lines.append(f"**Workloads:** {', '.join(f'`{w}`' for w in workloads)}")
    if matched_files:
        lines.append("**Matched files:**")
        for path in matched_files:
            lines.append(f"- `{path}`")
    lines.extend(
        [
            "",
            "Dry-run: would measure last good, then this PR, then compare. No timings collected.",
            "",
            "_This check is informational and does not block merge._",
            "",
        ]
    )
    return "\n".join(lines)


def verdict_line(compare: CompareResult) -> str:
    if compare.mode != "ab":
        return ""
    if compare.fingerprint_ok is False:
        return f"Compare refused: {compare.fingerprint_error}."
    return VERDICTS.get(compare.overall, VERDICTS["error"])


def render_markdown(
    compare: CompareResult,
    manifest: Manifest,
    *,
    matched_files: list[str] | None = None,
    workloads: list[str] | None = None,
) -> str:
    ab = compare.mode == "ab"
    baseline_col = "Last good" if ab else "Baseline"
    current_col = "This PR" if ab else "Current"
    lines = [
        "<!-- hotspot-detector-report -->",
        "## Performance regression report",
        "",
        f"**Service area:** `{manifest.service_area}`",
        f"**Overall:** `{compare.overall}`",
    ]
    if ab:
        lines.append("**Mode:** last good (merge-base) vs this PR")
        if compare.last_good_sha:
            lines.append(f"**Last good:** `{compare.last_good_sha}`")
        if compare.first_bad_sha:
            lines.append(f"**This PR:** `{compare.first_bad_sha}`")
    if workloads:
        lines.append(f"**Workloads:** {', '.join(f'`{w}`' for w in workloads)}")
    if matched_files:
        lines.append("**Matched files:**")
        for path in matched_files:
            lines.append(f"- `{path}`")
    verdict = verdict_line(compare)
    if verdict:
        lines.extend(["", verdict])
    lines.extend(
        [
            "",
            f"| Workload | Operation | {baseline_col} | {current_col} | Delta | Status |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for op in compare.operations:
        delta = format_ms(op.delta_ms)
        if op.delta_pct is not None:
            delta = f"{delta} ({format_pct(op.delta_pct)})"
        lines.append(
            f"| `{op.workload}` | `{op.operation}` | {format_ms(op.baseline_ms)} | "
            f"{format_ms(op.current_ms)} | {delta} | `{op.status}` |"
        )
    if compare.golden_overall is not None:
        lines.extend(
            [
                "",
                f"**vs golden snapshot:** `{compare.golden_overall}`",
                "",
                "| Workload | Operation | Golden | This PR | Delta | Status |",
                "|---|---|---:|---:|---:|---|",
            ]
        )
        for op in compare.golden_operations:
            delta = format_ms(op.delta_ms)
            if op.delta_pct is not None:
                delta = f"{delta} ({format_pct(op.delta_pct)})"
            lines.append(
                f"| `{op.workload}` | `{op.operation}` | {format_ms(op.baseline_ms)} | "
                f"{format_ms(op.current_ms)} | {delta} | `{op.status}` |"
            )
    lines.extend(
        [
            "",
            "_This check is informational and does not block merge._",
            "",
        ]
    )
    return "\n".join(lines)
