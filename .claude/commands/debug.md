# /project:debug — Debug Workflow

## Database Issues
```bash
# Check connection
python3 -c "from src.db.connection import get_db_cursor; print('OK')"

# Check tables exist
psql -U artcrm_admindude -d artcrm -h localhost -c "\dt"

# Check lookup values loaded
psql -U artcrm_admindude -d artcrm -h localhost \
  -c "SELECT category, COUNT(*) FROM lookup_values GROUP BY category;"
```

## AI Issues
```bash
# Test DeepSeek connection
python3 -c "
from src.engine.ai_client import call_ai
print(call_ai('Say hello', model='deepseek-chat'))
"

# Check env vars are loaded
python3 -c "from src.config import DEEPSEEK_API_KEY; print('key loaded:', bool(DEEPSEEK_API_KEY))"
```

## Import Issues
```bash
# Dry run first — always
python3 scripts/import_xlsx.py --dry-run

# Check import log
ls -lt ~/logs/import_*.log | head -5
tail -50 ~/logs/import_<timestamp>.log
```

## Test Failures
```bash
# Run single test file
pytest tests/unit/test_crm.py -v

# Run with full output
pytest tests/ -v --tb=long

# Check coverage drop
pytest --cov=src --cov-report=term-missing
```

## Event Bus
```bash
# Check what events are registered
python3 -c "from src.bus.events import bus; print(bus._listeners)"
```
