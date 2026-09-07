"""Match changed files against a hotspot manifest."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from hotspot_detector.manifest import Manifest


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Convert a glob with `*` / `**` / `?` into a full-match regex."""
    pattern = pattern.replace("\\", "/")
    out: list[str] = ["^"]
    i = 0
    n = len(pattern)
    while i < n:
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
            continue
        if pattern.startswith("**", i) and (i + 2 == n or pattern[i + 2] == "/"):
            out.append(".*")
            i += 2
            continue
        ch = pattern[i]
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    out.append("$")
    return re.compile("".join(out))


def path_matches(path: str, pattern: str) -> bool:
    normalized = path.replace("\\", "/")
    regex = glob_to_regex(pattern)
    if regex.match(normalized):
        return True
    # Allow patterns that omit a trailing ** file match against directories.
    if pattern.endswith("/") and normalized.startswith(pattern):
        return True
    return False


@dataclass
class MatchResult:
    trigger: bool
    hotspots: list[str] = field(default_factory=list)
    workloads: list[str] = field(default_factory=list)
    matched_files: list[str] = field(default_factory=list)
    excluded_files: list[str] = field(default_factory=list)
    relevant_files: list[str] = field(default_factory=list)
    cosmetic_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "trigger": self.trigger,
            "hotspots": self.hotspots,
            "workloads": self.workloads,
            "matched_files": self.matched_files,
            "excluded_files": self.excluded_files,
            "relevant_files": self.relevant_files,
            "cosmetic_files": self.cosmetic_files,
        }

    def skip_reason(self) -> str | None:
        if self.trigger:
            return None
        if self.cosmetic_files:
            return (
                "Hotspot files changed but only comments, docstrings, or "
                "whitespace; skipping workloads."
            )
        return "No hotspot files changed; skipping workloads."


def evaluate_pr_diff(
    changed_files: list[str],
    manifest: Manifest,
    *,
    is_cosmetic: Callable[[str], bool] | None = None,
) -> MatchResult:
    exclusions = manifest.global_filters.exclude_paths
    excluded: list[str] = []
    relevant: list[str] = []

    for path in changed_files:
        if any(path_matches(path, pattern) for pattern in exclusions):
            excluded.append(path)
        else:
            relevant.append(path)

    if not relevant:
        return MatchResult(
            trigger=False,
            excluded_files=excluded,
            relevant_files=relevant,
        )

    matched_workloads: set[str] = set()
    matched_hotspots: list[str] = []
    matched_files: list[str] = []
    cosmetic_files: list[str] = []

    for hotspot in manifest.hotspots:
        hotspot_hit = False
        for path in relevant:
            if not any(path_matches(path, pattern) for pattern in hotspot.paths):
                continue
            if is_cosmetic is not None and is_cosmetic(path):
                if path not in cosmetic_files:
                    cosmetic_files.append(path)
                continue
            hotspot_hit = True
            if path not in matched_files:
                matched_files.append(path)
        if hotspot_hit:
            matched_hotspots.append(hotspot.id)
            matched_workloads.update(hotspot.workloads)

    workloads = sorted(matched_workloads)
    return MatchResult(
        trigger=bool(workloads),
        hotspots=matched_hotspots,
        workloads=workloads,
        matched_files=matched_files,
        excluded_files=excluded,
        relevant_files=relevant,
        cosmetic_files=cosmetic_files,
    )
