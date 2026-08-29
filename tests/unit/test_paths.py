from pathlib import Path

import pytest

from ai_qa_engineering.paths import UnsafePathError, resolve_within


@pytest.mark.unit
def test_resolve_within_returns_a_path_below_root(tmp_path: Path) -> None:
    assert resolve_within(tmp_path, "artifacts/run-1") == tmp_path / "artifacts/run-1"


@pytest.mark.unit
@pytest.mark.parametrize("path", ["../outside", "/tmp/outside"])
def test_resolve_within_rejects_escape(tmp_path: Path, path: str) -> None:
    with pytest.raises(UnsafePathError):
        resolve_within(tmp_path, path)
