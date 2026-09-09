"""Typer CLI for hotspot matching, workload runs, comparison, and reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml

from hotspot_detector.ab import (
    git_rev_parse,
    last_good_worktree,
    resolve_merge_base,
    short_sha,
)
from hotspot_detector.compare import (
    CompareResult,
    OperationResult,
    attach_golden,
    compare_run,
    compare_runs,
    snapshot_from_run,
)
from hotspot_detector.cosmetic import is_cosmetic_path
from hotspot_detector.manifest import load_baselines, load_manifest
from hotspot_detector.matcher import MatchResult, evaluate_pr_diff
from hotspot_detector.report import render_ab_dry_run, render_markdown
from hotspot_detector.runner import is_dry_run, run_workloads

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


def _manifest_relative(manifest: Path, repo_root: Path) -> Path:
    return manifest.resolve().relative_to(repo_root.resolve())


def _cosmetic_checker(repo_root: Path, base_sha: str):
    def check(path: str) -> bool:
        return is_cosmetic_path(repo_root, base_sha, path)

    return check


def _skip_if_quiet(matched: MatchResult, report_path: Path | None = None) -> None:
    reason = matched.skip_reason()
    if reason is None:
        return
    typer.echo(reason)
    raise typer.Exit(0)


def _compare_result_from_payload(payload: dict) -> CompareResult:
    return CompareResult(
        overall=payload["overall"],
        operations=[OperationResult(**row) for row in payload["operations"]],
        mode=payload.get("mode", "baseline"),
        last_good_sha=payload.get("last_good_sha"),
        first_bad_sha=payload.get("first_bad_sha"),
        fingerprint_ok=payload.get("fingerprint_ok", True),
        fingerprint_error=payload.get("fingerprint_error"),
        golden_overall=payload.get("golden_overall"),
        golden_operations=[
            OperationResult(**row) for row in payload.get("golden_operations") or []
        ],
    )


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
    base_ref: str | None = typer.Option(
        None,
        "--base-ref",
        help="Git ref used to ignore comment/docstring/whitespace-only edits.",
    ),
) -> None:
    """Print matched workloads for a changed-file list."""
    loaded = load_manifest(manifest)
    files = _read_changed_files(changed_files)
    cosmetic = None
    if base_ref:
        sha = resolve_merge_base(_repo_root(), base_ref)
        cosmetic = _cosmetic_checker(_repo_root(), sha)
    result = evaluate_pr_diff(files, loaded, is_cosmetic=cosmetic).to_dict()
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
    last_good: Path | None = typer.Option(
        None,
        "--last-good",
        exists=True,
        dir_okay=False,
        help="Run JSON from the merge-base. Preferred over --baselines.",
    ),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Compare a run against last-good (same env) or a stored baseline snapshot."""
    loaded = load_manifest(manifest)
    run_payload = json.loads(run.read_text())
    if last_good is not None:
        result = compare_runs(json.loads(last_good.read_text()), run_payload, loaded)
        if baselines is not None:
            attach_golden(result, compare_run(run_payload, loaded, load_baselines(baselines)))
    else:
        captured = load_baselines(baselines) if baselines else None
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
    compare_result = _compare_result_from_payload(compare_payload)
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
    baselines: Path | None = typer.Option(
        None,
        exists=True,
        dir_okay=False,
        help="Golden snapshot. With --base-ref, reported alongside last good vs this PR.",
    ),
    base_ref: str | None = typer.Option(
        None,
        "--base-ref",
        help="Git ref for last good (merge-base). Runs base then this PR in the same env.",
    ),
    results_dir: Path = typer.Option(Path("results")),
    no_docker: bool = typer.Option(False, "--no-docker"),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Exit 1 on regression. Product PRs should leave this off.",
    ),
) -> None:
    """Match, run, compare, and report. Quiet-skips when nothing matches."""
    repo_root = _repo_root()
    files = _read_changed_files(changed_files)
    results_dir.mkdir(parents=True, exist_ok=True)
    run_path = results_dir / "run.json"
    last_good_path = results_dir / "last_good.json"
    compare_path = results_dir / "compare.json"
    report_path = results_dir / "report.md"

    if base_ref:
        last_good_sha = resolve_merge_base(repo_root, base_ref)
        first_bad_sha = git_rev_parse(repo_root, "HEAD")
        rel = _manifest_relative(manifest, repo_root)
        with last_good_worktree(repo_root, last_good_sha) as worktree:
            manifest_at_base = worktree / rel
            if not manifest_at_base.exists():
                (results_dir / "match.json").write_text(
                    json.dumps({"trigger": False, "workloads": [], "matched_files": [], "hotspots": []}, indent=2) + "\n"
                )
                typer.echo(f"Manifest {rel} not present at base; skipping hotspot check.")
                raise typer.Exit(0)
            harness = load_manifest(manifest_at_base)
            matched = evaluate_pr_diff(
                files,
                harness,
                is_cosmetic=_cosmetic_checker(repo_root, last_good_sha),
            )
            (results_dir / "match.json").write_text(
                json.dumps(matched.to_dict(), indent=2) + "\n"
            )
            _skip_if_quiet(matched, report_path)

            last_good = run_workloads(
                harness,
                matched.workloads,
                repo_root=worktree,
                output_path=last_good_path,
                prefer_docker=not no_docker,
                compose_project="hotspotlg",
                role="last_good",
                git_sha=last_good_sha,
            )
            first_bad = run_workloads(
                harness,
                matched.workloads,
                repo_root=repo_root,
                harness_root=worktree,
                output_path=run_path,
                prefer_docker=not no_docker,
                compose_project="hotspotfb",
                role="first_bad",
                git_sha=first_bad_sha,
            )
            first_bad["matched_files"] = matched.matched_files
            first_bad["hotspots"] = matched.hotspots
            run_path.write_text(json.dumps(first_bad, indent=2) + "\n")

            if is_dry_run() or last_good.get("dry_run") or first_bad.get("dry_run"):
                markdown = render_ab_dry_run(
                    harness,
                    matched_files=matched.matched_files,
                    workloads=matched.workloads,
                    last_good_sha=short_sha(repo_root, last_good_sha),
                    first_bad_sha=short_sha(repo_root, first_bad_sha),
                )
                report_path.write_text(markdown)
                typer.echo(markdown, nl=False)
                raise typer.Exit(0)

            compared = compare_runs(
                last_good,
                first_bad,
                harness,
                last_good_sha=short_sha(repo_root, last_good_sha),
                first_bad_sha=short_sha(repo_root, first_bad_sha),
            )
            if baselines is not None:
                attach_golden(
                    compared,
                    compare_run(first_bad, harness, load_baselines(baselines)),
                )
            compare_path.write_text(json.dumps(compared.to_dict(), indent=2) + "\n")
            markdown = render_markdown(
                compared,
                harness,
                matched_files=matched.matched_files,
                workloads=matched.workloads,
            )
            report_path.write_text(markdown)
            typer.echo(markdown, nl=False)
            if strict and compared.overall in {"regression", "error"}:
                raise typer.Exit(1)
            raise typer.Exit(0)

    loaded = load_manifest(manifest)
    matched = evaluate_pr_diff(files, loaded)
    (results_dir / "match.json").write_text(json.dumps(matched.to_dict(), indent=2) + "\n")
    _skip_if_quiet(matched, report_path)

    run_payload = run_workloads(
        loaded,
        matched.workloads,
        repo_root=repo_root,
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
    from_run: Path | None = typer.Option(
        None,
        "--from-run",
        exists=True,
        dir_okay=False,
        help="Reuse a completed run JSON instead of provisioning again.",
    ),
    no_docker: bool = typer.Option(False, "--no-docker"),
) -> None:
    """Run every workload and write a baselines.yaml snapshot."""
    loaded = load_manifest(manifest)
    if from_run is not None:
        payload = json.loads(from_run.read_text())
    else:
        run_path = Path("results") / "capture-run.json"
        payload = run_workloads(
            loaded,
            list(loaded.workloads),
            repo_root=_repo_root(),
            output_path=run_path,
            prefer_docker=not no_docker,
        )
    snapshot = snapshot_from_run(
        payload,
        service_area=loaded.service_area,
        repeats=max((spec.repeats for spec in loaded.workloads.values()), default=5),
        captured_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump(snapshot, sort_keys=False))
    typer.echo(f"Wrote {output}")


if __name__ == "__main__":
    app()
