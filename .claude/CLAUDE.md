# Art CRM & AI Assistant — Project Context

A Python-based CRM and AI assistant for a working artist (Christopher Rehm, Klosterlechfeld, Bavaria). Replaces an Excel spreadsheet used to track gallery outreach, show scheduling, online channels, and contact history.

**Current phase:** Phase 6 complete. Phase 7 (Email Integration) is next.

See `.claude/context/` for architecture, decisions, stack details, and gotchas.

---

## How to Run

```bash
source venv/bin/activate
python main.py          # interactive menu launcher
scripts/crm --help      # direct CLI access
pytest                  # run tests
```

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

## Do Not Touch

- `.env` — never commit secrets
- `data/art-marketing.xlsx` — source spreadsheet, do not modify
- `src/db/migrations/` — append only, never edit existing migration files

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
crm draft <id>                 AI draft first contact letter
crm followup <id>              AI draft follow-up letter
crm recon <city> [country]     Scout city for leads
crm shows list                 list upcoming shows
crm shows add                  add a show
crm overdue                    show contacts with overdue follow-ups
crm dormant                    show dormant contacts (12+ months)
```

---

## Build Sequence

| Phase | Deliverable             | Status |
|-------|-------------------------|--------|
| 1     | Database + schema       | Done   |
| 2     | CRM Engine              | Done   |
| 3     | Terminal CLI            | Done   |
| 4     | Spreadsheet Import      | Done   |
| 5     | AI Planner — DeepSeek   | Done   |
| 6     | Email Composer          | Done   |
| 7     | Email Integration       | TODO   |
| 8     | FastAPI web layer       | TODO   |
| 9     | Browser UI              | TODO   |
| 10    | Tkinter GUI             | TODO   |
