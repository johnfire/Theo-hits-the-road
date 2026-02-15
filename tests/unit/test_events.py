"""
Unit tests for the EventBus (artcrm/bus/events.py).
No mocking required — pure Python.
"""

import pytest
from artcrm.bus.events import (
    EventBus,
    EVENT_CONTACT_CREATED, EVENT_CONTACT_UPDATED, EVENT_CONTACT_DELETED,
    EVENT_INTERACTION_LOGGED, EVENT_SHOW_CREATED, EVENT_SHOW_UPDATED,
    EVENT_ANALYSIS_REQUESTED, EVENT_ANALYSIS_COMPLETE, EVENT_SUGGESTION_READY,
    EVENT_DRAFT_REQUESTED, EVENT_DRAFT_READY, EVENT_EMAIL_SENT,
    EVENT_SCOUT_STARTED, EVENT_SCOUT_COMPLETE, EVENT_LEAD_DISCOVERED,
)


@pytest.fixture
def bus():
    """Fresh EventBus for each test — never share state between tests."""
    return EventBus()


# ---------------------------------------------------------------------------
# Basic emit / subscribe
# ---------------------------------------------------------------------------

def test_handler_called_on_emit(bus):
    received = []
    bus.on('test_event', lambda data: received.append(data))
    bus.emit('test_event', {'key': 'value'})
    assert received == [{'key': 'value'}]


def test_multiple_handlers_all_called(bus):
    calls = []
    bus.on('evt', lambda d: calls.append('a'))
    bus.on('evt', lambda d: calls.append('b'))
    bus.emit('evt', {})
    assert calls == ['a', 'b']


def test_emit_no_handlers_is_silent(bus):
    # Should not raise even with no registered handlers.
    bus.emit('unknown_event', {'x': 1})


def test_emit_default_data_is_empty_dict(bus):
    received = []
    bus.on('evt', lambda data: received.append(data))
    bus.emit('evt')  # no data argument
    assert received == [{}]


def test_handler_receives_correct_data(bus):
    received = []
    bus.on('evt', lambda d: received.append(d))
    bus.emit('evt', {'contact_id': 42, 'name': 'Galerie Test'})
    assert received[0]['contact_id'] == 42
    assert received[0]['name'] == 'Galerie Test'


# ---------------------------------------------------------------------------
# Error isolation
# ---------------------------------------------------------------------------

def test_handler_exception_does_not_propagate(bus):
    """A bad handler must not crash the bus or prevent other handlers from running."""
    good_calls = []

    def bad_handler(data):
        raise RuntimeError("handler exploded")

    bus.on('evt', bad_handler)
    bus.on('evt', lambda d: good_calls.append(True))

    bus.emit('evt', {})  # should not raise
    assert good_calls == [True]


# ---------------------------------------------------------------------------
# clear()
# ---------------------------------------------------------------------------

def test_clear_removes_all_handlers(bus):
    calls = []
    bus.on('evt', lambda d: calls.append(1))
    bus.clear()
    bus.emit('evt', {})
    assert calls == []


def test_clear_allows_reregistration(bus):
    calls = []
    bus.on('evt', lambda d: calls.append('first'))
    bus.clear()
    bus.on('evt', lambda d: calls.append('second'))
    bus.emit('evt', {})
    assert calls == ['second']


# ---------------------------------------------------------------------------
# Multiple distinct events don't cross-fire
# ---------------------------------------------------------------------------

def test_events_are_isolated(bus):
    a_calls = []
    b_calls = []
    bus.on('event_a', lambda d: a_calls.append(True))
    bus.on('event_b', lambda d: b_calls.append(True))

    bus.emit('event_a', {})
    assert a_calls == [True]
    assert b_calls == []


# ---------------------------------------------------------------------------
# Event name constants are all strings (smoke test)
# ---------------------------------------------------------------------------

def test_event_constants_are_strings():
    constants = [
        EVENT_CONTACT_CREATED, EVENT_CONTACT_UPDATED, EVENT_CONTACT_DELETED,
        EVENT_INTERACTION_LOGGED, EVENT_SHOW_CREATED, EVENT_SHOW_UPDATED,
        EVENT_ANALYSIS_REQUESTED, EVENT_ANALYSIS_COMPLETE, EVENT_SUGGESTION_READY,
        EVENT_DRAFT_REQUESTED, EVENT_DRAFT_READY, EVENT_EMAIL_SENT,
        EVENT_SCOUT_STARTED, EVENT_SCOUT_COMPLETE, EVENT_LEAD_DISCOVERED,
    ]
    for c in constants:
        assert isinstance(c, str) and len(c) > 0


def test_event_constants_are_unique():
    constants = [
        EVENT_CONTACT_CREATED, EVENT_CONTACT_UPDATED, EVENT_CONTACT_DELETED,
        EVENT_INTERACTION_LOGGED, EVENT_SHOW_CREATED, EVENT_SHOW_UPDATED,
        EVENT_ANALYSIS_REQUESTED, EVENT_ANALYSIS_COMPLETE, EVENT_SUGGESTION_READY,
        EVENT_DRAFT_REQUESTED, EVENT_DRAFT_READY, EVENT_EMAIL_SENT,
        EVENT_SCOUT_STARTED, EVENT_SCOUT_COMPLETE, EVENT_LEAD_DISCOVERED,
    ]
    assert len(constants) == len(set(constants))
