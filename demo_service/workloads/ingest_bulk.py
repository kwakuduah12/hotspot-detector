"""Workload: bulk ingest serialize + index. Prints operation timings as JSON."""

from __future__ import annotations

import json
import os
import time

import httpx

RECORD_COUNT = 1200


def generate_records(count: int = RECORD_COUNT) -> list[dict]:
    records = []
    tags = ["alpha", "beta", "gamma"]
    for i in range(count):
        records.append(
            {
                "id": f"rec-{i:05d}",
                "name": f"record-{i}",
                "payload": {"n": i, "blob": "x" * ((i % 17) + 8)},
                "tags": [tags[i % len(tags)], tags[(i + 1) % len(tags)]],
            }
        )
    return records


def run(base_url: str | None = None) -> list[dict]:
    base = (base_url or os.environ.get("HOTSPOT_BASE_URL", "http://127.0.0.1:8000")).rstrip(
        "/"
    )
    records = generate_records()
    with httpx.Client(timeout=60.0) as client:
        t0 = time.perf_counter()
        serialize_resp = client.post(f"{base}/ingest/serialize", json={"records": records})
        serialize_resp.raise_for_status()
        serialize_ms = (time.perf_counter() - t0) * 1000.0
        serialized = serialize_resp.json()["records"]

        t1 = time.perf_counter()
        index_resp = client.post(f"{base}/ingest/index", json={"records": serialized})
        index_resp.raise_for_status()
        index_ms = (time.perf_counter() - t1) * 1000.0

    return [
        {"operation": "serialize", "duration_ms": round(serialize_ms, 3)},
        {"operation": "index", "duration_ms": round(index_ms, 3)},
    ]


def main() -> None:
    print(json.dumps(run()))


if __name__ == "__main__":
    main()
