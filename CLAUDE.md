# Art CRM & AI Assistant — Project Context

## What This Project Is
A Python-based CRM and AI assistant for a working artist (Christopher Rehm, Klosterlechfeld,
Bavaria). Replaces an Excel spreadsheet used to track gallery outreach, show scheduling,
online channels, and contact history. Full architecture in docs/art_crm_architecture.docx.

---

## Developer Preferences
- Clean, simple code. No cleverness for its own sake.
- One thing at a time. Complete a step fully before moving to the next.
- Show your work and stop. Wait for "next" before proceeding to the next step.
- Inline comments for code review. Architecture decisions as summary comments.
- Modular design. No module imports another directly — use the event bus.
- Some technical debt is acceptable. Delivery matters. But think about architecture first.
- Ask clarifying questions (3-20 depending on complexity) before starting any significant task.
- Always show pros and cons when presenting options.

---

## Tech Stack
- **Language:** Python 3.12
- **Database:** PostgreSQL (local first, VPS later — see Deployment section)
- **AI backends:** Hybrid — Ollama (local/Pi cluster) for routine tasks, Claude API for
  high-stakes writing (gallery letters, proposals)
- **Web layer (Phase 8+):** FastAPI behind nginx
- **Testing:** pytest for unit and integration tests
- **Email:** SMTP/IMAP (standard library + smtplib)

---

## Project Structure
```
artcrm/
├── CLAUDE.md                  ← this file
├── docs/
│   └── art_crm_architecture.docx
├── data/
│   └── art-marketing.xlsx     ← source spreadsheet for import
├── artcrm/                    ← main Python package
│   ├── __init__.py
│   ├── config.py              ← env vars, settings
│   ├── db/
│   │   ├── __init__.py
│   │   ├── connection.py      ← DB connection management
│   │   └── migrations/        ← SQL migration files
│   ├── models/
│   │   └── __init__.py        ← dataclasses / typed dicts for all entities
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── crm.py             ← CRM Engine module
│   │   ├── ai_planner.py      ← AI Planner module
│   │   └── email_composer.py  ← Email Composer module
│   ├── bus/
│   │   └── events.py          ← Event bus
│   ├── services/
│   │   └── service.py         ← Service Interface (what CLI, FastAPI, GUI all call)
│   ├── cli/
│   │   └── main.py            ← Terminal CLI (Click or Typer)
│   └── api/                   ← FastAPI layer (Phase 8+, stub only until then)
│       └── __init__.py
├── scripts/
│   └── import_xlsx.py         ← Spreadsheet import script (Phase 4)
├── tests/
│   ├── unit/
│   └── integration/
├── .env.example               ← environment variable template
└── requirements.txt
```

---

## Database

### Connection
Always use the `DATABASE_URL` environment variable. Never hardcode credentials.

```
DATABASE_URL=postgresql://artcrm_user:password@localhost:5432/artcrm
```

### Extensibility Rule — CRITICAL
All categorical fields (type, subtype, status, language, etc.) are stored as VARCHAR.
Valid values live in the `lookup_values` table. **Never use ENUM types in PostgreSQL.**
Adding a new valid value = one INSERT into lookup_values. No schema migration needed.

```sql
-- The lookup_values table is the single source of truth for all categories
SELECT value FROM lookup_values WHERE category = 'contact_type' AND active = TRUE;
```

### Core Tables (see architecture doc for full schema)
- `lookup_values`   — extensible value sets for all categorical fields
- `contacts`        — galleries, cafes, hotels, offices, coworking spaces, online platforms
- `interactions`    — full history per contact (replaces the 5-column spreadsheet model)
- `shows`           — exhibition pipeline, linked to contacts
- `ai_analysis`     — stored AI reasoning and suggestions per contact
- `people`          — individual collectors (Phase 2+, table defined in schema from Phase 1)

### Migration Strategy
Each migration is a numbered SQL file in `artcrm/db/migrations/`.
Format: `001_initial_schema.sql`, `002_seed_lookup_values.sql`, etc.
A simple migration runner applies them in order, tracking which have run in a
`schema_migrations` table.

---

## The Event Bus — CRITICAL ARCHITECTURE RULE
Modules do NOT import each other. They communicate only through the event bus.

```python
# CORRECT
from artcrm.bus.events import bus
bus.emit('contact_updated', {'contact_id': 42})

# WRONG — never do this
from artcrm.engine.ai_planner import reanalyse_contact
reanalyse_contact(42)
```

### Key Events
| Event                | Emitted By     | Handled By                          |
|----------------------|----------------|-------------------------------------|
| contact_created      | CRM Engine     | AI Planner (schedule analysis)      |
| contact_updated      | CRM Engine     | AI Planner (re-score)               |
| interaction_logged   | CRM Engine     | AI Planner (update next action)     |
| show_scheduled       | CRM Engine     | AI Planner (reprioritise contacts)  |
| suggestion_ready     | AI Planner     | Email Composer, CLI display         |
| draft_ready          | Email Composer | CLI display, Browser UI             |
| email_sent           | Email Composer | CRM Engine (auto-log interaction)   |

---

## AI Planner

### Model Selection
| Task                              | Model                  |
|-----------------------------------|------------------------|
| Daily brief / who to contact      | Ollama (local)         |
| Fit scoring a new contact         | Ollama (local)         |
| Reprioritising after show added   | Ollama (local)         |
| First contact letter to gallery   | Claude API             |
| Follow-up proposal draft          | Claude API             |

### Environment Variables for AI
```
OLLAMA_BASE_URL=http://<pi-hostname>:11434
OLLAMA_MODEL=llama3
ANTHROPIC_API_KEY=sk-ant-...
```

### Context Builder
Before every AI call, assemble context from:
1. Artist bio (read from `data/artist_bio.txt`)
2. Upcoming shows (next 90 days from `shows` table)
3. Contact full record + interaction history
4. Previous AI analyses for this contact
5. Approach notes for this contact type (gallery vs. office vs. café)

Always store the full AI response in `ai_analysis.raw_response` for debugging.

---

## Service Interface
All presentation layers (CLI, FastAPI, Tkinter) call ONLY the Service Interface.
They never call CRM Engine, AI Planner, or Email Composer directly.
This is what makes adding new interfaces straightforward.

---

## CLI Commands Reference
```
crm contacts list              list all contacts with status
crm contacts add               interactive add wizard
crm contacts show <id>         full record + interaction history
crm contacts edit <id>         edit a contact
crm contacts log <id>          log a new interaction
crm brief                      AI daily brief: who to contact this week
crm score <id>                 AI fit score for a contact
crm suggest [--limit N]        AI suggests next contacts to reach out to
crm draft <id>                 AI draft first contact letter (Claude API)
crm followup <id>              AI draft follow-up letter (Claude API)
crm recon <city> [country]     Scout city for leads (galleries, cafes, coworking)
                               Options: --type, --radius, --model (claude/ollama)
crm shows list                 list upcoming shows
crm shows add                  add a show
crm overdue                    show contacts with overdue follow-ups
crm dormant                    show dormant contacts (12+ months)
```

---

## Spreadsheet Import (Phase 4)
Source file: `data/art-marketing.xlsx`

### Sheet → Table Mapping
| Sheet             | Target                  | Notes                                        |
|-------------------|-------------------------|----------------------------------------------|
| contacts & leads  | contacts + interactions | 5 attempt cols → interaction rows            |
| current channels  | contacts                | Merge by name+city dedup key                 |
| show dates        | shows                   | Venue matched to contacts by fuzzy name      |
| on line           | contacts (type=online)  | Each platform = one contact                  |
| stats             | contacts (update)       | Adds follower/post counts to notes           |
| everything else   | notes files             | Stored as markdown in data/notes/            |

### Import Rules
- **Dedup key:** name + city. Never creates duplicates.
- **Never overwrites** existing data — only fills empty fields.
- **Re-runnable:** safe to run multiple times.
- **Dry-run flag:** `--dry-run` shows what would change without writing.
- **Import report:** written to `~/logs/import_<timestamp>.log`.

### 5-Column Conversion
The spreadsheet tracks contact attempts in 5 flat columns (1st try → 5th try).
Each non-empty attempt cell becomes one row in the `interactions` table.
Outcome is inferred from keywords in the text (e.g. "no reply", "interested", "rejected").

---

## Deployment

### Local (current)
```
DATABASE_URL=postgresql://artcrm_user:password@localhost:5432/artcrm
```

### VPS (future — Ubuntu, nginx already installed)
```
DATABASE_URL=postgresql://artcrm_user:password@vps-host:5432/artcrm
```
MongoDB is already on the VPS. Docker and Postgres are trivial to add.
The FastAPI layer runs as a systemd service behind nginx on port 443 with TLS.
All other code is identical between local and VPS.

### Ollama
Runs on Raspberry Pi cluster or laptop.
Accessed via HTTP at `OLLAMA_BASE_URL`. Same URL works from laptop or VPS
(assuming Pi cluster is network-accessible from both, or via VPN).

---

## Build Sequence
Work through phases in order. Each phase is independently usable.

| Phase | Deliverable          | Status   |
|-------|----------------------|----------|
| 1     | Database + schema    | DONE     |
| 2     | CRM Engine           | DONE     |
| 3     | Terminal CLI         | DONE     |
| 4     | Spreadsheet Import   | DONE     |
| 5     | AI Planner — Ollama  | DONE     |
| 6     | Email Composer (Claude) | DONE  |
| 7     | Email Integration    | TODO     |
| 8     | FastAPI web layer    | TODO     |
| 9     | Browser UI           | TODO     |
| 10    | Tkinter GUI          | TODO     |

Update the Status column as phases complete.

---

## Language & Localisation
- Contact outreach language is set per-contact via `preferred_language` field.
- Default for Augsburg/Bavaria area contacts: `de`
- International online platforms: `en`
- Always pass `preferred_language` to the AI prompt when drafting messages.
- Language values are extensible via the `lookup_values` table.
- Currently seeded: de, en, fr, cs, nl, es, it

---

## Key Business Rules
- Follow-up cadence: contact every 4-6 months until yes or explicit no.
- Dormant threshold: 12 months no response → status set to `dormant`.
- Both values are in app settings (config.py), never hardcoded.
- Fit scoring for galleries: assess match between artist style and gallery focus.
- Fit scoring for cafes/offices: assess suitability for showing work + upcoming shows.
- Success probability: AI estimate 0-100, stored in contacts.success_probability.
- All AI scores stored with reasoning in ai_analysis table — never a black box.
