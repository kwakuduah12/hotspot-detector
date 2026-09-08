"""Hot path: CPU-bound record serialization.

A path is a hotspot when it sits on the critical ingest path and profiling
shows it dominating CPU. See docs/methodology.md.

Plant a synthetic regression with:
  HOTSPOT_SLOWDOWN_MS   sleep added once per serialize call
  HOTSPOT_SLOWDOWN_ROUNDS extra sha256 rounds per record

This file is a hotspot: PRs that touch it should trigger ingest_bulk.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

HASH_ROUNDS = 256


def _effective_rounds() -> int:
    extra = int(os.environ.get("HOTSPOT_SLOWDOWN_ROUNDS", "0") or 0)
    return HASH_ROUNDS + extra


def serialize_records(records: list[dict]) -> list[dict]:
    """Normalize, hash, and expand each record. Intentionally CPU-heavy."""
    extra_ms = float(os.environ.get("HOTSPOT_SLOWDOWN_MS", "0") or 0)
    if extra_ms > 0:
        time.sleep(extra_ms / 1000.0)

    rounds = _effective_rounds()
    out: list[dict] = []
    for record in records:
        payload = json.dumps(record, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        for i in range(rounds):
            digest = hashlib.sha256(f"{digest}:{i}".encode("utf-8")).hexdigest()
        out.append(
            {
                **record,
                "_digest": digest,
                "_size": len(payload),
                "_normalized": payload,
            }
        )
    return out
