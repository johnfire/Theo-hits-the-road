"""
Unit tests for the AI Planner (artcrm/engine/ai_planner.py).

Mocking strategy:
- requests.post           → Ollama HTTP calls
- artcrm.engine.ai_planner.crm.*  → all crm module calls
- artcrm.engine.ai_planner.get_db_cursor → direct DB calls in score/suggest/batch
- artcrm.engine.ai_planner.bus.emit → event emission
"""

import pytest
from contextlib import contextmanager
from datetime import date
from unittest.mock import MagicMock, patch, call

from artcrm.models import Contact, Interaction, Show
from artcrm.engine.ai_planner import (
    call_ollama,
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


def mock_ollama_response(text: str):
    """Build a mock requests.Response with the given text as the Ollama response."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {'response': text}
    mock_resp.raise_for_status.return_value = None
    return mock_resp


# ---------------------------------------------------------------------------
# call_ollama
# ---------------------------------------------------------------------------

def test_call_ollama_returns_response_text():
    with patch('requests.post', return_value=mock_ollama_response('Hello artist')):
        result = call_ollama('What should I do?')
    assert result == 'Hello artist'


def test_call_ollama_posts_to_correct_url():
    with patch('requests.post', return_value=mock_ollama_response('ok')) as mock_post:
        call_ollama('prompt')
    url = mock_post.call_args[0][0]
    assert '/api/generate' in url


def test_call_ollama_includes_prompt_in_payload():
    with patch('requests.post', return_value=mock_ollama_response('ok')) as mock_post:
        call_ollama('My prompt text')
    payload = mock_post.call_args[1]['json']
    assert payload['prompt'] == 'My prompt text'


def test_call_ollama_includes_system_when_provided():
    with patch('requests.post', return_value=mock_ollama_response('ok')) as mock_post:
        call_ollama('prompt', system='You are helpful')
    payload = mock_post.call_args[1]['json']
    assert payload['system'] == 'You are helpful'


def test_call_ollama_no_system_key_when_not_provided():
    with patch('requests.post', return_value=mock_ollama_response('ok')) as mock_post:
        call_ollama('prompt')
    payload = mock_post.call_args[1]['json']
    assert 'system' not in payload


def test_call_ollama_stream_is_false():
    with patch('requests.post', return_value=mock_ollama_response('ok')) as mock_post:
        call_ollama('prompt')
    payload = mock_post.call_args[1]['json']
    assert payload['stream'] is False


def test_call_ollama_raises_runtime_error_on_request_exception():
    import requests as req
    with patch('requests.post', side_effect=req.exceptions.ConnectionError('refused')):
        with pytest.raises(RuntimeError, match='Failed to call Ollama'):
            call_ollama('prompt')


def test_call_ollama_raises_on_http_error():
    import requests as req
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = req.exceptions.HTTPError('500')
    with patch('requests.post', return_value=mock_resp):
        with pytest.raises(RuntimeError, match='Failed to call Ollama'):
            call_ollama('prompt')


def test_call_ollama_empty_response_key_returns_empty_string():
    mock_resp = MagicMock()
    mock_resp.json.return_value = {}  # no 'response' key
    mock_resp.raise_for_status.return_value = None
    with patch('requests.post', return_value=mock_resp):
        result = call_ollama('prompt')
    assert result == ''


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

def test_generate_daily_brief_returns_ollama_response():
    with patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_dormant_contacts', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ollama', return_value='Contact Galerie X first'):
        result = generate_daily_brief()
    assert result == 'Contact Galerie X first'


def test_generate_daily_brief_calls_ollama():
    with patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=[SAMPLE_CONTACT]), \
         patch('artcrm.engine.ai_planner.crm.get_dormant_contacts', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ollama', return_value='ok') as mock_ollama:
        generate_daily_brief()
    mock_ollama.assert_called_once()


def test_generate_daily_brief_prompt_includes_contact_counts():
    with patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=[SAMPLE_CONTACT, SAMPLE_CONTACT]), \
         patch('artcrm.engine.ai_planner.crm.get_dormant_contacts', return_value=[SAMPLE_CONTACT]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ollama', return_value='ok') as mock_ollama:
        generate_daily_brief()
    prompt = mock_ollama.call_args[0][0]
    assert '2 contacts have overdue' in prompt
    assert '1 contacts have been dormant' in prompt


# ---------------------------------------------------------------------------
# score_contact_fit
# ---------------------------------------------------------------------------

SCORE_RESPONSE = "SCORE: 75\nREASONING: Good gallery fit for watercolors\nAPPROACH: Send email intro"


def _patch_score_dependencies(ollama_response=SCORE_RESPONSE, cur=None):
    """Returns a dict of patches needed for score_contact_fit."""
    if cur is None:
        cur = make_cursor()

    @contextmanager
    def _mock_ctx():
        yield cur

    return [
        patch('artcrm.engine.ai_planner.crm.get_contact', return_value=SAMPLE_CONTACT),
        patch('artcrm.engine.ai_planner.build_context_for_contact', return_value='some context'),
        patch('artcrm.engine.ai_planner.call_ollama', return_value=ollama_response),
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
    patches = _patch_score_dependencies(ollama_response='SCORE: 150\nREASONING: Great\nAPPROACH: Visit')
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        result = score_contact_fit(1)
    assert result['fit_score'] == 100


def test_score_contact_fit_clamps_score_below_0():
    patches = _patch_score_dependencies(ollama_response='SCORE: -10\nREASONING: Poor\nAPPROACH: Skip')
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
        result = score_contact_fit(1)
    assert result['fit_score'] == 0


def test_score_contact_fit_falls_back_to_raw_when_no_reasoning():
    raw = 'This gallery is a good fit for the artist.'
    patches = _patch_score_dependencies(ollama_response=raw)
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


# ---------------------------------------------------------------------------
# suggest_next_contacts
# ---------------------------------------------------------------------------

def test_suggest_next_contacts_returns_list():
    cur = make_cursor(fetchall=[CONTACT_ROW])
    with cursor_patch(cur), \
         patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ollama', return_value='1. Contact X'), \
         patch('artcrm.engine.ai_planner.bus.emit'):
        result = suggest_next_contacts(limit=5)
    assert isinstance(result, list)


def test_suggest_next_contacts_respects_limit():
    contacts = [Contact(id=i, name=f'Gallery {i}') for i in range(1, 10)]
    cur = make_cursor(fetchall=[])
    with cursor_patch(cur), \
         patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=contacts), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ollama', return_value='ok'), \
         patch('artcrm.engine.ai_planner.bus.emit'):
        result = suggest_next_contacts(limit=3)
    assert len(result) <= 3


def test_suggest_next_contacts_deduplicates():
    # Same contact in overdue and high_fit — should appear only once
    cur = make_cursor(fetchall=[CONTACT_ROW])  # high_fit returns same contact as overdue
    with cursor_patch(cur), \
         patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=[SAMPLE_CONTACT]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ollama', return_value='ok'), \
         patch('artcrm.engine.ai_planner.bus.emit'):
        result = suggest_next_contacts(limit=5)
    ids = [r['contact'].id for r in result]
    assert len(ids) == len(set(ids))


def test_suggest_next_contacts_emits_event():
    cur = make_cursor(fetchall=[])
    with cursor_patch(cur), \
         patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=[]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ollama', return_value='ok'), \
         patch('artcrm.engine.ai_planner.bus.emit') as mock_emit:
        suggest_next_contacts()
    event_name = mock_emit.call_args[0][0]
    assert event_name == EVENT_SUGGESTION_READY


def test_suggest_next_contacts_result_has_expected_keys():
    cur = make_cursor(fetchall=[])
    with cursor_patch(cur), \
         patch('artcrm.engine.ai_planner.crm.get_overdue_contacts', return_value=[SAMPLE_CONTACT]), \
         patch('artcrm.engine.ai_planner.crm.get_shows', return_value=[]), \
         patch('artcrm.engine.ai_planner.call_ollama', return_value='ok'), \
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
    mock_score.assert_any_call(3)
    mock_score.assert_any_call(7)


def test_analyze_all_unscored_continues_on_error():
    cur = make_cursor(fetchall=[{'id': 1}, {'id': 2}])

    def score_raises_on_first(contact_id):
        if contact_id == 1:
            raise RuntimeError('Ollama down')

    with cursor_patch(cur), \
         patch('artcrm.engine.ai_planner.score_contact_fit', side_effect=score_raises_on_first):
        result = analyze_all_unscored_contacts()
    # Should complete both, returning 2 (count is based on IDs fetched, not successes)
    assert result == 2
