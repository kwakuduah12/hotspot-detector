"""Last-good vs first-bad: same CI environment, merge-base vs this PR."""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def git_rev_parse(repo_root: Path, ref: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    sha = completed.stdout.strip()
    if completed.returncode != 0 or not sha:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"unknown git ref {ref!r}: {detail}")
    return sha


def resolve_merge_base(repo_root: Path, base_ref: str) -> str:
    git_rev_parse(repo_root, base_ref)
    completed = subprocess.run(
        ["git", "merge-base", "HEAD", base_ref],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    sha = completed.stdout.strip()
    if completed.returncode == 0 and sha:
        return sha
    return git_rev_parse(repo_root, base_ref)


def git_show(repo_root: Path, ref: str, path: str) -> str | None:
    completed = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout


def short_sha(repo_root: Path, sha: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "--short", sha],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() or sha[:7]


@contextmanager
def last_good_worktree(repo_root: Path, sha: str) -> Iterator[Path]:
    """Detach a worktree at *sha* so last-good can build without touching HEAD."""
    dest = Path(tempfile.mkdtemp(prefix="hotspot-last-good-"))
    dest.rmdir()
    added = subprocess.run(
        ["git", "worktree", "add", "--detach", str(dest), sha],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if added.returncode != 0:
        raise RuntimeError(
            f"git worktree add failed for {sha}: {(added.stderr or added.stdout).strip()}"
        )
    try:
        yield dest
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(dest)],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
