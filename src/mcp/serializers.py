"""
Serializers for MCP tool responses.
Convert dataclasses to JSON-safe dicts with proper date handling.
"""

import json
from dataclasses import asdict
from datetime import date, datetime
from typing import List, Callable


def _clean_dict(d: dict) -> dict:
    """Convert dates to ISO strings and drop None values."""
    result = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, datetime):
            result[k] = v.isoformat()
        elif isinstance(v, date):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


def serialize_contact(contact) -> dict:
    return _clean_dict(asdict(contact))


def serialize_interaction(interaction) -> dict:
    return _clean_dict(asdict(interaction))


def serialize_show(show) -> dict:
    return _clean_dict(asdict(show))


def serialize_list(items: List, serializer: Callable) -> str:
    return json.dumps([serializer(item) for item in items], indent=2)
