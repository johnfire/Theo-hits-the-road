# Art CRM & AI Assistant
## Architecture & Design Document

Christopher Rehm | Klosterlechfeld, Bavaria
Version 1.0 | February 2026

---

## 1. Project Overview

The Art CRM & AI Assistant replaces an informal Excel-based marketing tracker with a properly structured, AI-augmented contact management system. It is designed to help a working artist manage gallery relationships, track outreach across multiple attempts, receive AI-drafted correspondence, and get intelligent suggestions on who to contact next and when.

The system is built for a single user working primarily in German-speaking Bavaria, with outreach extending across Germany, Czechia, France and worldwide via online channels. All language-sensitive features are configurable per-contact.

> **Design Philosophy:** Build modular, build local first. Every component is independently replaceable. The local version and the server version share identical code — only the connection strings change.

### 1.1  What the Spreadsheet Was Doing

A review of the existing spreadsheet (art-marketing.xlsx) revealed 13 sheets covering:

- Contacts and leads — ~593 rows, the core CRM data
- Current channels — active and prospective gallery relationships
- Show dates — upcoming exhibition pipeline for 2025-2026
- Online presence — platforms, follower counts, commission rates
- Social media stats — posts and followers across all platforms
- Supply inventory, painting ideas, live painting notes, helpers, funding options

The contact history was tracked using five flat columns (1st try through 5th try), which does not scale. Contact statuses, types, and notes were inconsistently named. There was no automation, no reminders, and no AI assistance.

### 1.2  Goals of the New System

- Replace flat spreadsheet contact tracking with a proper relational database
- Add unlimited interaction history per contact (replacing the 5-column limit)
- AI-assisted decision making: who to contact, when, and with what message
- AI-drafted outreach letters and follow-ups, in the correct language per contact
- Email integration: read and send from within the app
- Show schedule awareness: AI factors in upcoming exhibitions when prioritising
- Local-first, server-ready: runs on laptop, deploys to VPS without code changes
- Extensible everywhere: types, subtypes, statuses, languages all user-configurable

---

## 2. System Architecture

The system is divided into three layers: Presentation, Application, and Data. Each layer communicates with the next through a defined interface, making it straightforward to add new presentation surfaces (browser, desktop GUI) without touching the application or data logic.

### 2.1  Layer Diagram

```
PRESENTATION LAYER
Terminal CLI  |  Browser UI (FastAPI, later)  |  Tkinter GUI (later)
                    ▼  Service Interface  ▼
APPLICATION LAYER
CRM Engine  |  AI Planner  |  Email Composer  |  Event Bus
                   ▼  Repository Interface  ▼
DATA LAYER
PostgreSQL  |  File Store (drafts, AI context, bio)
```

### 2.2  The Event Bus

All three application modules communicate through a lightweight internal event bus rather than calling each other directly. This is the key architectural decision that keeps the modules decoupled and individually replaceable.

When the CRM Engine records a new interaction, it emits a `contact_updated` event. The AI Planner listens for that event and schedules a re-analysis. When the AI Planner produces a suggestion, it emits a `suggestion_ready` event. The Email Composer listens and can pre-draft a message. No module imports another directly.

> **Extensibility Note:** Adding a new module (e.g. a social media tracker, an artwork inventory link, or a calendar sync) means writing one listener and one emitter. No existing module code is touched.

| Event | Emitted By | Handled By |
| --- | --- | --- |
| `contact_created` | CRM Engine | AI Planner (schedule analysis) |
| `contact_updated` | CRM Engine | AI Planner (re-score contact) |
| `interaction_logged` | CRM Engine | AI Planner (update next action date) |
| `show_scheduled` | CRM Engine | AI Planner (reprioritise nearby contacts) |
| `suggestion_ready` | AI Planner | Email Composer, CLI display |
| `draft_ready` | Email Composer | CLI display, Browser UI |
| `email_sent` | Email Composer | CRM Engine (auto-log interaction) |

---

## 3. Data Layer

### 3.1  Database Choice: PostgreSQL

PostgreSQL is the right tool here. The data is inherently relational: contacts have many interactions, shows link to contacts, AI analyses belong to contacts. PostgreSQL gives us referential integrity, powerful querying, and a clear migration path from local to the VPS. SQLite could serve as a development fallback.

> **Local vs VPS:** The only configuration difference is the `DATABASE_URL` environment variable. All SQL code is identical in both environments.

### 3.2  Extensibility Strategy

All fields that represent a category (type, subtype, status, language, etc.) are stored as `VARCHAR` rather than `ENUM`. A companion lookup table holds the valid values for each category. New values are added by inserting a row into the lookup table, with no schema migration required.

```sql
-- Lookup table: stores all extensible value sets
CREATE TABLE lookup_values (
    id          SERIAL PRIMARY KEY,
    category    VARCHAR(60)  NOT NULL,   -- e.g. "contact_type", "status", "language"
    value       VARCHAR(60)  NOT NULL,
    label_de    VARCHAR(120),            -- German display label
    label_en    VARCHAR(120),            -- English display label
    sort_order  INTEGER DEFAULT 0,
    active      BOOLEAN DEFAULT TRUE,
    UNIQUE (category, value)
);
```

Initial values loaded at setup time include:

| Category | Initial Values |
| --- | --- |
| `contact_type` | gallery, cafe, hotel, office, corporate, coworking_space, restaurant, museum, person |
| `contact_subtype` | upscale, hippy, commercial, contemporary, traditional, tourist, local |
| `contact_status` | cold, contacted, meeting, proposal, accepted, rejected, dormant, on_hold |
| `language` | de, en, fr, cs, nl, es, it |
| `interaction_method` | email, in_person, phone, letter, social_media |
| `interaction_outcome` | no_reply, interested, rejected, meeting_set, proposal_requested, accepted, left_material |
| `show_status` | possible, confirmed, completed, cancelled |

All categories are extensible — new values are a single `INSERT` into `lookup_values`.

### 3.3  Core Schema

#### contacts

```sql
CREATE TABLE contacts (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(200) NOT NULL,
    type                VARCHAR(60),      -- FK to lookup_values(contact_type)
    subtype             VARCHAR(60),      -- FK to lookup_values(contact_subtype)
    city                VARCHAR(100),
    country             CHAR(2),          -- ISO 3166-1 alpha-2
    address             TEXT,
    website             VARCHAR(300),
    email               VARCHAR(200),
    phone               VARCHAR(60),
    preferred_language  VARCHAR(10),      -- FK to lookup_values(language)
    status              VARCHAR(60),      -- FK to lookup_values(contact_status)
    fit_score           SMALLINT,         -- 0-100, AI generated
    success_probability SMALLINT,         -- 0-100, AI generated
    best_visit_time     VARCHAR(200),     -- e.g. "Mon-Tue morning"
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
```

#### interactions

```sql
CREATE TABLE interactions (
    id                SERIAL PRIMARY KEY,
    contact_id        INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
    interaction_date  DATE NOT NULL,
    method            VARCHAR(60),   -- FK to lookup_values(interaction_method)
    direction         VARCHAR(10),   -- outbound | inbound
    summary           TEXT,
    outcome           VARCHAR(60),   -- FK to lookup_values(interaction_outcome)
    next_action       TEXT,
    next_action_date  DATE,
    ai_draft_used     BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);
```

#### shows

```sql
CREATE TABLE shows (
    id               SERIAL PRIMARY KEY,
    name             VARCHAR(200),
    venue_contact_id INTEGER REFERENCES contacts(id),
    city             VARCHAR(100),
    date_start       DATE,
    date_end         DATE,
    theme            VARCHAR(200),
    status           VARCHAR(60),   -- FK to lookup_values(show_status)
    notes            TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);
```

#### ai_analysis

```sql
CREATE TABLE ai_analysis (
    id                      SERIAL PRIMARY KEY,
    contact_id              INTEGER REFERENCES contacts(id) ON DELETE CASCADE,
    analysis_date           TIMESTAMPTZ DEFAULT NOW(),
    model_used              VARCHAR(100),  -- e.g. "deepseek-reasoner" or "claude-3-5-sonnet"
    fit_reasoning           TEXT,
    suggested_approach      TEXT,
    suggested_next_contact  DATE,
    priority_score          SMALLINT,      -- 0-100 urgency for this week
    raw_response            TEXT           -- full AI output for debugging
);
```

#### people (planned, not in phase 1)

```sql
CREATE TABLE people (
    id                  SERIAL PRIMARY KEY,
    name                VARCHAR(200) NOT NULL,
    email               VARCHAR(200),
    preferred_language  VARCHAR(10),
    notes               TEXT,
    linked_contact_id   INTEGER REFERENCES contacts(id),  -- optional venue link
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 4. Application Layer

### 4.1  CRM Engine

The CRM Engine is pure Python with no AI dependency. It handles all database operations: creating and updating contacts, logging interactions, querying who is overdue for follow-up, and listing shows within a specified horizon. Being AI-free means it runs instantly and works completely offline.

Key responsibilities:

- Add, edit, search, and delete contacts
- Log every interaction (replaces the 5-column spreadsheet model)
- Query: contacts with `next_action_date` in the past
- Query: contacts within X km of an upcoming show city
- Query: contacts not touched in more than N months
- Manage shows: add, update, list by date range
- Emit events to the bus after every write operation

> **Contact follow-up cycle:** Default follow-up cadence is 4-6 months. A contact is considered dormant after 12 months of no response. Both values are configurable in app settings, not hardcoded.

### 4.2  AI Planner

The AI Planner is the intelligence layer. It assembles rich context from the database, sends it to an AI model, stores the analysis, and emits a `suggestion_ready` event. It uses two backends, selectable per task.

| Task | Preferred Model | Reason |
| --- | --- | --- |
| Daily brief / who to contact this week | DeepSeek (deepseek-chat) | Fast, low cost, private for routine tasks |
| Fit scoring a new contact | DeepSeek (deepseek-chat) | Routine analysis, runs in background |
| First contact letter to a gallery | DeepSeek (deepseek-reasoner) | High stakes, reasoning quality matters |
| Follow-up proposal draft | DeepSeek (deepseek-reasoner) | Nuanced, formal writing required |
| Reprioritising after a show is added | DeepSeek (deepseek-chat) | Computational, not creative |

#### The Context Builder

Before every AI call, the Context Builder assembles the prompt. It pulls from multiple tables and from the file store to give the model everything it needs to make a good decision:

- Artist biography and style notes (from file store)
- Upcoming shows in the next 90 days
- The contact's full record: type, subtype, city, website, notes
- Full interaction history for that contact
- Previous AI analyses for that contact
- The artist's preferred approach for that contact type (gallery vs. office vs. café)

> **On fit scoring for galleries:** The AI is told: "This artist works in watercolour, oil, and acrylic. Styles include landscape, cityscape, fantasy, surreal, botanical, and Japanese woodblock print influence. Given the gallery's known focus and website content, how well does this match?" The `fit_score` reflects this reasoning.

### 4.3  Email Composer

The Email Composer takes an AI-drafted message and handles sending. Language is read from the contact's `preferred_language` field and passed to the AI prompt automatically. The module supports both SMTP (for sending) and IMAP (for reading incoming replies, which can be logged as interactions automatically).

- Drafts are stored in the file store before sending
- Sent emails are auto-logged as interactions in the CRM Engine via the event bus
- Language is per-contact — German for Augsburg galleries, English for international online platforms, French for French contacts, etc.
- Templates are stored as text files, editable without code changes

---

## 5. Presentation Layer

### 5.1  Terminal CLI (Phase 1)

The terminal CLI is the first and primary interface. It is clean and command-driven, structured to be discoverable without documentation. All operations map to simple commands.

```
crm contacts list              -- list all contacts with status
crm contacts add               -- interactive add wizard
crm contacts show <id>         -- full record + interaction history
crm contacts log <id>          -- log a new interaction
crm brief                      -- AI daily brief: who to contact this week
crm draft <id>                 -- AI draft an outreach message for contact
crm send <id>                  -- send a drafted message by email
crm shows list                 -- list upcoming shows
crm shows add                  -- add a show
crm import xlsx <file>         -- import from spreadsheet (see Section 7)
```

### 5.2  Browser UI (Phase 2 — FastAPI)

Adding the browser UI requires writing a FastAPI application that wraps the same Service Interface the CLI uses. No application or data layer code changes. FastAPI sits behind nginx on the VPS, or runs on localhost on the laptop.

> **Why FastAPI:** It is Python, async-native, auto-generates API documentation, and is the most natural fit with the existing Python codebase. It is production-grade behind nginx without additional tooling.

### 5.3  Tkinter GUI (Phase 3 — optional)

A native desktop GUI using Tkinter requires no server, no browser, and no network. It calls the same Service Interface as the CLI and browser. Useful for offline laptop use with a richer visual experience. This is the lowest-priority surface and is included in the plan for completeness.

---

## 6. Local → VPS Deployment

### 6.1  What Changes Between Local and Server

Because the architecture is environment-agnostic, the migration is configuration-only. No code is rewritten.

| Component | Local (laptop) | VPS (Ubuntu + nginx) |
| --- | --- | --- |
| PostgreSQL | localhost:5432 | VPS IP:5432 (or socket) |
| `DATABASE_URL` | `postgresql://user:pw@localhost/artcrm` | `postgresql://user:pw@vps-host/artcrm` |
| FastAPI | localhost:8000 (optional) | Behind nginx on port 443, TLS |
| DeepSeek | DEEPSEEK_API_KEY env var | Same env var, set in systemd service |
| Claude API | ANTHROPIC_API_KEY env var | Same env var, set in systemd service |
| File store | `~/artcrm/files/` | `/var/artcrm/files/` or Docker volume |

### 6.2  Ollama / Pi Cluster (Legacy Note)

The original design used a Raspberry Pi cluster running Ollama for local AI. This was replaced with DeepSeek in February 2026. The Pi cluster reference remains here for context. If a local-only AI backend is required in future, Ollama can be re-added via the `ai_client.py` module without changing any other code.

---

## 7. Spreadsheet Import Plan

### 7.1  Overview

The existing spreadsheet contains years of accumulated contact data, show history, online channel tracking, and ideas. The import process is careful, auditable, and re-runnable. It is not a one-time migration — it can be re-run if the spreadsheet is updated before the app is in full use.

### 7.2  Sheet Mapping

| Sheet | Maps To | Notes |
| --- | --- | --- |
| contacts & leads | contacts + interactions | Core import. 5 attempt columns → interaction rows. Status derived from notes. ~593 rows. |
| current channels | contacts | Galleries and venues with current status. Merge with contacts sheet by name. |
| show dates | shows | Dates and venues map directly. Venue name matched to contacts by fuzzy name match. |
| on line | contacts (type=online_platform) | Each online platform is a contact of type online_platform. Follower counts go into notes. |
| stats | contacts (update) | Supplements the online sheet with follower/post counts. |
| plans | notes file | Qualitative plans stored as a structured text file, not in the DB. |
| ideas | notes file | Painting ideas stored as a plain text file for now. |
| helpers, gofundme, live painting | notes files | Reference material, stored as markdown files in the file store. |
| inventory | skipped (Phase 1) | Art supply inventory is separate — existing app covers this. |

### 7.3  Import Strategy: The 5-Column Problem

The most complex part of the import is converting the spreadsheet's 5 flat attempt columns into proper interaction rows. The import script reads each attempt column and, if the cell is non-empty, creates one interaction record with the attempt content as the summary, the date derived from context where available, and the outcome inferred from keywords in the text.

```python
# Pseudocode for the 5-column → interaction conversion:
for each row in contacts_sheet:
    contact = create_or_update_contact(row)
    for attempt_num in [1, 2, 3, 4, 5]:
        text = row[attempt_col[attempt_num]]
        if text is not empty:
            outcome = infer_outcome(text)   # uses keyword matching
            create_interaction(
                contact_id = contact.id,
                method     = "unknown",     # not recorded in spreadsheet
                summary    = text,
                outcome    = outcome,
                direction  = "outbound"
            )
```

### 7.4  Import Script Design

The import script is a standalone Python module that can be run independently of the main app. It is designed to be re-runnable: running it twice on the same spreadsheet does not create duplicate contacts. It uses name + city as a deduplication key.

- Input: path to the `.xlsx` file
- Output: populated PostgreSQL database + import report (how many created, updated, skipped, errors)
- Dry-run mode: `--dry-run` flag shows what would be imported without writing to the database
- Conflict resolution: if a contact already exists (by name + city), the import updates fields that are empty in the database but populated in the spreadsheet, and never overwrites existing data
- The import report is written to a timestamped log file for auditing

> **Re-import safety:** Because the spreadsheet may continue to be updated during the transition period, the import script must be safe to run multiple times without data loss. The name+city deduplication key ensures this.

---

## 8. Build Sequence

Each phase is independently usable before the next begins. Work stops at the end of any phase and the system is still functional.

| Phase | Deliverable | Status |
| --- | --- | --- |
| 1 | Database + schema | Done |
| 2 | CRM Engine | Done |
| 3 | Terminal CLI | Done |
| 4 | Spreadsheet Import | Done |
| 5 | AI Planner — DeepSeek | Done |
| 6 | Email Composer (Claude API) | Done |
| 7 | Email Integration | TODO |
| 8 | FastAPI web layer | TODO |
| 9 | Browser UI | TODO |
| 10 | Tkinter GUI (optional) | TODO |

---

## 9. Open Questions & Future Considerations

### 9.1  Decided

| Question | Decision |
| --- | --- |
| Database | PostgreSQL — local first, VPS later |
| AI backends | DeepSeek for routine tasks and drafts; Claude API optional for high-stakes writing |
| First UI | Terminal CLI |
| Language handling | Per-contact `preferred_language` field, all values extensible |
| Extensibility | All categorical fields via `lookup_values` table |
| Artwork inventory | Separate — existing app handles this |
| Individual collectors | `people` table defined in schema, implemented Phase 2+ |
| Follow-up cadence | 4-6 months default, configurable in app settings |
| Import deduplication | Name + city as key, never overwrites existing data |

### 9.2  Future Considerations

- Mobile access — the FastAPI layer makes this straightforward once the VPS is live
- Social media posting scheduler — the online channels data is already in the system
- Show application tracker — expand the shows table to include call-for-artists deadlines
- Gallery website scraping — automatically pull gallery focus/style from their website to feed the fit scoring AI
- PDF export of outreach portfolios — a generated PDF with selected works for a specific gallery type

---

*Art CRM & AI Assistant — Architecture Document v1.0 | Christopher Rehm | February 2026*
