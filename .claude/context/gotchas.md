# Gotchas, Traps & Anti-Patterns

## Never use PostgreSQL ENUM types
All categorical fields use `VARCHAR` + `lookup_values` table. ENUMs require schema migrations to extend. Adding a new contact type = one INSERT into `lookup_values`. See ADR-003.

## Never import modules directly
CRM Engine, AI Planner, and Email Composer must NOT import each other. All communication goes through the event bus (`src/bus/events.py`). See ADR-002.

## Never hardcode database credentials
Always use `DATABASE_URL` from environment. The default in `src/config.py` must not contain real credentials.

## SQL injection — use column allowlists
`src/engine/crm.py` uses `_CONTACT_COLUMNS` and `_SHOW_COLUMNS` allowlists to validate column names before building dynamic UPDATE queries. Never bypass these checks. Never use f-strings to build SQL.

## Logs go to ~/logs/, not project-level logs/
The global logging convention writes all logs to `~/logs/`. The project-level `logs/` directory does not exist (gitignored). Import logs: `~/logs/import_<timestamp>.log`.

## Import script is re-runnable
`scripts/import_xlsx.py` uses name+city as a dedup key. Running it twice is safe — no duplicates, no overwrites. Always use `--dry-run` first on new data.

## The crm shell script needs the src import path
`scripts/crm` imports from `src.cli.main`. If the package is renamed again, update this script too (it's a shell script, not caught by Python linting).

## deepseek-reasoner is slow and costly — use sparingly
Default for `crm brief`, `crm score`, `crm suggest` is `deepseek-chat`. Only `crm draft` and `crm followup` default to `deepseek-reasoner`. Don't change these defaults without user intent.

## Migration files are append-only
Never edit `src/db/migrations/00X_*.sql` files that have already been applied. Add a new numbered file instead.

## The `people` table exists but is not implemented
Phase 2+ feature. The table is in the schema (migration 001). Don't add UI or engine code for it until Phase 2 is explicitly started.
