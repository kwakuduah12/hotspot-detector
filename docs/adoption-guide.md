# Adoption guide

Onboard a service area by adding a manifest and a workload that prints operation timings. The CLI does not change.

The worked example is **demo-platform** (`demo_service/`).

## Prerequisites

- A command that exercises the sensitive path and prints **only** a JSON array to stdout:

```json
[{"operation": "serialize", "duration_ms": 42.1}]
```

- A test environment the runner can provision (Docker Compose in this repo, or any process that serves `GET /health`).

## Steps

1. **Identify hotspots.** Profile a representative load. Map top frames to source files. Write the reasoning down (copy `docs/methodology.md`).
2. **Add `hotspot-manifest.yaml`.** Glob the hotspot files to one or more workloads. Set `threshold_pct` and `threshold_ms` per operation. Exclude docs/tests via `global_filters`.
3. **Add a workload module** whose `command` is listed in the manifest (see `demo_service/workloads/ingest_bulk.py`).
4. **Capture baselines** in the test environment:

```bash
hotspot-detector capture \
  --manifest path/to/hotspot-manifest.yaml \
  --output path/to/baselines.yaml
```

5. **Copy the workflows.** Point `--manifest` at your file and keep `--base-ref origin/<base>` so CI measures last good (merge-base) then this PR in one job. Keep `perf.yml` non-blocking (`continue-on-error: true`). Keep `tests` required so a planted slowdown still fails CI if the detector regresses.
6. **Prove the loop.** Open a test PR that touches a hotspot file, or run:

```bash
python scripts/plant_regression.py
```

That script starts the demo service with `HOTSPOT_SLOWDOWN_MS=150` and expects `gate --strict` to report a regression.

## Worked example (demo-platform)

| Piece | Location |
|---|---|
| Manifest | `demo_service/hotspot-manifest.yaml` |
| Baselines | `demo_service/baselines.yaml` |
| Ingest hotspot | `demo_service/app/ingest.py`, `index.py` → `ingest_bulk` |
| Query hotspot | `demo_service/app/query.py` → `query_filter` |
| Export hotspot | `demo_service/app/export.py` → `export_jsonl` |
| Cold paths | `config.py`, `health.py` (not listed) |

A docs-only change (`docs/**`, `**/*.md`, `tests/**`) matches nothing and the gate exits 0 without posting a comment. The same skip applies to comment, docstring, or whitespace-only edits in a hotspot `.py` file (compared to `--base-ref`). Matching uses the merge-base manifest so a PR cannot delete hotspots to skip, and unions hotspots the PR adds so a first onboard still runs. New workloads use the PR command (last good is still the merge-base SUT; golden / `baseline_ms` is the fallback until the next capture).

## Recorded CI proofs

- **First-bad / synthetic regression:** closed [PR #2](https://github.com/kwakuduah12/hotspot-detector/pull/2) planted a 150ms serialize sleep. The gate posted `regression`. Do not merge that change.
- **Docs-only quiet skip:** [PR #5](https://github.com/kwakuduah12/hotspot-detector/pull/5). `perf.yml` listed markdown, printed a skip, and posted no sticky comment.
- **First onboard skip (old behavior):** [PR #6](https://github.com/kwakuduah12/hotspot-detector/pull/6) added the export hotspot while matching used only the merge-base manifest, so the gate quiet-skipped. Matching now unions base hotspots with PR-added ones; a later onboard PR that touches the new path should run.
- **Live export trigger:** [PR #7](https://github.com/kwakuduah12/hotspot-detector/pull/7) touched `export.py` after the hotspot was on `main`. CI ran `export_jsonl`, posted last good vs this PR (`ok`, 137.1ms → 136.3ms), and a golden section.
- **Golden ~129ms:** [PR #9](https://github.com/kwakuduah12/hotspot-detector/pull/9) confirmed vs golden `materialize` **129.0ms** (not the old 73ms laptop fallback). Last good vs this PR was `ok`. The list-comprehension refactor was reverted in [PR #11](https://github.com/kwakuduah12/hotspot-detector/pull/11) (`ok` vs last good and vs golden).
- **Fixture golden is not a floor:** closed [PR #10](https://github.com/kwakuduah12/hotspot-detector/pull/10) was a nightly suggestion from a missing-export dispatch, same-day 123–138ms noise. Do not merge fixture branches or accept a suggested PR that did not run on `main`.

## Shadow snippet (next area)

`demo_service/candidates.yaml` is empty. The export path was the worked example of a warm candidate promoted into the live manifest: add a workload, set thresholds, capture a fallback `baseline_ms`, and move the hotspot entry. No CLI changes.

## Tuning

Thresholds live in the manifest. Tighten `threshold_pct` / `threshold_ms` after you have a few clean runs. Do not make `perf.yml` required until you are ready to block merges; the success bar for v1 is “results posted without blocking standard development flow.”
