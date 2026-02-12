#!/usr/bin/env python3
"""
Simple CRM Engine Test
Demonstrates all CRM operations with real database data.
"""

import sys
from pathlib import Path
from datetime import date, timedelta

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from artcrm.engine import crm
from artcrm.models import Contact, Interaction, Show

def main():
    print("=" * 80)
    print("CRM ENGINE TEST")
    print("=" * 80)
    print()

    # Test 1: Search existing contacts
    print("1. SEARCHING CONTACTS")
    print("-" * 80)
    contacts = crm.search_contacts(limit=5)
    print(f"Found {len(contacts)} contacts (showing first 5):")
    for c in contacts:
        print(f"  - ID {c.id}: {c.name} ({c.city}) - Status: {c.status}")
    print()

    # Test 2: Get a specific contact
    if contacts:
        test_contact = contacts[0]
        print("2. GET CONTACT DETAILS")
        print("-" * 80)
        full_contact = crm.get_contact(test_contact.id)
        print(f"Contact: {full_contact.name}")
        print(f"  Type: {full_contact.type}")
        print(f"  City: {full_contact.city}")
        print(f"  Status: {full_contact.status}")
        print(f"  Website: {full_contact.website or '(none)'}")
        print(f"  Notes: {full_contact.notes[:50] if full_contact.notes else '(none)'}")
        print()

        # Test 3: Get interactions for this contact
        print("3. GET INTERACTION HISTORY")
        print("-" * 80)
        interactions = crm.get_interactions(test_contact.id)
        print(f"Found {len(interactions)} interactions for {test_contact.name}:")
        for i in interactions[:3]:  # Show first 3
            print(f"  - {i.interaction_date}: {i.summary[:50] if i.summary else '(no summary)'}")
            print(f"    Outcome: {i.outcome}, Method: {i.method}")
        print()

        # Test 4: Log a new interaction
        print("4. LOG NEW INTERACTION")
        print("-" * 80)
        new_interaction = Interaction(
            contact_id=test_contact.id,
            interaction_date=date.today(),
            method='email',
            direction='outbound',
            summary='Test interaction from CRM Engine test script',
            outcome='no_reply',
            next_action='Follow up in 2 weeks',
            next_action_date=date.today() + timedelta(days=14)
        )
        interaction_id = crm.log_interaction(new_interaction)
        print(f"Created interaction ID {interaction_id}")
        print()

        # Test 5: Update contact
        print("5. UPDATE CONTACT")
        print("-" * 80)
        success = crm.update_contact(test_contact.id, {
            'notes': f"Updated by test script on {date.today()}"
        })
        print(f"Update {'successful' if success else 'failed'}")
        print()

    # Test 6: Query shows
    print("6. GET UPCOMING SHOWS")
    print("-" * 80)
    shows = crm.get_shows(date_from=date.today())
    print(f"Found {len(shows)} upcoming shows:")
    for s in shows[:5]:  # Show first 5
        print(f"  - {s.name}: {s.date_start or '(no date)'} - {s.status}")
    print()

    # Test 7: Get overdue contacts
    print("7. GET OVERDUE CONTACTS")
    print("-" * 80)
    overdue = crm.get_overdue_contacts()
    print(f"Found {len(overdue)} contacts needing follow-up:")
    for c in overdue[:5]:  # Show first 5
        print(f"  - {c.name} ({c.city})")
    print()

    # Test 8: Get dormant contacts
    print("8. GET DORMANT CONTACTS")
    print("-" * 80)
    dormant = crm.get_dormant_contacts()
    print(f"Found {len(dormant)} dormant contacts (no activity in 12+ months):")
    for c in dormant[:5]:  # Show first 5
        print(f"  - {c.name} ({c.city})")
    print()

    print("=" * 80)
    print("CRM ENGINE TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
