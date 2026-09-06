# Baseline metrics

Baselines are median operation runtimes from the test environment, stored in [`demo_service/baselines.yaml`](../demo_service/baselines.yaml). The manifest also carries `baseline_ms` as a fallback; `compare` prefers the YAML snapshot when `--baselines` is passed.

## Capture procedure

```bash
hotspot-detector capture \
  --manifest demo_service/hotspot-manifest.yaml \
  --output demo_service/baselines.yaml \
  --no-docker
```

Omit `--no-docker` when Docker is available so capture uses the same Compose stack as CI.

Each workload runs `repeats` times (5). The comparator uses the **median** of those samples. Thresholds were widened to 30% after capture-to-capture serialize variance of ~25% on the same laptop; recapture in GitHub Actions before treating CI numbers as authoritative.

## Environment (initial capture)

From `demo_service/baselines.yaml` after `hotspot-detector capture --no-docker` on 2026-09-04 (CPython 3.13, macOS, uvicorn on `http://127.0.0.1:8000`):

- ingest_bulk.serialize median: 173.3ms
- ingest_bulk.index median: 40.9ms
- query_filter.scan median: 35.2ms

Workload size is fixed: 1200 records, 256 sha256 rounds per record on serialize, 48 index rounds, 400 score rounds on query.

## Refresh

Re-run capture when the hardware, container image, or workload size changes. Do not edit medians by hand to “make CI green”; recapture in the environment that will run `perf.yml`.

Nightly (`.github/workflows/nightly.yml`) re-measures all workloads and uploads artifacts. It does not auto-commit new baselines; a human copies the snapshot after review.
