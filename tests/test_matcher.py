from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from hotspot_detector.manifest import load_manifest
from hotspot_detector.matcher import evaluate_pr_diff, glob_to_regex, path_matches


def test_glob_double_star_markdown():
    assert path_matches("docs/foo.md", "**/*.md")
    assert path_matches("README.md", "**/*.md")
    assert not path_matches("demo_service/app/ingest.py", "**/*.md")


def test_glob_docs_tree():
    assert path_matches("docs/methodology.md", "docs/**")
    assert not path_matches("demo_service/app/ingest.py", "docs/**")


def test_glob_single_star_in_directory():
    assert path_matches("demo_service/app/ingest.py", "demo_service/app/*.py")
    assert not path_matches("demo_service/app/store.py.bak", "demo_service/app/*.py")


def test_windows_separators_normalize(manifest):
    result = evaluate_pr_diff([r"demo_service\app\ingest.py"], manifest)
    assert result.trigger is True
    assert result.workloads == ["ingest_bulk"]


def test_directory_prefix_pattern():
    assert path_matches("docs/foo/bar.md", "docs/")


def test_exclude_only_skips(manifest):
    result = evaluate_pr_diff(
        ["docs/adoption-guide.md", "README.md", "tests/test_matcher.py"],
        manifest,
    )
    assert result.trigger is False
    assert result.workloads == []
    assert result.relevant_files == []


def test_empty_change_list_skips(manifest):
    result = evaluate_pr_diff([], manifest)
    assert result.trigger is False
    assert result.workloads == []


def test_single_hotspot_ingest(manifest):
    result = evaluate_pr_diff(["demo_service/app/ingest.py"], manifest)
    assert result.trigger is True
    assert result.hotspots == ["ingest-path"]
    assert result.workloads == ["ingest_bulk"]
    assert result.matched_files == ["demo_service/app/ingest.py"]


def test_query_hotspot(manifest):
    result = evaluate_pr_diff(["demo_service/app/query.py"], manifest)
    assert result.trigger is True
    assert "query_filter" in result.workloads
    assert "ingest_bulk" not in result.workloads


def test_many_to_many_union(manifest):
    result = evaluate_pr_diff(
        ["demo_service/app/ingest.py", "demo_service/app/query.py"],
        manifest,
    )
    assert result.trigger is True
    assert set(result.workloads) == {"ingest_bulk", "query_filter"}
    assert set(result.hotspots) == {"ingest-path", "query-path"}


def test_duplicate_file_does_not_duplicate_workload(manifest):
    result = evaluate_pr_diff(
        ["demo_service/app/ingest.py", "demo_service/app/index.py"],
        manifest,
    )
    assert result.workloads == ["ingest_bulk"]
    assert result.hotspots == ["ingest-path"]


def test_cold_config_does_not_match(manifest):
    result = evaluate_pr_diff(["demo_service/app/config.py"], manifest)
    assert result.trigger is False
    assert result.relevant_files == ["demo_service/app/config.py"]


def test_warm_export_is_onboarded(manifest):
    result = evaluate_pr_diff(["demo_service/app/export.py"], manifest)
    assert result.trigger is True
    assert result.workloads == ["export_jsonl"]
    assert result.hotspots == ["export-path"]


def test_mixed_docs_and_hotspot(manifest):
    result = evaluate_pr_diff(
        ["docs/methodology.md", "demo_service/app/index.py"],
        manifest,
    )
    assert result.trigger is True
    assert result.workloads == ["ingest_bulk"]
    assert "docs/methodology.md" in result.excluded_files


def test_unknown_workload_rejected(tmp_path):
    bad = {
        "version": 1,
        "service_area": "x",
        "hotspots": [{"id": "h", "paths": ["a.py"], "workloads": ["missing"]}],
        "workloads": {},
    }
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(bad))
    with pytest.raises(ValidationError, match="unknown workloads"):
        load_manifest(path)


def test_manifest_rejects_non_mapping(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- not-a-mapping\n")
    with pytest.raises(ValueError, match="not a mapping"):
        load_manifest(path)


def test_glob_to_regex_question_mark():
    regex = glob_to_regex("demo_service/app/ingest.p?")
    assert regex.match("demo_service/app/ingest.py")
