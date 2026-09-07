from hotspot_detector.cosmetic import is_cosmetic_path, is_cosmetic_python_change
from hotspot_detector.matcher import evaluate_pr_diff

OLD = '''\
"""Module docstring."""

def serialize_records(records):
    """Normalize records."""
    extra_ms = 0  # unused
    return records
'''


def test_comment_only_is_cosmetic():
    new = OLD.replace("# unused", "# still unused")
    assert is_cosmetic_python_change(OLD, new) is True


def test_docstring_only_is_cosmetic():
    new = OLD.replace("Module docstring.", "A longer module docstring.")
    new = new.replace("Normalize records.", "Normalize and hash records.")
    assert is_cosmetic_python_change(OLD, new) is True


def test_whitespace_only_is_cosmetic():
    new = OLD.replace("extra_ms = 0", "extra_ms    =    0")
    assert is_cosmetic_python_change(OLD, new) is True


def test_code_change_is_not_cosmetic():
    new = OLD.replace("extra_ms = 0", "extra_ms = 150")
    assert is_cosmetic_python_change(OLD, new) is False


def test_comment_plus_code_is_not_cosmetic():
    new = OLD.replace("# unused", "# planted").replace("return records", "return []")
    assert is_cosmetic_python_change(OLD, new) is False


def test_added_or_deleted_is_not_cosmetic():
    assert is_cosmetic_python_change(None, OLD) is False
    assert is_cosmetic_python_change(OLD, None) is False


def test_unparseable_is_not_cosmetic():
    assert is_cosmetic_python_change(OLD, "def broken(") is False


def test_non_python_path_is_not_cosmetic(repo_root):
    sha = "HEAD"
    assert is_cosmetic_path(repo_root, sha, "docker-compose.yml") is False


def test_missing_python_file_is_not_cosmetic(repo_root):
    assert is_cosmetic_path(repo_root, "HEAD", "demo_service/app/does_not_exist.py") is False


def test_matcher_skips_cosmetic_hotspot(manifest):
    result = evaluate_pr_diff(
        ["demo_service/app/ingest.py"],
        manifest,
        is_cosmetic=lambda path: path.endswith("ingest.py"),
    )
    assert result.trigger is False
    assert result.cosmetic_files == ["demo_service/app/ingest.py"]
    assert result.matched_files == []
    assert "comments, docstrings, or whitespace" in (result.skip_reason() or "")


def test_matcher_keeps_code_sibling_when_other_file_is_cosmetic(manifest):
    result = evaluate_pr_diff(
        ["demo_service/app/ingest.py", "demo_service/app/query.py"],
        manifest,
        is_cosmetic=lambda path: path.endswith("ingest.py"),
    )
    assert result.trigger is True
    assert result.workloads == ["query_filter"]
    assert result.cosmetic_files == ["demo_service/app/ingest.py"]
    assert result.matched_files == ["demo_service/app/query.py"]
