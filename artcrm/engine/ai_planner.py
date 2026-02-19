"""
AI Planner - Routine AI tasks (scoring, briefs, suggestions).
Uses DeepSeek or Claude via the unified ai_client module.
Stores all reasoning in ai_analysis table for transparency.
"""

import logging
from datetime import date, timedelta
from typing import List, Dict, Any, Optional

from artcrm.db.connection import get_db_cursor
from artcrm.logging_config import log_call
from artcrm.engine import crm
from artcrm.engine.ai_client import call_ai
from artcrm.models import Contact, Show
from artcrm.bus.events import bus, EVENT_ANALYSIS_COMPLETE, EVENT_SUGGESTION_READY
from artcrm.config import config

logger = logging.getLogger(__name__)


# =============================================================================
# CONTEXT BUILDER
# =============================================================================

def build_context_for_contact(contact_id: int) -> str:
    """
    Build rich context for AI about a specific contact.
    Includes: contact details, interaction history, previous analyses, upcoming shows.
    """
    # Get contact
    contact = crm.get_contact(contact_id)
    if not contact:
        logger.warning(f"build_context_for_contact: contact_id={contact_id} not found, returning empty context")
        return ""

    # Get interactions
    interactions = crm.get_interactions(contact_id)

    # Get upcoming shows
    upcoming_shows = crm.get_shows(
        status='confirmed',
        date_from=date.today(),
        date_to=date.today() + timedelta(days=90)
    )

    # Build context
    context_parts = []

    # Contact info
    context_parts.append(f"CONTACT: {contact.name}")
    context_parts.append(f"Type: {contact.type or 'unknown'}")
    context_parts.append(f"Subtype: {contact.subtype or 'N/A'}")
    context_parts.append(f"City: {contact.city or 'unknown'}")
    context_parts.append(f"Website: {contact.website or 'N/A'}")
    context_parts.append(f"Current Status: {contact.status}")
    if contact.notes:
        context_parts.append(f"Notes: {contact.notes}")

    # Interaction history
    if interactions:
        context_parts.append("\nINTERACTION HISTORY:")
        for i in interactions[:5]:  # Last 5 interactions
            context_parts.append(f"- {i.interaction_date}: {i.method} ({i.direction})")
            if i.summary:
                context_parts.append(f"  Summary: {i.summary[:100]}")
            context_parts.append(f"  Outcome: {i.outcome}")
    else:
        context_parts.append("\nNo previous interactions.")

    # Upcoming shows
    if upcoming_shows:
        context_parts.append("\nUPCOMING SHOWS (next 90 days):")
        for show in upcoming_shows[:3]:
            context_parts.append(f"- {show.name}: {show.date_start}")

    return "\n".join(context_parts)


def build_artist_context() -> str:
    """
    Build context about the artist (you).
    TODO: Read from data/artist_bio.txt when available.
    """
    # Placeholder - will be replaced with actual bio
    return """
ARTIST PROFILE:
Name: Christopher Rehm
Location: Klosterlechfeld, Bavaria, Germany
Mediums: Watercolor, oil, acrylic
Styles: Landscape, cityscape, fantasy, surreal, botanical, Japanese woodblock print influence
Career Stage: Working professional artist
Target Venues: Galleries, cafes, hotels, offices, coworking spaces in Bavaria and beyond
Preferred Approach: Personal visits for local venues, email for distant/online platforms
"""


# =============================================================================
# AI ANALYSIS FUNCTIONS
# =============================================================================

@log_call
def generate_daily_brief(model: Optional[str] = None) -> str:
    """
    Generate AI daily brief: who to contact this week and why.
    Returns formatted brief as text.
    """
    _model = model or config.DEFAULT_AI_MODEL
    logger.info(f"Generating daily brief with {_model}")

    # Get overdue contacts
    overdue = crm.get_overdue_contacts()

    # Get dormant contacts (sample)
    dormant = crm.get_dormant_contacts()[:10]

    # Get upcoming shows
    upcoming_shows = crm.get_shows(
        date_from=date.today(),
        date_to=date.today() + timedelta(days=90)
    )

    # Build prompt
    prompt = f"""You are an AI assistant helping an artist manage gallery relationships.

{build_artist_context()}

CURRENT SITUATION:
- {len(overdue)} contacts have overdue follow-ups
- {len(dormant)} contacts have been dormant (no activity 12+ months)
- {len(upcoming_shows)} upcoming shows in next 90 days

OVERDUE CONTACTS:
{chr(10).join([f"- {c.name} ({c.city}): {c.type}" for c in overdue[:5]])}

DORMANT CONTACTS (sample):
{chr(10).join([f"- {c.name} ({c.city}): {c.type}" for c in dormant[:5]])}

UPCOMING SHOWS:
{chr(10).join([f"- {s.name} on {s.date_start}" for s in upcoming_shows[:3]])}

Based on this information, provide a brief (200 words) daily plan:
1. Who should be contacted this week (prioritize overdue, then dormant near upcoming shows)
2. Why contact them (upcoming show nearby, follow-up needed, etc.)
3. Suggested approach (email, in-person visit, etc.)

Be specific and actionable. Focus on 3-5 specific contacts."""

    response = call_ai(prompt, model=_model)

    return response


@log_call
def score_contact_fit(contact_id: int, model: Optional[str] = None) -> Dict[str, Any]:
    """
    Score how well a contact fits the artist's work (0-100).
    Stores analysis in ai_analysis table.
    Returns: dict with fit_score, reasoning, suggested_approach
    """
    _model = model or config.DEFAULT_AI_MODEL
    logger.info(f"Scoring fit for contact #{contact_id} with {_model}")

    contact = crm.get_contact(contact_id)
    if not contact:
        raise ValueError(f"Contact {contact_id} not found")

    context = build_context_for_contact(contact_id)

    prompt = f"""You are an AI assistant helping an artist evaluate venue fit.

{build_artist_context()}

{context}

TASK: Evaluate how well this venue fits the artist's work.

Consider:
1. Venue type match (galleries vs cafes vs corporate)
2. Style alignment (based on website/notes if available)
3. Location (Bavaria-based artist, local presence matters)
4. Previous interaction outcomes

Provide:
1. Fit Score (0-100, where 100 = perfect match)
2. Reasoning (2-3 sentences explaining the score)
3. Suggested Approach (how to reach out: email/in-person/letter, and key talking points)

Format as:
SCORE: [0-100]
REASONING: [your reasoning]
APPROACH: [suggested approach]"""

    response = call_ai(prompt, model=_model)

    # Parse response (simple parsing)
    lines = response.split('\n')
    fit_score = 50  # default
    reasoning = ""
    suggested_approach = ""

    for line in lines:
        if line.startswith('SCORE:'):
            try:
                import re as _re
                _m = _re.search(r'-?\d+', line.split(':', 1)[1])
                fit_score = int(_m.group()) if _m else fit_score
                fit_score = max(0, min(100, fit_score))  # Clamp to 0-100
            except Exception as e:
                logger.warning(f"score_contact_fit: could not parse SCORE line {line!r}: {e}")
        elif line.startswith('REASONING:'):
            reasoning = line.split(':', 1)[1].strip()
        elif line.startswith('APPROACH:'):
            suggested_approach = line.split(':', 1)[1].strip()

    # If parsing failed, use raw response
    if not reasoning:
        reasoning = response[:500]

    # Store in database
    with get_db_cursor() as cur:
        cur.execute("""
            INSERT INTO ai_analysis (
                contact_id, analysis_date, model_used, fit_reasoning,
                suggested_approach, priority_score, raw_response, created_at
            ) VALUES (
                %s, NOW(), %s, %s, %s, %s, %s, NOW()
            )
        """, (contact_id, _model, reasoning, suggested_approach, fit_score, response))

    # Update contact fit_score
    crm.update_contact(contact_id, {'fit_score': fit_score})

    # Emit event
    bus.emit(EVENT_ANALYSIS_COMPLETE, {
        'contact_id': contact_id,
        'fit_score': fit_score,
        'reasoning': reasoning
    })

    logger.info(f"Contact #{contact_id} fit score: {fit_score}/100")

    return {
        'fit_score': fit_score,
        'reasoning': reasoning,
        'suggested_approach': suggested_approach,
        'raw_response': response
    }


@log_call
def suggest_next_contacts(limit: int = 5, model: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    AI suggests which contacts to reach out to next.
    Returns list of contacts with reasoning.
    """
    _model = model or config.DEFAULT_AI_MODEL
    logger.info(f"Getting AI suggestions for next {limit} contacts using {_model}")

    # Get candidates: overdue + dormant with fit_score
    overdue = crm.get_overdue_contacts()[:10]

    with get_db_cursor() as cur:
        cur.execute("""
            SELECT * FROM contacts
            WHERE deleted_at IS NULL
              AND fit_score IS NOT NULL
              AND status IN ('cold', 'contacted', 'meeting')
            ORDER BY fit_score DESC
            LIMIT 20
        """)
        high_fit = [Contact(**row) for row in cur.fetchall()]

    # Deduplicate by ID (can't use set() on dataclasses)
    seen_ids = set()
    candidates = []
    for c in (overdue + high_fit):
        if c.id not in seen_ids:
            seen_ids.add(c.id)
            candidates.append(c)
    candidates = candidates[:15]

    # Build prompt
    candidates_text = "\n".join([
        f"{i+1}. {c.name} ({c.city}): {c.type}, Status: {c.status}, Fit: {c.fit_score or 'N/A'}/100"
        for i, c in enumerate(candidates)
    ])

    upcoming_shows = crm.get_shows(
        date_from=date.today(),
        date_to=date.today() + timedelta(days=90)
    )

    prompt = f"""You are an AI assistant helping prioritize gallery outreach.

{build_artist_context()}

UPCOMING SHOWS: {len(upcoming_shows)} in next 90 days

CANDIDATE CONTACTS:
{candidates_text}

Select the top {limit} contacts to reach out to this week. For each, explain:
1. Why contact them now (timing, fit, opportunity)
2. What to say (key message)

Format as numbered list."""

    response = call_ai(prompt, model=_model)

    # Emit event
    bus.emit(EVENT_SUGGESTION_READY, {
        'suggestions': response,
        'candidate_count': len(candidates)
    })

    return [
        {
            'contact': c,
            'reasoning': 'See AI brief for details'
        }
        for c in candidates[:limit]
    ]


# =============================================================================
# BATCH OPERATIONS
# =============================================================================

@log_call
def analyze_all_unscored_contacts(limit: int = 10, model: Optional[str] = None) -> int:
    """
    Score all contacts that don't have a fit_score yet.
    Returns: number of contacts analyzed
    """
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT id FROM contacts
            WHERE deleted_at IS NULL
              AND fit_score IS NULL
              AND type IS NOT NULL
            LIMIT %s
        """, (limit,))

        contact_ids = [row['id'] for row in cur.fetchall()]

    logger.info(f"Analyzing {len(contact_ids)} unscored contacts")

    for contact_id in contact_ids:
        try:
            score_contact_fit(contact_id, model=model)
        except Exception as e:
            logger.error(f"Failed to score contact {contact_id}: {e}")

    return len(contact_ids)
