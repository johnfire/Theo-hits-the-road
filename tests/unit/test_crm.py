"""
Unit tests for the CRM Engine (artcrm/engine/crm.py).

Strategy: patch artcrm.engine.crm.get_db_cursor with a contextmanager that yields
a MagicMock cursor. Rows returned by the cursor are plain dicts, which unpack
cleanly into Contact / Interaction / Show dataclasses. Bus events are verified by
patching artcrm.engine.crm.bus.emit.
"""

import pytest
from contextlib import contextmanager
from datetime import date, datetime
from unittest.mock import MagicMock, patch, call

from artcrm.models import Contact, Interaction, Show
from artcrm.engine.crm import (
    _validate_columns,
    _CONTACT_COLUMNS,
    _SHOW_COLUMNS,
    create_contact,
    get_contact,
    update_contact,
    delete_contact,
    search_contacts,
    get_overdue_contacts,
    get_dormant_contacts,
    log_interaction,
    get_interactions,
    create_show,
    get_shows,
    update_show,
)
from artcrm.bus.events import (
    EVENT_CONTACT_CREATED, EVENT_CONTACT_UPDATED, EVENT_CONTACT_DELETED,
    EVENT_INTERACTION_LOGGED, EVENT_SHOW_CREATED, EVENT_SHOW_UPDATED,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

# A complete contact row as returned by RealDictCursor
CONTACT_ROW = {
    'id': 1, 'name': 'Galerie Stern', 'type': 'gallery', 'subtype': 'contemporary',
    'city': 'Augsburg', 'country': 'DE', 'address': 'Maximilianstr. 1',
    'website': 'https://galerie-stern.de', 'email': 'info@galerie-stern.de',
    'phone': '+4982112345', 'preferred_language': 'de', 'status': 'cold',
    'fit_score': None, 'success_probability': None, 'best_visit_time': None,
    'notes': None, 'created_at': None, 'updated_at': None, 'deleted_at': None,
}

INTERACTION_ROW = {
    'id': 10, 'contact_id': 1, 'interaction_date': date(2026, 1, 15),
    'method': 'email', 'direction': 'outbound', 'summary': 'Sent intro',
    'outcome': 'no_reply', 'next_action': 'Follow up', 'next_action_date': None,
    'ai_draft_used': False, 'created_at': None, 'deleted_at': None,
}

SHOW_ROW = {
    'id': 5, 'name': 'Frühjahrsausstellung', 'venue_contact_id': 1,
    'city': 'München', 'date_start': date(2026, 4, 1), 'date_end': date(2026, 4, 30),
    'theme': 'Landschaft', 'status': 'possible', 'notes': None,
    'created_at': None, 'updated_at': None, 'deleted_at': None,
}


def make_cursor(fetchone=None, fetchall=None, rowcount=1):
    """Build a MagicMock cursor with preset return values."""
    cur = MagicMock()
    cur.fetchone.return_value = fetchone
    cur.fetchall.return_value = fetchall if fetchall is not None else []
    cur.rowcount = rowcount
    return cur


def cursor_patch(cur):
    """Return a patch context manager that replaces get_db_cursor with one yielding cur."""
    @contextmanager
    def _mock_ctx():
        yield cur

    return patch('artcrm.engine.crm.get_db_cursor', _mock_ctx)


# ---------------------------------------------------------------------------
# _validate_columns — pure function, no mock needed
# ---------------------------------------------------------------------------

def test_validate_columns_valid_passes():
    _validate_columns({'name': 'X', 'city': 'Y'}, _CONTACT_COLUMNS, 'contact')


def test_validate_columns_invalid_raises():
    with pytest.raises(ValueError, match='contact'):
        _validate_columns({'name': 'X', 'injected_col': 'bad'}, _CONTACT_COLUMNS, 'contact')


def test_validate_columns_empty_dict_passes():
    _validate_columns({}, _CONTACT_COLUMNS, 'contact')


def test_validate_columns_show_invalid_raises():
    with pytest.raises(ValueError, match='show'):
        _validate_columns({'status': 'ok', 'DROP TABLE': 'x'}, _SHOW_COLUMNS, 'show')


# ---------------------------------------------------------------------------
# create_contact
# ---------------------------------------------------------------------------

def test_create_contact_returns_id():
    cur = make_cursor(fetchone={'id': 42})
    with cursor_patch(cur):
        contact_id = create_contact(Contact(name='Galerie Stern'))
    assert contact_id == 42


def test_create_contact_executes_insert():
    cur = make_cursor(fetchone={'id': 1})
    with cursor_patch(cur):
        create_contact(Contact(name='Galerie Stern'))
    cur.execute.assert_called_once()
    sql = cur.execute.call_args[0][0]
    assert 'INSERT INTO contacts' in sql


def test_create_contact_emits_event():
    contact = Contact(name='Galerie Stern')
    cur = make_cursor(fetchone={'id': 7})
    with cursor_patch(cur), patch('artcrm.engine.crm.bus.emit') as mock_emit:
        create_contact(contact)
    mock_emit.assert_called_once_with(EVENT_CONTACT_CREATED, {'contact_id': 7, 'contact': contact})


# ---------------------------------------------------------------------------
# get_contact
# ---------------------------------------------------------------------------

def test_get_contact_found_returns_contact():
    cur = make_cursor(fetchone=CONTACT_ROW)
    with cursor_patch(cur):
        result = get_contact(1)
    assert isinstance(result, Contact)
    assert result.name == 'Galerie Stern'
    assert result.id == 1


def test_get_contact_not_found_returns_none():
    cur = make_cursor(fetchone=None)
    with cursor_patch(cur):
        result = get_contact(999)
    assert result is None


# ---------------------------------------------------------------------------
# update_contact
# ---------------------------------------------------------------------------

def test_update_contact_empty_dict_returns_false():
    # No DB call should be made
    with patch('artcrm.engine.crm.get_db_cursor') as mock_ctx:
        result = update_contact(1, {})
    assert result is False
    mock_ctx.assert_not_called()


def test_update_contact_invalid_column_raises():
    with pytest.raises(ValueError):
        update_contact(1, {'evil_col': 'x'})


def test_update_contact_success_returns_true():
    cur = make_cursor(rowcount=1)
    with cursor_patch(cur), patch('artcrm.engine.crm.bus.emit'):
        result = update_contact(1, {'status': 'warm'})
    assert result is True


def test_update_contact_not_found_returns_false():
    cur = make_cursor(rowcount=0)
    with cursor_patch(cur):
        result = update_contact(1, {'status': 'warm'})
    assert result is False


def test_update_contact_emits_event():
    cur = make_cursor(rowcount=1)
    with cursor_patch(cur), patch('artcrm.engine.crm.bus.emit') as mock_emit:
        update_contact(1, {'status': 'warm'})
    assert mock_emit.called
    event_name = mock_emit.call_args[0][0]
    assert event_name == EVENT_CONTACT_UPDATED


def test_update_contact_no_event_when_not_found():
    cur = make_cursor(rowcount=0)
    with cursor_patch(cur), patch('artcrm.engine.crm.bus.emit') as mock_emit:
        update_contact(1, {'status': 'warm'})
    mock_emit.assert_not_called()


# ---------------------------------------------------------------------------
# delete_contact
# ---------------------------------------------------------------------------

def test_delete_contact_soft_returns_true():
    cur = make_cursor(rowcount=1)
    with cursor_patch(cur), patch('artcrm.engine.crm.bus.emit'):
        result = delete_contact(1, soft=True)
    assert result is True


def test_delete_contact_soft_uses_update_sql():
    cur = make_cursor(rowcount=1)
    with cursor_patch(cur), patch('artcrm.engine.crm.bus.emit'):
        delete_contact(1, soft=True)
    sql = cur.execute.call_args[0][0]
    assert 'deleted_at' in sql
    assert 'DELETE' not in sql


def test_delete_contact_hard_uses_delete_sql():
    cur = make_cursor(rowcount=1)
    with cursor_patch(cur), patch('artcrm.engine.crm.bus.emit'):
        delete_contact(1, soft=False)
    sql = cur.execute.call_args[0][0]
    assert 'DELETE FROM contacts' in sql


def test_delete_contact_not_found_returns_false():
    cur = make_cursor(rowcount=0)
    with cursor_patch(cur):
        result = delete_contact(999)
    assert result is False


def test_delete_contact_emits_event():
    cur = make_cursor(rowcount=1)
    with cursor_patch(cur), patch('artcrm.engine.crm.bus.emit') as mock_emit:
        delete_contact(1)
    mock_emit.assert_called_once_with(
        EVENT_CONTACT_DELETED, {'contact_id': 1, 'soft': True}
    )


# ---------------------------------------------------------------------------
# search_contacts
# ---------------------------------------------------------------------------

def test_search_contacts_returns_contact_list():
    cur = make_cursor(fetchall=[CONTACT_ROW])
    with cursor_patch(cur):
        results = search_contacts()
    assert len(results) == 1
    assert isinstance(results[0], Contact)
    assert results[0].name == 'Galerie Stern'


def test_search_contacts_empty_result():
    cur = make_cursor(fetchall=[])
    with cursor_patch(cur):
        results = search_contacts(name='nobody')
    assert results == []


def test_search_contacts_name_filter_adds_ilike():
    cur = make_cursor(fetchall=[])
    with cursor_patch(cur):
        search_contacts(name='Galerie')
    sql = cur.execute.call_args[0][0]
    assert 'ILIKE' in sql


def test_search_contacts_multiple_filters():
    cur = make_cursor(fetchall=[CONTACT_ROW])
    with cursor_patch(cur):
        results = search_contacts(name='Stern', city='Augsburg', type='gallery', status='cold')
    sql = cur.execute.call_args[0][0]
    assert 'ILIKE' in sql
    assert 'type' in sql
    assert 'status' in sql


# ---------------------------------------------------------------------------
# get_overdue_contacts
# ---------------------------------------------------------------------------

def test_get_overdue_contacts_strips_earliest_action():
    row_with_extra = {**CONTACT_ROW, 'earliest_action': date(2025, 12, 1)}
    cur = make_cursor(fetchall=[row_with_extra])
    with cursor_patch(cur):
        results = get_overdue_contacts()
    assert len(results) == 1
    assert not hasattr(results[0], 'earliest_action')


def test_get_overdue_contacts_returns_contact_list():
    row_with_extra = {**CONTACT_ROW, 'earliest_action': date(2025, 12, 1)}
    cur = make_cursor(fetchall=[row_with_extra])
    with cursor_patch(cur):
        results = get_overdue_contacts()
    assert isinstance(results[0], Contact)


# ---------------------------------------------------------------------------
# get_dormant_contacts
# ---------------------------------------------------------------------------

def test_get_dormant_contacts_returns_contact_list():
    cur = make_cursor(fetchall=[CONTACT_ROW])
    with cursor_patch(cur):
        results = get_dormant_contacts()
    assert len(results) == 1
    assert isinstance(results[0], Contact)


def test_get_dormant_contacts_uses_threshold_param():
    cur = make_cursor(fetchall=[])
    with cursor_patch(cur):
        get_dormant_contacts()
    # Threshold date should be passed as a parameter
    params = cur.execute.call_args[0][1]
    assert isinstance(params, tuple)
    assert isinstance(params[0], date)


# ---------------------------------------------------------------------------
# log_interaction
# ---------------------------------------------------------------------------

def test_log_interaction_returns_id():
    cur = make_cursor(fetchone={'id': 99})
    with cursor_patch(cur):
        interaction_id = log_interaction(Interaction(contact_id=1))
    assert interaction_id == 99


def test_log_interaction_executes_insert():
    cur = make_cursor(fetchone={'id': 1})
    with cursor_patch(cur):
        log_interaction(Interaction(contact_id=1))
    sql = cur.execute.call_args[0][0]
    assert 'INSERT INTO interactions' in sql


def test_log_interaction_emits_event():
    interaction = Interaction(contact_id=5)
    cur = make_cursor(fetchone={'id': 99})
    with cursor_patch(cur), patch('artcrm.engine.crm.bus.emit') as mock_emit:
        log_interaction(interaction)
    mock_emit.assert_called_once_with(
        EVENT_INTERACTION_LOGGED,
        {'interaction_id': 99, 'contact_id': 5, 'interaction': interaction}
    )


# ---------------------------------------------------------------------------
# get_interactions
# ---------------------------------------------------------------------------

def test_get_interactions_returns_list():
    cur = make_cursor(fetchall=[INTERACTION_ROW])
    with cursor_patch(cur):
        results = get_interactions(1)
    assert len(results) == 1
    assert isinstance(results[0], Interaction)
    assert results[0].method == 'email'


def test_get_interactions_empty():
    cur = make_cursor(fetchall=[])
    with cursor_patch(cur):
        results = get_interactions(999)
    assert results == []


# ---------------------------------------------------------------------------
# create_show
# ---------------------------------------------------------------------------

def test_create_show_returns_id():
    cur = make_cursor(fetchone={'id': 5})
    with cursor_patch(cur):
        show_id = create_show(Show(name='Ausstellung'))
    assert show_id == 5


def test_create_show_executes_insert():
    cur = make_cursor(fetchone={'id': 5})
    with cursor_patch(cur):
        create_show(Show(name='Ausstellung'))
    sql = cur.execute.call_args[0][0]
    assert 'INSERT INTO shows' in sql


def test_create_show_emits_event():
    show = Show(name='Ausstellung')
    cur = make_cursor(fetchone={'id': 5})
    with cursor_patch(cur), patch('artcrm.engine.crm.bus.emit') as mock_emit:
        create_show(show)
    mock_emit.assert_called_once_with(EVENT_SHOW_CREATED, {'show_id': 5, 'show': show})


# ---------------------------------------------------------------------------
# get_shows
# ---------------------------------------------------------------------------

def test_get_shows_returns_show_list():
    cur = make_cursor(fetchall=[SHOW_ROW])
    with cursor_patch(cur):
        results = get_shows()
    assert len(results) == 1
    assert isinstance(results[0], Show)
    assert results[0].name == 'Frühjahrsausstellung'


def test_get_shows_status_filter():
    cur = make_cursor(fetchall=[])
    with cursor_patch(cur):
        get_shows(status='confirmed')
    sql = cur.execute.call_args[0][0]
    assert 'status' in sql


def test_get_shows_date_range_filter():
    cur = make_cursor(fetchall=[])
    with cursor_patch(cur):
        get_shows(date_from=date(2026, 1, 1), date_to=date(2026, 12, 31))
    sql = cur.execute.call_args[0][0]
    assert 'date_start' in sql


# ---------------------------------------------------------------------------
# update_show
# ---------------------------------------------------------------------------

def test_update_show_empty_dict_returns_false():
    with patch('artcrm.engine.crm.get_db_cursor') as mock_ctx:
        result = update_show(1, {})
    assert result is False
    mock_ctx.assert_not_called()


def test_update_show_invalid_column_raises():
    with pytest.raises(ValueError):
        update_show(1, {'bad_col': 'x'})


def test_update_show_success_returns_true():
    cur = make_cursor(rowcount=1)
    with cursor_patch(cur), patch('artcrm.engine.crm.bus.emit'):
        result = update_show(1, {'status': 'confirmed'})
    assert result is True


def test_update_show_not_found_returns_false():
    cur = make_cursor(rowcount=0)
    with cursor_patch(cur):
        result = update_show(1, {'status': 'confirmed'})
    assert result is False


def test_update_show_emits_event():
    cur = make_cursor(rowcount=1)
    with cursor_patch(cur), patch('artcrm.engine.crm.bus.emit') as mock_emit:
        update_show(1, {'status': 'confirmed'})
    event_name = mock_emit.call_args[0][0]
    assert event_name == EVENT_SHOW_UPDATED
