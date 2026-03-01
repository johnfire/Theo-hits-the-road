"""
Event Bus - Decoupled Module Communication
Modules emit events, other modules listen. No direct imports between modules.
"""

from typing import Callable, Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class EventBus:
    """
    Simple event bus for decoupled module communication.
    Modules emit events, other modules register handlers to listen.
    """

    def __init__(self):
        self._handlers: Dict[str, List[Callable]] = {}

    def on(self, event_name: str, handler: Callable):
        """
        Register a handler for an event.

        Args:
            event_name: Name of the event to listen for
            handler: Callable that receives event_data dict
        """
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        self._handlers[event_name].append(handler)
        logger.debug(f"Registered handler for event '{event_name}': {handler.__name__}")

    def emit(self, event_name: str, event_data: Dict[str, Any] = None):
        """
        Emit an event to all registered handlers.

        Args:
            event_name: Name of the event
            event_data: Optional dict of data to pass to handlers
        """
        if event_data is None:
            event_data = {}

        logger.debug(f"Emitting event '{event_name}' with data: {event_data}")

        if event_name in self._handlers:
            for handler in self._handlers[event_name]:
                try:
                    handler(event_data)
                except Exception as e:
                    logger.error(f"Error in handler {handler.__name__} for event '{event_name}': {e}")

    def clear(self):
        """Clear all handlers (useful for testing)."""
        self._handlers.clear()


# Singleton instance
bus = EventBus()


# =============================================================================
# STANDARD EVENTS
# =============================================================================

# CRM Engine Events
EVENT_CONTACT_CREATED = 'contact_created'
EVENT_CONTACT_UPDATED = 'contact_updated'
EVENT_CONTACT_DELETED = 'contact_deleted'
EVENT_INTERACTION_LOGGED = 'interaction_logged'
EVENT_SHOW_CREATED = 'show_created'
EVENT_SHOW_UPDATED = 'show_updated'

# AI Planner Events (Phase 5+)
EVENT_ANALYSIS_REQUESTED = 'analysis_requested'
EVENT_ANALYSIS_COMPLETE = 'analysis_complete'
EVENT_SUGGESTION_READY = 'suggestion_ready'

# Email Composer Events (Phase 7+)
EVENT_DRAFT_REQUESTED = 'draft_requested'
EVENT_DRAFT_READY = 'draft_ready'
EVENT_EMAIL_SENT = 'email_sent'

# Lead Scout Events (Phase 6-Alpha)
EVENT_SCOUT_STARTED = 'scout_started'
EVENT_SCOUT_COMPLETE = 'scout_complete'
EVENT_LEAD_DISCOVERED = 'lead_discovered'
