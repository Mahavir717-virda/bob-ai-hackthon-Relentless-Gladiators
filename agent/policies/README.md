# `agent/policies` — Guardrail Policies & Verification Invariants

## Module Overview
Defines non-negotiable safety guardrails, response filters, and deterministic invariant checks for AI agent interactions.

- **Non-Negotiable Policies:**
  1. **Ground Truth Invariant:** LLMs never alter numbers produced by LightGBM, XGBoost, or OR-Tools.
  2. **Feasibility Invariant:** If optimization status is `infeasible`, the agent must never recommend unauthorized dispatches.
  3. **No Hallucinations Invariant:** Clear notation of missing telemetry or sensor dropouts.
  4. **No Direct Control Invariant:** GridPilot is a decision-support advisory system; commands require human operator confirmation.
- **Owned By:** Member 1 (Team Leader)
- **Branch:** `leader/integration`
