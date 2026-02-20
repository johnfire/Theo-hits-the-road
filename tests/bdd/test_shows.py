from datetime import date
from pytest_bdd import scenarios, given, when
from artcrm.cli.main import cli
from artcrm.models import Show

scenarios("features/shows.feature")

_SHOW = Show(
    id=5, name="Frühjahrsausstellung", city="München",
    date_start=date(2026, 4, 1), date_end=date(2026, 4, 30), status="confirmed",
)


@given("there are no shows scheduled")
def no_shows(mock_crm):
    mock_crm.get_shows.return_value = []


@given("a confirmed show exists in München")
def confirmed_show(mock_crm):
    mock_crm.get_shows.return_value = [_SHOW]


@when("the artist lists shows")
def list_shows(runner, context):
    context["result"] = runner.invoke(cli, ["shows", "list"])


@when("the artist lists upcoming shows")
def list_upcoming_shows(runner, context):
    context["result"] = runner.invoke(cli, ["shows", "list", "--upcoming"])
