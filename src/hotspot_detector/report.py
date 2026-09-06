"""Render comparison results as markdown and JSON."""

from __future__ import annotations

from hotspot_detector.compare import CompareResult
from hotspot_detector.manifest import Manifest


def format_ms(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}ms"


def format_pct(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def render_markdown(
    compare: CompareResult,
    manifest: Manifest,
    *,
    matched_files: list[str] | None = None,
    workloads: list[str] | None = None,
) -> str:
    lines = [
        "<!-- hotspot-detector-report -->",
        "## Performance regression report",
        "",
        f"**Service area:** `{manifest.service_area}`",
        f"**Overall:** `{compare.overall}`",
    ]
    if workloads:
        lines.append(f"**Workloads:** {', '.join(f'`{w}`' for w in workloads)}")
    if matched_files:
        lines.append("**Matched files:**")
        for path in matched_files:
            lines.append(f"- `{path}`")
    lines.extend(
        [
            "",
            "| Workload | Operation | Baseline | Current | Delta | Status |",
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
    lines.extend(
        [
            "",
            "_This check is informational and does not block merge._",
            "",
        ]
    )
    return "\n".join(lines)
