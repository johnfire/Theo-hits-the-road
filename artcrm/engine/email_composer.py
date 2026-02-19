"""
Email Composer - Letter and proposal drafting via AI.
For first contact letters, follow-ups, and proposals.
Defaults to Claude for high-quality writing; DeepSeek also supported.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from artcrm.logging_config import log_call
from artcrm.engine.ai_client import call_claude, call_ai  # noqa: F401 — call_claude re-exported for tests
from artcrm.engine import crm
from artcrm.models import Contact
from artcrm.bus.events import bus, EVENT_DRAFT_READY
from artcrm.config import config

logger = logging.getLogger(__name__)

# Draft storage
DRAFTS_DIR = Path(__file__).parent.parent.parent / "data" / "drafts"
DRAFTS_DIR.mkdir(exist_ok=True, parents=True)


# =============================================================================
# CONTEXT BUILDER
# =============================================================================

def build_artist_context() -> str:
    """
    Build artist bio for letter context.
    TODO: Read from data/artist_bio.txt when available.
    """
    bio_file = Path(__file__).parent.parent.parent / "data" / "artist_bio.txt"

    if bio_file.exists():
        return bio_file.read_text()

    # Placeholder bio
    return """
Christopher Rehm is a working professional artist based in Klosterlechfeld, Bavaria, Germany.

His work spans multiple mediums including watercolor, oil, and acrylic paintings. His artistic style encompasses landscapes, cityscapes, fantasy and surreal compositions, botanical studies, and works influenced by Japanese woodblock prints.

As an established artist actively seeking exhibition opportunities, Christopher is interested in collaborating with galleries, cafes, hotels, offices, and other venues throughout Bavaria and beyond that appreciate his diverse artistic range.
"""


def build_contact_context(contact: Contact) -> str:
    """Build context about the contact for personalization."""
    context_parts = []

    context_parts.append(f"Venue: {contact.name}")
    context_parts.append(f"Type: {contact.type or 'venue'}")
    context_parts.append(f"Location: {contact.city}, {contact.country or 'Germany'}")

    if contact.website:
        context_parts.append(f"Website: {contact.website}")

    if contact.notes:
        context_parts.append(f"Notes: {contact.notes[:200]}")

    return "\n".join(context_parts)


# =============================================================================
# DRAFT GENERATION
# =============================================================================

@log_call
def draft_first_contact_letter(
    contact_id: int,
    language: Optional[str] = None,
    include_portfolio_link: bool = True,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Draft a first contact letter to a gallery/venue.

    Args:
        contact_id: ID of contact to write to
        language: Override contact's preferred language
        include_portfolio_link: Include portfolio URL in draft
        model: AI model ('claude', 'deepseek-chat', 'deepseek-reasoner'); defaults to 'claude'

    Returns: dict with subject, body, language, metadata
    """
    _model = model or 'deepseek-reasoner'
    logger.info(f"Drafting first contact letter for contact #{contact_id} using {_model}")

    contact = crm.get_contact(contact_id)
    if not contact:
        raise ValueError(f"Contact {contact_id} not found")

    # Determine language
    lang = language or contact.preferred_language or 'de'
    lang_name = {'de': 'German', 'en': 'English', 'fr': 'French'}.get(lang, 'English')

    # Build context
    artist_bio = build_artist_context()
    contact_context = build_contact_context(contact)

    prompt = f"""Write a professional first contact letter from an artist to a {contact.type or 'venue'}.

ARTIST INFORMATION:
{artist_bio}

RECIPIENT:
{contact_context}

REQUIREMENTS:
- Language: {lang_name} (formal, professional tone)
- Length: 200-300 words
- Purpose: Introduce the artist and express interest in exhibiting work
- Include: Brief bio, artistic style, why this venue is a good fit
- Tone: Professional but warm, respectful, not overly salesy
- Call to action: Request to schedule a brief meeting or send portfolio
{"- Include: Portfolio link: https://www.artbychristopherrehm.com" if include_portfolio_link else ""}

DO NOT include:
- Placeholder text like [Your Name] or [Date]
- Generic template language
- Excessive flattery

Write the email now. Start with a subject line on its own line, then the email body."""

    system_prompt = """You are an experienced professional writer specializing in artist-gallery correspondence. You write clear, engaging letters that respect the recipient's time while showcasing the artist's unique value. Your writing is authentic and personalized to each recipient."""

    # Generate draft
    draft_text = call_ai(prompt, model=_model, system=system_prompt, max_tokens=1500)

    # Parse subject and body (simple parsing)
    lines = draft_text.split('\n', 1)
    subject = lines[0].replace('Subject:', '').strip()
    body = lines[1].strip() if len(lines) > 1 else draft_text

    # Save draft to file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    draft_filename = f"draft_{contact_id}_{timestamp}.txt"
    draft_path = DRAFTS_DIR / draft_filename

    draft_content = f"""TO: {contact.name}
EMAIL: {contact.email or '(no email on file)'}
LANGUAGE: {lang_name}
MODEL: {_model}
GENERATED: {datetime.now().isoformat()}

SUBJECT: {subject}

{body}
"""

    draft_path.write_text(draft_content)
    logger.info(f"Draft saved to {draft_path}")

    # Emit event
    bus.emit(EVENT_DRAFT_READY, {
        'contact_id': contact_id,
        'draft_path': str(draft_path),
        'language': lang
    })

    return {
        'contact_id': contact_id,
        'contact_name': contact.name,
        'subject': subject,
        'body': body,
        'language': lang,
        'draft_path': str(draft_path),
        'timestamp': timestamp
    }


@log_call
def draft_follow_up_letter(
    contact_id: int,
    previous_interaction_summary: str,
    language: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Draft a follow-up letter after previous contact.

    Args:
        contact_id: ID of contact
        previous_interaction_summary: Summary of last interaction
        language: Override language
        model: AI model ('claude', 'deepseek-chat', 'deepseek-reasoner'); defaults to 'claude'

    Returns: draft dict
    """
    _model = model or 'deepseek-reasoner'
    logger.info(f"Drafting follow-up letter for contact #{contact_id} using {_model}")

    contact = crm.get_contact(contact_id)
    if not contact:
        raise ValueError(f"Contact {contact_id} not found")

    lang = language or contact.preferred_language or 'de'
    lang_name = {'de': 'German', 'en': 'English', 'fr': 'French'}.get(lang, 'English')

    artist_bio = build_artist_context()
    contact_context = build_contact_context(contact)

    # Get interaction history
    interactions = crm.get_interactions(contact_id)
    interaction_history = "\n".join([
        f"- {i.interaction_date}: {i.summary[:100]}"
        for i in interactions[:3]
    ]) if interactions else "No previous interactions"

    prompt = f"""Write a professional follow-up email from an artist to a {contact.type or 'venue'}.

ARTIST:
{artist_bio}

RECIPIENT:
{contact_context}

PREVIOUS INTERACTION:
{previous_interaction_summary}

FULL HISTORY:
{interaction_history}

REQUIREMENTS:
- Language: {lang_name}
- Length: 150-250 words
- Reference previous contact appropriately
- Provide update or new information
- Gentle call to action
- Professional and courteous tone

Write the email with subject line first, then body."""

    draft_text = call_ai(prompt, model=_model, max_tokens=1200)

    lines = draft_text.split('\n', 1)
    subject = lines[0].replace('Subject:', '').strip()
    body = lines[1].strip() if len(lines) > 1 else draft_text

    # Save draft
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    draft_filename = f"followup_{contact_id}_{timestamp}.txt"
    draft_path = DRAFTS_DIR / draft_filename

    draft_content = f"""TO: {contact.name}
TYPE: Follow-up
EMAIL: {contact.email or '(no email)'}
LANGUAGE: {lang_name}
MODEL: {_model}
GENERATED: {datetime.now().isoformat()}

SUBJECT: {subject}

{body}
"""

    draft_path.write_text(draft_content)
    logger.info(f"Follow-up draft saved to {draft_path}")

    bus.emit(EVENT_DRAFT_READY, {
        'contact_id': contact_id,
        'draft_path': str(draft_path),
        'language': lang,
        'type': 'follow-up'
    })

    return {
        'contact_id': contact_id,
        'contact_name': contact.name,
        'subject': subject,
        'body': body,
        'language': lang,
        'draft_path': str(draft_path),
        'timestamp': timestamp
    }
