#!/usr/bin/env python3
"""
Art CRM - Interactive Menu Launcher
Run this file to access all CRM commands through a simple menu.

Usage:
    python main.py
"""

import subprocess
import sys
import os

# Ensure we're running from the project root with the venv python
PYTHON = sys.executable
CRM = [PYTHON, "artcrm/cli/main.py"]

# Project root on PYTHONPATH so 'artcrm' package is importable
ENV = os.environ.copy()
ENV["PYTHONPATH"] = os.path.dirname(os.path.abspath(__file__))


def run(args: list[str]):
    """Run a CRM CLI command and return to menu when done."""
    print()
    subprocess.run(CRM + args, env=ENV)
    print()
    input("  Press Enter to return to menu...")


def prompt(label: str, required: bool = True) -> str:
    """Prompt user for input. Returns empty string if optional and skipped."""
    while True:
        value = input(f"  {label}: ").strip()
        if value:
            return value
        if not required:
            return ""
        print("  (required - please enter a value)")


def prompt_optional(label: str) -> str:
    return prompt(f"{label} (optional, Enter to skip)", required=False)


def clear():
    os.system("cls" if os.name == "nt" else "clear")


# =============================================================================
# COMMAND HANDLERS
# =============================================================================

def contacts_list():
    args = ["contacts", "list"]
    t = prompt_optional("Filter by type (gallery/cafe/coworking)")
    s = prompt_optional("Filter by status (cold/contacted/lead_unverified)")
    c = prompt_optional("Filter by city")
    if t: args += ["--type", t]
    if s: args += ["--status", s]
    if c: args += ["--city", c]
    run(args)

def contacts_show():
    cid = prompt("Contact ID")
    run(["contacts", "show", cid])

def contacts_add():
    run(["contacts", "add"])

def contacts_log():
    cid = prompt("Contact ID")
    run(["contacts", "log", cid])

def contacts_edit():
    cid = prompt("Contact ID")
    args = ["contacts", "edit", cid]
    s = prompt_optional("New status")
    e = prompt_optional("New email")
    w = prompt_optional("New website")
    n = prompt_optional("New notes")
    if s: args += ["--status", s]
    if e: args += ["--email", e]
    if w: args += ["--website", w]
    if n: args += ["--notes", n]
    run(args)

def shows_list():
    args = ["shows", "list"]
    s = prompt_optional("Filter by status (possible/confirmed/completed)")
    u = input("  Upcoming only? (y/N): ").strip().lower()
    if s: args += ["--status", s]
    if u == "y": args += ["--upcoming"]
    run(args)

def shows_add():
    run(["shows", "add"])

def overdue():
    run(["overdue"])

def dormant():
    run(["dormant"])

def brief():
    run(["brief"])

def score():
    cid = prompt("Contact ID")
    run(["score", cid])

def suggest():
    n = prompt_optional("Number of suggestions (default: 5)")
    args = ["suggest"]
    if n: args += ["--limit", n]
    run(args)

def draft():
    cid = prompt("Contact ID")
    args = ["draft", cid]
    lang = prompt_optional("Language override (de/en/fr)")
    if lang: args += ["--language", lang]
    run(args)

def followup():
    cid = prompt("Contact ID")
    args = ["followup", cid]
    lang = prompt_optional("Language override (de/en/fr)")
    if lang: args += ["--language", lang]
    run(args)

def recon():
    city    = prompt("City name (e.g. Rosenheim)")
    country = prompt_optional("Country code (default: DE)") or "DE"
    args = ["recon", city, country]

    print("  Business types (Enter to use all: gallery, cafe, coworking)")
    types = prompt_optional("Types - space separated (e.g. gallery cafe)")
    if types:
        for t in types.split():
            args += ["--type", t]

    radius = prompt_optional("Search radius in km (default: 10)")
    if radius: args += ["--radius", radius]

    model = input("  AI model - ollama or claude (default: ollama): ").strip().lower()
    if model in ("claude", "ollama"): args += ["--model", model]

    no_google = input("  Skip Google Maps? (y/N): ").strip().lower()
    if no_google == "y": args += ["--no-google"]

    no_osm = input("  Skip OpenStreetMap? (y/N): ").strip().lower()
    if no_osm == "y": args += ["--no-osm"]

    run(args)


# =============================================================================
# MENU LAYOUT
# =============================================================================

MENU = [
    ("CONTACTS", [
        ("List contacts",                contacts_list),
        ("Show contact details",         contacts_show),
        ("Add new contact",              contacts_add),
        ("Log interaction",              contacts_log),
        ("Edit contact",                 contacts_edit),
    ]),
    ("SHOWS", [
        ("List shows",                   shows_list),
        ("Add show",                     shows_add),
    ]),
    ("REPORTS", [
        ("Overdue contacts",             overdue),
        ("Dormant contacts",             dormant),
    ]),
    ("AI FEATURES", [
        ("Daily brief (Ollama)",         brief),
        ("Score contact fit (Ollama)",   score),
        ("Suggest contacts (Ollama)",    suggest),
        ("Draft first letter (Claude)",  draft),
        ("Draft follow-up (Claude)",     followup),
    ]),
    ("LEAD GENERATION", [
        ("Recon a city for leads",       recon),
    ]),
]


def print_menu():
    clear()
    print("=" * 50)
    print("   ART CRM - COMMAND CENTRE")
    print("=" * 50)

    n = 1
    numbering = {}  # maps display number -> handler function

    for section, commands in MENU:
        print(f"\n  {section}")
        print(f"  {'-' * len(section)}")
        for label, handler in commands:
            print(f"  {n:>2}.  {label}")
            numbering[n] = handler
            n += 1

    print("\n" + "=" * 50)
    print("   0.  Exit")
    print("=" * 50)
    return numbering


def main():
    while True:
        numbering = print_menu()

        try:
            choice = input("\n  Select a command: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n  Goodbye!\n")
            break

        if choice == "0" or choice.lower() in ("q", "quit", "exit"):
            print("\n  Goodbye!\n")
            break

        try:
            n = int(choice)
            if n in numbering:
                clear()
                numbering[n]()
            else:
                print(f"\n  Invalid selection: {choice}")
                input("  Press Enter to continue...")
        except ValueError:
            print(f"\n  Please enter a number.")
            input("  Press Enter to continue...")


if __name__ == "__main__":
    main()
