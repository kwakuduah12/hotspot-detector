"""Compare workload operation timings against baselines."""

from __future__ import annotations

from dataclasses import dataclass, field

from hotspot_detector.manifest import BaselineCapture, Manifest, OperationSpec


def median(values: list[float]) -> float:
    if not values:
        raise ValueError("median() of empty list")
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def classify(
    current_ms: float,
    baseline_ms: float,
    threshold_pct: float,
    threshold_ms: float,
) -> str:
    if baseline_ms <= 0:
        return "error"
    delta = current_ms - baseline_ms
    delta_pct = (delta / baseline_ms) * 100.0
    if delta_pct > threshold_pct or delta > threshold_ms:
        return "regression"
    if delta_pct > (threshold_pct / 2.0) or delta > (threshold_ms / 2.0):
        return "warning"
    return "ok"


RANK = {"ok": 0, "warning": 1, "regression": 2, "error": 3}


@dataclass
class OperationResult:
    workload: str
    operation: str
    baseline_ms: float | None
    current_ms: float | None
    delta_ms: float | None
    delta_pct: float | None
    threshold_pct: float
    threshold_ms: float
    status: str
    samples: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "workload": self.workload,
            "operation": self.operation,
            "baseline_ms": self.baseline_ms,
            "current_ms": self.current_ms,
            "delta_ms": self.delta_ms,
            "delta_pct": self.delta_pct,
            "threshold_pct": self.threshold_pct,
            "threshold_ms": self.threshold_ms,
            "status": self.status,
            "samples": self.samples,
        }


@dataclass
class CompareResult:
    overall: str
    operations: list[OperationResult]

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "operations": [op.to_dict() for op in self.operations],
        }


def _baseline_for(
    workload_id: str,
    op: OperationSpec,
    baselines: BaselineCapture | None,
) -> float | None:
    if baselines is not None:
        captured = (
            baselines.operations.get(workload_id, {}).get(op.name, {}).get("baseline_ms")
        )
        if captured is not None:
            return float(captured)
    return op.baseline_ms


def compare_run(
    run: dict,
    manifest: Manifest,
    baselines: BaselineCapture | None = None,
) -> CompareResult:
    results: list[OperationResult] = []
    run_workloads: dict = run.get("workloads", {})

    for workload_id, samples_by_op in run_workloads.items():
        spec = manifest.workloads.get(workload_id)
        if spec is None:
            results.append(
                OperationResult(
                    workload=workload_id,
                    operation="*",
                    baseline_ms=None,
                    current_ms=None,
                    delta_ms=None,
                    delta_pct=None,
                    threshold_pct=0,
                    threshold_ms=0,
                    status="error",
                )
            )
            continue

        expected = {op.name: op for op in spec.operations}
        for name, op in expected.items():
            samples = [float(x) for x in samples_by_op.get(name, [])]
            threshold_pct = op.threshold_pct
            threshold_ms = op.threshold_ms
            baseline = _baseline_for(workload_id, op, baselines)

            if not samples:
                results.append(
                    OperationResult(
                        workload=workload_id,
                        operation=name,
                        baseline_ms=baseline,
                        current_ms=None,
                        delta_ms=None,
                        delta_pct=None,
                        threshold_pct=threshold_pct,
                        threshold_ms=threshold_ms,
                        status="error",
                    )
                )
                continue

            current = median(samples)
            if baseline is None:
                results.append(
                    OperationResult(
                        workload=workload_id,
                        operation=name,
                        baseline_ms=None,
                        current_ms=current,
                        delta_ms=None,
                        delta_pct=None,
                        threshold_pct=threshold_pct,
                        threshold_ms=threshold_ms,
                        status="error",
                        samples=samples,
                    )
                )
                continue

            delta = current - baseline
            delta_pct = (delta / baseline) * 100.0 if baseline else None
            status = classify(current, baseline, threshold_pct, threshold_ms)
            results.append(
                OperationResult(
                    workload=workload_id,
                    operation=name,
                    baseline_ms=baseline,
                    current_ms=current,
                    delta_ms=delta,
                    delta_pct=delta_pct,
                    threshold_pct=threshold_pct,
                    threshold_ms=threshold_ms,
                    status=status,
                    samples=samples,
                )
            )

        extra = set(samples_by_op) - set(expected)
        for name in sorted(extra):
            samples = [float(x) for x in samples_by_op[name]]
            current = median(samples) if samples else None
            results.append(
                OperationResult(
                    workload=workload_id,
                    operation=name,
                    baseline_ms=None,
                    current_ms=current,
                    delta_ms=None,
                    delta_pct=None,
                    threshold_pct=0,
                    threshold_ms=0,
                    status="error",
                    samples=samples,
                )
            )

    if not results:
        overall = "error"
    else:
        overall = max((op.status for op in results), key=lambda s: RANK.get(s, 0))

    return CompareResult(overall=overall, operations=results)
