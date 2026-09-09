"""Workload: seed then JSONL export of the full store. Prints timings as JSON."""

from __future__ import annotations

import json
import os
import time

import httpx

from demo_service.workloads.ingest_bulk import generate_records


def run(base_url: str | None = None) -> list[dict]:
    base = (base_url or os.environ.get("HOTSPOT_BASE_URL", "http://127.0.0.1:8000")).rstrip(
        "/"
    )
    records = generate_records()
    with httpx.Client(timeout=60.0) as client:
        seed = client.post(f"{base}/ingest", json={"records": records})
        seed.raise_for_status()

        t0 = time.perf_counter()
        resp = client.get(f"{base}/export")
        resp.raise_for_status()
        materialize_ms = (time.perf_counter() - t0) * 1000.0
        body = resp.text
        if body.count("\n") < 1:
            raise RuntimeError("export returned no records")

    return [{"operation": "materialize", "duration_ms": round(materialize_ms, 3)}]


def main() -> None:
    print(json.dumps(run()))


if __name__ == "__main__":
    main()
