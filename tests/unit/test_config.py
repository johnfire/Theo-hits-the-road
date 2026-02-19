"""
Unit tests for application configuration (artcrm/config.py).

Config is a class with attributes set at class-body parse time, and a module-level
singleton created immediately after. Testing different env var states requires
importlib.reload(), with load_dotenv mocked to a no-op so the .env file on disk
doesn't override what we set in the test environment.
"""

import importlib
import sys
import warnings
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Helper: reload artcrm.config with a controlled environment
# ---------------------------------------------------------------------------

def _reload_config(env_overrides: dict):
    """
    Reload artcrm.config with a specific set of environment variables.
    load_dotenv is patched to a no-op so the real .env file is ignored.
    Always restores the original module in sys.modules afterward.
    Returns the reloaded module.
    """
    original = sys.modules.get('artcrm.config')
    try:
        with patch.dict('os.environ', env_overrides, clear=True), \
             patch('dotenv.load_dotenv'):
            sys.modules.pop('artcrm.config', None)
            module = importlib.import_module('artcrm.config')
            return module
    finally:
        # Restore the original module so other tests are unaffected.
        if original is not None:
            sys.modules['artcrm.config'] = original
        elif 'artcrm.config' in sys.modules:
            del sys.modules['artcrm.config']


# ---------------------------------------------------------------------------
# DATABASE_URL guard
# ---------------------------------------------------------------------------

def test_missing_database_url_raises_value_error():
    with pytest.raises(ValueError, match='DATABASE_URL'):
        _reload_config({})


def test_empty_database_url_raises_value_error():
    with pytest.raises(ValueError, match='DATABASE_URL'):
        _reload_config({'DATABASE_URL': ''})


def test_database_url_set_does_not_raise():
    mod = _reload_config({
        'DATABASE_URL': 'postgresql://user:pass@localhost:5432/testdb',
    })
    assert mod.Config.DATABASE_URL == 'postgresql://user:pass@localhost:5432/testdb'


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------

def test_timezone_default():
    mod = _reload_config({
        'DATABASE_URL': 'postgresql://u:p@localhost/db',

    })
    assert mod.Config.TIMEZONE == 'Europe/Berlin'


def test_follow_up_cadence_default():
    mod = _reload_config({
        'DATABASE_URL': 'postgresql://u:p@localhost/db',

    })
    assert mod.Config.FOLLOW_UP_CADENCE_MONTHS == 4


def test_dormant_threshold_default():
    mod = _reload_config({
        'DATABASE_URL': 'postgresql://u:p@localhost/db',

    })
    assert mod.Config.DORMANT_THRESHOLD_MONTHS == 12


def test_default_ai_model_default():
    mod = _reload_config({
        'DATABASE_URL': 'postgresql://u:p@localhost/db',
    })
    assert mod.Config.DEFAULT_AI_MODEL == 'deepseek-chat'


def test_deepseek_base_url_default():
    mod = _reload_config({
        'DATABASE_URL': 'postgresql://u:p@localhost/db',
    })
    assert mod.Config.DEEPSEEK_BASE_URL == 'https://api.deepseek.com'


def test_smtp_port_default():
    mod = _reload_config({
        'DATABASE_URL': 'postgresql://u:p@localhost/db',

    })
    assert mod.Config.SMTP_PORT == 587


def test_imap_port_default():
    mod = _reload_config({
        'DATABASE_URL': 'postgresql://u:p@localhost/db',

    })
    assert mod.Config.IMAP_PORT == 993


def test_lead_scout_batch_size_default():
    mod = _reload_config({
        'DATABASE_URL': 'postgresql://u:p@localhost/db',

    })
    assert mod.Config.LEAD_SCOUT_BATCH_SIZE == 20


# ---------------------------------------------------------------------------
# Custom env var values are picked up
# ---------------------------------------------------------------------------

def test_custom_timezone():
    mod = _reload_config({
        'DATABASE_URL': 'postgresql://u:p@localhost/db',

        'TIMEZONE': 'UTC',
    })
    assert mod.Config.TIMEZONE == 'UTC'


def test_custom_follow_up_cadence():
    mod = _reload_config({
        'DATABASE_URL': 'postgresql://u:p@localhost/db',

        'FOLLOW_UP_CADENCE_MONTHS': '6',
    })
    assert mod.Config.FOLLOW_UP_CADENCE_MONTHS == 6


def test_custom_dormant_threshold():
    mod = _reload_config({
        'DATABASE_URL': 'postgresql://u:p@localhost/db',

        'DORMANT_THRESHOLD_MONTHS': '18',
    })
    assert mod.Config.DORMANT_THRESHOLD_MONTHS == 18


def test_custom_lead_scout_batch_size():
    mod = _reload_config({
        'DATABASE_URL': 'postgresql://u:p@localhost/db',

        'LEAD_SCOUT_BATCH_SIZE': '50',
    })
    assert mod.Config.LEAD_SCOUT_BATCH_SIZE == 50


# ---------------------------------------------------------------------------
# DeepSeek custom env vars
# ---------------------------------------------------------------------------

def test_custom_default_ai_model():
    mod = _reload_config({
        'DATABASE_URL': 'postgresql://u:p@localhost/db',
        'DEFAULT_AI_MODEL': 'claude',
    })
    assert mod.Config.DEFAULT_AI_MODEL == 'claude'


def test_custom_deepseek_base_url():
    mod = _reload_config({
        'DATABASE_URL': 'postgresql://u:p@localhost/db',
        'DEEPSEEK_BASE_URL': 'https://custom.deepseek.example.com',
    })
    assert mod.Config.DEEPSEEK_BASE_URL == 'https://custom.deepseek.example.com'
