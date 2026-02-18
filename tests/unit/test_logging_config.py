"""
Unit tests for artcrm/logging_config.py.

Tests configure_logging (idempotency, dir creation, level, handler type)
and log_call (entry/exit/failure logging, return value pass-through, re-raise).
"""

import logging
import logging.handlers
import os
from unittest.mock import MagicMock, patch

import pytest

from artcrm.logging_config import configure_logging, log_call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_artcrm_logger():
    """Close and remove all handlers from the artcrm logger."""
    logger = logging.getLogger("artcrm")
    for h in logger.handlers[:]:
        h.close()
        logger.removeHandler(h)
    logger.setLevel(logging.NOTSET)


# ---------------------------------------------------------------------------
# configure_logging
# ---------------------------------------------------------------------------

class TestConfigureLogging:

    def setup_method(self):
        _clear_artcrm_logger()

    def teardown_method(self):
        _clear_artcrm_logger()

    def test_returns_logger(self, tmp_path):
        with patch("artcrm.logging_config._LOG_DIR", tmp_path), \
             patch("artcrm.logging_config._LOG_FILE", tmp_path / "artcrm.log"):
            result = configure_logging()
        assert isinstance(result, logging.Logger)
        assert result.name == "artcrm"

    def test_creates_log_dir_if_missing(self, tmp_path):
        log_dir = tmp_path / "logs"
        assert not log_dir.exists()
        with patch("artcrm.logging_config._LOG_DIR", log_dir), \
             patch("artcrm.logging_config._LOG_FILE", log_dir / "artcrm.log"):
            configure_logging()
        assert log_dir.exists()

    def test_existing_log_dir_does_not_raise(self, tmp_path):
        with patch("artcrm.logging_config._LOG_DIR", tmp_path), \
             patch("artcrm.logging_config._LOG_FILE", tmp_path / "artcrm.log"):
            configure_logging()  # tmp_path already exists — should not raise

    def test_adds_rotating_file_handler(self, tmp_path):
        with patch("artcrm.logging_config._LOG_DIR", tmp_path), \
             patch("artcrm.logging_config._LOG_FILE", tmp_path / "artcrm.log"):
            configure_logging()
        logger = logging.getLogger("artcrm")
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.handlers.RotatingFileHandler)

    def test_idempotent_does_not_add_duplicate_handlers(self, tmp_path):
        with patch("artcrm.logging_config._LOG_DIR", tmp_path), \
             patch("artcrm.logging_config._LOG_FILE", tmp_path / "artcrm.log"):
            configure_logging()
            configure_logging()
            configure_logging()
        assert len(logging.getLogger("artcrm").handlers) == 1

    def test_default_level_is_info(self, tmp_path):
        env = {k: v for k, v in os.environ.items() if k != "LOG_LEVEL"}
        with patch.dict(os.environ, env, clear=True), \
             patch("artcrm.logging_config._LOG_DIR", tmp_path), \
             patch("artcrm.logging_config._LOG_FILE", tmp_path / "artcrm.log"):
            configure_logging()
        assert logging.getLogger("artcrm").level == logging.INFO

    def test_respects_log_level_debug(self, tmp_path):
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}), \
             patch("artcrm.logging_config._LOG_DIR", tmp_path), \
             patch("artcrm.logging_config._LOG_FILE", tmp_path / "artcrm.log"):
            configure_logging()
        assert logging.getLogger("artcrm").level == logging.DEBUG

    def test_respects_log_level_warning(self, tmp_path):
        with patch.dict(os.environ, {"LOG_LEVEL": "WARNING"}), \
             patch("artcrm.logging_config._LOG_DIR", tmp_path), \
             patch("artcrm.logging_config._LOG_FILE", tmp_path / "artcrm.log"):
            configure_logging()
        assert logging.getLogger("artcrm").level == logging.WARNING

    def test_invalid_log_level_falls_back_to_info(self, tmp_path):
        with patch.dict(os.environ, {"LOG_LEVEL": "BOGUS"}), \
             patch("artcrm.logging_config._LOG_DIR", tmp_path), \
             patch("artcrm.logging_config._LOG_FILE", tmp_path / "artcrm.log"):
            configure_logging()
        assert logging.getLogger("artcrm").level == logging.INFO


# ---------------------------------------------------------------------------
# log_call decorator
# ---------------------------------------------------------------------------

class TestLogCall:

    def test_passes_return_value_through(self):
        @log_call
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_preserves_function_name(self):
        @log_call
        def my_func():
            pass

        assert my_func.__name__ == "my_func"

    def test_logs_call_on_entry(self):
        @log_call
        def greet(name):
            return f"hello {name}"

        mock_logger = MagicMock()
        with patch("artcrm.logging_config.logging") as mock_logging:
            mock_logging.getLogger.return_value = mock_logger
            greet("Alice")

        mock_logger.debug.assert_called_once()
        msg = mock_logger.debug.call_args[0][0]
        assert "CALL" in msg
        assert "greet" in msg

    def test_call_log_includes_positional_args(self):
        @log_call
        def func(x, y):
            pass

        mock_logger = MagicMock()
        with patch("artcrm.logging_config.logging") as mock_logging:
            mock_logging.getLogger.return_value = mock_logger
            func(1, 2)

        msg = mock_logger.debug.call_args[0][0]
        assert "1" in msg
        assert "2" in msg

    def test_call_log_includes_kwargs(self):
        @log_call
        def func(x, y=10):
            return x + y

        mock_logger = MagicMock()
        with patch("artcrm.logging_config.logging") as mock_logging:
            mock_logging.getLogger.return_value = mock_logger
            func(1, y=99)

        msg = mock_logger.debug.call_args[0][0]
        assert "y=99" in msg

    def test_no_args_shows_em_dash(self):
        @log_call
        def func():
            pass

        mock_logger = MagicMock()
        with patch("artcrm.logging_config.logging") as mock_logging:
            mock_logging.getLogger.return_value = mock_logger
            func()

        msg = mock_logger.debug.call_args[0][0]
        assert "\u2014" in msg  # em-dash

    def test_logs_ok_on_success(self):
        @log_call
        def noop():
            pass

        mock_logger = MagicMock()
        with patch("artcrm.logging_config.logging") as mock_logging:
            mock_logging.getLogger.return_value = mock_logger
            noop()

        mock_logger.info.assert_called_once()
        msg = mock_logger.info.call_args[0][0]
        assert "OK" in msg
        assert "noop" in msg

    def test_ok_log_includes_timing(self):
        @log_call
        def noop():
            pass

        mock_logger = MagicMock()
        with patch("artcrm.logging_config.logging") as mock_logging:
            mock_logging.getLogger.return_value = mock_logger
            noop()

        msg = mock_logger.info.call_args[0][0]
        assert "ms" in msg

    def test_logs_fail_on_exception(self):
        @log_call
        def boom():
            raise ValueError("bad input")

        mock_logger = MagicMock()
        with patch("artcrm.logging_config.logging") as mock_logging:
            mock_logging.getLogger.return_value = mock_logger
            with pytest.raises(ValueError):
                boom()

        mock_logger.error.assert_called_once()
        msg = mock_logger.error.call_args[0][0]
        assert "FAIL" in msg
        assert "boom" in msg
        assert "ValueError" in msg
        assert "bad input" in msg

    def test_fail_log_includes_timing(self):
        @log_call
        def boom():
            raise RuntimeError("oops")

        mock_logger = MagicMock()
        with patch("artcrm.logging_config.logging") as mock_logging:
            mock_logging.getLogger.return_value = mock_logger
            with pytest.raises(RuntimeError):
                boom()

        msg = mock_logger.error.call_args[0][0]
        assert "ms" in msg

    def test_reraises_exception_unchanged(self):
        @log_call
        def boom():
            raise RuntimeError("oops")

        with patch("artcrm.logging_config.logging") as mock_logging:
            mock_logging.getLogger.return_value = MagicMock()
            with pytest.raises(RuntimeError, match="oops"):
                boom()

    def test_does_not_log_info_on_failure(self):
        @log_call
        def boom():
            raise ValueError("bad")

        mock_logger = MagicMock()
        with patch("artcrm.logging_config.logging") as mock_logging:
            mock_logging.getLogger.return_value = mock_logger
            with pytest.raises(ValueError):
                boom()

        mock_logger.info.assert_not_called()
