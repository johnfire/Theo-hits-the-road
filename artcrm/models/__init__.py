"""
Data Models
Dataclasses for all entities. These are pure Python objects, no database logic.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class Contact:
    """Contact entity (gallery, cafe, hotel, office, online platform, etc.)"""
    id: Optional[int] = None
    name: str = ''
    type: Optional[str] = None
    subtype: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    preferred_language: str = 'de'
    status: str = 'cold'
    fit_score: Optional[int] = None
    success_probability: Optional[int] = None
    best_visit_time: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


@dataclass
class Interaction:
    """Interaction history record"""
    id: Optional[int] = None
    contact_id: int = 0
    interaction_date: Optional[date] = None
    method: Optional[str] = None
    direction: str = 'outbound'
    summary: Optional[str] = None
    outcome: Optional[str] = None
    next_action: Optional[str] = None
    next_action_date: Optional[date] = None
    ai_draft_used: bool = False
    created_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None


@dataclass
class Show:
    """Exhibition/show entity"""
    id: Optional[int] = None
    name: Optional[str] = None
    venue_contact_id: Optional[int] = None
    city: Optional[str] = None
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    theme: Optional[str] = None
    status: str = 'possible'
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
