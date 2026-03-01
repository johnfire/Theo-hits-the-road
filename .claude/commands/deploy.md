# /project:deploy — Deployment Steps

## Local → VPS Checklist

1. **Tests pass locally**
   ```bash
   pytest
   ```

2. **No secrets in source**
   ```bash
   git grep -r "password\|secret\|api_key" src/ scripts/
   ```

3. **Push to remote**
   ```bash
   git push origin main
   ```

4. **On VPS: pull and restart**
   ```bash
   git pull origin main
   source venv/bin/activate
   pip install -r requirements.txt
   # Apply any new migrations:
   psql -U artcrm_admindude -d artcrm -h localhost -f src/db/migrations/<new>.sql
   # Restart FastAPI service (Phase 8+):
   sudo systemctl restart artcrm
   ```

5. **Verify**
   ```bash
   scripts/crm contacts list --limit 5
   ```

## Environment Variables Required on VPS
See `.env.example` for the full list. At minimum:
- `DATABASE_URL`
- `DEEPSEEK_API_KEY`
- `ANTHROPIC_API_KEY` (optional)
