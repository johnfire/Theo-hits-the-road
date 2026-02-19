"""
Unit tests for the AI Planner (artcrm/engine/ai_planner.py).

Mocking strategy:
- artcrm.engine.ai_planner.call_ai       → AI backend calls
- artcrm.engine.ai_planner.crm.*         → all crm module calls
- artcrm.engine.ai_planner.get_db_cursor → direct DB calls in score/suggest/batch
- artcrm.engine.ai_planner.bus.emit      → event emission
"""

import pytest
from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, patch, call

from artcrm.models import Contact, Interaction, Show
from artcrm.engine.ai_planner import (
    build_artist_context,
    build_context_for_contact,
    generate_daily_brief,
    score_contact_fit,
    suggest_next_contacts,
    analyze_all_unscored_contacts,
)
from artcrm.bus.events import EVENT_ANALYSIS_COMPLETE, EVENT_SUGGESTION_READY


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

SAMPLE_CONTACT = Contact(
    id=1, name='Galerie Stern', type='gallery', subtype='contemporary',
    city='Augsburg', country='DE', website='https://galerie-stern.de',
    status='cold', preferred_language='de',
)

SAMPLE_INTERACTION = Interaction(
    id=10, contact_id=1, interaction_date=date(2026, 1, 15),
    method='email', direction='outbound', summary='Sent intro letter',
    outcome='no_reply',
)

SAMPLE_SHOW = Show(
    id=5, name='Frühjahrsausstellung', city='München',
    date_start=date(2026, 4, 1), status='confirmed',
)

CONTACT_ROW = {
    'id': 1, 'name': 'Galerie Stern', 'type': 'gallery', 'subtype': None,
    'city': 'Augsburg', 'country': 'DE', 'address': None,
    'website': None, 'email': None, 'phone': None,
    'preferred_language': 'de', 'status': 'cold',
    'fit_score': None, 'success_probability': None, 'best_visit_time': None,
    'notes': None, 'created_at': None, 'updated_at': None, 'deleted_at': None,
}


def make_cursor(fetchone=None, fetchall=None, rowcount=1):
    cur = MagicMock()
    cur.fetchone.return_value = fetchone
    cur.fetchall.return_value = fetchall if fetchall is not None else []
    cur.rowcount = rowcount
    return cur


def cursor_patch(cur):
    @contextmanager
    def _mock_ctx():
        yield cur
    return patch('artcrm.engine.ai_planner.get_db_cursor', _mock_ctx)


# ---------------------------------------------------------------------------
# build_artist_context
# ---------------------------------------------------------------------------

def test_build_artist_context_returns_string():
    result = build_artist_context()
    assert isinstance(result, str)
    assert len(result) > 0


def test_build_artist_context_contains_artist_name():
    result = build_artist_context()
    assert 'Christopher Rehm' in result


def test_build_artist_context_contains_location():
    result = build_artist_context()
    assert 'Bavaria' in result


# ---------------------------------------------------------------------------
# build_context_for_contact
# ---------------------------------------------------------------------------

def test_build_context_contact_not_found_returns_empty():
    with patch('artcrm.engine.ai_planner.crm.get_contact', return_value=None), \
         patch('artcrm.engine.ai_planner.crm.get_interactions', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]):
        result = build_context_for_contact(999)
    assert result == ''


def test_build_context_includes_contact_name():
    with patch('artcrm.engine.ai_planner.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.ai_planner.crm.get_interactions', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]):
        result = build_context_for_contact(1)
    assert 'Galerie Stern' in result


def test_build_context_no_interactions_message():
    with patch('artcrm.engine.ai_planner.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.ai_planner.crm.get_interactions', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]):
        result = build_context_for_contact(1)
    assert 'No previous interactions' in result


def test_build_context_includes_interaction_history():
    with patch('artcrm.engine.ai_planner.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.ai_planner.crm.get_interactions', return_value=[SAMPLE_INTERACTION]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]):
        result = build_context_for_contact(1)
    assert 'INTERACTION HISTORY' in result
    assert 'email' in result


def test_build_context_includes_upcoming_shows():
    with patch('artcrm.engine.ai_planner.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.ai_planner.crm.get_interactions', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[SAMPLE_SHOW]):
        result = build_context_for_contact(1)
    assert 'UPCOMING SHOWS' in result
    assert 'Frühjahrsausstellung' in result


def test_build_context_includes_notes_when_present():
    contact_with_notes = Contact(**{**SAMPLE_CONTACT.__dict__, 'notes': 'Very welcoming'})
    with patch('artcrm.engine.ai_planner.crm.get_contact', return_value=contact_with_notes), \
         patch('artcrm.engine.ai_planner.crm.get_interactions', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]):
        result = build_context_for_contact(1)
    assert 'Very welcoming' in result


# ---------------------------------------------------------------------------
# generate_daily_brief
# ---------------------------------------------------------------------------

def test_generate_daily_brief_returns_ai_response():
    with patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_dormant_contacts', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ai', return_value='Contact Galerie X first'):
        result = generate_daily_brief()
    assert result == 'Contact Galerie X first'


def test_generate_daily_brief_calls_ai():
    with patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=[SAMPLE_CONTACT]), \
         patch('artcrm.engine.ai_planner.crm.get_dormant_contacts', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ai', return_value='ok') as mock_ai:
        generate_daily_brief()
    mock_ai.assert_called_once()


def test_generate_daily_brief_uses_specified_model():
    with patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_dormant_contacts', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ai', return_value='ok') as mock_ai:
        generate_daily_brief(model='deepseek-reasoner')
    assert mock_ai.call_args[1]['model'] == 'deepseek-reasoner'


def test_generate_daily_brief_prompt_includes_contact_counts():
    with patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=[SAMPLE_CONTACT, SAMPLE_CONTACT]), \
         patch('artcrm.engine.ai_planner.crm.get_dormant_contacts', return_value=[SAMPLE_CONTACT]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ai', return_value='ok') as mock_ai:
        generate_daily_brief()
    prompt = mock_ai.call_args[0][0]
    assert '2 contacts have overdue' in prompt
    assert '1 contacts have been dormant' in prompt


# ---------------------------------------------------------------------------
# score_contact_fit
# ---------------------------------------------------------------------------

SCORE_RESPONSE = "SCORE: 75\nREASONING: Good gallery fit for watercolors\nAPPROACH: Send email intro"


def _patch_score_dependencies(ai_response=SCORE_RESPONSE, cur=None):
    """Returns a dict of patches needed for score_contact_fit."""
    if cur is None:
        cur = make_cursor()

    @contextmanager
    def _mock_ctx():
        yield cur

    return [
        patch('artcrm.engine.ai_planner.crm.get_contact', return_value=SAMPLE_CONTACT),
        patch('artcrm.engine.ai_planner.build_context_for_contact', return_value='some context'),
        patch('artcrm.engine.ai_planner.call_ai', return_value=ai_response),
        patch('artcrm.engine.ai_planner.get_db_cursor', _mock_ctx),
        patch('artcrm.engine.ai_planner.crm.update_contact', return_value=True),
        patch('artcrm.engine.ai_planner.bus.emit'),
    ]


def test_score_contact_fit_raises_when_not_found():
    with patch('artcrm.engine.ai_planner.crm.get_contact', return_value=None):
        with pytest.raises(ValueError, match='not found'):
            score_contact_fit(999)


def test_score_contact_fit_returns_dict_with_expected_keys():
    patches = _patch_score_dependencies()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        result = score_contact_fit(1)
    assert 'fit_score' in result
    assert 'reasoning' in result
    assert 'suggested_approach' in result
    assert 'raw_response' in result


def test_score_contact_fit_parses_score_correctly():
    patches = _patch_score_dependencies()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        result = score_contact_fit(1)
    assert result['fit_score'] == 75


def test_score_contact_fit_parses_reasoning():
    patches = _patch_score_dependencies()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        result = score_contact_fit(1)
    assert 'watercolors' in result['reasoning']


def test_score_contact_fit_parses_approach():
    patches = _patch_score_dependencies()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        result = score_contact_fit(1)
    assert 'email' in result['suggested_approach']


def test_score_contact_fit_clamps_score_above_100():
    patches = _patch_score_dependencies(ai_response='SCORE: 150\nREASONING: Great\nAPPROACH: Visit')
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        result = score_contact_fit(1)
    assert result['fit_score'] == 100


def test_score_contact_fit_clamps_score_below_0():
    patches = _patch_score_dependencies(ai_response='SCORE: -10\nREASONING: Poor\nAPPROACH: Skip')
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        result = score_contact_fit(1)
    assert result['fit_score'] == 0


def test_score_contact_fit_falls_back_to_raw_when_no_reasoning():
    raw = 'This gallery is a good fit for the artist.'
    patches = _patch_score_dependencies(ai_response=raw)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        result = score_contact_fit(1)
    assert result['reasoning'] == raw[:500]


def test_score_contact_fit_emits_analysis_complete():
    patches = _patch_score_dependencies()
    with patches[0], patches[1], patches[2], patches[3], patches[4], \
         patch('artcrm.engine.ai_planner.bus.emit') as mock_emit:
        score_contact_fit(1)
    event_name = mock_emit.call_args[0][0]
    assert event_name == EVENT_ANALYSIS_COMPLETE


def test_score_contact_fit_updates_contact_fit_score():
    patches = _patch_score_dependencies()
    with patches[0], patches[1], patches[2], patches[3], \
         patch('artcrm.engine.ai_planner.crm.update_contact') as mock_update, \
         patches[5]:
        score_contact_fit(1)
    mock_update.assert_called_once_with(1, {'fit_score': 75})


def test_score_contact_fit_stores_in_db():
    cur = make_cursor()
    patches = _patch_score_dependencies(cur=cur)
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        score_contact_fit(1)
    cur.execute.assert_called_once()
    sql = cur.execute.call_args[0][0]
    assert 'INSERT INTO ai_analysis' in sql


def test_score_contact_fit_uses_specified_model():
    patches = _patch_score_dependencies()
    with patches[0], patches[1], \
         patch('artcrm.engine.ai_planner.call_ai', return_value=SCORE_RESPONSE) as mock_ai, \
         patches[3], patches[4], patches[5]:
        score_contact_fit(1, model='claude')
    assert mock_ai.call_args[1].get('model') == 'claude'


# ---------------------------------------------------------------------------
# suggest_next_contacts
# ---------------------------------------------------------------------------

def test_suggest_next_contacts_returns_list():
    cur = make_cursor(fetchall=[CONTACT_ROW])
    with cursor_patch(cur), \
         patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ai', return_value='1. Contact X'), \
         patch('artcrm.engine.ai_planner.bus.emit'):
        result = suggest_next_contacts(limit=5)
    assert isinstance(result, list)


def test_suggest_next_contacts_respects_limit():
    contacts = [Contact(id=i, name=f'Gallery {i}') for i in range(1, 10)]
    cur = make_cursor(fetchall=[])
    with cursor_patch(cur), \
         patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=contacts), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ai', return_value='ok'), \
         patch('artcrm.engine.ai_planner.bus.emit'):
        result = suggest_next_contacts(limit=3)
    assert len(result) <= 3


def test_suggest_next_contacts_deduplicates():
    # Same contact in overdue and high_fit — should appear only once
    cur = make_cursor(fetchall=[CONTACT_ROW])  # high_fit returns same contact as overdue
    with cursor_patch(cur), \
         patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=[SAMPLE_CONTACT]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ai', return_value='ok'), \
         patch('artcrm.engine.ai_planner.bus.emit'):
        result = suggest_next_contacts(limit=5)
    ids = [r['contact'].id for r in result]
    assert len(ids) == len(set(ids))


def test_suggest_next_contacts_emits_event():
    cur = make_cursor(fetchall=[])
    with cursor_patch(cur), \
         patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ai', return_value='ok'), \
         patch('artcrm.engine.ai_planner.bus.emit') as mock_emit:
        suggest_next_contacts()
    event_name = mock_emit.call_args[0][0]
    assert event_name == EVENT_SUGGESTION_READY


def test_suggest_next_contacts_result_has_expected_keys():
    cur = make_cursor(fetchall=[])
    with cursor_patch(cur), \
         patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=[SAMPLE_CONTACT]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ai', return_value='ok'), \
         patch('artcrm.engine.ai_planner.bus.emit'):
        result = suggest_next_contacts(limit=5)
    assert all('contact' in r and 'reasoning' in r for r in result)


# ---------------------------------------------------------------------------
# analyze_all_unscored_contacts
# ---------------------------------------------------------------------------

def test_analyze_all_unscored_returns_count():
    cur = make_cursor(fetchall=[{'id': 1}, {'id': 2}])
    with cursor_patch(cur), \
         patch('artcrm.engine.ai_planner.score_contact_fit'):
        result = analyze_all_unscored_contacts(limit=10)
    assert result == 2


def test_analyze_all_unscored_returns_zero_when_none():
    cur = make_cursor(fetchall=[])
    with cursor_patch(cur), \
         patch('artcrm.engine.ai_planner.score_contact_fit') as mock_score:
        result = analyze_all_unscored_contacts()
    assert result == 0
    mock_score.assert_not_called()


def test_analyze_all_unscored_calls_score_for_each():
    cur = make_cursor(fetchall=[{'id': 3}, {'id': 7}])
    with cursor_patch(cur), \
         patch('artcrm.engine.ai_planner.score_contact_fit') as mock_score:
        analyze_all_unscored_contacts()
    assert mock_score.call_count == 2
    mock_score.assert_any_call(3, model=None)
    mock_score.assert_any_call(7, model=None)


def test_analyze_all_unscored_continues_on_error():
    cur = make_cursor(fetchall=[{'id': 1}, {'id': 2}])

    def score_raises_on_first(contact_id, model=None):
        if contact_id == 1:
            raise RuntimeError('DeepSeek down')

    with cursor_patch(cur), \
         patch('artcrm.engine.ai_planner.score_contact_fit', side_effect=score_raises_on_first):
        result = analyze_all_unscored_contacts()
    # Should complete both, returning 2 (count is based on IDs fetched, not successes)
    assert result == 2
