# Baseline metrics

PR compares are **last good vs this PR**, both measured in the same CI job. Last good is the merge-base (`main`) built and timed first; this PR is timed second with the same workload commands from that merge-base. Stored [`demo_service/baselines.yaml`](../demo_service/baselines.yaml) is a fallback for local `gate` without `--base-ref`. The manifest `baseline_ms` fields are a last-resort fallback.

## Capture procedure

```bash
hotspot-detector capture \
  --manifest demo_service/hotspot-manifest.yaml \
  --output demo_service/baselines.yaml
```

That is the same Docker Compose stack `perf.yml` uses. Add `--no-docker` only for a local laptop snapshot; those numbers are not valid CI baselines.

Each workload runs `repeats` times (5). The comparator uses the **median** of those samples. Thresholds were widened to 30% after capture-to-capture serialize variance of ~25% on the same laptop.

`perf.yml` does not read the checked-in snapshot. It runs `gate --base-ref origin/<base>` so both sides use `ubuntu-latest` and the same Compose stack. Use `capture` / `baselines.yaml` for local `--no-docker` compares and as the nightly floor.

## Environment (CI capture)

From `demo_service/baselines.yaml` after `hotspot-detector capture` on GitHub Actions, 2026-09-06 (`ubuntu-latest`, Docker, `http://127.0.0.1:8000`):

- ingest_bulk.serialize median: 261.8ms
- ingest_bulk.index median: 58.4ms
- query_filter.scan median: 69.7ms

Workload size is fixed: 1200 records, 256 sha256 rounds per record on serialize, 48 index rounds, 400 score rounds on query.

## Refresh

Re-run capture when the hardware, container image, or workload size changes. Do not edit medians by hand to “make CI green”; recapture in the environment that will run `perf.yml`.

Nightly (`.github/workflows/nightly.yml`) re-measures all workloads and uploads artifacts. It does not auto-commit new baselines; a human copies the snapshot after review.
