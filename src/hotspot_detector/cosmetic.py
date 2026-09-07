"""Ignore comment, docstring, and whitespace-only edits on hotspot files."""

from __future__ import annotations

import ast
from pathlib import Path

from hotspot_detector.ab import git_show


def _strip_docstrings(node: ast.AST) -> None:
    if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        body = list(node.body)
        if body and isinstance(body[0], ast.Expr):
            value = body[0].value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                node.body = body[1:] or [ast.Pass()]
    for child in ast.iter_child_nodes(node):
        _strip_docstrings(child)


def _normalized_ast(source: str) -> str | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    _strip_docstrings(tree)
    return ast.dump(tree, include_attributes=False)


def is_cosmetic_python_change(old: str | None, new: str | None) -> bool:
    """True when both sides parse and the runtime AST is unchanged.

    Comments are not in the AST. Module/class/function docstrings are stripped.
    Added or deleted files are never cosmetic. Unparseable Python is not cosmetic.
    """
    if old is None or new is None:
        return False
    old_ast = _normalized_ast(old)
    new_ast = _normalized_ast(new)
    if old_ast is None or new_ast is None:
        return False
    return old_ast == new_ast


def is_cosmetic_path(repo_root: Path, base_sha: str, path: str) -> bool:
    """Compare merge-base contents to the working tree (or HEAD if missing)."""
    normalized = path.replace("\\", "/")
    if not normalized.endswith(".py"):
        return False
    old = git_show(repo_root, base_sha, normalized)
    disk = repo_root / normalized
    if disk.is_file():
        new = disk.read_text(encoding="utf-8")
    else:
        new = git_show(repo_root, "HEAD", normalized)
    return is_cosmetic_python_change(old, new)
