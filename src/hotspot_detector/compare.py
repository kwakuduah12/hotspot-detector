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
    mode: str = "baseline"
    last_good_sha: str | None = None
    first_bad_sha: str | None = None

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "operations": [op.to_dict() for op in self.operations],
            "mode": self.mode,
            "last_good_sha": self.last_good_sha,
            "first_bad_sha": self.first_bad_sha,
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


def baselines_from_run(run: dict) -> BaselineCapture:
    """Treat a completed run's medians as a baseline snapshot."""
    operations: dict[str, dict[str, dict[str, float]]] = {}
    medians = run.get("medians") or {}
    if medians:
        for workload_id, ops in medians.items():
            operations[str(workload_id)] = {
                str(name): {"baseline_ms": float(value)} for name, value in ops.items()
            }
    else:
        for workload_id, samples_by_op in run.get("workloads", {}).items():
            operations[str(workload_id)] = {}
            for name, samples in samples_by_op.items():
                values = [float(item) for item in samples]
                if values:
                    operations[str(workload_id)][str(name)] = {
                        "baseline_ms": median(values)
                    }

    environment = run.get("environment")
    if not isinstance(environment, dict):
        environment = {"runtime": environment} if environment else {}

    return BaselineCapture(
        service_area=run.get("service_area"),
        environment=environment,
        operations=operations,
    )


def compare_runs(
    last_good: dict,
    first_bad: dict,
    manifest: Manifest,
    *,
    last_good_sha: str | None = None,
    first_bad_sha: str | None = None,
) -> CompareResult:
    """Compare this PR (first-bad) against a same-env last-good run."""
    result = compare_run(first_bad, manifest, baselines_from_run(last_good))
    result.mode = "ab"
    result.last_good_sha = last_good_sha or last_good.get("git_sha")
    result.first_bad_sha = first_bad_sha or first_bad.get("git_sha")
    return result
