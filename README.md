# Art CRM - Gallery & Contact Management System

A Python-based CRM and AI assistant for artists managing gallery relationships, exhibition scheduling, and venue outreach.

## Features

- **Contact Management** - Track galleries, cafes, co-working spaces, and online platforms
- **Interaction History** - Log all communications and follow-ups
- **Exhibition Scheduling** - Manage show dates and venues
- **AI Planning** - Daily briefs and fit scoring using Ollama (local AI)
- **AI Letter Drafting** - Professional outreach letters using Claude API
- **Lead Generation** - Automated discovery of venues via Google Maps and OpenStreetMap

## Quick Start

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
psql $DATABASE_URL -f artcrm/db/migrations/001_initial_schema.sql
psql $DATABASE_URL -f artcrm/db/migrations/002_seed_lookup_values.sql
psql $DATABASE_URL -f artcrm/db/migrations/003_add_lead_unverified_status.sql

# Use the CLI
./crm --help
```

## All Available Commands

### Contact Management

#### `./crm contacts list`
List all contacts with optional filtering.

**Options:**
- `--type TEXT` - Filter by type (gallery, cafe, coworking, etc.)
- `--status TEXT` - Filter by status (cold, contacted, meeting, lead_unverified, etc.)
- `--city TEXT` - Filter by city
- `--limit INTEGER` - Max results (default: 50)

**Examples:**
```bash
./crm contacts list
./crm contacts list --type gallery --city Augsburg
./crm contacts list --status lead_unverified
./crm contacts list --limit 100
```

#### `./crm contacts show <contact_id>`
Show full details for a specific contact including interaction history.

**Examples:**
```bash
./crm contacts show 42
```

#### `./crm contacts add`
Interactive wizard to add a new contact.

**Examples:**
```bash
./crm contacts add
```

#### `./crm contacts log <contact_id>`
Log an interaction (email, in-person visit, phone call, etc.) with a contact.

**Examples:**
```bash
./crm contacts log 42
```

#### `./crm contacts edit <contact_id>`
Edit a contact's information.

**Options:**
- `--status TEXT` - Update status
- `--email TEXT` - Update email
- `--website TEXT` - Update website
- `--notes TEXT` - Update notes

**Examples:**
```bash
./crm contacts edit 42 --status contacted
./crm contacts edit 42 --email gallery@example.com
./crm contacts edit 42 --notes "Interested in watercolors"
```

---

### Exhibition Management

#### `./crm shows list`
List all exhibitions and shows.

**Options:**
- `--status TEXT` - Filter by status (possible, confirmed, completed)
- `--upcoming` - Show only upcoming shows

**Examples:**
```bash
./crm shows list
./crm shows list --status confirmed
./crm shows list --upcoming
```

#### `./crm shows add`
Interactive wizard to add a new show.

**Examples:**
```bash
./crm shows add
```

---

### Queries & Reports

#### `./crm overdue`
Show contacts with overdue follow-ups (next_action_date in the past).

**Examples:**
```bash
./crm overdue
```

#### `./crm dormant`
Show contacts with no activity in 12+ months.

**Examples:**
```bash
./crm dormant
```

---

### AI Features

#### `./crm brief`
Generate AI daily brief using Ollama - suggests who to contact this week and why.

**Examples:**
```bash
./crm brief
```

**Requires:** Ollama running locally (`ollama serve`)

#### `./crm score <contact_id>`
AI evaluates how well a contact fits your art (0-100 score) using Ollama.

**Examples:**
```bash
./crm score 42
```

**Requires:** Ollama running locally

#### `./crm suggest`
AI suggests next contacts to reach out to, prioritizing by fit score and timing.

**Options:**
- `--limit INTEGER` - Number of suggestions (default: 5)

**Examples:**
```bash
./crm suggest
./crm suggest --limit 10
```

**Requires:** Ollama running locally

#### `./crm draft <contact_id>`
Draft a professional first contact letter using Claude API.

**Options:**
- `--language TEXT` - Override contact's language (de/en/fr)
- `--no-portfolio` - Exclude portfolio link

**Examples:**
```bash
./crm draft 42
./crm draft 42 --language en
./crm draft 42 --no-portfolio
```

**Requires:** `ANTHROPIC_API_KEY` in `.env`

#### `./crm followup <contact_id>`
Draft a follow-up letter based on previous interactions using Claude API.

**Options:**
- `--language TEXT` - Override contact's language (de/en/fr)

**Examples:**
```bash
./crm followup 42
./crm followup 42 --language de
```

**Requires:** `ANTHROPIC_API_KEY` in `.env`

---

### Lead Generation (Phase 6-Alpha)

#### `./crm recon <city> [country]`
Scout a city for potential leads (galleries, cafes, co-working spaces) using Google Maps and OpenStreetMap.

**Arguments:**
- `city` - City name (e.g., "Rosenheim")
- `country` - Country code (default: "DE")

**Options:**
- `--type TEXT` - Business types to search (can be used multiple times)
  - Valid types: `gallery`, `cafe`, `coworking`
- `--radius FLOAT` - Search radius in kilometers (default: 10)
- `--model TEXT` - AI model for enrichment: `claude` or `ollama` (default: ollama)
- `--no-google` - Skip Google Maps API
- `--no-osm` - Skip OpenStreetMap

**Examples:**
```bash
# Basic usage - all types
./crm recon Rosenheim DE

# Specific type only
./crm recon Augsburg DE --type gallery

# Multiple types
./crm recon München DE --type gallery --type cafe

# Use Claude for better AI enrichment
./crm recon Rosenheim DE --model claude

# OpenStreetMap only (no Google API key needed)
./crm recon Rosenheim DE --no-google

# Custom search radius
./crm recon Rosenheim DE --radius 20
```

**Requires:**
- `GOOGLE_MAPS_API_KEY` in `.env` (for Google Maps)
- `ANTHROPIC_API_KEY` in `.env` (if using `--model claude`)
- Ollama running locally (if using `--model ollama`)

**Output:**
- Creates contacts with status `lead_unverified`
- Saves raw JSON to `data/scout_results/`
- Shows progress bar during processing

---

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/artcrm

# AI - Ollama (local, free)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3

# AI - Claude API (paid, high-quality writing)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Lead Generation
GOOGLE_MAPS_API_KEY=your-google-maps-key-here
LEAD_SCOUT_BATCH_SIZE=20
LEAD_SCOUT_RATE_LIMIT_SECONDS=1.0

# Application Settings
TIMEZONE=Europe/Berlin
FOLLOW_UP_CADENCE_MONTHS=4
DORMANT_THRESHOLD_MONTHS=12
```

## Development

### Running tests

```bash
source venv/bin/activate
python -m pytest tests/ -q
```

Coverage report:

```bash
python -m pytest tests/ --cov=artcrm --cov-report=term-missing
```

### Pre-commit hook

A pre-commit hook is included that runs linting and the relevant tests before every commit. It blocks the commit if anything fails and shows you why.

**One-time setup** (run once per clone):

```bash
git config core.hooksPath .githooks
```

After that it runs automatically on every `git commit`. What it checks:

- **flake8** — syntax errors and undefined names on staged `.py` files
- **pytest** — the test file(s) that cover whichever source files you staged; falls back to the full suite for anything unmapped

To bypass in an emergency:

```bash
git commit --no-verify
```

## Project Structure

```
artcrm/
├── artcrm/                    # Main Python package
│   ├── db/                   # Database migrations
│   ├── models/               # Data models
│   ├── engine/               # Business logic
│   │   ├── crm.py           # CRM operations
│   │   ├── ai_planner.py    # AI planning (Ollama)
│   │   ├── email_composer.py # Letter drafting (Claude)
│   │   └── lead_scout.py    # Lead generation
│   ├── bus/                  # Event bus
│   ├── cli/                  # Terminal interface
│   └── config.py            # Configuration
├── data/                     # Data files
│   ├── drafts/              # Generated letters
│   └── scout_results/       # Lead generation results
├── docs/                     # Documentation
├── scripts/                  # Utility scripts
└── tests/                    # Test files
```

## Documentation

- **[CLAUDE.md](CLAUDE.md)** - Complete project architecture and developer guide
- **[TODO.md](TODO.md)** - Roadmap and future enhancements
- **[docs/GOOGLE_MAPS_SETUP.md](docs/GOOGLE_MAPS_SETUP.md)** - Google Maps API setup guide

## Development Status

| Phase | Feature                  | Status |
|-------|--------------------------|--------|
| 1     | Database + Schema        | ✅ DONE |
| 2     | CRM Engine               | ✅ DONE |
| 3     | Terminal CLI             | ✅ DONE |
| 4     | Spreadsheet Import       | ✅ DONE |
| 5     | AI Planner (Ollama)      | ✅ DONE |
| 6     | Email Composer (Claude)  | ✅ DONE |
| 6α    | Lead Generation          | ✅ DONE |
| 7     | Email Integration        | 📋 TODO |
| 8     | FastAPI Web Layer        | 📋 TODO |
| 9     | Browser UI               | 📋 TODO |
| 10    | Desktop GUI              | 📋 TODO |

## License

Private project for Christopher Rehm.

## Support

For issues or questions, check [TODO.md](TODO.md) for known issues and planned features.
