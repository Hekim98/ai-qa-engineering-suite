import pytest

from ai_qa_engineering.observability import BrowserObserver


@pytest.mark.unit
def test_observer_keeps_errors_and_filters_allowlisted_noise() -> None:
    observer = BrowserObserver(("analytics.example",))

    observer.record_console(level="warning", text="not actionable")
    observer.record_console(level="error", text="boom", url="https://app.example")
    observer.record_console(level="error", text="blocked", url="https://analytics.example")
    observer.record_request_failure(
        url="https://app.example/api", method="POST", reason="HTTP 500", status=500
    )
    observer.record_request_failure(
        url="https://analytics.example/pixel", method="GET", reason="blocked"
    )

    assert [record.text for record in observer.console_errors] == ["boom"]
    assert [record.status for record in observer.failed_requests] == [500]
