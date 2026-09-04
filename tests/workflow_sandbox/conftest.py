from __future__ import annotations

import os
import threading
from collections.abc import Generator

import pytest

from ai_qa_engineering.observability import BrowserObserver
from tests.workflow_sandbox.support import WorkflowSandboxServer


@pytest.fixture(scope="session", autouse=True)
def workflow_server() -> Generator[WorkflowSandboxServer, None, None]:
    token = os.environ["WORKFLOW_SANDBOX_API_TOKEN"]
    server = WorkflowSandboxServer(("127.0.0.1", 8771), token)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


@pytest.fixture(autouse=True)
def reset_workflow_state(workflow_server: WorkflowSandboxServer) -> None:
    workflow_server.reset()


@pytest.fixture(autouse=True)
def capture_browser_diagnostics(browser_observer: BrowserObserver) -> Generator[None, None, None]:
    yield
