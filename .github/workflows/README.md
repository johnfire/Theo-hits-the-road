# GitHub Actions CI/CD

## Workflows

### CI Pipeline (`ci.yml`)

Runs on every push to `main`/`develop` and on pull requests.

**What it does:**
1. Sets up Python 3.12
2. Installs dependencies from `requirements.txt`
3. Starts PostgreSQL test database (service container)
4. Runs database migrations
5. Runs CRM Engine tests (`scripts/test_crm.py`)
6. Optionally tests import script (if data file present)

**Database:**
- Uses PostgreSQL 15 service container
- Test database: `artcrm_test`
- User: `artcrm_admindude`
- Password: `test_password` (CI only)

**Adding More Tests:**
To add more test scripts, add steps in the workflow:
```yaml
- name: Run your test
  env:
    DATABASE_URL: postgresql://artcrm_admindude:test_password@localhost:5432/artcrm_test
  run: |
    python scripts/your_test.py
```

## Local Testing

To test the same setup locally:
```bash
# Create test database
createdb artcrm_test

# Run migrations
psql -d artcrm_test -f artcrm/db/migrations/001_initial_schema.sql
psql -d artcrm_test -f artcrm/db/migrations/002_seed_lookup_values.sql

# Run tests
DATABASE_URL=postgresql://yourusername@localhost/artcrm_test python scripts/test_crm.py
```

## Future Workflows

Potential additions:
- **Deploy** - Deploy to VPS on merge to main
- **Lint** - Code quality checks (flake8, black, mypy)
- **Security** - Dependency vulnerability scanning
- **Release** - Automated versioning and changelog
