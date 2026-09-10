# Baseline metrics

PR compares are **last good vs this PR**, both measured in the same CI job. Last good is the merge-base (`main`) built and timed first; this PR is timed second with the same workload commands from that merge-base. Stored [`demo_service/baselines.yaml`](../demo_service/baselines.yaml) is the **golden floor** (`gate --baselines`) and a fallback for local `gate` without `--base-ref`. The manifest `baseline_ms` fields are a last-resort fallback.

## Capture procedure

```bash
hotspot-detector capture \
  --manifest demo_service/hotspot-manifest.yaml \
  --output demo_service/baselines.yaml
```

That is the same Docker Compose stack `perf.yml` uses. Add `--no-docker` only for a local laptop snapshot; those numbers are not valid CI baselines.

Each workload runs `repeats` times (5). The comparator uses the **median** of those samples. The PR comment shows this PR’s median and the min–max spread of the repeats so a 0.4% delta is not mistaken for a tight measurement. Thresholds were widened to 30% after capture-to-capture serialize variance of ~25% on the same laptop.

`perf.yml` measures last good vs this PR in one job, then also compares this PR to the checked-in golden snapshot (`--baselines`). Nightly (`.github/workflows/nightly.yml`) is the golden floor: it re-measures all workloads and writes a copy-ready `results/baselines.yaml`. A suggested PR on `nightly/golden-update` opens only when the job ran on the default branch **and** the floor drifted or a new operation appeared. It always cuts that branch from `origin/<default>`. It does not merge itself. `workflow_dispatch` off `main` uploads artifacts only.

Reuse a completed run instead of provisioning twice:

```bash
hotspot-detector capture \
  --manifest demo_service/hotspot-manifest.yaml \
  --from-run results/nightly-run.json \
  --output results/baselines.yaml
```

## Environment (CI capture)

From `demo_service/baselines.yaml` after `hotspot-detector capture` on GitHub Actions, 2026-09-09 (`ubuntu-latest`, Docker, `http://127.0.0.1:8000`):

- ingest_bulk.serialize median: 255.6ms
- ingest_bulk.index median: 56.2ms
- query_filter.scan median: 70.4ms
- export_jsonl.materialize median: 129.0ms

Workload size is fixed: 1200 records, 256 sha256 rounds per record on serialize, 48 index rounds, 400 score rounds on query, 12 JSON round-trips on export.

## Refresh

Re-run capture when the hardware, container image, or workload size changes. Do not edit medians by hand to “make CI green”; recapture in the environment that will run `perf.yml`. Accept a nightly suggested PR only after reviewing the new snapshot, and only if that nightly ran on `main`. Same-day jitter is not a new floor.

Last good vs this PR answers “did this change hurt us?” The golden snapshot answers “are we slower than the last reviewed capture?” Compare refuses if the two CI runs have different environment fingerprints (runtime, Python, machine, OS, and a short hash of `Dockerfile` + `docker-compose.yml`). The hash is the container recipe, not the built image, so app-code layers do not look like an environment change.
