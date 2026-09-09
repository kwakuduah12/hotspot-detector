import httpx
import pytest

from demo_service.workloads import export_jsonl as export_workload
from demo_service.workloads import query_filter

from demo_service.app.config import APP_NAME
from demo_service.app.export import export_jsonl
from demo_service.app.health import health_payload
from demo_service.app.index import index_records
from demo_service.app.ingest import serialize_records
from demo_service.app.main import app
from demo_service.app.query import scan_filter
from demo_service.app.store import RecordStore
from demo_service.workloads.ingest_bulk import generate_records


@pytest.fixture
def store():
    target = RecordStore()
    yield target
    target.reset()


def test_health_payload():
    assert health_payload() == {"status": "ok"}
    assert APP_NAME == "demo-platform"


def test_serialize_index_query_export_roundtrip(store):
    records = generate_records(40)
    serialized = serialize_records(records)
    assert len(serialized) == 40
    assert all("_digest" in row for row in serialized)

    stats = index_records(serialized, store=store)
    assert stats["indexed"] == 40
    assert stats["unique_ids"] == 40

    matched = scan_filter(tag="alpha", store=store)
    assert matched
    assert matched[0]["_score"] >= matched[-1]["_score"]

    exported = export_jsonl(store=store)
    assert exported.count("\n") == 40


def test_query_without_tag_returns_all(store):
    serialized = serialize_records(generate_records(10))
    index_records(serialized, store=store)
    assert len(scan_filter(store=store)) == 10


def test_serialize_respects_slowdown_rounds(monkeypatch):
    monkeypatch.setenv("HOTSPOT_SLOWDOWN_ROUNDS", "2")
    monkeypatch.setenv("HOTSPOT_SLOWDOWN_MS", "1")
    out = serialize_records([{"id": "1", "name": "n", "tags": []}])
    assert out[0]["_digest"]


def test_routes_are_registered():
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/health" in paths
    assert "/ingest/serialize" in paths
    assert "/ingest/index" in paths
    assert "/query" in paths
    assert "/export" in paths


def test_query_filter_workload_requires_a_server():
    with pytest.raises(httpx.ConnectError):
        query_filter.run("http://127.0.0.1:9")


def test_export_jsonl_workload_requires_a_server():
    with pytest.raises(httpx.ConnectError):
        export_workload.run("http://127.0.0.1:9")
