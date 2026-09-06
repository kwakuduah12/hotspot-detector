"""Warm path: identified as performance-sensitive, not wired in v1.

Export walks the full store and materializes a JSONL payload. It is a
candidate hotspot (see demo_service/candidates.yaml) until a workload and
baseline exist.
"""

from __future__ import annotations

import json

from demo_service.app.store import STORE, RecordStore


def export_jsonl(store: RecordStore | None = None) -> str:
    target = store or STORE
    lines = [json.dumps(record, sort_keys=True) for record in target.records]
    return "\n".join(lines) + ("\n" if lines else "")
