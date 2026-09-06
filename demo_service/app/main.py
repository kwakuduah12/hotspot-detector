"""FastAPI app exposing hot, warm, and cold paths."""

from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from demo_service.app import config
from demo_service.app.export import export_jsonl
from demo_service.app.health import health_payload
from demo_service.app.index import index_records
from demo_service.app.ingest import serialize_records
from demo_service.app.query import scan_filter
from demo_service.app.store import STORE

app = FastAPI(title=config.APP_NAME, version=config.VERSION)


class RecordBatch(BaseModel):
    records: list[dict] = Field(default_factory=list)


@app.get("/health")
def health() -> dict:
    return health_payload()


@app.get("/config")
def get_config() -> dict:
    return {
        "name": config.APP_NAME,
        "version": config.VERSION,
        "page_size": config.DEFAULT_PAGE_SIZE,
    }


@app.post("/ingest/serialize")
def ingest_serialize(batch: RecordBatch) -> dict:
    serialized = serialize_records(batch.records)
    return {"records": serialized, "count": len(serialized)}


@app.post("/ingest/index")
def ingest_index(batch: RecordBatch) -> dict:
    stats = index_records(batch.records)
    return stats


@app.post("/ingest")
def ingest(batch: RecordBatch) -> dict:
    serialized = serialize_records(batch.records)
    stats = index_records(serialized)
    return {"count": stats["indexed"], **stats}


@app.get("/query")
def query(tag: str | None = Query(default=None)) -> dict:
    matched = scan_filter(tag=tag)
    return {"count": len(matched), "records": matched}


@app.get("/export", response_class=PlainTextResponse)
def export() -> str:
    return export_jsonl()


@app.post("/reset")
def reset() -> dict:
    STORE.reset()
    return {"reset": True}
