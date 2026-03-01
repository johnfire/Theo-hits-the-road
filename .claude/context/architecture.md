# Architecture

## Project Structure

```
project-root/
├── .claude/                  ← Claude Code context (CLAUDE.md, context/, commands/)
├── config/                   ← Non-secret config defaults (JSON)
├── data/                     ← Source spreadsheet, drafts, notes, scout results
├── docs/
│   ├── architecture/         ← System design docs
│   ├── deployment/           ← Setup and deployment runbooks
│   └── guides/               ← Reference docs
├── scripts/                  ← CLI wrapper (crm), import, inspect scripts
├── src/                      ← Main Python package
│   ├── api/                  ← FastAPI layer (Phase 8+, stub only)
│   ├── bus/events.py         ← Event bus
│   ├── cli/main.py           ← Terminal CLI (Click)
│   ├── config.py             ← Env var loader
│   ├── db/
│   │   ├── connection.py     ← DB connection management
│   │   └── migrations/       ← Numbered SQL migration files
│   ├── engine/
│   │   ├── crm.py            ← CRM Engine
│   │   ├── ai_planner.py     ← AI Planner
│   │   ├── ai_client.py      ← DeepSeek/Claude API client
│   │   ├── email_composer.py ← Email Composer
│   │   └── lead_scout.py     ← City recon / lead generation
│   ├── logging_config.py     ← Structured logging setup
│   ├── models/__init__.py    ← Dataclasses: Contact, Interaction, Show
│   └── services/             ← Service Interface (CLI/API/GUI all call this)
├── tests/
│   ├── bdd/                  ← Gherkin/pytest-bdd behaviour tests
│   ├── integration/          ← Tests requiring real DB
│   └── unit/                 ← Fast isolated tests
├── main.py                   ← Interactive menu launcher
└── .env                      ← Secrets (gitignored)
```

---

## The Event Bus — CRITICAL

Modules do NOT import each other. They communicate only through the event bus.

```python
# CORRECT
from src.bus.events import bus
bus.emit('contact_updated', {'contact_id': 42})

# WRONG — never do this
from src.engine.ai_planner import reanalyse_contact
```

| Event              | Emitted By     | Handled By                         |
|--------------------|----------------|------------------------------------|
| contact_created    | CRM Engine     | AI Planner (schedule analysis)     |
| contact_updated    | CRM Engine     | AI Planner (re-score)              |
| interaction_logged | CRM Engine     | AI Planner (update next action)    |
| show_scheduled     | CRM Engine     | AI Planner (reprioritise contacts) |
| suggestion_ready   | AI Planner     | Email Composer, CLI display        |
| draft_ready        | Email Composer | CLI display, Browser UI            |
| email_sent         | Email Composer | CRM Engine (auto-log interaction)  |

---

## Service Interface

All presentation layers (CLI, FastAPI, Tkinter) call ONLY the Service Interface.
They never call CRM Engine, AI Planner, or Email Composer directly.

---

## Database

**Connection:** Always use `DATABASE_URL` env var. Never hardcode credentials.

**Core tables:**
- `lookup_values` — extensible value sets for all categorical fields
- `contacts` — galleries, cafes, hotels, offices, coworking spaces, online platforms
- `interactions` — full history per contact
- `shows` — exhibition pipeline, linked to contacts
- `ai_analysis` — stored AI reasoning and suggestions per contact
- `people` — individual collectors (Phase 2+)

**Migration strategy:** Numbered SQL files in `src/db/migrations/`. Append only — never edit existing files.

**Extensibility rule:** All categorical fields use VARCHAR + `lookup_values` table. Never ENUM. New valid value = one INSERT, no migration needed.

---

## Spreadsheet Import

Source: `data/art-marketing.xlsx`

| Sheet            | Target                 | Notes                                   |
|------------------|------------------------|-----------------------------------------|
| contacts & leads | contacts + interactions | 5 attempt cols → interaction rows      |
| current channels | contacts               | Merge by name+city dedup key            |
| show dates       | shows                  | Venue matched by fuzzy name             |
| on line          | contacts (type=online) | Each platform = one contact             |
| stats            | contacts (update)      | Adds follower/post counts to notes      |
| everything else  | notes files            | Stored as markdown in data/notes/       |

Import is re-runnable. Dedup key: name + city. Never overwrites existing data.

---

## Language & Localisation

- Language set per-contact via `preferred_language` field.
- Default for Bavaria area: `de`. International online platforms: `en`.
- Always pass `preferred_language` to AI prompt when drafting messages.
- Seeded values: `de, en, fr, cs, nl, es, it` (extensible via `lookup_values`).
