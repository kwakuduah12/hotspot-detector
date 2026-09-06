"""Hot path: in-memory secondary indexes built after serialize."""

from __future__ import annotations

import hashlib

from demo_service.app.store import STORE, RecordStore

INDEX_ROUNDS = 48


def index_records(records: list[dict], store: RecordStore | None = None) -> dict:
    target = store or STORE
    fingerprint = "0"
    for record in records:
        digest = str(record.get("_digest", ""))
        fingerprint = hashlib.sha256(f"{fingerprint}:{digest}".encode()).hexdigest()
        for i in range(INDEX_ROUNDS):
            fingerprint = hashlib.sha256(f"{fingerprint}:{i}".encode()).hexdigest()
    target.replace(records)
    return {
        "indexed": len(records),
        "unique_ids": len(target.by_id),
        "tags": len(target.by_tag),
        "_fingerprint": fingerprint,
    }
