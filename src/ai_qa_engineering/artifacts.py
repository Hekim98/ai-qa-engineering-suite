"""Create isolated, repository-safe directories for QA run evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ai_qa_engineering.paths import resolve_within


def safe_slug(value: str) -> str:
    """Return a stable lowercase identifier suitable for an artifact path."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError("Artifact identifiers must contain a letter or number")
    return slug


@dataclass(frozen=True)
class RunPaths:
    run_id: str
    root: Path
    test_results: Path
    observability: Path
    logs: Path

    @classmethod
    def create(
        cls,
        *,
        repository_root: str | Path,
        artifact_root: str | Path,
        project: str,
        profile: str,
        now: datetime | None = None,
    ) -> RunPaths:
        timestamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
        base_run_id = f"{timestamp}-{safe_slug(project)}-{safe_slug(profile)}"
        configured_root = resolve_within(repository_root, artifact_root)
        run_id = base_run_id
        run_root = resolve_within(configured_root, run_id)
        counter = 2
        while run_root.exists():
            run_id = f"{base_run_id}-{counter}"
            run_root = resolve_within(configured_root, run_id)
            counter += 1
        test_results = run_root / "test-results"
        observability = run_root / "observability"
        logs = run_root / "logs"
        for directory in (test_results, observability, logs):
            directory.mkdir(parents=True, exist_ok=False)
        return cls(
            run_id=run_id,
            root=run_root,
            test_results=test_results,
            observability=observability,
            logs=logs,
        )
