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
_SEPARATORS = (",", ":")


def _round_trip_json(payload: str) -> str:
    """Repeat dumps/loads so export stays allocation-heavy."""
    dumps = json.dumps
    loads = json.loads
    for _ in range(JSON_PASSES):
        payload = dumps(loads(payload), sort_keys=True, separators=_SEPARATORS)
    return payload


def export_jsonl(store: RecordStore | None = None) -> str:
    """Serialize the whole store to JSONL. Intentionally allocation-heavy."""
    target = store or STORE
    lines: list[str] = []
    for record in target.records:
        payload = json.dumps(record, sort_keys=True, separators=_SEPARATORS)
        lines.append(_round_trip_json(payload))
    return "\n".join(lines) + ("\n" if lines else "")
