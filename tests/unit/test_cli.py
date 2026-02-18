"""
Unit tests for artcrm/cli/main.py.

Mocking strategy:
  - patch artcrm.cli.main.crm for all CRM-level calls
  - patch artcrm.cli.main.configure_logging (autouse) to prevent file I/O
  - AI commands import their modules lazily inside the function body, so
    we patch at artcrm.engine.<module>.<function>
  - Use click.testing.CliRunner to invoke commands end-to-end
"""

import pytest
from datetime import date
from unittest.mock import MagicMock, patch, call

from click.testing import CliRunner

from artcrm.cli.main import cli, _prompt_date, _prompt_email
from artcrm.models import Contact, Interaction, Show


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_CONTACT = Contact(
    id=1, name='Galerie Stern', type='gallery', subtype='contemporary',
    city='Augsburg', country='DE', email='info@galerie-stern.de',
    preferred_language='de', status='cold',
)

SAMPLE_INTERACTION = Interaction(
    id=10, contact_id=1, interaction_date=date(2026, 1, 15),
    method='email', direction='outbound', summary='Sent intro letter',
    outcome='no_reply', next_action=None, next_action_date=None,
    ai_draft_used=False,
)

SAMPLE_SHOW = Show(
    id=5, name='Fruhjahrsausstellung', city='Munchen',
    date_start=date(2026, 4, 1), date_end=date(2026, 4, 30), status='confirmed',
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def no_logging():
    """Prevent configure_logging from creating log files during tests."""
    with patch("artcrm.cli.main.configure_logging"):
        yield


# ---------------------------------------------------------------------------
# contacts list
# ---------------------------------------------------------------------------

class TestContactsList:

    def test_empty_result(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.search_contacts.return_value = []
            result = runner.invoke(cli, ["contacts", "list"])
        assert result.exit_code == 0
        assert "No contacts found" in result.output

    def test_lists_contacts(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.search_contacts.return_value = [SAMPLE_CONTACT]
            result = runner.invoke(cli, ["contacts", "list"])
        assert result.exit_code == 0
        assert "Galerie Stern" in result.output
        assert "Augsburg" in result.output
        assert "gallery" in result.output

    def test_passes_filters_to_crm(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.search_contacts.return_value = []
            runner.invoke(cli, [
                "contacts", "list",
                "--type", "gallery",
                "--status", "cold",
                "--city", "Augsburg",
                "--limit", "10",
            ])
        mock_crm.search_contacts.assert_called_once_with(
            type="gallery", status="cold", city="Augsburg", limit=10
        )

    def test_default_limit_is_500(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.search_contacts.return_value = []
            runner.invoke(cli, ["contacts", "list"])
        _, kwargs = mock_crm.search_contacts.call_args
        assert kwargs["limit"] == 500


# ---------------------------------------------------------------------------
# contacts show
# ---------------------------------------------------------------------------

class TestContactsShow:

    def test_not_found(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_contact.return_value = None
            result = runner.invoke(cli, ["contacts", "show", "99"])
        assert result.exit_code == 0
        assert "not found" in result.output

    def test_shows_contact_details(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_contact.return_value = SAMPLE_CONTACT
            mock_crm.get_interactions.return_value = []
            result = runner.invoke(cli, ["contacts", "show", "1"])
        assert result.exit_code == 0
        assert "Galerie Stern" in result.output
        assert "Augsburg" in result.output
        assert "No interactions yet" in result.output

    def test_shows_interactions(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_contact.return_value = SAMPLE_CONTACT
            mock_crm.get_interactions.return_value = [SAMPLE_INTERACTION]
            result = runner.invoke(cli, ["contacts", "show", "1"])
        assert "Sent intro letter" in result.output

    def test_interaction_with_next_action(self, runner):
        interaction = Interaction(
            id=11, contact_id=1, interaction_date=date(2026, 1, 15),
            method='email', direction='outbound', summary='Follow-up sent',
            outcome='interested', next_action='Call back', next_action_date=date(2026, 2, 1),
        )
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_contact.return_value = SAMPLE_CONTACT
            mock_crm.get_interactions.return_value = [interaction]
            result = runner.invoke(cli, ["contacts", "show", "1"])
        assert "Call back" in result.output

    def test_contact_with_notes(self, runner):
        contact = Contact(id=1, name='Test', status='cold', preferred_language='de', notes='Great gallery')
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_contact.return_value = contact
            mock_crm.get_interactions.return_value = []
            result = runner.invoke(cli, ["contacts", "show", "1"])
        assert "Great gallery" in result.output


# ---------------------------------------------------------------------------
# contacts edit
# ---------------------------------------------------------------------------

class TestContactsEdit:

    def test_no_options_prints_error(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            result = runner.invoke(cli, ["contacts", "edit", "1"])
        assert result.exit_code == 0
        assert "No updates specified" in result.output
        mock_crm.update_contact.assert_not_called()

    def test_updates_status(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.update_contact.return_value = True
            result = runner.invoke(cli, ["contacts", "edit", "1", "--status", "contacted"])
        assert result.exit_code == 0
        assert "Updated" in result.output
        mock_crm.update_contact.assert_called_once_with(1, {"status": "contacted"})

    def test_not_found(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.update_contact.return_value = False
            result = runner.invoke(cli, ["contacts", "edit", "1", "--status", "contacted"])
        assert "not found" in result.output

    def test_multiple_fields(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.update_contact.return_value = True
            runner.invoke(cli, [
                "contacts", "edit", "1",
                "--email", "new@test.de",
                "--website", "https://test.de",
                "--notes", "Updated notes",
            ])
        mock_crm.update_contact.assert_called_once_with(1, {
            "email": "new@test.de",
            "website": "https://test.de",
            "notes": "Updated notes",
        })


# ---------------------------------------------------------------------------
# contacts add (interactive)
# ---------------------------------------------------------------------------

class TestContactsAdd:

    def test_creates_contact(self, runner):
        # Prompts: name, type, subtype, city, country, website, email, language, notes
        inputs = "Neue Galerie\n\n\nMunchen\n\n\n\n\n\n"
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.create_contact.return_value = 42
            result = runner.invoke(cli, ["contacts", "add"], input=inputs)
        assert result.exit_code == 0
        assert "42" in result.output
        assert "Neue Galerie" in result.output

    def test_create_contact_called_with_correct_name(self, runner):
        inputs = "My Gallery\n\n\n\n\n\n\n\n\n"
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.create_contact.return_value = 1
            runner.invoke(cli, ["contacts", "add"], input=inputs)
        contact_arg = mock_crm.create_contact.call_args[0][0]
        assert contact_arg.name == "My Gallery"
        assert contact_arg.status == "cold"


# ---------------------------------------------------------------------------
# contacts log (interactive)
# ---------------------------------------------------------------------------

class TestContactsLog:

    def test_contact_not_found(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_contact.return_value = None
            result = runner.invoke(cli, ["contacts", "log", "99"])
        assert result.exit_code == 0
        assert "not found" in result.output

    def test_logs_interaction(self, runner):
        # Prompts: date (accept default), method, direction, summary, outcome, next_action (empty)
        inputs = "\n\n\nSent intro\n\n\n"
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_contact.return_value = SAMPLE_CONTACT
            mock_crm.log_interaction.return_value = 10
            result = runner.invoke(cli, ["contacts", "log", "1"], input=inputs)
        assert result.exit_code == 0
        assert "10" in result.output

    def test_interaction_with_next_action(self, runner):
        # Prompts: date, method, direction, summary, outcome, next_action, days_ahead
        inputs = "\n\n\nSent intro\n\nCall back\n30\n"
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_contact.return_value = SAMPLE_CONTACT
            mock_crm.log_interaction.return_value = 11
            result = runner.invoke(cli, ["contacts", "log", "1"], input=inputs)
        assert result.exit_code == 0
        interaction_arg = mock_crm.log_interaction.call_args[0][0]
        assert interaction_arg.next_action == "Call back"


# ---------------------------------------------------------------------------
# shows list
# ---------------------------------------------------------------------------

class TestShowsList:

    def test_empty_result(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_shows.return_value = []
            result = runner.invoke(cli, ["shows", "list"])
        assert result.exit_code == 0
        assert "No shows found" in result.output

    def test_lists_shows(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_shows.return_value = [SAMPLE_SHOW]
            result = runner.invoke(cli, ["shows", "list"])
        assert result.exit_code == 0
        assert "Fruhjahrsausstellung" in result.output

    def test_show_without_date(self, runner):
        show = Show(id=6, name='Untitled Show', status='possible')
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_shows.return_value = [show]
            result = runner.invoke(cli, ["shows", "list"])
        assert "no date" in result.output

    def test_upcoming_flag_filters_by_today(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_shows.return_value = []
            runner.invoke(cli, ["shows", "list", "--upcoming"])
        _, kwargs = mock_crm.get_shows.call_args
        assert kwargs["date_from"] == date.today()

    def test_no_upcoming_flag_passes_none(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_shows.return_value = []
            runner.invoke(cli, ["shows", "list"])
        _, kwargs = mock_crm.get_shows.call_args
        assert kwargs["date_from"] is None

    def test_status_filter_passed_through(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_shows.return_value = []
            runner.invoke(cli, ["shows", "list", "--status", "confirmed"])
        _, kwargs = mock_crm.get_shows.call_args
        assert kwargs["status"] == "confirmed"


# ---------------------------------------------------------------------------
# shows add (interactive)
# ---------------------------------------------------------------------------

class TestShowsAdd:

    def test_creates_show(self, runner):
        # Prompts: name, city, start_date, end_date, theme, status, notes
        inputs = "Fruhjahrsschau\nMunchen\n\n\n\n\n\n"
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.create_show.return_value = 5
            result = runner.invoke(cli, ["shows", "add"], input=inputs)
        assert result.exit_code == 0
        assert "5" in result.output
        assert "Fruhjahrsschau" in result.output

    def test_show_created_with_correct_name(self, runner):
        inputs = "My Show\n\n\n\n\n\n\n"
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.create_show.return_value = 1
            runner.invoke(cli, ["shows", "add"], input=inputs)
        show_arg = mock_crm.create_show.call_args[0][0]
        assert show_arg.name == "My Show"


# ---------------------------------------------------------------------------
# overdue
# ---------------------------------------------------------------------------

class TestOverdue:

    def test_no_overdue(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_overdue_contacts.return_value = []
            result = runner.invoke(cli, ["overdue"])
        assert result.exit_code == 0
        assert "all caught up" in result.output

    def test_lists_overdue_contacts(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_overdue_contacts.return_value = [SAMPLE_CONTACT]
            result = runner.invoke(cli, ["overdue"])
        assert result.exit_code == 0
        assert "Galerie Stern" in result.output
        assert "1 contacts" in result.output


# ---------------------------------------------------------------------------
# dormant
# ---------------------------------------------------------------------------

class TestDormant:

    def test_no_dormant(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_dormant_contacts.return_value = []
            result = runner.invoke(cli, ["dormant"])
        assert result.exit_code == 0
        assert "No dormant contacts" in result.output

    def test_lists_dormant_contacts(self, runner):
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_dormant_contacts.return_value = [SAMPLE_CONTACT]
            result = runner.invoke(cli, ["dormant"])
        assert result.exit_code == 0
        assert "Galerie Stern" in result.output

    def test_truncates_at_20_with_more_message(self, runner):
        contacts = [
            Contact(id=i, name=f"Gallery {i}", type='gallery', status='cold', preferred_language='de')
            for i in range(25)
        ]
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_dormant_contacts.return_value = contacts
            result = runner.invoke(cli, ["dormant"])
        assert "and 5 more" in result.output

    def test_exactly_20_no_more_message(self, runner):
        contacts = [
            Contact(id=i, name=f"Gallery {i}", type='gallery', status='cold', preferred_language='de')
            for i in range(20)
        ]
        with patch("artcrm.cli.main.crm") as mock_crm:
            mock_crm.get_dormant_contacts.return_value = contacts
            result = runner.invoke(cli, ["dormant"])
        assert "more" not in result.output


# ---------------------------------------------------------------------------
# brief
# ---------------------------------------------------------------------------

class TestBrief:

    def test_success(self, runner):
        with patch("artcrm.engine.ai_planner.generate_daily_brief") as mock_brief:
            mock_brief.return_value = "Contact Galerie Stern this week."
            result = runner.invoke(cli, ["brief"])
        assert result.exit_code == 0
        assert "Contact Galerie Stern this week." in result.output

    def test_exception_handled_gracefully(self, runner):
        with patch("artcrm.engine.ai_planner.generate_daily_brief") as mock_brief:
            mock_brief.side_effect = Exception("Ollama not running")
            result = runner.invoke(cli, ["brief"])
        assert result.exit_code == 0
        assert "Error" in result.output


# ---------------------------------------------------------------------------
# score
# ---------------------------------------------------------------------------

class TestScore:

    def test_success(self, runner):
        mock_result = {
            "fit_score": 78,
            "reasoning": "Good match for abstract work.",
            "suggested_approach": "Send email first.",
        }
        with patch("artcrm.engine.ai_planner.score_contact_fit") as mock_score:
            mock_score.return_value = mock_result
            result = runner.invoke(cli, ["score", "1"])
        assert result.exit_code == 0
        assert "78" in result.output
        assert "Good match" in result.output

    def test_passes_contact_id(self, runner):
        mock_result = {"fit_score": 50, "reasoning": "OK", "suggested_approach": "Try"}
        with patch("artcrm.engine.ai_planner.score_contact_fit") as mock_score:
            mock_score.return_value = mock_result
            runner.invoke(cli, ["score", "42"])
        mock_score.assert_called_once_with(42)

    def test_exception_handled_gracefully(self, runner):
        with patch("artcrm.engine.ai_planner.score_contact_fit") as mock_score:
            mock_score.side_effect = Exception("AI error")
            result = runner.invoke(cli, ["score", "1"])
        assert result.exit_code == 0
        assert "Error" in result.output


# ---------------------------------------------------------------------------
# suggest
# ---------------------------------------------------------------------------

class TestSuggest:

    def test_success(self, runner):
        suggestions = [{"contact": SAMPLE_CONTACT}]
        with patch("artcrm.engine.ai_planner.suggest_next_contacts") as mock_suggest:
            mock_suggest.return_value = suggestions
            result = runner.invoke(cli, ["suggest"])
        assert result.exit_code == 0
        assert "Galerie Stern" in result.output

    def test_default_limit_is_5(self, runner):
        with patch("artcrm.engine.ai_planner.suggest_next_contacts") as mock_suggest:
            mock_suggest.return_value = []
            runner.invoke(cli, ["suggest"])
        mock_suggest.assert_called_once_with(limit=5)

    def test_custom_limit(self, runner):
        with patch("artcrm.engine.ai_planner.suggest_next_contacts") as mock_suggest:
            mock_suggest.return_value = []
            runner.invoke(cli, ["suggest", "--limit", "10"])
        mock_suggest.assert_called_once_with(limit=10)

    def test_exception_handled_gracefully(self, runner):
        with patch("artcrm.engine.ai_planner.suggest_next_contacts") as mock_suggest:
            mock_suggest.side_effect = Exception("AI unavailable")
            result = runner.invoke(cli, ["suggest"])
        assert result.exit_code == 0
        assert "Error" in result.output


# ---------------------------------------------------------------------------
# draft
# ---------------------------------------------------------------------------

class TestDraft:

    DRAFT_RESULT = {
        "contact_name": "Galerie Stern",
        "language": "de",
        "subject": "Vorstellung als Kuenstler",
        "body": "Sehr geehrte Damen und Herren...",
        "draft_path": "/tmp/draft_001.txt",
    }

    def test_success(self, runner):
        with patch("artcrm.engine.email_composer.draft_first_contact_letter") as mock_draft:
            mock_draft.return_value = self.DRAFT_RESULT
            result = runner.invoke(cli, ["draft", "1"])
        assert result.exit_code == 0
        assert "Galerie Stern" in result.output
        assert "Vorstellung" in result.output

    def test_passes_contact_id_and_options(self, runner):
        with patch("artcrm.engine.email_composer.draft_first_contact_letter") as mock_draft:
            mock_draft.return_value = self.DRAFT_RESULT
            runner.invoke(cli, ["draft", "42", "--language", "en", "--no-portfolio"])
        mock_draft.assert_called_once_with(
            contact_id=42, language="en", include_portfolio_link=False
        )

    def test_value_error_handled(self, runner):
        with patch("artcrm.engine.email_composer.draft_first_contact_letter") as mock_draft:
            mock_draft.side_effect = ValueError("Contact not found")
            result = runner.invoke(cli, ["draft", "1"])
        assert result.exit_code == 0
        assert "Error" in result.output

    def test_runtime_error_handled(self, runner):
        with patch("artcrm.engine.email_composer.draft_first_contact_letter") as mock_draft:
            mock_draft.side_effect = RuntimeError("API key missing")
            result = runner.invoke(cli, ["draft", "1"])
        assert result.exit_code == 0
        assert "API Error" in result.output
        assert "ANTHROPIC_API_KEY" in result.output


# ---------------------------------------------------------------------------
# followup
# ---------------------------------------------------------------------------

class TestFollowup:

    FOLLOWUP_RESULT = {
        "contact_name": "Galerie Stern",
        "language": "de",
        "subject": "Nachfrage",
        "body": "Guten Tag, ich wollte nachfragen...",
        "draft_path": "/tmp/followup_001.txt",
    }

    def test_success(self, runner):
        with patch("artcrm.engine.email_composer.draft_follow_up_letter") as mock_followup:
            mock_followup.return_value = self.FOLLOWUP_RESULT
            result = runner.invoke(cli, ["followup", "1"], input="Hatte gutes Gesprach\n")
        assert result.exit_code == 0
        assert "Galerie Stern" in result.output
        assert "Nachfrage" in result.output

    def test_passes_summary_to_composer(self, runner):
        with patch("artcrm.engine.email_composer.draft_follow_up_letter") as mock_followup:
            mock_followup.return_value = self.FOLLOWUP_RESULT
            runner.invoke(cli, ["followup", "1"], input="My summary\n")
        _, kwargs = mock_followup.call_args
        assert kwargs["previous_interaction_summary"] == "My summary"

    def test_value_error_handled(self, runner):
        with patch("artcrm.engine.email_composer.draft_follow_up_letter") as mock_followup:
            mock_followup.side_effect = ValueError("No interactions found")
            result = runner.invoke(cli, ["followup", "1"], input="summary\n")
        assert result.exit_code == 0
        assert "Error" in result.output

    def test_runtime_error_handled(self, runner):
        with patch("artcrm.engine.email_composer.draft_follow_up_letter") as mock_followup:
            mock_followup.side_effect = RuntimeError("API error")
            result = runner.invoke(cli, ["followup", "1"], input="summary\n")
        assert result.exit_code == 0
        assert "API Error" in result.output


# ---------------------------------------------------------------------------
# recon
# ---------------------------------------------------------------------------

class TestRecon:

    SCOUT_STATS = {
        "city": "Munchen",
        "country": "DE",
        "sources_used": ["OpenStreetMap"],
        "by_type": {"gallery": 3, "cafe": 5, "coworking": 2},
        "total_found": 10,
        "total_inserted": 8,
        "total_skipped": 2,
    }

    def test_success(self, runner):
        with patch("artcrm.engine.lead_scout.scout_city") as mock_scout:
            mock_scout.return_value = self.SCOUT_STATS
            result = runner.invoke(cli, ["recon", "Munchen"])
        assert result.exit_code == 0
        assert "Mission complete" in result.output
        assert "Munchen" in result.output

    def test_displays_stats(self, runner):
        with patch("artcrm.engine.lead_scout.scout_city") as mock_scout:
            mock_scout.return_value = self.SCOUT_STATS
            result = runner.invoke(cli, ["recon", "Munchen"])
        assert "10" in result.output  # total_found
        assert "8" in result.output   # total_inserted
        assert "2" in result.output   # total_skipped

    def test_default_types_passed(self, runner):
        with patch("artcrm.engine.lead_scout.scout_city") as mock_scout:
            mock_scout.return_value = self.SCOUT_STATS
            runner.invoke(cli, ["recon", "Munchen"])
        _, kwargs = mock_scout.call_args
        assert set(kwargs["business_types"]) == {"gallery", "cafe", "coworking"}

    def test_custom_type_passed(self, runner):
        with patch("artcrm.engine.lead_scout.scout_city") as mock_scout:
            mock_scout.return_value = self.SCOUT_STATS
            runner.invoke(cli, ["recon", "Munchen", "--type", "gallery"])
        _, kwargs = mock_scout.call_args
        assert kwargs["business_types"] == ["gallery"]

    def test_unknown_type_prints_warning(self, runner):
        with patch("artcrm.engine.lead_scout.scout_city") as mock_scout:
            mock_scout.return_value = self.SCOUT_STATS
            result = runner.invoke(cli, ["recon", "Munchen", "--type", "museum"])
        assert "Warning" in result.output or "Unknown type" in result.output

    def test_all_sources_disabled_exits_early(self, runner):
        with patch("artcrm.engine.lead_scout.scout_city") as mock_scout:
            result = runner.invoke(cli, ["recon", "Munchen", "--no-google", "--no-osm"])
        assert result.exit_code == 0
        assert "All data sources disabled" in result.output
        mock_scout.assert_not_called()

    def test_radius_passed_through(self, runner):
        with patch("artcrm.engine.lead_scout.scout_city") as mock_scout:
            mock_scout.return_value = self.SCOUT_STATS
            runner.invoke(cli, ["recon", "Munchen", "--radius", "5"])
        _, kwargs = mock_scout.call_args
        assert kwargs["radius_km"] == 5.0

    def test_country_argument(self, runner):
        with patch("artcrm.engine.lead_scout.scout_city") as mock_scout:
            mock_scout.return_value = self.SCOUT_STATS
            runner.invoke(cli, ["recon", "Wien", "AT"])
        _, kwargs = mock_scout.call_args
        assert kwargs["country"] == "AT"


# ---------------------------------------------------------------------------
# _prompt_date helper
# ---------------------------------------------------------------------------

class TestPromptDate:

    def test_valid_date_returned(self):
        with patch("artcrm.cli.main.click.prompt", return_value="2026-03-15"), \
             patch("artcrm.cli.main.click.echo"):
            result = _prompt_date("Date")
        assert result == date(2026, 3, 15)

    def test_empty_input_returns_none(self):
        with patch("artcrm.cli.main.click.prompt", return_value=""), \
             patch("artcrm.cli.main.click.echo"):
            result = _prompt_date("Date")
        assert result is None

    def test_invalid_then_valid_retries(self):
        with patch("artcrm.cli.main.click.prompt", side_effect=["not-a-date", "2026-06-01"]), \
             patch("artcrm.cli.main.click.echo"):
            result = _prompt_date("Date")
        assert result == date(2026, 6, 1)

    def test_default_shown_when_provided(self):
        default = date(2026, 1, 1)
        with patch("artcrm.cli.main.click.prompt", return_value=str(default)) as mock_prompt, \
             patch("artcrm.cli.main.click.echo"):
            _prompt_date("Date", default=default)
        _, kwargs = mock_prompt.call_args
        assert kwargs.get("default") == "2026-01-01"


# ---------------------------------------------------------------------------
# _prompt_email helper
# ---------------------------------------------------------------------------

class TestPromptEmail:

    def test_valid_email_returned(self):
        with patch("artcrm.cli.main.click.prompt", return_value="test@example.com"), \
             patch("artcrm.cli.main.click.echo"):
            result = _prompt_email()
        assert result == "test@example.com"

    def test_empty_input_returns_none(self):
        with patch("artcrm.cli.main.click.prompt", return_value=""), \
             patch("artcrm.cli.main.click.echo"):
            result = _prompt_email()
        assert result is None

    def test_invalid_then_valid_retries(self):
        with patch("artcrm.cli.main.click.prompt", side_effect=["not-an-email", "valid@example.com"]), \
             patch("artcrm.cli.main.click.echo"):
            result = _prompt_email()
        assert result == "valid@example.com"

    def test_various_valid_formats(self):
        valid_emails = [
            "user@domain.com",
            "user.name+tag@sub.domain.org",
            "a@b.de",
        ]
        for email in valid_emails:
            with patch("artcrm.cli.main.click.prompt", return_value=email), \
                 patch("artcrm.cli.main.click.echo"):
                result = _prompt_email()
            assert result == email

    def test_invalid_formats_rejected(self):
        invalid_inputs = ["not-an-email", "missing@tld", "@nodomain.com"]
        for bad in invalid_inputs:
            with patch("artcrm.cli.main.click.prompt", side_effect=[bad, "good@example.com"]), \
                 patch("artcrm.cli.main.click.echo") as mock_echo:
                _prompt_email()
            mock_echo.assert_called()  # error message was shown
