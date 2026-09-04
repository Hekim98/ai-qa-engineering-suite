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


@pytest.mark.unit
def test_observer_respects_disabled_capture_channels() -> None:
    observer = BrowserObserver(
        capture_console_errors=False,
        capture_failed_requests=False,
    )

    observer.record_console(level="error", text="hidden")
    observer.record_request_failure(url="https://example.test/api", method="GET", reason="HTTP 500")

    assert observer.console_errors == []
    assert observer.failed_requests == []


@pytest.mark.unit
def test_observer_can_discard_an_expected_negative_request() -> None:
    observer = BrowserObserver()
    observer.record_console(
        level="error",
        text="HTTP 404",
        url="https://example.test/protected",
    )
    observer.record_request_failure(
        url="https://example.test/protected",
        method="GET",
        reason="HTTP 404",
        status=404,
    )

    observer.discard_expected("/protected")

    assert observer.console_errors == []
    assert observer.failed_requests == []

    observer.allow_expected("/protected")
    observer.record_request_failure(
        url="https://example.test/protected",
        method="GET",
        reason="HTTP 404",
        status=404,
    )
    assert observer.failed_requests == []


@pytest.mark.unit
def test_observer_redacts_secrets_from_console_and_network_records() -> None:
    observer = BrowserObserver(redact=lambda value: value.replace("secret-123", "[REDACTED]"))

    observer.record_console(
        level="error",
        text="Login failed for secret-123",
        url="https://example.test/?token=secret-123",
    )
    observer.record_request_failure(
        url="https://example.test/?token=secret-123",
        method="GET",
        reason="Rejected secret-123",
    )

    assert observer.console_errors[0].text == "Login failed for [REDACTED]"
    assert observer.console_errors[0].url == "https://example.test/?token=[REDACTED]"
    assert observer.failed_requests[0].url.endswith("token=[REDACTED]")
    assert observer.failed_requests[0].reason == "Rejected [REDACTED]"
