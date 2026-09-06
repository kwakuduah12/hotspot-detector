"""Load and validate a hotspot manifest."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class OperationSpec(BaseModel):
    name: str
    baseline_ms: float | None = None
    threshold_pct: float = 20.0
    threshold_ms: float = 40.0


class WorkloadSpec(BaseModel):
    description: str = ""
    command: list[str]
    repeats: int = 5
    operations: list[OperationSpec] = Field(default_factory=list)


class Hotspot(BaseModel):
    id: str
    paths: list[str]
    workloads: list[str]
    notes: str = ""


class GlobalFilters(BaseModel):
    exclude_paths: list[str] = Field(default_factory=list)


class Manifest(BaseModel):
    version: int
    service_area: str
    global_filters: GlobalFilters = Field(default_factory=GlobalFilters)
    hotspots: list[Hotspot]
    workloads: dict[str, WorkloadSpec]

    @model_validator(mode="after")
    def workloads_exist(self) -> Manifest:
        known = set(self.workloads)
        for hotspot in self.hotspots:
            missing = [w for w in hotspot.workloads if w not in known]
            if missing:
                raise ValueError(
                    f"hotspot {hotspot.id!r} references unknown workloads: {missing}"
                )
        return self

    def operation_map(self, workload_id: str) -> dict[str, OperationSpec]:
        spec = self.workloads[workload_id]
        return {op.name: op for op in spec.operations}


def load_manifest(path: str | Path) -> Manifest:
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError(f"manifest {path} is not a mapping")
    return Manifest.model_validate(data)


class BaselineCapture(BaseModel):
    service_area: str | None = None
    captured_at: str | None = None
    environment: dict = Field(default_factory=dict)
    repeats: int | None = None
    operations: dict[str, dict[str, dict[str, float]]] = Field(default_factory=dict)


def load_baselines(path: str | Path) -> BaselineCapture:
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError(f"baselines {path} is not a mapping")
    return BaselineCapture.model_validate(data)
