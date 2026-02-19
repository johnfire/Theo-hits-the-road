"""
Art CRM Configuration
Loads settings from environment variables with sensible defaults.
"""

import logging
import os
import warnings
from pathlib import Path
from dotenv import load_dotenv

_logger = logging.getLogger(__name__)

# Load .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


class Config:
    """Application configuration."""

    # Database — must be set in .env; never hardcode credentials here
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        _logger.critical("DATABASE_URL is not set — cannot start. Copy .env.example to .env and configure it.")
        raise ValueError("DATABASE_URL environment variable is not set. Copy .env.example to .env and configure it.")

    # Timezone
    TIMEZONE = os.getenv('TIMEZONE', 'Europe/Berlin')

    # Follow-up cadence (months)
    FOLLOW_UP_CADENCE_MONTHS = int(os.getenv('FOLLOW_UP_CADENCE_MONTHS', '4'))

    # Dormant threshold (months) - no response in this time = dormant
    DORMANT_THRESHOLD_MONTHS = int(os.getenv('DORMANT_THRESHOLD_MONTHS', '12'))

    # AI Configuration (Phase 5+)
    # DeepSeek (routine tasks: scoring, briefs, suggestions)
    DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
    DEEPSEEK_BASE_URL = os.getenv('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    DEFAULT_AI_MODEL = os.getenv('DEFAULT_AI_MODEL', 'deepseek-chat')
    # Claude (high-stakes writing: gallery letters, proposals)
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')

    # Lead Generation (Phase 6-Alpha)
    GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', '')
    LEAD_SCOUT_BATCH_SIZE = int(os.getenv('LEAD_SCOUT_BATCH_SIZE', '20'))
    LEAD_SCOUT_RATE_LIMIT_SECONDS = float(os.getenv('LEAD_SCOUT_RATE_LIMIT_SECONDS', '1.0'))

    # Email Configuration (Phase 7+)
    SMTP_HOST = os.getenv('SMTP_HOST', '')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    IMAP_HOST = os.getenv('IMAP_HOST', '')
    IMAP_PORT = int(os.getenv('IMAP_PORT', '993'))


# Singleton instance
config = Config()
