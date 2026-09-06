# hotspot-detector

Event-driven performance testing. When a pull request touches code that is known to be performance-sensitive, run only the workloads that exercise those paths, compare operation runtimes to stored baselines, and post a **non-blocking** report.

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

Dry-run (print the plan, do not provision):

```bash
HOTSPOT_DRY_RUN=1 hotspot-detector run \
  --manifest demo_service/hotspot-manifest.yaml \
  --workloads ingest_bulk \
  --output run.json
```

## Layout

- `src/hotspot_detector/` — reusable CLI (`match`, `run`, `compare`, `report`, `gate`, `capture`)
- `demo_service/` — first onboarded service area (FastAPI)
- `docs/methodology.md` — how a path becomes a hotspot
- `docs/baseline-metrics.md` — how baselines were captured
- `docs/adoption-guide.md` — how another team onboards

## Docs-only PRs

Changes under `docs/**`, `**/*.md`, and `tests/**` are excluded. The gate prints a skip and exits 0 with no comment.
