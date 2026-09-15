# `scripts` — Developer Tools & Pipeline Automation

## Module Overview
Automation scripts for local development, data preparation, testing, and IBM Bob setup.

- **Key Scripts:**
  - `setup_bob_mcp.ps1` / `.sh` — Registers GridPilot API MCP server with the IBM Bob CLI.
  - `seed_database.py` — Ingests baseline test datasets into PostgreSQL.
  - `validate_submission.py` — Verifies `submission.yaml`, documentation links, and demo assets.
  - `run_deterministic_scenario.py` — Executes the full 15-minute pipeline replay.
- **Owned By:** Member 1 (Team Leader)
- **Branch:** `leader/integration`
