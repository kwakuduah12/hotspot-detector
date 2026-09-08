import pytest

from hotspot_detector.ab import git_rev_parse, last_good_worktree, resolve_merge_base, short_sha


def test_git_rev_parse_head(repo_root):
    sha = git_rev_parse(repo_root, "HEAD")
    assert len(sha) == 40


def test_git_rev_parse_unknown_ref(repo_root):
    with pytest.raises(RuntimeError, match="unknown git ref"):
        git_rev_parse(repo_root, "definitely-not-a-ref")


def test_resolve_merge_base_head(repo_root):
    assert resolve_merge_base(repo_root, "HEAD") == git_rev_parse(repo_root, "HEAD")


def test_short_sha(repo_root):
    sha = git_rev_parse(repo_root, "HEAD")
    short = short_sha(repo_root, sha)
    assert sha.startswith(short)
    assert 4 <= len(short) <= 12


def test_last_good_worktree_has_manifest(repo_root, manifest_path):
    sha = git_rev_parse(repo_root, "HEAD")
    rel = manifest_path.resolve().relative_to(repo_root.resolve())
    with last_good_worktree(repo_root, sha) as tree:
        assert (tree / rel).is_file()
        assert (tree / "demo_service" / "app" / "ingest.py").is_file()


def test_last_good_worktree_rejects_bad_sha(repo_root):
    with pytest.raises(RuntimeError, match="worktree add failed"):
        with last_good_worktree(repo_root, "0" * 40):
            pass
