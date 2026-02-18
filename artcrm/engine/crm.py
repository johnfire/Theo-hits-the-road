"""
CRM Engine - Core Database Operations
Pure Python module with no AI dependency. Handles all CRUD operations.
Communicates via event bus only - never imported directly by other modules.
"""

import logging
from datetime import date, timedelta
from typing import List, Optional, Dict, Any

from artcrm.db.connection import get_db_cursor
from artcrm.models import Contact, Interaction, Show
from artcrm.bus.events import bus, EVENT_CONTACT_CREATED, EVENT_CONTACT_UPDATED, EVENT_CONTACT_DELETED, EVENT_INTERACTION_LOGGED, EVENT_SHOW_CREATED, EVENT_SHOW_UPDATED
from artcrm.config import config

logger = logging.getLogger(__name__)

# Allowlists for dynamic UPDATE queries — column names never come from user input directly
_CONTACT_COLUMNS = {
    'name', 'type', 'subtype', 'city', 'country', 'address', 'website', 'email',
    'phone', 'preferred_language', 'status', 'fit_score', 'success_probability',
    'best_visit_time', 'notes',
}
_SHOW_COLUMNS = {
    'name', 'venue_contact_id', 'city', 'date_start', 'date_end', 'theme', 'status', 'notes',
}


def _validate_columns(updates: Dict[str, Any], allowed: set, entity: str) -> None:
    """Raise ValueError if any key in updates is not an allowed column name."""
    invalid = set(updates.keys()) - allowed
    if invalid:
        raise ValueError(f"Invalid {entity} fields: {invalid}")


# =============================================================================
# CONTACT OPERATIONS
# =============================================================================

def create_contact(contact: Contact) -> int:
    """
    Create a new contact.
    Returns: contact_id
    """
    with get_db_cursor() as cur:
        cur.execute("""
            INSERT INTO contacts (
                name, type, subtype, city, country, address, website, email,
                phone, preferred_language, status, fit_score, success_probability,
                best_visit_time, notes, created_at, updated_at
            ) VALUES (
                %(name)s, %(type)s, %(subtype)s, %(city)s, %(country)s, %(address)s,
                %(website)s, %(email)s, %(phone)s, %(preferred_language)s, %(status)s,
                %(fit_score)s, %(success_probability)s, %(best_visit_time)s, %(notes)s,
                NOW(), NOW()
            ) RETURNING id
        """, contact.__dict__)

        contact_id = cur.fetchone()['id']
        logger.info(f"Created contact ID {contact_id}: {contact.name}")

        # Emit event
        bus.emit(EVENT_CONTACT_CREATED, {'contact_id': contact_id, 'contact': contact})

        return contact_id


def get_contact(contact_id: int) -> Optional[Contact]:
    """Get contact by ID."""
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT * FROM contacts
            WHERE id = %s AND deleted_at IS NULL
        """, (contact_id,))

        row = cur.fetchone()
        if row:
            return Contact(**row)
        logger.debug(f"get_contact: contact_id={contact_id} not found")
        return None


def update_contact(contact_id: int, updates: Dict[str, Any]) -> bool:
    """
    Update contact fields.
    Args:
        contact_id: ID of contact to update
        updates: Dict of field_name: new_value
    Returns: True if updated, False if not found
    """
    if not updates:
        return False

    # Guard: only known columns may appear in the SET clause
    _validate_columns(updates, _CONTACT_COLUMNS, 'contact')

    # Build SET clause — keys are validated against the allowlist above
    set_clauses = [f"{key} = %({key})s" for key in updates.keys()]
    set_clause = ', '.join(set_clauses)

    updates['contact_id'] = contact_id

    with get_db_cursor() as cur:
        cur.execute(f"""
            UPDATE contacts
            SET {set_clause}, updated_at = NOW()
            WHERE id = %(contact_id)s AND deleted_at IS NULL
        """, updates)

        if cur.rowcount > 0:
            logger.info(f"Updated contact ID {contact_id}: {list(updates.keys())}")
            bus.emit(EVENT_CONTACT_UPDATED, {'contact_id': contact_id, 'updates': updates})
            return True
        return False


def delete_contact(contact_id: int, soft: bool = True) -> bool:
    """
    Delete contact (soft delete by default).
    Args:
        contact_id: ID to delete
        soft: If True, sets deleted_at. If False, hard delete.
    Returns: True if deleted, False if not found
    """
    with get_db_cursor() as cur:
        if soft:
            cur.execute("""
                UPDATE contacts
                SET deleted_at = NOW()
                WHERE id = %s AND deleted_at IS NULL
            """, (contact_id,))
        else:
            cur.execute("""
                DELETE FROM contacts WHERE id = %s
            """, (contact_id,))

        if cur.rowcount > 0:
            logger.info(f"{'Soft ' if soft else ''}Deleted contact ID {contact_id}")
            bus.emit(EVENT_CONTACT_DELETED, {'contact_id': contact_id, 'soft': soft})
            return True
        return False


def search_contacts(
    name: Optional[str] = None,
    city: Optional[str] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100
) -> List[Contact]:
    """
    Search contacts with optional filters.
    Returns list of matching contacts.
    """
    conditions = ["deleted_at IS NULL"]
    params = {}

    if name:
        conditions.append("name ILIKE %(name)s")
        params['name'] = f"%{name}%"

    if city:
        conditions.append("city ILIKE %(city)s")
        params['city'] = f"%{city}%"

    if type:
        conditions.append("type = %(type)s")
        params['type'] = type

    if status:
        conditions.append("status = %(status)s")
        params['status'] = status

    params['limit'] = limit

    where_clause = " AND ".join(conditions)

    with get_db_cursor() as cur:
        cur.execute(f"""
            SELECT * FROM contacts
            WHERE {where_clause}
            ORDER BY updated_at DESC
            LIMIT %(limit)s
        """, params)

        rows = cur.fetchall()
        logger.debug(f"search_contacts: {len(rows)} results (type={type}, status={status}, city={city})")
        return [Contact(**row) for row in rows]


def get_overdue_contacts() -> List[Contact]:
    """
    Get contacts with next_action_date in the past.
    Returns list of contacts that need follow-up.
    """
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT c.*, MIN(i.next_action_date) as earliest_action
            FROM contacts c
            JOIN interactions i ON c.id = i.contact_id
            WHERE c.deleted_at IS NULL
              AND i.deleted_at IS NULL
              AND i.next_action_date IS NOT NULL
              AND i.next_action_date < CURRENT_DATE
            GROUP BY c.id
            ORDER BY earliest_action ASC
        """)

        rows = cur.fetchall()
        logger.debug(f"get_overdue_contacts: {len(rows)} contacts with overdue actions")
        return [Contact(**{k: v for k, v in row.items() if k != 'earliest_action'}) for row in rows]


def get_dormant_contacts() -> List[Contact]:
    """
    Get contacts not touched in more than DORMANT_THRESHOLD_MONTHS.
    Returns list of dormant contacts.
    """
    threshold_date = date.today() - timedelta(days=30 * config.DORMANT_THRESHOLD_MONTHS)

    with get_db_cursor() as cur:
        cur.execute("""
            SELECT c.*
            FROM contacts c
            LEFT JOIN interactions i ON c.id = i.contact_id AND i.deleted_at IS NULL
            WHERE c.deleted_at IS NULL
            GROUP BY c.id
            HAVING MAX(i.interaction_date) < %s OR MAX(i.interaction_date) IS NULL
            ORDER BY MAX(i.interaction_date) ASC NULLS FIRST
        """, (threshold_date,))

        rows = cur.fetchall()
        logger.debug(f"get_dormant_contacts: {len(rows)} dormant contacts")
        return [Contact(**row) for row in rows]


# =============================================================================
# INTERACTION OPERATIONS
# =============================================================================

def log_interaction(interaction: Interaction) -> int:
    """
    Log an interaction for a contact.
    Returns: interaction_id
    """
    with get_db_cursor() as cur:
        cur.execute("""
            INSERT INTO interactions (
                contact_id, interaction_date, method, direction, summary,
                outcome, next_action, next_action_date, ai_draft_used, created_at
            ) VALUES (
                %(contact_id)s, %(interaction_date)s, %(method)s, %(direction)s,
                %(summary)s, %(outcome)s, %(next_action)s, %(next_action_date)s,
                %(ai_draft_used)s, NOW()
            ) RETURNING id
        """, interaction.__dict__)

        interaction_id = cur.fetchone()['id']
        logger.info(f"Logged interaction ID {interaction_id} for contact {interaction.contact_id}")

        # Emit event
        bus.emit(EVENT_INTERACTION_LOGGED, {
            'interaction_id': interaction_id,
            'contact_id': interaction.contact_id,
            'interaction': interaction
        })

        return interaction_id


def get_interactions(contact_id: int) -> List[Interaction]:
    """Get all interactions for a contact."""
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT * FROM interactions
            WHERE contact_id = %s AND deleted_at IS NULL
            ORDER BY interaction_date DESC
        """, (contact_id,))

        rows = cur.fetchall()
        logger.debug(f"get_interactions: contact_id={contact_id} → {len(rows)} interactions")
        return [Interaction(**row) for row in rows]


# =============================================================================
# SHOW OPERATIONS
# =============================================================================

def create_show(show: Show) -> int:
    """
    Create a new show.
    Returns: show_id
    """
    with get_db_cursor() as cur:
        cur.execute("""
            INSERT INTO shows (
                name, venue_contact_id, city, date_start, date_end,
                theme, status, notes, created_at, updated_at
            ) VALUES (
                %(name)s, %(venue_contact_id)s, %(city)s, %(date_start)s,
                %(date_end)s, %(theme)s, %(status)s, %(notes)s, NOW(), NOW()
            ) RETURNING id
        """, show.__dict__)

        show_id = cur.fetchone()['id']
        logger.info(f"Created show ID {show_id}: {show.name}")

        # Emit event
        bus.emit(EVENT_SHOW_CREATED, {'show_id': show_id, 'show': show})

        return show_id


def get_shows(
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None
) -> List[Show]:
    """
    Get shows with optional filters.
    """
    conditions = ["deleted_at IS NULL"]
    params = {}

    if status:
        conditions.append("status = %(status)s")
        params['status'] = status

    if date_from:
        conditions.append("date_start >= %(date_from)s")
        params['date_from'] = date_from

    if date_to:
        conditions.append("date_start <= %(date_to)s")
        params['date_to'] = date_to

    where_clause = " AND ".join(conditions)

    with get_db_cursor() as cur:
        cur.execute(f"""
            SELECT * FROM shows
            WHERE {where_clause}
            ORDER BY date_start ASC NULLS LAST
        """, params)

        rows = cur.fetchall()
        logger.debug(f"get_shows: {len(rows)} shows (status={status}, date_from={date_from})")
        return [Show(**row) for row in rows]


def update_show(show_id: int, updates: Dict[str, Any]) -> bool:
    """Update show fields."""
    if not updates:
        return False

    # Guard: only known columns may appear in the SET clause
    _validate_columns(updates, _SHOW_COLUMNS, 'show')

    # Build SET clause — keys are validated against the allowlist above
    set_clauses = [f"{key} = %({key})s" for key in updates.keys()]
    set_clause = ', '.join(set_clauses)

    updates['show_id'] = show_id

    with get_db_cursor() as cur:
        cur.execute(f"""
            UPDATE shows
            SET {set_clause}, updated_at = NOW()
            WHERE id = %(show_id)s AND deleted_at IS NULL
        """, updates)

        if cur.rowcount > 0:
            logger.info(f"Updated show ID {show_id}")
            bus.emit(EVENT_SHOW_UPDATED, {'show_id': show_id, 'updates': updates})
            return True
        return False
