# Architecture Decision Records

## ADR-001: PostgreSQL over SQLite / MongoDB
**Date:** 2026-02
**Status:** Accepted
**Reason:** Data is inherently relational — contacts → interactions → shows → ai_analysis. Referential integrity matters. SQLite is a viable dev fallback but PostgreSQL is identical between local and VPS.
**Consequences:** Requires local Postgres install; `DATABASE_URL` env var required.

---

## ADR-002: Event Bus — No Direct Module Imports
**Date:** 2026-02
**Status:** Accepted
**Reason:** CRM Engine, AI Planner, and Email Composer must remain independently replaceable. Direct imports create tight coupling that breaks this.
**Consequences:** All inter-module communication via `src/bus/events.py`. Adding a new module means writing one listener and one emitter — no existing code touched.

---

## ADR-003: VARCHAR + lookup_values Over PostgreSQL ENUM
**Date:** 2026-02
**Status:** Accepted
**Reason:** ENUM changes require schema migrations. The artist will need to add new contact types, statuses, and languages as the business evolves. A lookup table makes this a single INSERT.
**Consequences:** No ENUMs anywhere in the schema. All valid values queried from `lookup_values` at runtime.

---

## ADR-004: DeepSeek Replaces Ollama (Feb 2026)
**Date:** 2026-02
**Status:** Accepted
**Reason:** Ollama on Pi cluster was unreliable for daily use. DeepSeek API offers comparable quality at low cost with no infrastructure to maintain.
**Consequences:** `DEEPSEEK_API_KEY` required. `ai_client.py` handles both DeepSeek and Claude. Ollama can be re-added via `ai_client.py` without touching other code if needed.

---

## ADR-005: src/ as Package Name
**Date:** 2026-03
**Status:** Accepted
**Reason:** Renamed from `artcrm/` to `src/` for consistency with the CAR standard project structure.
**Consequences:** All imports use `from src.X import Y`. This is unconventional for Python packages but consistent across the codebase.

---

## ADR-006: Name + City as Import Dedup Key
**Date:** 2026-02
**Status:** Accepted
**Reason:** The spreadsheet has no unique IDs. Name alone has collisions (e.g. two "Café Central" in different cities). Name + city is reliable enough for the dataset.
**Consequences:** Import script is safe to re-run. Never creates duplicates. Never overwrites existing DB data.

---

## Key Business Rules

- Follow-up cadence: contact every 4-6 months until yes or explicit no.
- Dormant threshold: 12 months no response → status `dormant`.
- Both values are in `src/config.py`, never hardcoded.
- Fit scoring for galleries: match between artist style and gallery focus.
- Fit scoring for cafes/offices: suitability for showing work + upcoming shows.
- Success probability: AI estimate 0-100, stored in `contacts.success_probability`.
- All AI scores stored with reasoning in `ai_analysis` — never a black box.
