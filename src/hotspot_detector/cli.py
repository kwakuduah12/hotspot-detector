"""Typer CLI for hotspot matching, workload runs, comparison, and reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml

from hotspot_detector.compare import compare_run
from hotspot_detector.manifest import load_baselines, load_manifest
from hotspot_detector.matcher import evaluate_pr_diff
from hotspot_detector.report import render_markdown
from hotspot_detector.runner import run_workloads

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _repo_root() -> Path:
    return Path.cwd()


def _read_changed_files(path: Path) -> list[str]:
    text = path.read_text().strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
        return [str(item) for item in data]
    return [line.strip() for line in text.splitlines() if line.strip()]


def _write_json(path: Path | None, payload: dict) -> None:
    rendered = json.dumps(payload, indent=2) + "\n"
    if path is None:
        typer.echo(rendered, nl=False)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered)
    typer.echo(rendered, nl=False)


@app.command()
def match(
    manifest: Path = typer.Option(..., exists=True, dir_okay=False),
    changed_files: Path = typer.Option(
        ...,
        "--changed-files",
        exists=True,
        dir_okay=False,
        help="Newline-separated paths or a JSON array.",
    ),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Print matched workloads for a changed-file list."""
    loaded = load_manifest(manifest)
    files = _read_changed_files(changed_files)
    result = evaluate_pr_diff(files, loaded).to_dict()
    _write_json(output, result)


@app.command()
def run(
    manifest: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(Path("run.json"), "--output", "-o"),
    workloads: str | None = typer.Option(
        None,
        "--workloads",
        help="Comma-separated workload ids. Ignored when --all is set.",
    ),
    all_workloads: bool = typer.Option(False, "--all", help="Run every workload."),
    no_docker: bool = typer.Option(False, "--no-docker"),
) -> None:
    """Provision the test environment and execute workloads."""
    loaded = load_manifest(manifest)
    if all_workloads:
        selected = list(loaded.workloads)
    elif workloads:
        selected = [item.strip() for item in workloads.split(",") if item.strip()]
    else:
        raise typer.BadParameter("pass --workloads or --all")
    unknown = [item for item in selected if item not in loaded.workloads]
    if unknown:
        raise typer.BadParameter(f"unknown workloads: {unknown}")
    payload = run_workloads(
        loaded,
        selected,
        repo_root=_repo_root(),
        output_path=output,
        prefer_docker=not no_docker,
    )
    typer.echo(json.dumps(payload, indent=2))


@app.command()
def compare(
    run: Path = typer.Option(..., exists=True, dir_okay=False),
    manifest: Path = typer.Option(..., exists=True, dir_okay=False),
    baselines: Path | None = typer.Option(None, exists=True, dir_okay=False),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Compare a run against baselines and thresholds."""
    loaded = load_manifest(manifest)
    captured = load_baselines(baselines) if baselines else None
    run_payload = json.loads(run.read_text())
    result = compare_run(run_payload, loaded, captured)
    _write_json(output, result.to_dict())


@app.command()
def report(
    run: Path = typer.Option(..., exists=True, dir_okay=False),
    compare_file: Path = typer.Option(..., "--compare", exists=True, dir_okay=False),
    manifest: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(Path("report.md"), "--output", "-o"),
) -> None:
    """Write a markdown report from run + compare JSON."""
    loaded = load_manifest(manifest)
    run_payload = json.loads(run.read_text())
    compare_payload = json.loads(compare_file.read_text())
    from hotspot_detector.compare import CompareResult, OperationResult

    compare_result = CompareResult(
        overall=compare_payload["overall"],
        operations=[OperationResult(**row) for row in compare_payload["operations"]],
    )
    markdown = render_markdown(
        compare_result,
        loaded,
        matched_files=run_payload.get("matched_files"),
        workloads=list(run_payload.get("workloads", {})),
    )
    output.write_text(markdown)
    typer.echo(markdown, nl=False)


@app.command()
def gate(
    manifest: Path = typer.Option(..., exists=True, dir_okay=False),
    changed_files: Path = typer.Option(..., "--changed-files", exists=True, dir_okay=False),
    baselines: Path | None = typer.Option(None, exists=True, dir_okay=False),
    results_dir: Path = typer.Option(Path("results")),
    no_docker: bool = typer.Option(False, "--no-docker"),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Exit 1 on regression. Product PRs should leave this off.",
    ),
) -> None:
    """Match, run, compare, and report. Quiet-skips when nothing matches."""
    loaded = load_manifest(manifest)
    files = _read_changed_files(changed_files)
    matched = evaluate_pr_diff(files, loaded)
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "match.json").write_text(json.dumps(matched.to_dict(), indent=2) + "\n")

    if not matched.trigger:
        typer.echo("No hotspot files changed; skipping workloads.")
        raise typer.Exit(0)

    run_path = results_dir / "run.json"
    compare_path = results_dir / "compare.json"
    report_path = results_dir / "report.md"

    run_payload = run_workloads(
        loaded,
        matched.workloads,
        repo_root=_repo_root(),
        output_path=run_path,
        prefer_docker=not no_docker,
    )
    run_payload["matched_files"] = matched.matched_files
    run_payload["hotspots"] = matched.hotspots
    run_path.write_text(json.dumps(run_payload, indent=2) + "\n")

    captured = load_baselines(baselines) if baselines else None
    compared = compare_run(run_payload, loaded, captured)
    compare_path.write_text(json.dumps(compared.to_dict(), indent=2) + "\n")
    markdown = render_markdown(
        compared,
        loaded,
        matched_files=matched.matched_files,
        workloads=matched.workloads,
    )
    report_path.write_text(markdown)
    typer.echo(markdown, nl=False)

    if strict and compared.overall in {"regression", "error"}:
        raise typer.Exit(1)
    raise typer.Exit(0)


@app.command()
def capture(
    manifest: Path = typer.Option(..., exists=True, dir_okay=False),
    output: Path = typer.Option(..., "--output", "-o"),
    no_docker: bool = typer.Option(False, "--no-docker"),
) -> None:
    """Run every workload and write a baselines.yaml snapshot."""
    loaded = load_manifest(manifest)
    run_path = Path("results") / "capture-run.json"
    payload = run_workloads(
        loaded,
        list(loaded.workloads),
        repo_root=_repo_root(),
        output_path=run_path,
        prefer_docker=not no_docker,
    )
    snapshot = {
        "service_area": loaded.service_area,
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "environment": {
            "runtime": payload.get("environment", "unknown"),
            "base_url": payload.get("base_url"),
        },
        "repeats": max((spec.repeats for spec in loaded.workloads.values()), default=5),
        "operations": {},
    }
    for workload_id, medians in payload.get("medians", {}).items():
        snapshot["operations"][workload_id] = {
            name: {"baseline_ms": round(float(value), 3)} for name, value in medians.items()
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(snapshot, sort_keys=False))
    typer.echo(f"Wrote {output}")


if __name__ == "__main__":
    app()
