from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_qa_engineering.artifacts import RunPaths, safe_slug


@pytest.mark.unit
def test_run_paths_create_isolated_directories(tmp_path: Path) -> None:
    paths = RunPaths.create(
        repository_root=tmp_path,
        artifact_root="artifacts/runs",
        project="Demo AI App",
        profile="Desktop Chromium",
        now=datetime(2026, 8, 28, 20, 15, tzinfo=UTC),
    )

    assert paths.run_id == "20260828T201500Z-demo-ai-app-desktop-chromium"
    assert paths.test_results.is_dir()
    assert paths.observability.is_dir()
    assert paths.logs.is_dir()


@pytest.mark.unit
def test_safe_slug_rejects_empty_identifier() -> None:
    with pytest.raises(ValueError, match="letter or number"):
        safe_slug("---")


@pytest.mark.unit
def test_run_paths_add_suffix_when_same_run_id_exists(tmp_path: Path) -> None:
    moment = datetime(2026, 8, 28, 20, 15, tzinfo=UTC)
    RunPaths.create(
        repository_root=tmp_path,
        artifact_root="artifacts/runs",
        project="Demo",
        profile="Desktop",
        now=moment,
    )

    second = RunPaths.create(
        repository_root=tmp_path,
        artifact_root="artifacts/runs",
        project="Demo",
        profile="Desktop",
        now=moment,
    )

    assert second.run_id == "20260828T201500Z-demo-desktop-2"
