"""Hot path: allocation-heavy JSONL export of the full store.

Walks every record, round-trips JSON, and materializes JSONL. A path is a
hotspot when it sits on a user-visible export and profiling shows it
dominating allocations. See docs/methodology.md.

This file is a hotspot: PRs that touch it should trigger export_jsonl.
"""

from __future__ import annotations

import json

from demo_service.app.store import STORE, RecordStore

JSON_PASSES = 12


def export_jsonl(store: RecordStore | None = None) -> str:
    """Serialize the whole store to JSONL. Intentionally allocation-heavy."""
    target = store or STORE
    lines: list[str] = []
    for record in target.records:
        payload = json.dumps(record, sort_keys=True, separators=(",", ":"))
        for _ in range(JSON_PASSES):
            payload = json.dumps(json.loads(payload), sort_keys=True, separators=(",", ":"))
        lines.append(payload)
    return "\n".join(lines) + ("\n" if lines else "")
