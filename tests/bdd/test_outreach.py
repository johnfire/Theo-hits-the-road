from unittest.mock import patch
from pytest_bdd import scenarios, given, when
from artcrm.cli.main import cli
from artcrm.models import Contact

scenarios("features/outreach.feature")

_CONTACT = Contact(
    id=1, name="Galerie Stern", type="gallery",
    city="Augsburg", preferred_language="de", status="cold",
)


@given("there are no overdue contacts")
def no_overdue(mock_crm):
    mock_crm.get_overdue_contacts.return_value = []


@given("a gallery contact has an overdue follow-up")
def contact_overdue(mock_crm):
    mock_crm.get_overdue_contacts.return_value = [_CONTACT]


@given("there are no dormant contacts")
def no_dormant(mock_crm):
    mock_crm.get_dormant_contacts.return_value = []


@given("the AI returns a brief recommendation")
def ai_brief_given(context):
    # Patch is applied in the when step so the CLI import path is correct
    context["brief_text"] = "Contact Galerie Stern this week."


@when("the artist checks overdue contacts")
def check_overdue(runner, context):
    context["result"] = runner.invoke(cli, ["overdue"])


@when("the artist checks dormant contacts")
def check_dormant(runner, context):
    context["result"] = runner.invoke(cli, ["dormant"])


@when("the artist requests the daily brief")
def request_brief(runner, context):
    brief_text = context.get("brief_text", "Contact Galerie Stern this week.")
    with patch("artcrm.engine.ai_planner.generate_daily_brief") as mock_brief:
        mock_brief.return_value = brief_text
        context["result"] = runner.invoke(cli, ["brief"])
