"""
Unit tests for the MCP server (src/mcp/server.py) and serializers.

Strategy: patch engine functions, call MCP tool functions directly,
verify correct delegation and JSON serialization.
"""

import json
import pytest
from datetime import date, datetime
from unittest.mock import patch, MagicMock

from src.models import Contact, Interaction, Show
from src.mcp.serializers import (
    serialize_contact, serialize_interaction, serialize_show, serialize_list,
)
from src.mcp.server import (
    contact_create, contact_get, contact_update, contact_delete,
    contact_search, contacts_overdue, contacts_dormant,
    interaction_log, interaction_list,
    show_create, show_list, show_update,
    ai_daily_brief, ai_score_contact, ai_suggest_contacts, ai_score_unscored,
    draft_first_contact, draft_follow_up,
    scout_city,
)


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

SAMPLE_CONTACT = Contact(
    id=1, name='Galerie Stern', type='gallery', subtype='contemporary',
    city='Augsburg', country='DE', address='Maximilianstr. 1',
    website='https://galerie-stern.de', email='info@galerie-stern.de',
    phone='+4982112345', preferred_language='de', status='cold',
    created_at=datetime(2026, 1, 1, 12, 0, 0),
    updated_at=datetime(2026, 1, 15, 9, 30, 0),
)

SAMPLE_INTERACTION = Interaction(
    id=10, contact_id=1, interaction_date=date(2026, 1, 15),
    method='email', direction='outbound', summary='Sent intro',
    outcome='no_reply', next_action='Follow up',
    next_action_date=date(2026, 2, 15),
    ai_draft_used=False,
    created_at=datetime(2026, 1, 15, 10, 0, 0),
)

SAMPLE_SHOW = Show(
    id=5, name='Spring Exhibition', venue_contact_id=1,
    city='Augsburg', date_start=date(2026, 4, 1),
    date_end=date(2026, 4, 30), theme='Landscapes',
    status='confirmed',
    created_at=datetime(2026, 1, 1, 12, 0, 0),
    updated_at=datetime(2026, 2, 1, 8, 0, 0),
)


# ---------------------------------------------------------------------------
# Serializer tests
# ---------------------------------------------------------------------------

class TestSerializers:
    def test_serialize_contact_dates_as_iso(self):
        result = serialize_contact(SAMPLE_CONTACT)
        assert result['created_at'] == '2026-01-01T12:00:00'
        assert result['updated_at'] == '2026-01-15T09:30:00'

    def test_serialize_contact_drops_none(self):
        result = serialize_contact(SAMPLE_CONTACT)
        assert 'fit_score' not in result
        assert 'deleted_at' not in result
        assert 'notes' not in result

    def test_serialize_contact_keeps_values(self):
        result = serialize_contact(SAMPLE_CONTACT)
        assert result['name'] == 'Galerie Stern'
        assert result['id'] == 1
        assert result['city'] == 'Augsburg'

    def test_serialize_interaction_date(self):
        result = serialize_interaction(SAMPLE_INTERACTION)
        assert result['interaction_date'] == '2026-01-15'
        assert result['next_action_date'] == '2026-02-15'

    def test_serialize_show(self):
        result = serialize_show(SAMPLE_SHOW)
        assert result['date_start'] == '2026-04-01'
        assert result['status'] == 'confirmed'

    def test_serialize_list_json(self):
        result = serialize_list([SAMPLE_CONTACT], serialize_contact)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]['name'] == 'Galerie Stern'

    def test_serialize_empty_list(self):
        result = serialize_list([], serialize_contact)
        assert json.loads(result) == []

    def test_serialize_contact_bool_false_kept(self):
        """Boolean False should not be dropped (only None is dropped)."""
        result = serialize_interaction(SAMPLE_INTERACTION)
        assert result['ai_draft_used'] is False


# ---------------------------------------------------------------------------
# Contact tool tests
# ---------------------------------------------------------------------------

class TestContactTools:
    @patch('src.mcp.server.crm.create_contact')
    def test_contact_create(self, mock_create):
        mock_create.return_value = 42
        result = json.loads(contact_create(name='Test Gallery'))
        assert result['contact_id'] == 42
        assert result['name'] == 'Test Gallery'
        mock_create.assert_called_once()

    @patch('src.mcp.server.crm.get_contact')
    def test_contact_get_found(self, mock_get):
        mock_get.return_value = SAMPLE_CONTACT
        result = json.loads(contact_get(contact_id=1))
        assert result['name'] == 'Galerie Stern'
        mock_get.assert_called_once_with(1)

    @patch('src.mcp.server.crm.get_contact')
    def test_contact_get_not_found(self, mock_get):
        mock_get.return_value = None
        result = json.loads(contact_get(contact_id=999))
        assert 'error' in result

    @patch('src.mcp.server.crm.update_contact')
    def test_contact_update_success(self, mock_update):
        mock_update.return_value = True
        result = json.loads(contact_update(contact_id=1, updates='{"status": "contacted"}'))
        assert result['updated'] is True
        mock_update.assert_called_once_with(1, {"status": "contacted"})

    @patch('src.mcp.server.crm.update_contact')
    def test_contact_update_not_found(self, mock_update):
        mock_update.return_value = False
        result = json.loads(contact_update(contact_id=999, updates='{"status": "contacted"}'))
        assert 'error' in result

    def test_contact_update_bad_json(self):
        result = json.loads(contact_update(contact_id=1, updates='not json'))
        assert 'error' in result
        assert 'Invalid JSON' in result['error']

    @patch('src.mcp.server.crm.delete_contact')
    def test_contact_delete_soft(self, mock_delete):
        mock_delete.return_value = True
        result = json.loads(contact_delete(contact_id=1))
        assert result['deleted'] is True
        assert result['soft'] is True
        mock_delete.assert_called_once_with(1, soft=True)

    @patch('src.mcp.server.crm.search_contacts')
    def test_contact_search(self, mock_search):
        mock_search.return_value = [SAMPLE_CONTACT]
        result = json.loads(contact_search(city='Augsburg'))
        assert len(result) == 1
        assert result[0]['city'] == 'Augsburg'
        mock_search.assert_called_once_with(
            name=None, city='Augsburg', type=None, status=None, limit=100,
        )

    @patch('src.mcp.server.crm.get_overdue_contacts')
    def test_contacts_overdue(self, mock_overdue):
        mock_overdue.return_value = [SAMPLE_CONTACT]
        result = json.loads(contacts_overdue())
        assert len(result) == 1

    @patch('src.mcp.server.crm.get_dormant_contacts')
    def test_contacts_dormant(self, mock_dormant):
        mock_dormant.return_value = []
        result = json.loads(contacts_dormant())
        assert result == []


# ---------------------------------------------------------------------------
# Interaction tool tests
# ---------------------------------------------------------------------------

class TestInteractionTools:
    @patch('src.mcp.server.crm.log_interaction')
    def test_interaction_log(self, mock_log):
        mock_log.return_value = 10
        result = json.loads(interaction_log(
            contact_id=1, interaction_date='2026-01-15',
            method='email', direction='outbound', summary='Sent intro',
        ))
        assert result['interaction_id'] == 10
        mock_log.assert_called_once()

    def test_interaction_log_bad_date(self):
        result = json.loads(interaction_log(
            contact_id=1, interaction_date='not-a-date', method='email',
        ))
        assert 'error' in result

    @patch('src.mcp.server.crm.get_interactions')
    def test_interaction_list(self, mock_list):
        mock_list.return_value = [SAMPLE_INTERACTION]
        result = json.loads(interaction_list(contact_id=1))
        assert len(result) == 1
        assert result[0]['method'] == 'email'


# ---------------------------------------------------------------------------
# Show tool tests
# ---------------------------------------------------------------------------

class TestShowTools:
    @patch('src.mcp.server.crm.create_show')
    def test_show_create(self, mock_create):
        mock_create.return_value = 5
        result = json.loads(show_create(name='Spring Exhibition'))
        assert result['show_id'] == 5
        mock_create.assert_called_once()

    @patch('src.mcp.server.crm.get_shows')
    def test_show_list(self, mock_list):
        mock_list.return_value = [SAMPLE_SHOW]
        result = json.loads(show_list(status='confirmed'))
        assert len(result) == 1
        assert result[0]['status'] == 'confirmed'

    @patch('src.mcp.server.crm.update_show')
    def test_show_update(self, mock_update):
        mock_update.return_value = True
        result = json.loads(show_update(show_id=5, updates='{"status": "cancelled"}'))
        assert result['updated'] is True

    def test_show_update_bad_json(self):
        result = json.loads(show_update(show_id=5, updates='{bad}'))
        assert 'error' in result


# ---------------------------------------------------------------------------
# AI tool tests
# ---------------------------------------------------------------------------

class TestAITools:
    @patch('src.mcp.server.ai_planner.generate_daily_brief')
    def test_ai_daily_brief(self, mock_brief):
        mock_brief.return_value = 'Contact Galerie Stern this week.'
        result = json.loads(ai_daily_brief())
        assert 'brief' in result
        assert 'Galerie Stern' in result['brief']

    @patch('src.mcp.server.ai_planner.score_contact_fit')
    def test_ai_score_contact(self, mock_score):
        mock_score.return_value = {'fit_score': 85, 'reasoning': 'Great fit', 'suggested_approach': 'Email', 'raw_response': '...'}
        result = json.loads(ai_score_contact(contact_id=1))
        assert result['fit_score'] == 85
        mock_score.assert_called_once_with(1)

    @patch('src.mcp.server.ai_planner.suggest_next_contacts')
    def test_ai_suggest_contacts(self, mock_suggest):
        mock_suggest.return_value = [
            {'contact': SAMPLE_CONTACT, 'reasoning': 'Overdue follow-up'}
        ]
        result = json.loads(ai_suggest_contacts(limit=3))
        assert len(result) == 1
        assert result[0]['contact']['name'] == 'Galerie Stern'

    @patch('src.mcp.server.ai_planner.analyze_all_unscored_contacts')
    def test_ai_score_unscored(self, mock_analyze):
        mock_analyze.return_value = 7
        result = json.loads(ai_score_unscored(limit=10))
        assert result['scored_count'] == 7


# ---------------------------------------------------------------------------
# Email tool tests
# ---------------------------------------------------------------------------

class TestEmailTools:
    @patch('src.mcp.server.email_composer.draft_first_contact_letter')
    def test_draft_first_contact(self, mock_draft):
        mock_draft.return_value = {
            'contact_id': 1, 'contact_name': 'Galerie Stern',
            'subject': 'Hello', 'body': 'Dear...', 'language': 'de',
            'draft_path': '/tmp/draft.txt', 'timestamp': '20260115_100000',
        }
        result = json.loads(draft_first_contact(contact_id=1))
        assert result['subject'] == 'Hello'
        mock_draft.assert_called_once_with(
            contact_id=1, language=None, include_portfolio_link=True,
        )

    @patch('src.mcp.server.email_composer.draft_follow_up_letter')
    def test_draft_follow_up(self, mock_draft):
        mock_draft.return_value = {
            'contact_id': 1, 'contact_name': 'Galerie Stern',
            'subject': 'Follow-up', 'body': 'Dear...', 'language': 'de',
            'draft_path': '/tmp/followup.txt', 'timestamp': '20260115_100000',
        }
        result = json.loads(draft_follow_up(
            contact_id=1, previous_interaction_summary='Met at fair',
        ))
        assert result['subject'] == 'Follow-up'
        mock_draft.assert_called_once_with(
            contact_id=1, previous_interaction_summary='Met at fair', language=None,
        )


# ---------------------------------------------------------------------------
# Scout tool tests
# ---------------------------------------------------------------------------

class TestScoutTools:
    @patch('src.mcp.server.lead_scout.scout_city')
    def test_scout_city(self, mock_scout):
        mock_scout.return_value = {
            'city': 'Munich', 'country': 'DE',
            'total_found': 15, 'total_inserted': 12,
        }
        result = json.loads(scout_city(city='Munich', business_types='["gallery", "cafe"]'))
        assert result['total_found'] == 15
        mock_scout.assert_called_once_with(
            city='Munich', country='DE',
            business_types=['gallery', 'cafe'],
            radius_km=10.0,
            use_google_maps=True, use_osm=True, skip_duplicates=True,
        )

    @patch('src.mcp.server.lead_scout.scout_city')
    def test_scout_city_default_types(self, mock_scout):
        mock_scout.return_value = {'city': 'Munich', 'total_found': 0}
        scout_city(city='Munich')
        mock_scout.assert_called_once_with(
            city='Munich', country='DE',
            business_types=None,
            radius_km=10.0,
            use_google_maps=True, use_osm=True, skip_duplicates=True,
        )

    def test_scout_city_bad_json(self):
        result = json.loads(scout_city(city='Munich', business_types='not json'))
        assert 'error' in result


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @patch('src.mcp.server.crm.get_contact')
    def test_exception_returns_error_json(self, mock_get):
        mock_get.side_effect = RuntimeError("DB connection failed")
        result = json.loads(contact_get(contact_id=1))
        assert 'error' in result
        assert 'DB connection failed' in result['error']

    @patch('src.mcp.server.crm.create_contact')
    def test_create_exception(self, mock_create):
        mock_create.side_effect = Exception("insert failed")
        result = json.loads(contact_create(name='Test'))
        assert 'error' in result
