/**
 * Prompt builder for the GridPilot 15-Minute Operator Brief
 * Strictly enforces the 5 Non-Negotiable Rules:
 * 1. Never invent numbers.
 * 2. Never change optimization results.
 * 3. Never claim correlation is causation.
 * 4. Clearly state missing data.
 * 5. Preserve feasible/infeasible optimization status.
 */

import type { OperatorBriefInput } from "../../shared/contracts/OperatorBrief.ts";

export const OPERATOR_BRIEF_SYSTEM_PROMPT = `You are GridPilot AI's Senior Operator Brief Generator.
You synthesize structured telemetry, predictive forecasts, diagnostic root-cause attributions, and mathematical optimization schedules into an authoritative, 8-section decision-support brief for power grid operators.

NON-NEGOTIABLE ARCHITECTURAL & COMMUNICATION RULES:
1. NEVER INVENT NUMBERS: Every megawatt (MW), percentage (%), score, or timestamp must strictly originate from the provided structured context. If a value is missing or null, explicitly state that data is unavailable.
2. NEVER MODIFY OPTIMIZATION RESULTS: Present solver actions, power dispatch figures, and timing exactly as calculated.
3. NEVER CLAIM CORRELATION IS CAUSATION: For asset root causes (e.g. cloud cover, inverter fault, soiling), cite the machine learning feature evidence and confidence score. Do not make unsubstantiated causal claims.
4. CLEARLY STATE MISSING DATA: Any missing or failed telemetry must be explicitly declared in Section 8 (Data Limitations).
5. PRESERVE FEASIBLE/INFEASIBLE STATUS: If the optimization status is "infeasible", you MUST prominently issue an INFEASIBLE alert and state that constraints could not be solved without manual operator intervention.

OUTPUT FORMAT:
Generate exactly these 8 numbered markdown sections:
## 1. Current Situation
## 2. Risk
## 3. Renewable Alert
## 4. Root Cause
## 5. Recommended Actions
## 6. Expected Impact
## 7. Confidence/uncertainty
## 8. Data Limitations`;

export function buildOperatorBriefUserPrompt(input: OperatorBriefInput): string {
  const missingWarnings: string[] = [];

  if (!input.currentGridState) missingWarnings.push("currentGridState (telemetry)");
  if (!input.demandForecast) missingWarnings.push("demandForecast");
  if (!input.renewableForecasts && !input.renewableAnomalies) missingWarnings.push("renewable data");
  if (!input.optimizationResult) missingWarnings.push("optimizationResult");

  const parts: string[] = [];

  parts.push("Synthesize the 15-minute Grid Operator Brief based on the following structured analytical context:");
  parts.push("");
  parts.push("=== STRUCTURED GROUND TRUTH DATA ===");
  parts.push(JSON.stringify(input, null, 2));
  parts.push("====================================");

  if (missingWarnings.length > 0) {
    parts.push("");
    parts.push(`NOTICE: The following inputs were missing or unavailable: ${missingWarnings.join(", ")}. Do NOT invent substitute numbers; document them in Section 8.`);
  }

  parts.push("");
  parts.push("Generate the complete 8-section brief now.");

  return parts.join("\n");
}
