"""
Art CRM Configuration
Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


class Config:
    """Application configuration."""

    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://artcrm_admindude:aw4e0rfeA1!Q@localhost:5432/artcrm')

    # Timezone
    TIMEZONE = os.getenv('TIMEZONE', 'Europe/Berlin')

    # Follow-up cadence (months)
    FOLLOW_UP_CADENCE_MONTHS = int(os.getenv('FOLLOW_UP_CADENCE_MONTHS', '4'))

    # Dormant threshold (months) - no response in this time = dormant
    DORMANT_THRESHOLD_MONTHS = int(os.getenv('DORMANT_THRESHOLD_MONTHS', '12'))

    # AI Configuration (Phase 5+)
    OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3')
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
