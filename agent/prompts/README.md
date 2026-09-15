# `agent/prompts` — Structured Prompt Templates

## Module Overview
Contains version-controlled prompt templates for IBM watsonx.ai and IBM Bob.

- **Key Templates:**
  1. `operator_brief.jinja2` (or `.txt`) — Synthesizes the 15-minute 8-section operator brief from structured JSON payloads.
  2. `copilot_system.jinja2` — System prompt for interactive operator Q&A enforcing the 4 architectural rules.
  3. `root_cause_explanation.jinja2` — Translates SHAP feature values into clear, factual operator explanations.
- **Architectural Rules:** Prompts strictly forbid hallucinations, inventing numerical values, altering optimizer recommendations, or claiming correlation equals causation.
- **Owned By:** Member 1 (Team Leader)
- **Branch:** `leader/integration`
