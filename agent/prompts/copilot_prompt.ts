/**
 * Operator Copilot Prompt Templates
 *
 * Implements strict system prompts enforcing:
 * - Architectural Rule A (ML for predictions only)
 * - Architectural Rule B (Optimizer for decisions only)
 * - Architectural Rule C (LLM for communication only)
 * - Uncertainty reporting & missing data transparency
 */

export const COPILOT_SYSTEM_PROMPT = `You are GridPilot AI, the real-time operational copilot for power grid control room operators.
You are assisting operators managing demand spikes, renewable energy drops, battery dispatch, and flexible load shifting.

NON-NEGOTIABLE ARCHITECTURAL INVARIANTS:
1. RULE A — ML is responsible for PREDICTIONS only:
   LightGBM and XGBoost output forecasts and spike probabilities. You must communicate them faithfully.
2. RULE B — The Optimizer is responsible for DECISIONS:
   The OR-Tools Mixed-Integer Linear Programming (MILP) engine is the SOLE authority on dispatch schedules.
   - You must NEVER invent, infer, or recommend free-form numerical dispatch decisions.
   - You must NEVER bypass the optimizer.
   - If the optimizer result is "infeasible", you MUST warn the operator that constraints cannot be satisfied and NOT suggest manual dispatch.
3. RULE C — LLM is responsible for COMMUNICATION:
   - Base your explanation purely on the structured tool outputs provided.
   - State uncertainty where relevant (e.g. demand forecast confidence intervals P10/P90, spike risk probability, anomaly attribution confidence).
   - If telemetry or tool data is missing or failed, explicitly disclose the missing information.
   - Never claim correlation is causation.`;

export function buildCopilotUserPrompt(
  operatorQuery: string,
  toolResults: Record<string, any>,
  missingData: string[] = [],
  toolErrors: string[] = []
): string {
  const sections: string[] = [];

  sections.push(`### OPERATOR QUERY\n${operatorQuery}`);

  if (toolErrors.length > 0) {
    sections.push(`### TOOL EXECUTION ERRORS\n${toolErrors.map((e) => `- ⚠️ ${e}`).join("\n")}`);
  }

  if (missingData.length > 0) {
    sections.push(`### MISSING DATA / TELEMETRY GAPS\n${missingData.map((m) => `- ⚠️ ${m}`).join("\n")}`);
  }

  sections.push(`### STRUCTURED TOOL OUTPUTS`);

  if (toolResults.get_current_grid_state) {
    sections.push(`#### 1. Current Grid State\n\`\`\`json\n${JSON.stringify(toolResults.get_current_grid_state, null, 2)}\n\`\`\``);
  }

  if (toolResults.get_demand_forecast) {
    sections.push(`#### 2. Demand Forecast\n\`\`\`json\n${JSON.stringify(toolResults.get_demand_forecast, null, 2)}\n\`\`\``);
  }

  if (toolResults.get_renewable_status) {
    sections.push(`#### 3. Renewable Status\n\`\`\`json\n${JSON.stringify(toolResults.get_renewable_status, null, 2)}\n\`\`\``);
  }

  if (toolResults.get_weather_forecast) {
    sections.push(`#### 4. Weather Forecast\n\`\`\`json\n${JSON.stringify(toolResults.get_weather_forecast, null, 2)}\n\`\`\``);
  }

  if (toolResults.get_renewable_anomalies) {
    sections.push(`#### 5. Renewable Anomalies\n\`\`\`json\n${JSON.stringify(toolResults.get_renewable_anomalies, null, 2)}\n\`\`\``);
  }

  if (toolResults.analyze_root_cause) {
    sections.push(`#### 6. Root Cause Diagnostics\n\`\`\`json\n${JSON.stringify(toolResults.analyze_root_cause, null, 2)}\n\`\`\``);
  }

  if (toolResults.run_optimization) {
    sections.push(`#### 7. Mathematical Optimization Result\n\`\`\`json\n${JSON.stringify(toolResults.run_optimization, null, 2)}\n\`\`\``);
  }

  if (toolResults.simulate_action) {
    sections.push(`#### 8. Simulated Action Evaluation\n\`\`\`json\n${JSON.stringify(toolResults.simulate_action, null, 2)}\n\`\`\``);
  }

  sections.push(`\nSynthesize your response following these 4 elements:
1. Situation Explanation (explain what is occurring on the grid from the telemetry).
2. Risk & Uncertainty (state forecast confidence bounds, spike probabilities, and data limitations).
3. Recommended Actions (ONLY quote actions from the optimizer result if feasible; if optimizer is infeasible or not run, clearly state that no dispatch actions can be recommended).
4. Feasibility Status (explicitly confirm whether the solution is mathematically feasible or requires operator intervention).`);

  return sections.join("\n\n");
}
