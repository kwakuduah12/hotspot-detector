# hotspot-detector

Event-driven performance testing. When a pull request touches code that is known to be performance-sensitive, run only the workloads that exercise those paths, compare this PR to a **last-good** run of the merge-base in the same CI environment, and post a **non-blocking** report.

Scheduled nightly runs remain the backstop. This tool adds a targeted signal at PR time.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Match a changed-file list against the demo service manifest:

```bash
echo 'demo_service/app/ingest.py' > /tmp/changed.txt
hotspot-detector match \
  --manifest demo_service/hotspot-manifest.yaml \
  --changed-files /tmp/changed.txt
```

Run workloads against a local test environment (Docker when available, otherwise uvicorn):

```bash
hotspot-detector run \
  --manifest demo_service/hotspot-manifest.yaml \
  --all \
  --output run.json
```

Compare this PR to last good (merge-base) in one environment:

```bash
hotspot-detector gate \
  --manifest demo_service/hotspot-manifest.yaml \
  --changed-files /tmp/changed.txt \
  --base-ref origin/main
```

Dry-run (print the plan, do not provision):

```bash
HOTSPOT_DRY_RUN=1 hotspot-detector run \
  --manifest demo_service/hotspot-manifest.yaml \
  --workloads ingest_bulk \
  --output run.json
```

## Layout

- `src/hotspot_detector/` — reusable CLI (`match`, `run`, `compare`, `report`, `gate`, `capture`)
- `demo_service/` — in-repo lab (FastAPI)
- [`inbox-api`](https://github.com/kwakuduah12/inbox-api) — separate watched service; CI installs this CLI from GitHub
- `docs/methodology.md` — how a path becomes a hotspot
- `docs/baseline-metrics.md` — how baselines were captured
- `docs/adoption-guide.md` — how another team onboards

## Docs-only PRs

Changes under `docs/**`, `**/*.md`, and `tests/**` are excluded. Comment, docstring, or whitespace-only edits to a hotspot `.py` file are also skipped when `gate`/`match` has `--base-ref`. The gate prints a skip and exits 0 with no comment.
