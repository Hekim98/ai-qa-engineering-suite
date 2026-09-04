import json
import stat
from pathlib import Path
from typing import cast

import pytest
from playwright.sync_api import BrowserContext

from ai_qa_engineering.auth import SessionStateError, SessionStateStore


class StorageStateContext:
    def storage_state(self, *, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps({"cookies": [], "origins": []}),
            encoding="utf-8",
        )


@pytest.mark.unit
def test_session_state_store_uses_private_permissions_and_safe_names(tmp_path: Path) -> None:
    store = SessionStateStore(tmp_path / "sessions")

    state_path = store.save(
        cast(BrowserContext, StorageStateContext()),
        "Admin / Primary",
    )

    assert state_path == (tmp_path / "sessions" / "admin-primary.json").resolve()
    assert stat.S_IMODE(store.root.stat().st_mode) == 0o700
    assert stat.S_IMODE(state_path.stat().st_mode) == 0o600
    assert store.load("Admin / Primary") == state_path


@pytest.mark.unit
def test_session_state_store_rejects_missing_or_invalid_state(tmp_path: Path) -> None:
    store = SessionStateStore(tmp_path / "sessions")

    with pytest.raises(SessionStateError, match="Session state not found"):
        store.load("member")

    invalid_path = store.root / "member.json"
    invalid_path.write_text('{"cookies": []}', encoding="utf-8")

    with pytest.raises(SessionStateError, match="Invalid session state"):
        store.load("member")


@pytest.mark.unit
def test_session_state_store_clears_only_requested_account(tmp_path: Path) -> None:
    store = SessionStateStore(tmp_path / "sessions")
    context = cast(BrowserContext, StorageStateContext())
    member = store.save(context, "member")
    admin = store.save(context, "admin")

    store.clear("member")

    assert not member.exists()
    assert admin.exists()
    store.clear("missing")
