# Phase 1: Database + Schema — COMPLETE ✓

**Completed:** 2026-02-12
**Status:** Ready to use

## What Was Delivered

### 1. Project Structure
Created the complete directory structure as specified in CLAUDE.md:

```
artcrm/
├── artcrm/               ← Main Python package
│   ├── db/
│   │   └── migrations/   ← SQL migration files
│   ├── models/
│   ├── engine/
│   ├── bus/
│   ├── services/
│   ├── cli/
│   └── api/
├── docs/                 ← Documentation
│   ├── art_crm_architecture.docx
│   ├── DATABASE_SETUP.md
│   └── PHASE_1_COMPLETE.md
├── data/                 ← Source data
│   ├── art-marketing.xlsx
│   └── notes/
├── scripts/              ← Utility scripts
└── tests/
    ├── unit/
    └── integration/
```

### 2. Database Schema Files

#### [001_initial_schema.sql](../artcrm/db/migrations/001_initial_schema.sql)
Complete database schema with:
- **schema_migrations** table with full tracking (timestamps, checksums, rollback capability)
- **lookup_values** table for extensible categorical fields
- **contacts** table with soft deletes
- **interactions** table with full history tracking
- **shows** table for exhibition pipeline
- **ai_analysis** table for storing AI reasoning
- **people** table (defined for Phase 2+)
- Automatic `updated_at` triggers for contacts, shows, and people
- Comprehensive indexes for performance
- Full-text search index for contacts (German language)
- Verification checks to ensure migration success

#### [002_seed_lookup_values.sql](../artcrm/db/migrations/002_seed_lookup_values.sql)
Minimal seed data for 7 categories:
- **contact_type**: 10 values (gallery, cafe, hotel, office, restaurant, coworking_space, online_platform, museum, corporate, other)
- **contact_subtype**: 7 values (upscale, hippy, commercial, contemporary, traditional, tourist, local)
- **contact_status**: 8 values (cold, contacted, meeting, proposal, accepted, rejected, dormant, on_hold)
- **language**: 7 values (de, en, fr, cs, nl, es, it)
- **interaction_method**: 6 values (email, in_person, phone, letter, social_media, unknown)
- **interaction_outcome**: 9 values (no_reply, interested, rejected, meeting_set, proposal_requested, accepted, left_material, follow_up_needed, not_interested)
- **show_status**: 4 values (possible, confirmed, completed, cancelled)

All values include German and English labels for UI flexibility.

### 3. Configuration Files

#### [.env.example](../.env.example)
Environment variable template with:
- Database credentials: `artcrm` / `artcrm_admindude` / `aw4e0rfeA1!Q`
- Timezone: Europe/Berlin
- Ollama configuration (placeholder for Phase 5)
- Claude API configuration (placeholder for Phase 6)
- Email configuration (placeholder for Phase 7)
- Application settings (follow-up cadence, dormant threshold)

#### [requirements.txt](../requirements.txt)
Python dependencies for Phase 1:
- `psycopg2-binary==2.9.9` (PostgreSQL adapter)
- `python-dotenv==1.0.1` (Environment variables)
- Future dependencies listed but commented out

### 4. Documentation

#### [DATABASE_SETUP.md](DATABASE_SETUP.md)
Complete PostgreSQL installation and setup guide including:
- Ubuntu/Debian installation instructions
- Database and user creation steps
- Connection testing procedures
- pg_hba.conf configuration for password auth
- Virtual environment setup
- Manual migration execution
- Verification queries
- Troubleshooting guide
- VPS deployment notes
- Backup and restore commands

#### [migrations/README.md](../artcrm/db/migrations/README.md)
Migration documentation including:
- How to run migrations manually
- Verification queries
- Soft delete explanation
- Extensibility guide (adding new lookup values)
- Rollback procedures
- Template for future migrations
- Troubleshooting guide

## Key Features Implemented

### Soft Deletes
All tables include `deleted_at TIMESTAMPTZ` column:
- Records are never physically deleted
- Queries filter with `WHERE deleted_at IS NULL`
- Preserves historical data for audit and recovery

### Extensibility
The `lookup_values` table eliminates the need for schema migrations when adding new categorical values:
```sql
-- Add a new contact type without ALTER TABLE
INSERT INTO lookup_values (category, value, label_de, label_en, sort_order)
VALUES ('contact_type', 'library', 'Bibliothek', 'Library', 85);
```

### Automatic Timestamps
Database triggers automatically update `updated_at` on contacts, shows, and people tables.

### Full Migration Tracking
The `schema_migrations` table tracks:
- Migration name
- Applied timestamp
- Checksum for verification
- Execution time (for future automated runner)
- Rollback capability (for future automated runner)

### Berlin Timezone
All `TIMESTAMPTZ` columns respect the Europe/Berlin timezone configuration.

### Performance Optimization
Comprehensive indexes on:
- Foreign keys
- Date fields for range queries
- Status fields for filtering
- Full-text search on contact names and notes (German language)

## How to Use

### 1. Install PostgreSQL
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

### 2. Create Database
```bash
sudo -u postgres psql
CREATE USER artcrm_admindude WITH PASSWORD 'aw4e0rfeA1!Q';
CREATE DATABASE artcrm OWNER artcrm_admindude;
GRANT ALL PRIVILEGES ON DATABASE artcrm TO artcrm_admindude;
\q
```

### 3. Run Migrations
```bash
cd /home/christopher/programming/theo-hits-the-road

psql -U artcrm_admindude -d artcrm -h localhost -f artcrm/db/migrations/001_initial_schema.sql
psql -U artcrm_admindude -d artcrm -h localhost -f artcrm/db/migrations/002_seed_lookup_values.sql
```

### 4. Verify
```bash
psql -U artcrm_admindude -d artcrm -h localhost -c "\dt"
psql -U artcrm_admindude -d artcrm -h localhost -c "SELECT category, COUNT(*) FROM lookup_values GROUP BY category;"
```

## Testing Checklist

- [ ] PostgreSQL is installed and running
- [ ] Database `artcrm` exists
- [ ] User `artcrm_admindude` can connect
- [ ] Migration 001 runs without errors
- [ ] Migration 002 runs without errors
- [ ] All 7 tables exist (`\dt` shows them)
- [ ] Lookup values are seeded (7 categories)
- [ ] Triggers are created (3 triggers for updated_at)
- [ ] Indexes are created (check with `\di`)

## What's Next: Phase 2 Options

Now that the database is ready, you have three options for Phase 2:

### Option A: Build CRM Engine (Original Plan — Phase 2)
Build the pure Python module for all database operations:
- Contact CRUD operations
- Interaction logging
- Show management
- Query builders (overdue contacts, nearby venues)
- Event bus skeleton
- No AI, no UI — just the data layer

**Pros:**
- Follows original plan
- Tests database schema thoroughly
- Foundation for everything else

**Cons:**
- Can't see data visually until Phase 3
- Abstract without UI to test with

### Option B: Build Import Script First (Reordered — Phase 4 before Phase 2)
Build the spreadsheet import to populate the database with real data:
- Import 593 contacts from art-marketing.xlsx
- Convert 5-column attempts to interactions
- Import show dates
- Import online channels
- Real data to develop against

**Pros:**
- Immediate value — your data in the database
- Real data to test CRM Engine and CLI against
- Validates schema with actual use case
- You mentioned "before" for import timing

**Cons:**
- Builds "top down" instead of "bottom up"
- May need CRM Engine functions for deduplication logic

### Option C: Build Minimal CLI Early
Build a bare-bones CLI just to see the data:
- List contacts (read-only query)
- Show contact details
- List shows
- Query lookup values
- Simple read-only operations

**Pros:**
- Visual feedback immediately
- Tests database connection
- Validates schema is usable
- Motivating to see progress

**Cons:**
- Minimal functionality
- Will need significant expansion in Phase 3

## Recommendation

Based on your preference ("import then clean up", "before"), I recommend:

**Option B: Build Import Script Next**

This will:
1. Get your real data into the system
2. Validate the schema handles actual data
3. Give us 593 contacts to test against when building CRM Engine
4. Let you start using the database immediately
5. Reveal any schema issues early

Then we build CRM Engine (Phase 2) with real data to test against, followed by CLI (Phase 3) with populated database.

## Your Call

Which option would you like to pursue next?
- **A**: CRM Engine (Phase 2 as planned)
- **B**: Import Script (Phase 4 early) ← Recommended
- **C**: Minimal CLI for visibility
- **Other**: Something else?

---

**Phase 1 Complete.** Waiting for direction on Phase 2.
