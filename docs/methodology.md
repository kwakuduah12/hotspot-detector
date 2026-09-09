# Hotspot selection methodology

A hotspot is a source path that (1) sits on a critical request path and (2) shows up as a top frame when the owning team profiles a representative workload. This file records how that decision was made for **demo-platform**, the first onboarded service area.

## Service area

`demo_service` is a small FastAPI stand-in for a platform ingest/query API:

- **Hot:** serialize + index on ingest (`ingest.py`, `index.py`), the shared in-memory store (`store.py`), scan/filter on query (`query.py`), and JSONL export (`export.py`)
- **Cold:** health, config, FastAPI wiring — must not trigger workloads

We are the owning team of this service, so stakeholder input and profiling happen in-tree.

## How a path is promoted

1. Name the user-visible operation (ingest a batch, query by tag).
2. Run a fixed-size workload (1200 records, see `demo_service/workloads/`).
3. Profile with `python scripts/profile_hotspots.py` (cProfile, cumulative time).
4. Map the hottest application frames to source files.
5. Confirm the file is on the critical path (not a helper that only runs in tests).
6. Attach the workload that exercises it, plus per-operation thresholds.
7. Capture baselines in the test environment (`hotspot-detector capture`).

A path that fails step 5 or 6 goes into `demo_service/candidates.yaml` instead of the active manifest.

## Profile evidence (demo-platform)

Command:

```bash
PYTHONPATH=src:. python scripts/profile_hotspots.py
```

Observed (local CPython 3.13, 1200 records, `HASH_ROUNDS=256`):

- **ingest serialize + index:** ~0.40s in-process. `serialize_records` (`demo_service/app/ingest.py`) dominates (~0.34s) via `hashlib.sha256` and `json.dumps`. `index_records` (`demo_service/app/index.py`) is the next application frame (~0.06s) and still sits on the ingest critical path, so both files share the `ingest_bulk` workload. `RecordStore.replace` (`demo_service/app/store.py`) is on that same path; it is wired to `ingest_bulk`.
- **query scan_filter:** after seeding, `scan_filter` / `_score` (`demo_service/app/query.py`) account for the scan. Wired to `query_filter`.
- **export export_jsonl:** after seeding, `export_jsonl` (`demo_service/app/export.py`) dominates via repeated `json.dumps` / `json.loads` while materializing JSONL. Wired to `export_jsonl`.

## What we left out

- Comment, docstring, and whitespace-only edits in a hotspot file. `ast.parse` drops comments; we also strip module/class/function docstrings before comparing merge-base to this PR. A `#` or docstring change on `ingest.py` does not run `ingest_bulk`.
- `demo_service/app/main.py` — request routing only.
- `demo_service/app/config.py` and `health.py` — cold paths; covered by `global_filters` plus simply not listing them.
- Transitive / shared-library changes outside listed paths. The nightly workflow is the backstop for regressions that the path matcher cannot see.
- Auto-discovery from production traces. Inside a larger org that would be Tracer/Argus + codesearch; the manifest schema does not change.

## Thresholds

Each operation has `threshold_pct` and `threshold_ms`. On a PR, last good is the merge-base median and this PR is the candidate. A result is a **regression** if the median exceeds last good by *either* bound, and a **warning** at half those bounds. After two captures on the same machine swung ~25% on serialize, demo-platform thresholds were tuned to 30% (and 80ms on serialize) so ordinary noise does not page. Product PRs never fail closed; `perf.yml` is `continue-on-error: true`. The comment names a first-bad PR; it does not mark the PR unmergeable.
