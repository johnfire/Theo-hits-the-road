"""
Unit tests for data models (artcrm/models/__init__.py).
Pure Python — no DB, no mocking required.
"""

from datetime import date, datetime
import pytest
from artcrm.models import Contact, Interaction, Show


# ---------------------------------------------------------------------------
# Contact defaults
# ---------------------------------------------------------------------------

def test_contact_default_status():
    c = Contact(name='Galerie Stern')
    assert c.status == 'cold'


def test_contact_default_preferred_language():
    c = Contact(name='Galerie Stern')
    assert c.preferred_language == 'de'


def test_contact_optional_fields_default_to_none():
    c = Contact()
    for field in ('id', 'type', 'subtype', 'city', 'country', 'address',
                  'website', 'email', 'phone', 'fit_score', 'success_probability',
                  'best_visit_time', 'notes', 'created_at', 'updated_at', 'deleted_at'):
        assert getattr(c, field) is None, f"Expected {field} to be None"


def test_contact_name_defaults_to_empty_string():
    c = Contact()
    assert c.name == ''


def test_contact_stores_all_fields():
    now = datetime(2026, 2, 15, 10, 0, 0)
    c = Contact(
        id=1,
        name='Galerie Stern',
        type='gallery',
        subtype='contemporary',
        city='Augsburg',
        country='DE',
        address='Maximilianstr. 1',
        website='https://galerie-stern.de',
        email='info@galerie-stern.de',
        phone='+4982112345',
        preferred_language='de',
        status='warm',
        fit_score=80,
        success_probability=65,
        best_visit_time='Tuesday afternoon',
        notes='Friendly director',
        created_at=now,
        updated_at=now,
    )
    assert c.id == 1
    assert c.name == 'Galerie Stern'
    assert c.type == 'gallery'
    assert c.city == 'Augsburg'
    assert c.fit_score == 80
    assert c.success_probability == 65


def test_contact_equality():
    c1 = Contact(id=1, name='Galerie Stern', city='Augsburg')
    c2 = Contact(id=1, name='Galerie Stern', city='Augsburg')
    assert c1 == c2


def test_contact_inequality():
    c1 = Contact(id=1, name='Galerie Stern')
    c2 = Contact(id=2, name='Galerie Stern')
    assert c1 != c2


# ---------------------------------------------------------------------------
# Interaction defaults
# ---------------------------------------------------------------------------

def test_interaction_default_direction():
    i = Interaction(contact_id=1)
    assert i.direction == 'outbound'


def test_interaction_default_ai_draft_used():
    i = Interaction(contact_id=1)
    assert i.ai_draft_used is False


def test_interaction_default_contact_id():
    i = Interaction()
    assert i.contact_id == 0


def test_interaction_optional_fields_default_to_none():
    i = Interaction()
    for field in ('id', 'interaction_date', 'method', 'summary', 'outcome',
                  'next_action', 'next_action_date', 'created_at', 'deleted_at'):
        assert getattr(i, field) is None, f"Expected {field} to be None"


def test_interaction_stores_all_fields():
    today = date(2026, 2, 15)
    i = Interaction(
        id=10,
        contact_id=42,
        interaction_date=today,
        method='email',
        direction='outbound',
        summary='Sent intro letter',
        outcome='no_reply',
        next_action='Follow up in 4 weeks',
        next_action_date=date(2026, 3, 15),
        ai_draft_used=True,
    )
    assert i.contact_id == 42
    assert i.method == 'email'
    assert i.ai_draft_used is True
    assert i.next_action_date == date(2026, 3, 15)


def test_interaction_equality():
    i1 = Interaction(id=1, contact_id=5, method='email')
    i2 = Interaction(id=1, contact_id=5, method='email')
    assert i1 == i2


# ---------------------------------------------------------------------------
# Show defaults
# ---------------------------------------------------------------------------

def test_show_default_status():
    s = Show()
    assert s.status == 'possible'


def test_show_optional_fields_default_to_none():
    s = Show()
    for field in ('id', 'name', 'venue_contact_id', 'city', 'date_start',
                  'date_end', 'theme', 'notes', 'created_at', 'updated_at', 'deleted_at'):
        assert getattr(s, field) is None, f"Expected {field} to be None"


def test_show_stores_all_fields():
    s = Show(
        id=3,
        name='Frühjahrsausstellung',
        venue_contact_id=7,
        city='München',
        date_start=date(2026, 4, 1),
        date_end=date(2026, 4, 30),
        theme='Landschaft',
        status='confirmed',
        notes='40 works planned',
    )
    assert s.name == 'Frühjahrsausstellung'
    assert s.city == 'München'
    assert s.status == 'confirmed'
    assert s.date_start == date(2026, 4, 1)


def test_show_equality():
    s1 = Show(id=1, name='Ausstellung', city='Augsburg')
    s2 = Show(id=1, name='Ausstellung', city='Augsburg')
    assert s1 == s2
