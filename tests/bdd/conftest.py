"""
Shared fixtures and step definitions for BDD tests.

- runner, mock_crm, context: available to all scenario files in this directory
- no_logging: autouse, prevents log file creation during tests
- 'the output contains' step: shared across all feature files
"""

import pytest
from unittest.mock import patch
from click.testing import CliRunner
from pytest_bdd import then, parsers


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_crm():
    with patch("artcrm.cli.main.crm") as mock:
        yield mock


@pytest.fixture
def context():
    """Mutable dict shared between Given/When/Then steps within a scenario."""
    return {}


@pytest.fixture(autouse=True)
def no_logging():
    with patch("artcrm.cli.main.configure_logging"):
        yield


@then(parsers.parse('the output contains "{text}"'))
def output_contains(context, text):
    assert text in context["result"].output, (
        f"Expected {text!r} in output:\n{context['result'].output}"
    )
