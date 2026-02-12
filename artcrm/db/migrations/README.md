# Database Migrations

## Overview

This directory contains SQL migration files for the Art CRM database schema. Migrations must be run in numerical order.

## Phase 1: Manual Migration

For Phase 1, migrations are run manually using `psql`. An automated migration runner will be built in a later phase.

## Migration Files

| File | Description | Status |
|------|-------------|--------|
| 001_initial_schema.sql | Creates all core tables, indexes, and triggers | Ready |
| 002_seed_lookup_values.sql | Seeds extensible lookup values | Ready |

## Running Migrations

### Prerequisites

1. PostgreSQL is installed and running
2. Database and user are created (see [DATABASE_SETUP.md](../../../docs/DATABASE_SETUP.md))
3. You have the database credentials

### Step-by-Step

```bash
# 1. Ensure you're in the project root directory
cd /path/to/theo-hits-the-road

# 2. Run migration 001 - Initial Schema
psql -U artcrm_admindude -d artcrm -h localhost -f artcrm/db/migrations/001_initial_schema.sql

# You should see:
# NOTICE:  Migration 001 successful: all tables created

# 3. Run migration 002 - Seed Lookup Values
psql -U artcrm_admindude -d artcrm -h localhost -f artcrm/db/migrations/002_seed_lookup_values.sql

# You should see:
# NOTICE:  Category contact_type has 10 values
# NOTICE:  Category contact_subtype has 7 values
# ... (more categories)
# NOTICE:  Migration 002 successful: all lookup values seeded

# 4. Verify the setup
psql -U artcrm_admindude -d artcrm -h localhost -c "\dt"

# You should see all tables listed
```

### Verification Queries

After running migrations, verify the setup:

```sql
-- Connect to database
psql -U artcrm_admindude -d artcrm -h localhost

-- Check all tables exist
\dt

-- Check migration history
SELECT migration_name, applied_at, checksum FROM schema_migrations ORDER BY applied_at;

-- Check lookup values are seeded
SELECT category, COUNT(*) as count
FROM lookup_values
WHERE deleted_at IS NULL
GROUP BY category
ORDER BY category;

-- Check sample lookup values
SELECT category, value, label_de, label_en
FROM lookup_values
WHERE category = 'contact_type'
ORDER BY sort_order;

-- Verify triggers are created
SELECT trigger_name, event_object_table
FROM information_schema.triggers
WHERE trigger_schema = 'public';
```

## Migration Features

### Soft Deletes
All tables include a `deleted_at` column for soft deletion. Records are never physically deleted in production.

### Automatic Timestamps
Tables with `updated_at` columns automatically update this timestamp on any UPDATE via database triggers.

### Extensibility
The `lookup_values` table allows adding new categorical values without schema changes. To add a new contact type:

```sql
INSERT INTO lookup_values (category, value, label_de, label_en, sort_order)
VALUES ('contact_type', 'library', 'Bibliothek', 'Library', 85);
```

### Migration Tracking
The `schema_migrations` table tracks:
- Migration name and when it was applied
- Checksum for verification
- Execution time (populated by future automated runner)
- Rollback capability (populated by future automated runner)

## Rollback (Manual)

To rollback migrations, you need to manually drop objects in reverse order:

```bash
# WARNING: This will delete all data!

# Drop all tables (this will cascade to foreign keys)
psql -U artcrm_admindude -d artcrm -h localhost -c "
DROP TABLE IF EXISTS people CASCADE;
DROP TABLE IF EXISTS ai_analysis CASCADE;
DROP TABLE IF EXISTS shows CASCADE;
DROP TABLE IF EXISTS interactions CASCADE;
DROP TABLE IF EXISTS contacts CASCADE;
DROP TABLE IF EXISTS lookup_values CASCADE;
DROP TABLE IF EXISTS schema_migrations CASCADE;
"
```

## Future: Automated Migration Runner

In a future phase, we will build an automated migration runner that:
- Automatically detects and runs pending migrations
- Calculates and verifies checksums
- Tracks execution time
- Supports rollback scripts
- Prevents running migrations out of order
- Works with both local and VPS deployments

## Adding New Migrations

When adding a new migration:

1. **Name it sequentially**: `003_description.sql`, `004_description.sql`, etc.
2. **Record it**: First line should insert into `schema_migrations`
3. **Be idempotent**: Use `IF NOT EXISTS` where possible
4. **Add verification**: Include verification queries at the end
5. **Document it**: Add it to the table above
6. **Test it**: Run on a test database first

Example template:

```sql
-- Migration: 003_add_artwork_table.sql
-- Description: Add artwork inventory tracking
-- Date: 2026-XX-XX

INSERT INTO schema_migrations (migration_name, checksum)
VALUES ('003_add_artwork_table.sql', 'placeholder');

CREATE TABLE IF NOT EXISTS artworks (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

-- Verification
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'artworks') THEN
        RAISE EXCEPTION 'Migration 003 failed: artworks table not created';
    END IF;
    RAISE NOTICE 'Migration 003 successful';
END $$;
```

## Troubleshooting

### "relation already exists"
You may have run the migration before. Check `schema_migrations` table:
```sql
SELECT * FROM schema_migrations;
```

### "permission denied"
Ensure you're connecting as `artcrm_admindude` and the user has proper grants.

### "database does not exist"
Run the database setup steps in [DATABASE_SETUP.md](../../../docs/DATABASE_SETUP.md) first.

### Migrations run out of order
Migrations must be run in numerical order. Check `schema_migrations` to see what has run, then run missing migrations in sequence.
