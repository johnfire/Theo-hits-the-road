"""
Art CRM MCP Server
Exposes CRM engine functions as MCP tools for Claude Desktop, Claude Code, and other MCP clients.
"""

import json
import logging
from datetime import date

from mcp.server.fastmcp import FastMCP

from src.logging_config import configure_logging
from src.engine import crm
from src.engine import ai_planner
from src.engine import email_composer
from src.engine import lead_scout
from src.models import Contact, Interaction, Show
from src.mcp.serializers import (
    serialize_contact, serialize_interaction, serialize_show, serialize_list,
)

configure_logging()
logger = logging.getLogger(__name__)

server = FastMCP("art-crm", "1.0.0")


# =============================================================================
# CONTACT TOOLS
# =============================================================================

@server.tool()
def contact_create(
    name: str,
    type: str = "",
    subtype: str = "",
    city: str = "",
    country: str = "",
    address: str = "",
    website: str = "",
    email: str = "",
    phone: str = "",
    preferred_language: str = "de",
    status: str = "cold",
    notes: str = "",
) -> str:
    """Create a new contact in the CRM. Returns the new contact ID."""
    try:
        contact = Contact(
            name=name,
            type=type or None,
            subtype=subtype or None,
            city=city or None,
            country=country or None,
            address=address or None,
            website=website or None,
            email=email or None,
            phone=phone or None,
            preferred_language=preferred_language,
            status=status,
            notes=notes or None,
        )
        contact_id = crm.create_contact(contact)
        return json.dumps({"contact_id": contact_id, "name": name})
    except Exception as e:
        logger.error(f"contact_create failed: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
def contact_get(contact_id: int) -> str:
    """Get full details for a contact by ID, including all fields."""
    try:
        contact = crm.get_contact(contact_id)
        if not contact:
            return json.dumps({"error": f"Contact {contact_id} not found"})
        return json.dumps(serialize_contact(contact))
    except Exception as e:
        logger.error(f"contact_get failed: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
def contact_update(contact_id: int, updates: str) -> str:
    """Update one or more fields on a contact. Pass updates as a JSON object, e.g. '{"status": "contacted", "notes": "Called today"}'."""
    try:
        updates_dict = json.loads(updates)
        success = crm.update_contact(contact_id, updates_dict)
        if success:
            return json.dumps({"updated": True, "contact_id": contact_id})
        return json.dumps({"error": f"Contact {contact_id} not found"})
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON in updates: {e}"})
    except Exception as e:
        logger.error(f"contact_update failed: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
def contact_delete(contact_id: int, soft: bool = True) -> str:
    """Delete a contact. Soft-delete by default (recoverable)."""
    try:
        success = crm.delete_contact(contact_id, soft=soft)
        if success:
            return json.dumps({"deleted": True, "contact_id": contact_id, "soft": soft})
        return json.dumps({"error": f"Contact {contact_id} not found"})
    except Exception as e:
        logger.error(f"contact_delete failed: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
def contact_search(
    name: str = "",
    city: str = "",
    type: str = "",
    status: str = "",
    limit: int = 100,
) -> str:
    """Search contacts with optional filters. Returns list of matching contacts."""
    try:
        results = crm.search_contacts(
            name=name or None,
            city=city or None,
            type=type or None,
            status=status or None,
            limit=limit,
        )
        return serialize_list(results, serialize_contact)
    except Exception as e:
        logger.error(f"contact_search failed: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
def contacts_overdue() -> str:
    """List contacts with overdue follow-up actions."""
    try:
        results = crm.get_overdue_contacts()
        return serialize_list(results, serialize_contact)
    except Exception as e:
        logger.error(f"contacts_overdue failed: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
def contacts_dormant() -> str:
    """List contacts with no activity in 12+ months."""
    try:
        results = crm.get_dormant_contacts()
        return serialize_list(results, serialize_contact)
    except Exception as e:
        logger.error(f"contacts_dormant failed: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# INTERACTION TOOLS
# =============================================================================

@server.tool()
def interaction_log(
    contact_id: int,
    interaction_date: str,
    method: str,
    direction: str = "outbound",
    summary: str = "",
    outcome: str = "",
    next_action: str = "",
    next_action_date: str = "",
    ai_draft_used: bool = False,
) -> str:
    """Log a new interaction (email, call, visit, etc.) for a contact. Dates as YYYY-MM-DD."""
    try:
        interaction = Interaction(
            contact_id=contact_id,
            interaction_date=date.fromisoformat(interaction_date),
            method=method,
            direction=direction,
            summary=summary or None,
            outcome=outcome or None,
            next_action=next_action or None,
            next_action_date=date.fromisoformat(next_action_date) if next_action_date else None,
            ai_draft_used=ai_draft_used,
        )
        interaction_id = crm.log_interaction(interaction)
        return json.dumps({"interaction_id": interaction_id, "contact_id": contact_id})
    except ValueError as e:
        return json.dumps({"error": f"Invalid date format: {e}"})
    except Exception as e:
        logger.error(f"interaction_log failed: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
def interaction_list(contact_id: int) -> str:
    """Get all interactions for a contact, newest first."""
    try:
        results = crm.get_interactions(contact_id)
        return serialize_list(results, serialize_interaction)
    except Exception as e:
        logger.error(f"interaction_list failed: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# SHOW TOOLS
# =============================================================================

@server.tool()
def show_create(
    name: str,
    venue_contact_id: int = 0,
    city: str = "",
    date_start: str = "",
    date_end: str = "",
    theme: str = "",
    status: str = "possible",
    notes: str = "",
) -> str:
    """Create a new show/exhibition entry. Dates as YYYY-MM-DD."""
    try:
        show = Show(
            name=name,
            venue_contact_id=venue_contact_id or None,
            city=city or None,
            date_start=date.fromisoformat(date_start) if date_start else None,
            date_end=date.fromisoformat(date_end) if date_end else None,
            theme=theme or None,
            status=status,
            notes=notes or None,
        )
        show_id = crm.create_show(show)
        return json.dumps({"show_id": show_id, "name": name})
    except ValueError as e:
        return json.dumps({"error": f"Invalid date format: {e}"})
    except Exception as e:
        logger.error(f"show_create failed: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
def show_list(
    status: str = "",
    date_from: str = "",
    date_to: str = "",
) -> str:
    """List shows with optional filters by status and date range. Dates as YYYY-MM-DD."""
    try:
        results = crm.get_shows(
            status=status or None,
            date_from=date.fromisoformat(date_from) if date_from else None,
            date_to=date.fromisoformat(date_to) if date_to else None,
        )
        return serialize_list(results, serialize_show)
    except ValueError as e:
        return json.dumps({"error": f"Invalid date format: {e}"})
    except Exception as e:
        logger.error(f"show_list failed: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
def show_update(show_id: int, updates: str) -> str:
    """Update show fields. Pass updates as a JSON object, e.g. '{"status": "confirmed"}'."""
    try:
        updates_dict = json.loads(updates)
        success = crm.update_show(show_id, updates_dict)
        if success:
            return json.dumps({"updated": True, "show_id": show_id})
        return json.dumps({"error": f"Show {show_id} not found"})
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON in updates: {e}"})
    except Exception as e:
        logger.error(f"show_update failed: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# AI PLANNER TOOLS
# =============================================================================

@server.tool()
def ai_daily_brief() -> str:
    """Generate an AI daily brief: who to contact this week and why. Uses DeepSeek for fast analysis."""
    try:
        brief = ai_planner.generate_daily_brief()
        return json.dumps({"brief": brief})
    except Exception as e:
        logger.error(f"ai_daily_brief failed: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
def ai_score_contact(contact_id: int) -> str:
    """Score how well a contact fits the artist's work (0-100) using AI analysis."""
    try:
        result = ai_planner.score_contact_fit(contact_id)
        return json.dumps(result)
    except Exception as e:
        logger.error(f"ai_score_contact failed: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
def ai_suggest_contacts(limit: int = 5) -> str:
    """AI suggests the best contacts to reach out to next, ranked by priority."""
    try:
        suggestions = ai_planner.suggest_next_contacts(limit=limit)
        # Serialize contacts within the suggestion dicts
        serialized = []
        for s in suggestions:
            entry = {"reasoning": s.get("reasoning", "")}
            if "contact" in s and s["contact"]:
                entry["contact"] = serialize_contact(s["contact"])
            serialized.append(entry)
        return json.dumps(serialized, indent=2)
    except Exception as e:
        logger.error(f"ai_suggest_contacts failed: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
def ai_score_unscored(limit: int = 10) -> str:
    """Batch-score all contacts that don't have a fit score yet. May take a few minutes."""
    try:
        count = ai_planner.analyze_all_unscored_contacts(limit=limit)
        return json.dumps({"scored_count": count})
    except Exception as e:
        logger.error(f"ai_score_unscored failed: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# EMAIL COMPOSER TOOLS
# =============================================================================

@server.tool()
def draft_first_contact(
    contact_id: int,
    language: str = "",
    include_portfolio_link: bool = True,
) -> str:
    """Draft a first contact letter to a gallery or venue. Uses DeepSeek Reasoner for quality writing."""
    try:
        result = email_composer.draft_first_contact_letter(
            contact_id=contact_id,
            language=language or None,
            include_portfolio_link=include_portfolio_link,
        )
        return json.dumps(result)
    except Exception as e:
        logger.error(f"draft_first_contact failed: {e}")
        return json.dumps({"error": str(e)})


@server.tool()
def draft_follow_up(
    contact_id: int,
    previous_interaction_summary: str,
    language: str = "",
) -> str:
    """Draft a follow-up letter referencing a previous interaction. Uses DeepSeek Reasoner for quality writing."""
    try:
        result = email_composer.draft_follow_up_letter(
            contact_id=contact_id,
            previous_interaction_summary=previous_interaction_summary,
            language=language or None,
        )
        return json.dumps(result)
    except Exception as e:
        logger.error(f"draft_follow_up failed: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# LEAD SCOUT TOOLS
# =============================================================================

@server.tool()
def scout_city(
    city: str,
    country: str = "DE",
    business_types: str = "",
    radius_km: float = 10.0,
    use_google_maps: bool = True,
    use_osm: bool = True,
    skip_duplicates: bool = True,
) -> str:
    """Scout a city for potential venues (galleries, cafes, coworking spaces) using Google Maps and OpenStreetMap. Pass business_types as JSON array, e.g. '["gallery", "cafe"]'. May take several minutes."""
    try:
        types_list = json.loads(business_types) if business_types else None
        result = lead_scout.scout_city(
            city=city,
            country=country,
            business_types=types_list,
            radius_km=radius_km,
            use_google_maps=use_google_maps,
            use_osm=use_osm,
            skip_duplicates=skip_duplicates,
        )
        return json.dumps(result, default=str)
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid JSON in business_types: {e}"})
    except Exception as e:
        logger.error(f"scout_city failed: {e}")
        return json.dumps({"error": str(e)})


# =============================================================================
# RESOURCES
# =============================================================================

@server.resource("crm://contacts")
def resource_contacts_list() -> str:
    """Summary list of all active contacts."""
    contacts = crm.search_contacts(limit=500)
    lines = []
    for c in contacts:
        parts = [f"#{c.id} {c.name}"]
        if c.city:
            parts.append(c.city)
        if c.type:
            parts.append(c.type)
        parts.append(f"status={c.status}")
        if c.fit_score is not None:
            parts.append(f"fit={c.fit_score}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


@server.resource("crm://contacts/{contact_id}")
def resource_contact_detail(contact_id: int) -> str:
    """Full contact record with recent interactions."""
    contact = crm.get_contact(contact_id)
    if not contact:
        return f"Contact {contact_id} not found"

    parts = [json.dumps(serialize_contact(contact), indent=2)]

    interactions = crm.get_interactions(contact_id)
    if interactions:
        parts.append("\nRecent interactions:")
        for i in interactions[:10]:
            line = f"  {i.interaction_date} | {i.method} ({i.direction})"
            if i.summary:
                line += f" | {i.summary[:80]}"
            if i.outcome:
                line += f" | outcome: {i.outcome}"
            parts.append(line)

    return "\n".join(parts)


@server.resource("crm://shows")
def resource_shows_list() -> str:
    """All shows."""
    shows = crm.get_shows()
    lines = []
    for s in shows:
        parts = [f"#{s.id} {s.name}"]
        if s.city:
            parts.append(s.city)
        if s.date_start:
            parts.append(str(s.date_start))
        parts.append(f"status={s.status}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


# =============================================================================
# PROMPTS
# =============================================================================

@server.prompt()
def weekly_outreach_plan() -> str:
    """Review overdue contacts, dormant contacts, and upcoming shows. Create a prioritized outreach plan for this week."""
    return """Review the CRM data and create a prioritized outreach plan for this week:

1. First, check contacts_overdue to see who needs follow-up
2. Then check contacts_dormant to find re-engagement opportunities
3. Check show_list for upcoming shows that might create urgency
4. Use ai_daily_brief to get AI-powered recommendations
5. For the top 3-5 contacts, look up their full details with contact_get

Create a concrete plan with specific actions for each contact."""


@server.prompt()
def evaluate_contact(contact_id: str) -> str:
    """Look up a contact, review their interaction history, score their fit, and recommend next steps."""
    return f"""Evaluate contact #{contact_id}:

1. Use contact_get to look up the full contact record
2. Use interaction_list to review their interaction history
3. Use ai_score_contact to get an AI fit score
4. Based on all this information, recommend:
   - Whether to pursue this contact
   - What approach to take (email, visit, call)
   - What to say in the first/next contact
   - When to reach out"""


@server.prompt()
def prepare_first_contact(contact_id: str) -> str:
    """Look up a contact, score their fit if not scored, then draft a first contact letter."""
    return f"""Prepare a first contact letter for contact #{contact_id}:

1. Use contact_get to look up the contact details
2. If they don't have a fit_score, use ai_score_contact first
3. Use draft_first_contact to generate a personalized letter
4. Review the draft and suggest any improvements
5. Ask if the user wants to log this as an interaction"""


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    server.run()
