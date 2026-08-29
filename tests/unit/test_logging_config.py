import logging
from pathlib import Path

import pytest

from ai_qa_engineering.logging_config import configure_logging


@pytest.mark.unit
def test_configure_logging_writes_file_without_duplicate_handlers(tmp_path: Path) -> None:
    logger = configure_logging(name="ai_qa.test", level=logging.INFO, log_dir=tmp_path)
    handler_count = len(logger.handlers)

    same_logger = configure_logging(name="ai_qa.test", level=logging.DEBUG, log_dir=tmp_path)
    same_logger.info("configuration ready")
    for handler in same_logger.handlers:
        handler.flush()

    assert len(same_logger.handlers) == handler_count == 2
    assert all(handler.level == logging.DEBUG for handler in same_logger.handlers)
    assert "configuration ready" in (tmp_path / "ai-qa.log").read_text(encoding="utf-8")


@pytest.mark.unit
def test_configure_logging_replaces_owned_handlers_for_new_directory(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    configure_logging(name="ai_qa.reconfigure", log_dir=first)

    logger = configure_logging(name="ai_qa.reconfigure", log_dir=second)
    logger.warning("new destination")
    for handler in logger.handlers:
        handler.flush()

    assert len(logger.handlers) == 2
    assert "new destination" in (second / "ai-qa.log").read_text(encoding="utf-8")
