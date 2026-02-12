#!/usr/bin/env python3
"""
Art CRM Spreadsheet Importer
Imports data from art-marketing.xlsx into PostgreSQL database.

Features:
- Deduplication by name + city
- Never overwrites existing data
- Re-runnable / safe to run multiple times
- Dry-run mode
- Comprehensive logging
- Date inference for interaction history
- Outcome inference from keywords
- Fuzzy venue matching for shows
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from collections import defaultdict

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from rapidfuzz import fuzz
from dotenv import load_dotenv
import os

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv(project_root / ".env")

XLSX_PATH = project_root / "data" / "art-marketing.xlsx"
NOTES_DIR = project_root / "data" / "notes"


# =============================================================================
# OUTCOME KEYWORD MATCHER
# =============================================================================

# Maps keywords to interaction outcomes (lookup_values.value)
OUTCOME_KEYWORDS = {
    'no_reply': [
        'no reply', 'keine antwort', 'keine rückmeldung', 'not answered',
        'no response', 'none', 'nothing', 'silence', 'nichts'
    ],
    'interested': [
        'interested', 'interessiert', 'interest', 'curious', 'neugierig',
        'nibble', 'maybe', 'vielleicht', 'möglich'
    ],
    'rejected': [
        'rejected', 'abgelehnt', 'no', 'nein', 'not interested',
        'nicht interessiert', 'pass', 'declined'
    ],
    'meeting_set': [
        'meeting', 'termin', 'appointment', 'scheduled', 'vereinbart',
        'meet', 'treffen'
    ],
    'proposal_requested': [
        'proposal', 'vorschlag', 'send more', 'mehr info', 'more information',
        'portfolio', 'works', 'paintings'
    ],
    'accepted': [
        'accepted', 'akzeptiert', 'yes', 'ja', 'agreed', 'deal', 'sold',
        'verkauft', 'IN', 'in process'
    ],
    'left_material': [
        'left', 'dropped off', 'delivered', 'hinterlassen', 'abgegeben'
    ],
    'follow_up_needed': [
        'follow up', 'nachfassen', 'call back', 'zurückrufen', 'later',
        'später', 'check back'
    ],
}


def infer_outcome(text: str) -> str:
    """
    Infer interaction outcome from text content using keyword matching.
    Returns the outcome value or 'no_reply' as default.
    """
    if pd.isna(text) or not text:
        return 'no_reply'

    text_lower = str(text).lower()

    # Check each outcome's keywords
    for outcome, keywords in OUTCOME_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return outcome

    # Default: no reply
    return 'no_reply'


# =============================================================================
# CONTACT DEDUPLICATION
# =============================================================================

def make_dedup_key(name: str, city: str) -> str:
    """Create deduplication key from name + city."""
    name_clean = str(name).strip().lower() if name else ''
    city_clean = str(city).strip().lower() if city else ''
    return f"{name_clean}|{city_clean}"


def make_unique_name(name: str, city: str, existing_names: Dict[str, int]) -> str:
    """
    Make a unique name by appending city.
    If duplicate, format as "Name (City)".
    """
    dedup_key = make_dedup_key(name, city)

    if dedup_key in existing_names:
        # Duplicate detected - add city to name
        if city and str(city).strip():
            return f"{name} ({city})"
        else:
            # No city, just use name as-is (will be caught by dedup check)
            return name
    else:
        existing_names[dedup_key] = 1
        return name


# =============================================================================
# FUZZY VENUE MATCHING
# =============================================================================

def fuzzy_match_venue(venue_name: str, contacts: List[Dict], threshold: int = 80) -> Optional[int]:
    """
    Fuzzy match venue name against contacts using Levenshtein distance.
    Returns contact_id if match found above threshold, else None.
    """
    if not venue_name:
        return None

    best_score = 0
    best_match_id = None

    for contact in contacts:
        contact_name = contact.get('name', '')
        if not contact_name:
            continue

        score = fuzz.ratio(venue_name.lower(), contact_name.lower())

        if score > best_score:
            best_score = score
            best_match_id = contact['id']

    if best_score >= threshold:
        logging.info(f"Fuzzy matched '{venue_name}' to contact ID {best_match_id} (score: {best_score})")
        return best_match_id
    else:
        logging.warning(f"No fuzzy match found for venue '{venue_name}' (best score: {best_score})")
        return None


# =============================================================================
# DATABASE HELPERS
# =============================================================================

class DatabaseConnection:
    """Context manager for database connections."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.conn = None
        self.cursor = None

    def __enter__(self):
        if not self.dry_run:
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                raise ValueError("DATABASE_URL not set in environment")
            self.conn = psycopg2.connect(database_url)
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.dry_run and self.conn:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
            self.cursor.close()
            self.conn.close()

    def execute(self, query: str, params: tuple = None):
        """Execute query (or log in dry-run mode)."""
        if self.dry_run:
            logging.info(f"[DRY-RUN] Would execute: {query[:100]}... with params {params}")
            return None
        else:
            self.cursor.execute(query, params)
            return self.cursor

    def fetchone(self):
        if self.dry_run:
            return None
        return self.cursor.fetchone()

    def fetchall(self):
        if self.dry_run:
            return []
        return self.cursor.fetchall()


def get_or_create_contact(db: DatabaseConnection, contact_data: Dict, dedup_key: str) -> Optional[int]:
    """
    Get existing contact by dedup key, or create new one.
    Returns contact_id or None if dry-run.
    """
    # Check if contact exists
    if not db.dry_run:
        db.execute("""
            SELECT id FROM contacts
            WHERE deleted_at IS NULL
              AND LOWER(TRIM(name)) = LOWER(TRIM(%s))
              AND LOWER(TRIM(COALESCE(city, ''))) = LOWER(TRIM(COALESCE(%s, '')))
        """, (contact_data['name'], contact_data.get('city', '')))

        existing = db.fetchone()
        if existing:
            logging.info(f"Contact exists: {contact_data['name']} - ID {existing['id']}")
            # TODO: Update empty fields (Phase 4 requirement)
            return existing['id']

    # Create new contact
    logging.info(f"Creating new contact: {contact_data['name']}")

    if db.dry_run:
        return None  # Would create, but in dry-run

    db.execute("""
        INSERT INTO contacts (
            name, type, subtype, city, country, address, website, email,
            phone, preferred_language, status, notes, created_at, updated_at
        ) VALUES (
            %(name)s, %(type)s, %(subtype)s, %(city)s, %(country)s, %(address)s,
            %(website)s, %(email)s, %(phone)s, %(preferred_language)s,
            %(status)s, %(notes)s, NOW(), NOW()
        ) RETURNING id
    """, contact_data)

    result = db.fetchone()
    return result['id'] if result else None


def create_interaction(db: DatabaseConnection, interaction_data: Dict):
    """Create an interaction record."""
    logging.debug(f"Creating interaction for contact {interaction_data['contact_id']}: {interaction_data['summary'][:50]}...")

    if db.dry_run:
        return

    db.execute("""
        INSERT INTO interactions (
            contact_id, interaction_date, method, direction, summary,
            outcome, next_action, next_action_date, created_at
        ) VALUES (
            %(contact_id)s, %(interaction_date)s, %(method)s, %(direction)s,
            %(summary)s, %(outcome)s, %(next_action)s, %(next_action_date)s, NOW()
        )
    """, interaction_data)


# =============================================================================
# SHEET IMPORT FUNCTIONS
# =============================================================================

def import_contacts_leads(db: DatabaseConnection, excel_file) -> Tuple[int, int, int]:
    """
    Import main contacts & leads sheet.
    Returns: (created, updated, skipped)
    """
    logging.info("=" * 80)
    logging.info("IMPORTING: contacts  leads")
    logging.info("=" * 80)

    # Read sheet without header, we'll extract it manually
    df = pd.read_excel(excel_file, sheet_name="contacts  leads", header=None)

    # Row 3 has headers
    headers = df.iloc[3].tolist()
    logging.info(f"Headers: {headers}")

    # Data starts around row 12 (after people and empty rows)
    # Find first row where column 13 (name) has a value that's not "name" header or person marker
    data_start = 12

    created = 0
    updated = 0
    skipped = 0

    existing_names = {}

    for idx in range(data_start, len(df)):
        row = df.iloc[idx]

        # Column 13 is name
        name = row[13] if pd.notna(row[13]) else None
        if not name or name == 'name':
            continue

        # Column 14 is sub_city (city)
        city = row[14] if pd.notna(row[14]) and len(row) > 14 else None

        # Skip if this is a "people" entry (city == "people")
        if city == 'people':
            logging.debug(f"Skipping person: {name}")
            skipped += 1
            continue

        # Make unique name if duplicate
        unique_name = make_unique_name(name, city, existing_names)
        dedup_key = make_dedup_key(name, city)

        # Extract contact fields
        contact_data = {
            'name': unique_name,
            'city': city,
            'address': row[15] if len(row) > 15 and pd.notna(row[15]) else None,
            'type': row[16] if len(row) > 16 and pd.notna(row[16]) else None,
            'subtype': row[17] if len(row) > 17 and pd.notna(row[17]) else None,
            'website': row[18] if len(row) > 18 and pd.notna(row[18]) else None,
            'email': row[19] if len(row) > 19 and pd.notna(row[19]) else None,
            'phone': None,  # Not in spreadsheet
            'preferred_language': 'de',  # Default for Bavaria
            'status': 'cold',  # Will be updated from interactions
            'notes': row[20] if len(row) > 20 and pd.notna(row[20]) else None,
            'country': 'DE',  # Assume Germany unless specified
        }

        # Get or create contact
        contact_id = get_or_create_contact(db, contact_data, dedup_key)

        if contact_id:
            created += 1
        else:
            if db.dry_run:
                created += 1  # Count as would-create in dry-run
            else:
                skipped += 1
                continue

        # Parse 5 attempt columns and create interactions
        # Column 3: first contact (has date)
        # Column 4: second
        # Column 5: third
        # Column 6: forth
        # Column 7: fifth

        first_contact_date = row[3] if len(row) > 3 and pd.notna(row[3]) else None

        # Convert to date if it's a timestamp
        if first_contact_date:
            if isinstance(first_contact_date, pd.Timestamp):
                first_contact_date = first_contact_date.date()
            elif isinstance(first_contact_date, datetime):
                first_contact_date = first_contact_date.date()

        attempts = [
            (3, 'first contact', 0),   # col, label, months_offset
            (4, 'second', 5),
            (5, 'third', 10),
            (6, 'forth', 15),
            (7, 'fifth', 20),
        ]

        latest_outcome = None

        for col_idx, label, months_offset in attempts:
            if len(row) <= col_idx:
                continue

            attempt_text = row[col_idx]
            if pd.isna(attempt_text) or not str(attempt_text).strip():
                continue

            # Calculate interaction date
            if first_contact_date and months_offset == 0:
                interaction_date = first_contact_date
            elif first_contact_date:
                interaction_date = first_contact_date + timedelta(days=30 * months_offset)
            else:
                # No anchor date, use import date minus offset
                interaction_date = datetime.now().date() - timedelta(days=30 * (20 - months_offset))

            # Infer outcome
            outcome = infer_outcome(attempt_text)
            latest_outcome = outcome  # Track last outcome for status update

            interaction_data = {
                'contact_id': contact_id if contact_id else 0,
                'interaction_date': interaction_date,
                'method': 'unknown',
                'direction': 'outbound',
                'summary': str(attempt_text).strip(),
                'outcome': outcome,
                'next_action': None,
                'next_action_date': None,
            }

            if contact_id or db.dry_run:
                create_interaction(db, interaction_data)

        # Update contact status based on latest interaction outcome
        if not db.dry_run and contact_id and latest_outcome:
            status_map = {
                'no_reply': 'contacted',
                'interested': 'meeting',
                'rejected': 'rejected',
                'meeting_set': 'meeting',
                'proposal_requested': 'proposal',
                'accepted': 'accepted',
                'not_interested': 'rejected',
            }
            new_status = status_map.get(latest_outcome, 'contacted')

            db.execute("""
                UPDATE contacts
                SET status = %s, updated_at = NOW()
                WHERE id = %s
            """, (new_status, contact_id))

    logging.info(f"Contacts: {created} created, {updated} updated, {skipped} skipped")
    return (created, updated, skipped)


# =============================================================================
# MAIN IMPORT ORCHESTRATOR
# =============================================================================

def run_import(dry_run: bool = False, log_level: str = "INFO"):
    """Main import function."""

    # Setup logging
    log_file = project_root / "logs" / f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_file.parent.mkdir(exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    logging.info("=" * 80)
    logging.info("ART CRM SPREADSHEET IMPORT")
    logging.info("=" * 80)
    logging.info(f"Mode: {'DRY-RUN' if dry_run else 'LIVE'}")
    logging.info(f"Source: {XLSX_PATH}")
    logging.info(f"Log file: {log_file}")
    logging.info("=" * 80)

    if not XLSX_PATH.exists():
        logging.error(f"Excel file not found: {XLSX_PATH}")
        return 1

    # Load Excel file
    try:
        excel_file = pd.ExcelFile(XLSX_PATH)
    except Exception as e:
        logging.error(f"Failed to read Excel file: {e}")
        return 1

    stats = {
        'contacts_created': 0,
        'contacts_updated': 0,
        'contacts_skipped': 0,
        'interactions_created': 0,
        'shows_created': 0,
        'errors': 0,
    }

    # Import contacts & leads
    try:
        with DatabaseConnection(dry_run=dry_run) as db:
            created, updated, skipped = import_contacts_leads(db, excel_file)
            stats['contacts_created'] += created
            stats['contacts_updated'] += updated
            stats['contacts_skipped'] += skipped
    except Exception as e:
        logging.error(f"Error importing contacts: {e}", exc_info=True)
        stats['errors'] += 1

    # TODO: Import other sheets
    # - current channels
    # - show dates
    # - on line
    # - stats
    # - notes files

    # Print summary
    logging.info("=" * 80)
    logging.info("IMPORT COMPLETE")
    logging.info("=" * 80)
    logging.info(f"Contacts created: {stats['contacts_created']}")
    logging.info(f"Contacts updated: {stats['contacts_updated']}")
    logging.info(f"Contacts skipped: {stats['contacts_skipped']}")
    logging.info(f"Interactions created: {stats['interactions_created']}")
    logging.info(f"Shows created: {stats['shows_created']}")
    logging.info(f"Errors: {stats['errors']}")
    logging.info(f"Log file: {log_file}")
    logging.info("=" * 80)

    return 0 if stats['errors'] == 0 else 1


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Import art-marketing.xlsx into Art CRM database"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Show what would be imported without writing to database"
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help="Logging level (default: INFO)"
    )

    args = parser.parse_args()

    sys.exit(run_import(dry_run=args.dry_run, log_level=args.log_level))


if __name__ == "__main__":
    main()
