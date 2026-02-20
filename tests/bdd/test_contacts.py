from pytest_bdd import scenarios, given, when, parsers
from artcrm.cli.main import cli
from artcrm.models import Contact

scenarios("features/contacts.feature")

_CONTACT = Contact(
    id=1, name="Galerie Stern", type="gallery", subtype="contemporary",
    city="Augsburg", country="DE", email="info@galerie-stern.de",
    preferred_language="de", status="cold",
)


@given("there are no contacts in the system")
def no_contacts(mock_crm):
    mock_crm.search_contacts.return_value = []
    mock_crm.get_contact.return_value = None


@given("a gallery contact exists")
def gallery_contact_exists(mock_crm):
    mock_crm.search_contacts.return_value = [_CONTACT]
    mock_crm.get_contact.return_value = _CONTACT
    mock_crm.get_interactions.return_value = []


@when("the artist lists contacts")
def list_contacts(runner, context):
    context["result"] = runner.invoke(cli, ["contacts", "list"])


@when(parsers.parse("the artist views contact {contact_id:d}"))
def view_contact(runner, context, contact_id):
    context["result"] = runner.invoke(cli, ["contacts", "show", str(contact_id)])
