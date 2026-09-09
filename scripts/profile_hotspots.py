"""cProfile ingest serialize and query scan; print hottest frames."""

from __future__ import annotations

import cProfile
import pstats
from io import StringIO

from demo_service.app.export import export_jsonl
from demo_service.app.index import index_records
from demo_service.app.ingest import serialize_records
from demo_service.app.query import scan_filter
from demo_service.app.store import RecordStore
from demo_service.workloads.ingest_bulk import generate_records


def _run_ingest() -> None:
    records = generate_records()
    serialized = serialize_records(records)
    index_records(serialized, store=RecordStore())


def _profile_query() -> str:
    store = RecordStore()
    records = generate_records()
    serialized = serialize_records(records)
    index_records(serialized, store=store)

    def _scan() -> None:
        scan_filter(tag="alpha", store=store)

    return _profile(_scan, "query scan_filter")


def _profile_export() -> str:
    store = RecordStore()
    records = generate_records()
    serialized = serialize_records(records)
    index_records(serialized, store=store)

    def _export() -> None:
        export_jsonl(store=store)

    return _profile(_export, "export export_jsonl")


def _profile(fn, label: str) -> str:
    profiler = cProfile.Profile()
    profiler.enable()
    fn()
    profiler.disable()
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumtime")
    stats.print_stats(15)
    return f"## {label}\n{stream.getvalue()}"


def main() -> None:
    print(_profile(_run_ingest, "ingest serialize + index"))
    print(_profile_query())
    print(_profile_export())


if __name__ == "__main__":
    main()
