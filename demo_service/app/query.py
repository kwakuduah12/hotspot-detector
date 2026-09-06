"""Hot path: allocation-heavy scan and filter over the in-memory store."""

from __future__ import annotations

from demo_service.app.store import STORE, RecordStore


SCORE_ROUNDS = 400


def _score(record: dict) -> float:
    digest = str(record.get("_digest", "0"))
    size = int(record.get("_size", 0))
    tag_bonus = len(record.get("tags", [])) * 1.7
    acc = 0.0
    for i in range(SCORE_ROUNDS):
        acc += (int(digest[i % len(digest)], 16) + i) * 0.01
    return float(size) + (int(digest[:8], 16) % 1000) / 100.0 + tag_bonus + acc


def scan_filter(
    tag: str | None = None,
    store: RecordStore | None = None,
) -> list[dict]:
    """Build a new scored projection for every matching record."""
    target = store or STORE
    matched: list[dict] = []
    for record in target.records:
        tags = [str(t) for t in record.get("tags", [])]
        if tag and tag not in tags:
            continue
        projection = {
            "id": record.get("id"),
            "name": record.get("name"),
            "tags": list(tags),
            "_score": _score(record),
            "_digest": record.get("_digest"),
        }
        matched.append(projection)
    matched.sort(key=lambda row: row["_score"], reverse=True)
    return matched
