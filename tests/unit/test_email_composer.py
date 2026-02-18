"""
Unit tests for the Email Composer (artcrm/engine/email_composer.py).

Mocking strategy:
- artcrm.engine.email_composer.Anthropic  → Claude API client
- artcrm.engine.email_composer.crm.*      → DB-touching crm calls
- artcrm.engine.email_composer.call_claude → when testing draft functions
- artcrm.engine.email_composer.DRAFTS_DIR  → tmp_path (avoids disk writes)
- artcrm.engine.email_composer.bus.emit   → event capture
"""

import pytest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

from artcrm.models import Contact, Interaction
from artcrm.engine.email_composer import (
    call_claude,
    build_artist_context,
    build_contact_context,
    draft_first_contact_letter,
    draft_follow_up_letter,
)
from artcrm.bus.events import EVENT_DRAFT_READY


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

SAMPLE_CONTACT = Contact(
    id=1, name='Galerie Stern', type='gallery', subtype='contemporary',
    city='Augsburg', country='DE', website='https://galerie-stern.de',
    email='info@galerie-stern.de', preferred_language='de', status='cold',
)

SAMPLE_INTERACTION = Interaction(
    id=10, contact_id=1, interaction_date=date(2026, 1, 15),
    method='email', direction='outbound', summary='Sent intro letter', outcome='no_reply',
)

DRAFT_RESPONSE = "Subject: Kunstwerke für Ihre Galerie\n\nSehr geehrte Damen und Herren,\n\nIch stelle mich vor."


def mock_anthropic_client(text: str):
    """Return a mock Anthropic class that produces the given text."""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=text)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_message
    mock_cls = MagicMock(return_value=mock_client)
    return mock_cls, mock_client


# ---------------------------------------------------------------------------
# call_claude
# ---------------------------------------------------------------------------

def test_call_claude_raises_when_no_api_key(monkeypatch):
    monkeypatch.setattr('artcrm.engine.email_composer.config.ANTHROPIC_API_KEY', '')
    with pytest.raises(ValueError, match='ANTHROPIC_API_KEY'):
        call_claude('prompt')


def test_call_claude_returns_message_text():
    mock_cls, _ = mock_anthropic_client('Hello from Claude')
    with patch('artcrm.engine.email_composer.config.ANTHROPIC_API_KEY', 'sk-test'), \
         patch('artcrm.engine.email_composer.Anthropic', mock_cls):
        result = call_claude('Write a letter')
    assert result == 'Hello from Claude'


def test_call_claude_passes_prompt_in_messages():
    mock_cls, mock_client = mock_anthropic_client('ok')
    with patch('artcrm.engine.email_composer.config.ANTHROPIC_API_KEY', 'sk-test'), \
         patch('artcrm.engine.email_composer.Anthropic', mock_cls):
        call_claude('My prompt here')
    messages = mock_client.messages.create.call_args[1]['messages']
    assert messages[0]['content'] == 'My prompt here'


def test_call_claude_uses_provided_system_prompt():
    mock_cls, mock_client = mock_anthropic_client('ok')
    with patch('artcrm.engine.email_composer.config.ANTHROPIC_API_KEY', 'sk-test'), \
         patch('artcrm.engine.email_composer.Anthropic', mock_cls):
        call_claude('prompt', system='You are a poet')
    system = mock_client.messages.create.call_args[1]['system']
    assert system == 'You are a poet'


def test_call_claude_uses_default_system_when_none():
    mock_cls, mock_client = mock_anthropic_client('ok')
    with patch('artcrm.engine.email_composer.config.ANTHROPIC_API_KEY', 'sk-test'), \
         patch('artcrm.engine.email_composer.Anthropic', mock_cls):
        call_claude('prompt')
    system = mock_client.messages.create.call_args[1]['system']
    assert 'artist' in system.lower() or 'writer' in system.lower()


def test_call_claude_respects_max_tokens():
    mock_cls, mock_client = mock_anthropic_client('ok')
    with patch('artcrm.engine.email_composer.config.ANTHROPIC_API_KEY', 'sk-test'), \
         patch('artcrm.engine.email_composer.Anthropic', mock_cls):
        call_claude('prompt', max_tokens=500)
    max_tokens = mock_client.messages.create.call_args[1]['max_tokens']
    assert max_tokens == 500


def test_call_claude_raises_runtime_error_on_exception():
    # Exception must come from inside the try block (messages.create), not the constructor
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception('API down')
    mock_cls = MagicMock(return_value=mock_client)
    with patch('artcrm.engine.email_composer.config.ANTHROPIC_API_KEY', 'sk-test'), \
         patch('artcrm.engine.email_composer.Anthropic', mock_cls):
        with pytest.raises(RuntimeError, match='Failed to call Claude API'):
            call_claude('prompt')


def test_call_claude_initialises_client_with_api_key():
    mock_cls, _ = mock_anthropic_client('ok')
    with patch('artcrm.engine.email_composer.config.ANTHROPIC_API_KEY', 'sk-ant-test'), \
         patch('artcrm.engine.email_composer.Anthropic', mock_cls):
        call_claude('prompt')
    mock_cls.assert_called_once_with(api_key='sk-ant-test')


# ---------------------------------------------------------------------------
# build_artist_context
# ---------------------------------------------------------------------------

def test_build_artist_context_returns_string():
    result = build_artist_context()
    assert isinstance(result, str) and len(result) > 0


def test_build_artist_context_contains_artist_name():
    result = build_artist_context()
    assert 'Christopher Rehm' in result


def test_build_artist_context_reads_bio_file_when_present(tmp_path):
    bio_file = tmp_path / 'artist_bio.txt'
    bio_file.write_text('Custom bio content here')
    with patch('artcrm.engine.email_composer.Path') as MockPath:
        # Make the bio_file path return our temp file
        mock_path_instance = MagicMock()
        mock_path_instance.__truediv__ = MagicMock(return_value=bio_file)
        mock_path_instance.exists.return_value = True
        MockPath.return_value = mock_path_instance
        # Easier: just patch the bio_file existence directly
    # Direct approach: patch at the resolved path level
    with patch.object(Path, 'exists', return_value=True), \
         patch.object(Path, 'read_text', return_value='Custom bio content here'):
        result = build_artist_context()
    assert 'Custom bio content here' in result


def test_build_artist_context_placeholder_when_no_bio_file():
    with patch.object(Path, 'exists', return_value=False):
        result = build_artist_context()
    assert 'Bavaria' in result or 'Klosterlechfeld' in result


# ---------------------------------------------------------------------------
# build_contact_context
# ---------------------------------------------------------------------------

def test_build_contact_context_includes_name():
    result = build_contact_context(SAMPLE_CONTACT)
    assert 'Galerie Stern' in result


def test_build_contact_context_includes_type():
    result = build_contact_context(SAMPLE_CONTACT)
    assert 'gallery' in result


def test_build_contact_context_includes_city():
    result = build_contact_context(SAMPLE_CONTACT)
    assert 'Augsburg' in result


def test_build_contact_context_includes_website_when_present():
    result = build_contact_context(SAMPLE_CONTACT)
    assert 'galerie-stern.de' in result


def test_build_contact_context_omits_website_when_absent():
    contact = Contact(id=2, name='Cafe Kunst', type='cafe', city='München')
    result = build_contact_context(contact)
    assert 'Website' not in result


def test_build_contact_context_includes_notes_when_present():
    contact = Contact(**{**SAMPLE_CONTACT.__dict__, 'notes': 'Very welcoming owner'})
    result = build_contact_context(contact)
    assert 'Very welcoming owner' in result


def test_build_contact_context_omits_notes_when_absent():
    result = build_contact_context(SAMPLE_CONTACT)
    assert 'Notes' not in result


def test_build_contact_context_truncates_notes_at_200():
    long_notes = 'x' * 300
    contact = Contact(**{**SAMPLE_CONTACT.__dict__, 'notes': long_notes})
    result = build_contact_context(contact)
    # Notes in context should not exceed 200 chars
    lines = [l for l in result.split('\n') if l.startswith('Notes:')]
    assert len(lines[0]) <= len('Notes: ') + 200


def test_build_contact_context_uses_germany_as_default_country():
    contact = Contact(id=3, name='Cafe X', city='Augsburg', country=None)
    result = build_contact_context(contact)
    assert 'Germany' in result


# ---------------------------------------------------------------------------
# draft_first_contact_letter
# ---------------------------------------------------------------------------

def test_draft_first_contact_raises_when_not_found(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=None), \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        with pytest.raises(ValueError, match='not found'):
            draft_first_contact_letter(999)


def test_draft_first_contact_returns_expected_keys(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.email_composer.call_claude', return_value=DRAFT_RESPONSE), \
         patch('artcrm.engine.email_composer.bus.emit'), \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        result = draft_first_contact_letter(1)
    for key in ('contact_id', 'contact_name', 'subject', 'body', 'language', 'draft_path', 'timestamp'):
        assert key in result


def test_draft_first_contact_uses_contact_language(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.email_composer.call_claude', return_value=DRAFT_RESPONSE), \
         patch('artcrm.engine.email_composer.bus.emit'), \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        result = draft_first_contact_letter(1)
    assert result['language'] == 'de'


def test_draft_first_contact_language_override(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.email_composer.call_claude', return_value=DRAFT_RESPONSE), \
         patch('artcrm.engine.email_composer.bus.emit'), \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        result = draft_first_contact_letter(1, language='en')
    assert result['language'] == 'en'


def test_draft_first_contact_parses_subject_from_first_line(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.email_composer.call_claude', return_value=DRAFT_RESPONSE), \
         patch('artcrm.engine.email_composer.bus.emit'), \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        result = draft_first_contact_letter(1)
    assert 'Kunstwerke' in result['subject']


def test_draft_first_contact_parses_body_from_remainder(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.email_composer.call_claude', return_value=DRAFT_RESPONSE), \
         patch('artcrm.engine.email_composer.bus.emit'), \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        result = draft_first_contact_letter(1)
    assert 'Sehr geehrte' in result['body']


def test_draft_first_contact_writes_file(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.email_composer.call_claude', return_value=DRAFT_RESPONSE), \
         patch('artcrm.engine.email_composer.bus.emit'), \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        result = draft_first_contact_letter(1)
    assert Path(result['draft_path']).exists()


def test_draft_first_contact_emits_event(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.email_composer.call_claude', return_value=DRAFT_RESPONSE), \
         patch('artcrm.engine.email_composer.bus.emit') as mock_emit, \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        draft_first_contact_letter(1)
    mock_emit.assert_called_once()
    assert mock_emit.call_args[0][0] == EVENT_DRAFT_READY


def test_draft_first_contact_portfolio_link_in_prompt_when_requested(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.email_composer.call_claude', return_value=DRAFT_RESPONSE) as mock_claude, \
         patch('artcrm.engine.email_composer.bus.emit'), \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        draft_first_contact_letter(1, include_portfolio_link=True)
    prompt = mock_claude.call_args[0][0]
    # CWE-020: parse URL components rather than doing string membership/substring checks.
    parsed = [urlparse(w) for w in prompt.split()]
    assert any(p.scheme == 'https' and p.netloc == 'www.artbychristopherrehm.com' for p in parsed)


def test_draft_first_contact_no_portfolio_link_when_false(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.email_composer.call_claude', return_value=DRAFT_RESPONSE) as mock_claude, \
         patch('artcrm.engine.email_composer.bus.emit'), \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        draft_first_contact_letter(1, include_portfolio_link=False)
    prompt = mock_claude.call_args[0][0]
    parsed = [urlparse(w) for w in prompt.split()]
    assert not any(p.scheme == 'https' and p.netloc == 'www.artbychristopherrehm.com' for p in parsed)


# ---------------------------------------------------------------------------
# draft_follow_up_letter
# ---------------------------------------------------------------------------

def test_draft_follow_up_raises_when_not_found(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=None), \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        with pytest.raises(ValueError, match='not found'):
            draft_follow_up_letter(999, 'Previous email sent')


def test_draft_follow_up_returns_expected_keys(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.email_composer.crm.get_interactions', return_value=[]), \
         patch('artcrm.engine.email_composer.call_claude', return_value=DRAFT_RESPONSE), \
         patch('artcrm.engine.email_composer.bus.emit'), \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        result = draft_follow_up_letter(1, 'Sent intro in January')
    for key in ('contact_id', 'contact_name', 'subject', 'body', 'language', 'draft_path', 'timestamp'):
        assert key in result


def test_draft_follow_up_uses_contact_language(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.email_composer.crm.get_interactions', return_value=[]), \
         patch('artcrm.engine.email_composer.call_claude', return_value=DRAFT_RESPONSE), \
         patch('artcrm.engine.email_composer.bus.emit'), \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        result = draft_follow_up_letter(1, 'Previous contact')
    assert result['language'] == 'de'


def test_draft_follow_up_includes_interaction_history_in_prompt(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.email_composer.crm.get_interactions', return_value=[SAMPLE_INTERACTION]), \
         patch('artcrm.engine.email_composer.call_claude', return_value=DRAFT_RESPONSE) as mock_claude, \
         patch('artcrm.engine.email_composer.bus.emit'), \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        draft_follow_up_letter(1, 'Initial contact in January')
    prompt = mock_claude.call_args[0][0]
    assert 'Sent intro letter' in prompt


def test_draft_follow_up_no_history_message(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.email_composer.crm.get_interactions', return_value=[]), \
         patch('artcrm.engine.email_composer.call_claude', return_value=DRAFT_RESPONSE) as mock_claude, \
         patch('artcrm.engine.email_composer.bus.emit'), \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        draft_follow_up_letter(1, 'Previous contact')
    prompt = mock_claude.call_args[0][0]
    assert 'No previous interactions' in prompt


def test_draft_follow_up_writes_file(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.email_composer.crm.get_interactions', return_value=[]), \
         patch('artcrm.engine.email_composer.call_claude', return_value=DRAFT_RESPONSE), \
         patch('artcrm.engine.email_composer.bus.emit'), \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        result = draft_follow_up_letter(1, 'Previous contact')
    assert Path(result['draft_path']).exists()


def test_draft_follow_up_emits_event(tmp_path):
    with patch('artcrm.engine.email_composer.crm.get_contact', return_value=SAMPLE_CONTACT), \
         patch('artcrm.engine.email_composer.crm.get_interactions', return_value=[]), \
         patch('artcrm.engine.email_composer.call_claude', return_value=DRAFT_RESPONSE), \
         patch('artcrm.engine.email_composer.bus.emit') as mock_emit, \
         patch('artcrm.engine.email_composer.DRAFTS_DIR', tmp_path):
        draft_follow_up_letter(1, 'Previous contact')
    mock_emit.assert_called_once()
    assert mock_emit.call_args[0][0] == EVENT_DRAFT_READY
    assert mock_emit.call_args[0][1].get('type') == 'follow-up'
