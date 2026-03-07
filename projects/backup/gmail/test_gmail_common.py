import os
import logging
from unittest.mock import patch
from datetime import date


def test_setup_logging_creates_log_dir(tmp_path):
    from gmail_common import setup_logging
    with patch("gmail_common.LOG_BASE", str(tmp_path)):
        logger = setup_logging("test-script")
        log_dir = tmp_path / "test-script"
        assert log_dir.is_dir()
        assert any(isinstance(h, logging.FileHandler) for h in logger.handlers)
        log_file = log_dir / f"{date.today().isoformat()}.log"
        logger.info("hello")
        assert log_file.exists()
