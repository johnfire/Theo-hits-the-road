# Tech Stack

## Core

| Component   | Choice                        | Notes                                      |
|-------------|-------------------------------|--------------------------------------------|
| Language    | Python 3.12                   |                                            |
| Database    | PostgreSQL                    | Local first, same code on VPS              |
| CLI         | Click 8.1                     | `src/cli/main.py`                          |
| Testing     | pytest + pytest-bdd           | Unit, integration, BDD (Gherkin)           |
| AI (routine)| DeepSeek `deepseek-chat`      | Brief, score, suggest, recon               |
| AI (drafts) | DeepSeek `deepseek-reasoner`  | Draft letters, follow-ups                  |
| AI (optional)| Claude API (Anthropic)       | High-stakes writing, selectable via --model|
| Web layer   | FastAPI + nginx               | Phase 8+, stub only currently              |
| Email       | SMTP/IMAP (smtplib)           | Phase 7                                    |

---

## AI Model Selection

| Task                          | Default Model        |
|-------------------------------|----------------------|
| Daily brief / who to contact  | deepseek-chat        |
| Fit scoring a contact         | deepseek-chat        |
| Suggest next contacts         | deepseek-chat        |
| City recon                    | deepseek-chat        |
| Draft first contact letter    | deepseek-reasoner    |
| Draft follow-up letter        | deepseek-reasoner    |

All AI commands accept `--model claude` to switch to Claude API.

### Context Builder (before every AI call)
1. Artist bio — `data/artist_bio.txt`
2. Upcoming shows — next 90 days from `shows` table
3. Contact full record + interaction history
4. Previous AI analyses for this contact
5. Approach notes for this contact type

Always store full AI response in `ai_analysis.raw_response` for debugging.

---

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://artcrm_user:password@localhost:5432/artcrm

# AI — DeepSeek (required)
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1   # default, can omit

# AI — Claude (optional, for --model claude)
ANTHROPIC_API_KEY=sk-ant-...

# AI — defaults (can override in config/)
DEFAULT_AI_MODEL=deepseek-chat

# Email (Phase 7)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=user@example.com
SMTP_PASSWORD=...
IMAP_HOST=imap.example.com
```

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
FastAPI runs as a systemd service behind nginx on port 443 with TLS.
All code is identical between local and VPS — only env vars differ.

---

## Key Dependencies (requirements.txt)

- `psycopg2-binary` — PostgreSQL adapter
- `click` — CLI framework
- `python-dotenv` — env var loading
- `anthropic` — Claude API client
- `requests` — HTTP (DeepSeek, Overpass API)
- `pandas` + `openpyxl` — spreadsheet import
- `rapidfuzz` — fuzzy venue name matching
- `pytest` + `pytest-bdd` + `pytest-cov` — testing
