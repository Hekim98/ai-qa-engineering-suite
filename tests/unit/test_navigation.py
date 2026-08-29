from unittest.mock import Mock

import pytest
from playwright.sync_api import Error as PlaywrightError

from ai_qa_engineering.navigation import TargetUnavailableError, navigate_or_incomplete


@pytest.mark.unit
def test_navigation_classifies_transport_error_as_incomplete() -> None:
    page = Mock()
    page.goto.side_effect = PlaywrightError("net::ERR_CONNECTION_REFUSED")

    with pytest.raises(TargetUnavailableError, match="unavailable"):
        navigate_or_incomplete(page, "https://staging.example")


@pytest.mark.unit
def test_navigation_classifies_server_error_as_incomplete() -> None:
    page = Mock()
    page.goto.return_value.status = 503

    with pytest.raises(TargetUnavailableError, match="HTTP 503"):
        navigate_or_incomplete(page, "https://staging.example")
