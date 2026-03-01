# /project:review — Code Review Checklist

Run through these before committing or raising a PR.

## Security
- [ ] No hardcoded credentials, API keys, or passwords
- [ ] No f-string SQL — use parameterised queries or column allowlists
- [ ] No `os.system()` — use `subprocess.run()` with a list, not a shell string
- [ ] External HTTP calls use `verify=True` and reasonable timeouts

## Architecture
- [ ] No direct cross-module imports — all inter-module calls go through the event bus
- [ ] No business logic in CLI handlers — logic lives in engine/ or services/
- [ ] No ENUM types added to the schema — use VARCHAR + lookup_values

## Code Quality
- [ ] New functions have tests (unit or BDD scenario)
- [ ] Logs go to `~/logs/` — no hardcoded log paths
- [ ] No new project-level logs/ directory
- [ ] `flake8` passes — run `flake8 src/ scripts/`

## Tests
- [ ] `pytest` passes with no failures
- [ ] Coverage hasn't dropped significantly

## Docs
- [ ] CLAUDE.md build sequence updated if a phase completed
- [ ] `.claude/context/decisions.md` updated if a significant decision was made
