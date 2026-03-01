# Changelog

All notable changes to this project will be documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### In Progress
- Phase 7: Email Integration (SMTP/IMAP)

---

## [0.6.0] — 2026-03

### Changed
- Renamed package `artcrm/` → `src/` for consistency with project structure standard
- Converted `docs/art_crm_architecture.docx` to Markdown
- Reorganised `docs/` into `architecture/`, `deployment/`, `guides/` subdirectories
- Moved `.claude/CLAUDE.md` from project root; split into context files
- Added `config/default.json`, `tmp/`, `CHANGELOG.md`, `LICENSE`
- Moved `crm` shell script to `scripts/crm`; fixed stale import path

### Added
- BDD test suite (`tests/bdd/`) with pytest-bdd and Gherkin feature files
- `.claude/context/` — architecture, decisions, stack, gotchas
- `.claude/commands/` — review, deploy, debug slash commands

---

## [0.5.0] — 2026-02

### Added
- Phase 6: Email Composer using Claude API / DeepSeek for draft letters and follow-ups
- Phase 5: AI Planner with DeepSeek integration (replaced Ollama)
- `crm draft <id>` and `crm followup <id>` commands
- Model selection (`--model`) on all AI commands

### Changed
- Replaced Ollama with DeepSeek API (`deepseek-chat`, `deepseek-reasoner`)
- All logs moved from `logs/` (project root) to `~/logs/`

### Security
- Hardcoded DB credentials removed from `config.py` default
- SQL injection guarded with column allowlists
- `os.system()` replaced with `subprocess.run()`
- `requests` bumped to 2.32.4 (CVE-2024-35195)
- `tqdm` bumped to 4.66.4 (CVE-2024-34062)

---

## [0.4.0] — 2026-02

### Added
- Phase 4: Spreadsheet import (`scripts/import_xlsx.py`)
- Import from `data/art-marketing.xlsx` — contacts, interactions, shows, online channels
- 5-column → interaction row conversion
- `--dry-run` flag, dedup by name+city, timestamped import log

---

## [0.3.0] — 2026-02

### Added
- Phase 3: Terminal CLI (`src/cli/main.py`) with Click
- `crm contacts list/add/show/edit/log`
- `crm shows list/add`
- `crm overdue`, `crm dormant`
- `crm recon <city>` — lead scouting via OpenStreetMap

---

## [0.2.0] — 2026-02

### Added
- Phase 2: CRM Engine (`src/engine/crm.py`)
- Contacts CRUD, interaction logging, show management
- Event bus (`src/bus/events.py`)
- Full test suite (unit + integration)

---

## [0.1.0] — 2026-02

### Added
- Phase 1: Database schema and migrations
- PostgreSQL setup, all tables, `lookup_values` seeded
- `src/models/` dataclasses, `src/config.py`, `src/db/connection.py`
