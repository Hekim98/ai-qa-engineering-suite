"""Repository-safe path helpers."""

from __future__ import annotations

from pathlib import Path


class UnsafePathError(ValueError):
    """Raised when a configured path escapes its allowed root."""


def resolve_within(root: str | Path, relative_path: str | Path) -> Path:
    """Resolve a relative path and reject traversal outside ``root``."""
    root_path = Path(root).resolve()
    candidate_input = Path(relative_path)
    if candidate_input.is_absolute():
        raise UnsafePathError("Expected a relative path")

    candidate = (root_path / candidate_input).resolve()
    if not candidate.is_relative_to(root_path):
        raise UnsafePathError(f"Path escapes allowed root: {relative_path}")
    return candidate
