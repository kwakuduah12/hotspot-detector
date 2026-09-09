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

`perf.yml` measures last good vs this PR in one job, then also compares this PR to the checked-in golden snapshot (`--baselines`). Nightly (`.github/workflows/nightly.yml`) is the golden floor: it re-measures all workloads against `baselines.yaml` and uploads artifacts. It does not auto-commit; a human copies the snapshot after review.

## Environment (CI capture)

From `demo_service/baselines.yaml` after `hotspot-detector capture` on GitHub Actions, 2026-09-06 (`ubuntu-latest`, Docker, `http://127.0.0.1:8000`):

- ingest_bulk.serialize median: 261.8ms
- ingest_bulk.index median: 58.4ms
- query_filter.scan median: 69.7ms
- export_jsonl.materialize fallback: 73.0ms (local in-process median, 1200 records, 12 JSON round-trips). CI PRs use last good vs this PR, not this number.

Workload size is fixed: 1200 records, 256 sha256 rounds per record on serialize, 48 index rounds, 400 score rounds on query, 12 JSON round-trips on export.

## Refresh

Re-run capture when the hardware, container image, or workload size changes. Do not edit medians by hand to “make CI green”; recapture in the environment that will run `perf.yml`.

Nightly (`.github/workflows/nightly.yml`) re-measures all workloads against the golden snapshot and uploads artifacts. It does not auto-commit new baselines; a human copies the snapshot after review.

Last good vs this PR answers “did this change hurt us?” The golden snapshot answers “are we slower than the last reviewed capture?” Compare refuses if the two CI runs have different environment fingerprints (runtime, Python, machine, OS).
