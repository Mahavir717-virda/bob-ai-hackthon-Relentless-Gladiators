# Session 04 — LLM Safety Review

**Member:** M1 (Team Leader)
**Date:** <!-- fill in date -->
**Purpose:** Audit the LLM/operator-assistance layer to ensure the model stays within its communication boundary and cannot hallucinate dispatch decisions.

---

## Bob Prompt

```text
Review the GridPilot LLM/operator-assistance design.

The LLM must:
- interpret structured outputs
- explain
- summarize
- answer operator questions

The LLM must NOT:
- invent forecasts
- calculate grid constraints
- select numerical dispatch quantities
- override optimization results

Return a risk review without modifying code.
```

---

## Bob Response Summary

<!-- Paste or summarize Bob's response here after running the session -->

---

## Files Bob Changed

None — read-only risk review session.

---

## Accepted

<!-- List risk findings accepted and actions taken -->

---

## Rejected

<!-- List anything Bob flagged that was assessed as not a real risk, and the reasoning -->

---

## Follow-up Work

<!-- e.g. add guardrails, update system prompt, add hallucination tests -->
