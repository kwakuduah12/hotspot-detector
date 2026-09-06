"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from hotspot_detector.manifest import load_manifest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "demo_service" / "hotspot-manifest.yaml"
BASELINES_PATH = ROOT / "demo_service" / "baselines.yaml"


@pytest.fixture
def repo_root() -> Path:
    return ROOT


@pytest.fixture
def manifest_path() -> Path:
    return MANIFEST_PATH


@pytest.fixture
def baselines_path() -> Path:
    return BASELINES_PATH


@pytest.fixture
def manifest():
    return load_manifest(MANIFEST_PATH)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
