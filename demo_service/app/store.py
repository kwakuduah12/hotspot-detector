"""In-memory record store shared by ingest, index, and query."""

from __future__ import annotations


class RecordStore:
    def __init__(self) -> None:
        self.records: list[dict] = []
        self.by_id: dict[str, dict] = {}
        self.by_tag: dict[str, list[str]] = {}

    def reset(self) -> None:
        self.records.clear()
        self.by_id.clear()
        self.by_tag.clear()

    def replace(self, records: list[dict]) -> None:
        self.reset()
        self.records.extend(records)
        for record in records:
            record_id = str(record["id"])
            self.by_id[record_id] = record
            for tag in record.get("tags", []):
                self.by_tag.setdefault(str(tag), []).append(record_id)


STORE = RecordStore()
