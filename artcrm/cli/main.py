#!/usr/bin/env python3
"""
Art CRM Terminal CLI
Command-line interface for all CRM operations.
"""

import click
from datetime import date, timedelta
from typing import Optional

from artcrm.engine import crm
from artcrm.models import Contact, Interaction, Show


@click.group()
def cli():
    """Art CRM - Gallery & Contact Management System"""
    pass


# =============================================================================
# CONTACTS COMMANDS
# =============================================================================

@cli.group()
def contacts():
    """Manage contacts (galleries, cafes, platforms, etc.)"""
    pass


@contacts.command('list')
@click.option('--type', help='Filter by type (gallery, cafe, etc.)')
@click.option('--status', help='Filter by status (cold, contacted, etc.)')
@click.option('--city', help='Filter by city')
@click.option('--limit', default=50, help='Max results (default: 50)')
def contacts_list(type, status, city, limit):
    """List all contacts"""
    results = crm.search_contacts(
        type=type,
        status=status,
        city=city,
        limit=limit
    )

    if not results:
        click.echo("No contacts found.")
        return

    click.echo(f"\nFound {len(results)} contacts:\n")
    click.echo(f"{'ID':<6} {'Name':<30} {'City':<15} {'Type':<15} {'Status':<10}")
    click.echo("-" * 80)

    for c in results:
        click.echo(
            f"{c.id:<6} {c.name[:28]:<30} "
            f"{(c.city or '')[:13]:<15} {(c.type or '')[:13]:<15} "
            f"{c.status:<10}"
        )


@contacts.command('show')
@click.argument('contact_id', type=int)
def contacts_show(contact_id):
    """Show full contact details"""
    contact = crm.get_contact(contact_id)

    if not contact:
        click.echo(f"Contact ID {contact_id} not found.", err=True)
        return

    click.echo(f"\n{'='*80}")
    click.echo(f"CONTACT #{contact.id}: {contact.name}")
    click.echo(f"{'='*80}")
    click.echo(f"Type:        {contact.type or '(not set)'}")
    click.echo(f"Subtype:     {contact.subtype or '(not set)'}")
    click.echo(f"City:        {contact.city or '(not set)'}")
    click.echo(f"Country:     {contact.country or '(not set)'}")
    click.echo(f"Address:     {contact.address or '(not set)'}")
    click.echo(f"Website:     {contact.website or '(not set)'}")
    click.echo(f"Email:       {contact.email or '(not set)'}")
    click.echo(f"Phone:       {contact.phone or '(not set)'}")
    click.echo(f"Language:    {contact.preferred_language}")
    click.echo(f"Status:      {contact.status}")
    click.echo(f"Fit Score:   {contact.fit_score or 'N/A'}")
    click.echo(f"Best Visit:  {contact.best_visit_time or '(not set)'}")
    click.echo(f"Created:     {contact.created_at}")
    click.echo(f"Updated:     {contact.updated_at}")

    if contact.notes:
        click.echo(f"\nNotes:\n{contact.notes}")

    # Show interactions
    click.echo(f"\n{'='*80}")
    click.echo("INTERACTION HISTORY")
    click.echo(f"{'='*80}")

    interactions = crm.get_interactions(contact_id)
    if interactions:
        for i in interactions:
            click.echo(f"\n[{i.interaction_date}] {i.method or 'unknown'} ({i.direction})")
            if i.summary:
                click.echo(f"  {i.summary[:100]}")
            click.echo(f"  Outcome: {i.outcome or 'N/A'}")
            if i.next_action:
                click.echo(f"  Next: {i.next_action} (by {i.next_action_date})")
    else:
        click.echo("No interactions yet.")

    click.echo()


@contacts.command('add')
def contacts_add():
    """Add a new contact (interactive)"""
    click.echo("\n=== ADD NEW CONTACT ===\n")

    name = click.prompt("Name", type=str)
    type = click.prompt("Type (gallery/cafe/hotel/etc)", default="gallery")
    subtype = click.prompt("Subtype (upscale/hippy/commercial/etc)", default="", show_default=False) or None
    city = click.prompt("City", default="", show_default=False) or None
    country = click.prompt("Country (2-letter code)", default="DE")
    website = click.prompt("Website", default="", show_default=False) or None
    email = click.prompt("Email", default="", show_default=False) or None
    preferred_language = click.prompt("Preferred language", default="de")
    notes = click.prompt("Notes", default="", show_default=False) or None

    contact = Contact(
        name=name,
        type=type,
        subtype=subtype,
        city=city,
        country=country,
        website=website,
        email=email,
        preferred_language=preferred_language,
        status='cold',
        notes=notes
    )

    contact_id = crm.create_contact(contact)
    click.echo(f"\n✓ Created contact #{contact_id}: {name}")


@contacts.command('log')
@click.argument('contact_id', type=int)
def contacts_log(contact_id):
    """Log an interaction with a contact"""
    # Verify contact exists
    contact = crm.get_contact(contact_id)
    if not contact:
        click.echo(f"Contact ID {contact_id} not found.", err=True)
        return

    click.echo(f"\n=== LOG INTERACTION: {contact.name} ===\n")

    interaction_date = click.prompt("Date (YYYY-MM-DD)", default=str(date.today()))
    method = click.prompt("Method (email/in_person/phone/letter)", default="email")
    direction = click.prompt("Direction (outbound/inbound)", default="outbound")
    summary = click.prompt("Summary")
    outcome = click.prompt("Outcome (no_reply/interested/rejected/etc)", default="no_reply")
    next_action = click.prompt("Next action", default="", show_default=False) or None

    if next_action:
        days_ahead = click.prompt("Days until next action", type=int, default=30)
        next_action_date = date.today() + timedelta(days=days_ahead)
    else:
        next_action_date = None

    interaction = Interaction(
        contact_id=contact_id,
        interaction_date=date.fromisoformat(interaction_date),
        method=method,
        direction=direction,
        summary=summary,
        outcome=outcome,
        next_action=next_action,
        next_action_date=next_action_date,
        ai_draft_used=False
    )

    interaction_id = crm.log_interaction(interaction)
    click.echo(f"\n✓ Logged interaction #{interaction_id}")


@contacts.command('edit')
@click.argument('contact_id', type=int)
@click.option('--status', help='Update status')
@click.option('--email', help='Update email')
@click.option('--website', help='Update website')
@click.option('--notes', help='Update notes')
def contacts_edit(contact_id, status, email, website, notes):
    """Edit a contact (use options to set fields)"""
    updates = {}
    if status:
        updates['status'] = status
    if email:
        updates['email'] = email
    if website:
        updates['website'] = website
    if notes:
        updates['notes'] = notes

    if not updates:
        click.echo("No updates specified. Use --status, --email, --website, or --notes", err=True)
        return

    success = crm.update_contact(contact_id, updates)
    if success:
        click.echo(f"✓ Updated contact #{contact_id}")
    else:
        click.echo(f"Contact #{contact_id} not found", err=True)


# =============================================================================
# SHOWS COMMANDS
# =============================================================================

@cli.group()
def shows():
    """Manage exhibitions and shows"""
    pass


@shows.command('list')
@click.option('--status', help='Filter by status (possible/confirmed/completed)')
@click.option('--upcoming', is_flag=True, help='Show only upcoming shows')
def shows_list(status, upcoming):
    """List all shows"""
    date_from = date.today() if upcoming else None

    results = crm.get_shows(status=status, date_from=date_from)

    if not results:
        click.echo("No shows found.")
        return

    click.echo(f"\nFound {len(results)} shows:\n")
    click.echo(f"{'ID':<6} {'Name':<35} {'Date':<12} {'Status':<10}")
    click.echo("-" * 70)

    for s in results:
        date_str = str(s.date_start) if s.date_start else '(no date)'
        click.echo(
            f"{s.id:<6} {s.name[:33]:<35} {date_str:<12} {s.status:<10}"
        )


@shows.command('add')
def shows_add():
    """Add a new show (interactive)"""
    click.echo("\n=== ADD NEW SHOW ===\n")

    name = click.prompt("Show name", type=str)
    city = click.prompt("City", default="", show_default=False) or None
    date_start = click.prompt("Start date (YYYY-MM-DD)", default="", show_default=False)
    date_end = click.prompt("End date (YYYY-MM-DD)", default="", show_default=False)
    theme = click.prompt("Theme", default="", show_default=False) or None
    status = click.prompt("Status (possible/confirmed)", default="possible")
    notes = click.prompt("Notes", default="", show_default=False) or None

    show = Show(
        name=name,
        city=city,
        date_start=date.fromisoformat(date_start) if date_start else None,
        date_end=date.fromisoformat(date_end) if date_end else None,
        theme=theme,
        status=status,
        notes=notes
    )

    show_id = crm.create_show(show)
    click.echo(f"\n✓ Created show #{show_id}: {name}")


# =============================================================================
# QUERY COMMANDS
# =============================================================================

@cli.command('overdue')
def overdue():
    """Show contacts with overdue follow-ups"""
    results = crm.get_overdue_contacts()

    if not results:
        click.echo("No overdue contacts. You're all caught up! ✓")
        return

    click.echo(f"\n⚠️  {len(results)} contacts need follow-up:\n")
    click.echo(f"{'ID':<6} {'Name':<30} {'City':<15}")
    click.echo("-" * 55)

    for c in results:
        click.echo(f"{c.id:<6} {c.name[:28]:<30} {(c.city or '')[:13]:<15}")


@cli.command('dormant')
def dormant():
    """Show contacts with no activity in 12+ months"""
    results = crm.get_dormant_contacts()

    if not results:
        click.echo("No dormant contacts.")
        return

    click.echo(f"\n💤 {len(results)} dormant contacts (no activity in 12+ months):\n")
    click.echo(f"{'ID':<6} {'Name':<30} {'City':<15}")
    click.echo("-" * 55)

    for c in results[:20]:  # Show first 20
        click.echo(f"{c.id:<6} {c.name[:28]:<30} {(c.city or '')[:13]:<15}")

    if len(results) > 20:
        click.echo(f"\n... and {len(results) - 20} more")


# =============================================================================
# AI COMMANDS (Phase 5)
# =============================================================================

@cli.command('brief')
def brief():
    """AI daily brief - who to contact this week"""
    try:
        from artcrm.engine import ai_planner

        click.echo("\n🤖 Generating AI daily brief...\n")
        result = ai_planner.generate_daily_brief()
        click.echo(result)
        click.echo()

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("Make sure Ollama is running: ollama serve", err=True)


@cli.command('score')
@click.argument('contact_id', type=int)
def score(contact_id):
    """AI fit score for a contact"""
    try:
        from artcrm.engine import ai_planner

        click.echo(f"\n🤖 Analyzing contact #{contact_id}...\n")
        result = ai_planner.score_contact_fit(contact_id)

        click.echo(f"Fit Score: {result['fit_score']}/100")
        click.echo(f"\nReasoning:\n{result['reasoning']}")
        click.echo(f"\nSuggested Approach:\n{result['suggested_approach']}")
        click.echo()

    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@cli.command('suggest')
@click.option('--limit', default=5, help='Number of suggestions')
def suggest(limit):
    """AI suggests next contacts to reach out to"""
    try:
        from artcrm.engine import ai_planner

        click.echo(f"\n🤖 Getting AI suggestions for next {limit} contacts...\n")
        results = ai_planner.suggest_next_contacts(limit=limit)

        for r in results:
            contact = r['contact']
            click.echo(f"• {contact.name} ({contact.city})")
            click.echo(f"  Type: {contact.type}, Fit: {contact.fit_score or 'N/A'}/100")
            click.echo()

    except Exception as e:
        click.echo(f"Error: {e}", err=True)


@cli.command('draft')
@click.argument('contact_id', type=int)
@click.option('--language', help='Override contact language (de/en/fr)')
@click.option('--no-portfolio', is_flag=True, help='Exclude portfolio link')
def draft(contact_id, language, no_portfolio):
    """Draft a first contact letter using Claude API"""
    try:
        from artcrm.engine import email_composer

        click.echo(f"\n✍️  Drafting first contact letter for contact #{contact_id}...\n")
        click.echo("(This uses Claude API and may take a few seconds)\n")

        result = email_composer.draft_first_contact_letter(
            contact_id=contact_id,
            language=language,
            include_portfolio_link=not no_portfolio
        )

        click.echo(f"{'='*80}")
        click.echo(f"TO: {result['contact_name']}")
        click.echo(f"LANGUAGE: {result['language']}")
        click.echo(f"{'='*80}")
        click.echo(f"\nSUBJECT: {result['subject']}\n")
        click.echo(result['body'])
        click.echo(f"\n{'='*80}")
        click.echo(f"✓ Draft saved to: {result['draft_path']}")
        click.echo()

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
    except RuntimeError as e:
        click.echo(f"API Error: {e}", err=True)
        click.echo("Make sure ANTHROPIC_API_KEY is set in .env", err=True)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)


@cli.command('followup')
@click.argument('contact_id', type=int)
@click.option('--language', help='Override contact language (de/en/fr)')
def followup(contact_id, language):
    """Draft a follow-up letter using Claude API"""
    try:
        from artcrm.engine import email_composer

        # Prompt user for context about last interaction
        click.echo(f"\n✍️  Drafting follow-up letter for contact #{contact_id}...\n")

        previous_summary = click.prompt(
            "Brief summary of last interaction (what happened, what was discussed)",
            type=str
        )

        click.echo("\n(This uses Claude API and may take a few seconds)\n")

        result = email_composer.draft_follow_up_letter(
            contact_id=contact_id,
            previous_interaction_summary=previous_summary,
            language=language
        )

        click.echo(f"{'='*80}")
        click.echo(f"TO: {result['contact_name']}")
        click.echo(f"TYPE: Follow-up")
        click.echo(f"LANGUAGE: {result['language']}")
        click.echo(f"{'='*80}")
        click.echo(f"\nSUBJECT: {result['subject']}\n")
        click.echo(result['body'])
        click.echo(f"\n{'='*80}")
        click.echo(f"✓ Draft saved to: {result['draft_path']}")
        click.echo()

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
    except RuntimeError as e:
        click.echo(f"API Error: {e}", err=True)
        click.echo("Make sure ANTHROPIC_API_KEY is set in .env", err=True)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)


# =============================================================================
# LEAD GENERATION (Phase 6-Alpha)
# =============================================================================

@cli.command('recon')
@click.argument('city')
@click.argument('country', default='DE')
@click.option('--type', 'types', multiple=True, help='Business types to search (gallery, cafe, coworking)')
@click.option('--radius', default=10.0, help='Search radius in km (default: 10)')
@click.option('--model', type=click.Choice(['claude', 'ollama']), default='ollama', help='AI model for enrichment')
@click.option('--no-google', is_flag=True, help='Skip Google Maps API')
@click.option('--no-osm', is_flag=True, help='Skip OpenStreetMap')
def recon(city, country, types, radius, model, no_google, no_osm):
    """Scout a city for potential leads (galleries, cafes, coworking spaces)"""
    try:
        from artcrm.engine import lead_scout

        click.echo(f"\n🎯 Starting reconnaissance mission for {city}, {country}\n")

        # Default types if none specified
        if not types:
            types = ['gallery', 'cafe', 'coworking']
        else:
            # Validate types
            valid_types = {'gallery', 'cafe', 'coworking'}
            for t in types:
                if t not in valid_types:
                    click.echo(f"Warning: Unknown type '{t}'. Valid types: {', '.join(valid_types)}", err=True)

        click.echo(f"Target types: {', '.join(types)}")
        click.echo(f"Search radius: {radius} km")
        click.echo(f"AI model: {model}")
        click.echo(f"Data sources: ", nl=False)

        sources = []
        if not no_google:
            sources.append("Google Maps")
        if not no_osm:
            sources.append("OpenStreetMap")

        click.echo(', '.join(sources) if sources else 'None (this will not work!)')
        click.echo()

        if not sources:
            click.echo("Error: All data sources disabled. Enable at least one source.", err=True)
            return

        # Run scout
        stats = lead_scout.scout_city(
            city=city,
            country=country,
            business_types=list(types),
            radius_km=radius,
            ai_model=model,
            use_google_maps=not no_google,
            use_osm=not no_osm,
            skip_duplicates=True
        )

        # Display results
        click.echo(f"\n{'='*80}")
        click.echo(f"RECONNAISSANCE COMPLETE")
        click.echo(f"{'='*80}")
        click.echo(f"\nCity: {stats['city']}, {stats['country']}")
        click.echo(f"Data sources: {', '.join(stats['sources_used'])}")
        click.echo(f"\nResults by type:")
        for biz_type, count in stats['by_type'].items():
            click.echo(f"  {biz_type}: {count} venues found")

        click.echo(f"\nTotal found: {stats['total_found']}")
        click.echo(f"Inserted: {stats['total_inserted']}")
        click.echo(f"Skipped (duplicates): {stats['total_skipped']}")

        click.echo(f"\n✓ Mission complete!")
        click.echo(f"\nNext steps:")
        click.echo(f"  • Review leads: ./crm contacts list --status lead_unverified")
        click.echo(f"  • Score a lead: ./crm score <contact_id>")
        click.echo(f"  • Draft letter: ./crm draft <contact_id>")
        click.echo()

    except ImportError as e:
        click.echo(f"Error: Missing dependencies. Run: pip install -r requirements.txt", err=True)
        click.echo(f"Details: {e}", err=True)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    cli()
