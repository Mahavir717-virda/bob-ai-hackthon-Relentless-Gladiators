/**
 * GridPilot Operator Copilot Orchestration Engine
 *
 * Implements:
 * 1. determine which information is needed
 * 2. call the appropriate tools
 * 3. use their structured outputs
 * 4. explain the situation
 * 5. recommend actions only from optimizer results
 * 6. state uncertainty where relevant
 *
 * Non-negotiable Rules:
 * - Do not allow free-form numerical dispatch decisions by the LLM.
 * - Do not bypass the optimizer.
 */

import { GridTools } from "../tools/grid-tools.ts";
import { getLLMProvider } from "../provider/index.ts";
import { COPILOT_SYSTEM_PROMPT, buildCopilotUserPrompt } from "../prompts/copilot_prompt.ts";
import { DispatchGuardrail } from "../policies/dispatch-guardrail.ts";
import type { ServiceClient } from "../../apps/api/src/service-client.ts";
import type { OptimizationAction, OptimizationResult } from "../../shared/contracts/OptimizationResult.ts";

export interface CopilotQueryInput {
  query: string;
  zoneId?: string;
  assetId?: string;
  explicitTools?: string[];
  simulationArgs?: {
    resourceId: string;
    actionType: string;
    powerMw: number;
    durationMinutes?: number;
  };
}

export interface ToolExecutionSummary {
  name: string;
  success: boolean;
  durationMs: number;
  error?: string;
}

export interface CopilotResponse {
  query: string;
  toolsCalled: string[];
  toolSummaries: ToolExecutionSummary[];
  toolResults: Record<string, any>;
  explanation: string;
  recommendedActions: OptimizationAction[];
  uncertainty: string;
  solverStatus: "feasible" | "infeasible" | "not_run";
  missingData: string[];
  toolErrors: string[];
  guardrailVerified: boolean;
  guardrailViolations: string[];
}

export class OperatorCopilot {
  private gridTools: GridTools;

  constructor(serviceClient?: ServiceClient) {
    this.gridTools = new GridTools(serviceClient);
  }

  /**
   * 1. Determine which information is needed based on query intent
   */
  determineRequiredTools(query: string, explicitTools?: string[]): string[] {
    if (explicitTools && explicitTools.length > 0) {
      return explicitTools;
    }

    const q = query.toLowerCase();
    const needed = new Set<string>();

    // If query asks for complete status, overview, brief, or situation
    if (
      q.includes("status") ||
      q.includes("overview") ||
      q.includes("brief") ||
      q.includes("situation") ||
      q.includes("grid") ||
      q.includes("telemetry")
    ) {
      needed.add("get_current_grid_state");
      needed.add("get_demand_forecast");
      needed.add("get_renewable_status");
    }

    // Demand / load forecast / spike
    if (q.includes("demand") || q.includes("load") || q.includes("spike") || q.includes("forecast")) {
      needed.add("get_demand_forecast");
      needed.add("get_current_grid_state");
    }

    // Renewable / solar / wind
    if (q.includes("renewable") || q.includes("solar") || q.includes("wind") || q.includes("pv")) {
      needed.add("get_renewable_status");
      needed.add("get_weather_forecast");
    }

    // Anomalies or underperformance
    if (
      q.includes("anomaly") ||
      q.includes("anomalies") ||
      q.includes("underperform") ||
      q.includes("drop") ||
      q.includes("deviation")
    ) {
      needed.add("get_renewable_anomalies");
      needed.add("get_renewable_status");
      needed.add("analyze_root_cause");
    }

    // Root cause diagnostics
    if (q.includes("root cause") || q.includes("why") || q.includes("diagnos") || q.includes("cause")) {
      needed.add("analyze_root_cause");
      needed.add("get_renewable_anomalies");
    }

    // Weather
    if (q.includes("weather") || q.includes("irradiance") || q.includes("cloud") || q.includes("temp")) {
      needed.add("get_weather_forecast");
    }

    // Optimization / dispatch / battery / load shift / mitigate / actions
    if (
      q.includes("optimiz") ||
      q.includes("dispatch") ||
      q.includes("battery") ||
      q.includes("bess") ||
      q.includes("shift") ||
      q.includes("curtail") ||
      q.includes("recommend") ||
      q.includes("action")
    ) {
      needed.add("get_current_grid_state");
      needed.add("get_demand_forecast");
      needed.add("run_optimization");
    }

    // Simulation / what if
    if (q.includes("simulat") || q.includes("what if") || q.includes("test action")) {
      needed.add("simulate_action");
    }

    // Default fallback: query grid state and forecast if nothing matched
    if (needed.size === 0) {
      needed.add("get_current_grid_state");
      needed.add("get_demand_forecast");
    }

    return Array.from(needed);
  }

  /**
   * 2. Call the appropriate tools and record structured outputs
   */
  async executeTools(
    toolNames: string[],
    options: {
      zoneId?: string;
      assetId?: string;
      simulationArgs?: any;
    } = {}
  ): Promise<{
    results: Record<string, any>;
    summaries: ToolExecutionSummary[];
    toolErrors: string[];
    missingData: string[];
  }> {
    const results: Record<string, any> = {};
    const summaries: ToolExecutionSummary[] = [];
    const toolErrors: string[] = [];
    const missingData: string[] = [];

    const zoneId = options.zoneId || "NL_LIANDER_SUB_01";

    for (const name of toolNames) {
      const tool = this.gridTools.getToolByName(name);
      if (!tool) {
        toolErrors.push(`Unknown tool: ${name}`);
        continue;
      }

      let toolArgs: any = {};
      if (name === "get_current_grid_state") {
        toolArgs = { zoneId };
      } else if (name === "get_demand_forecast") {
        toolArgs = { zoneId, horizonMinutes: 15 };
      } else if (name === "get_renewable_status") {
        toolArgs = { assetId: options.assetId };
      } else if (name === "get_weather_forecast") {
        toolArgs = { zoneId };
      } else if (name === "analyze_root_cause") {
        toolArgs = { assetId: options.assetId || "SOLAR_FARM_ZEELAND_01" };
      } else if (name === "run_optimization") {
        toolArgs = { scenarioId: `COPILOT_${Date.now()}` };
      } else if (name === "simulate_action") {
        toolArgs = options.simulationArgs || {
          resourceId: "BESS_SUB_01",
          actionType: "battery_discharge",
          powerMw: 10.0,
          durationMinutes: 15,
        };
      }

      const execResult = await tool.execute(toolArgs);
      summaries.push({
        name,
        success: execResult.success,
        durationMs: execResult.durationMs,
        error: execResult.error,
      });

      if (execResult.success) {
        results[name] = execResult.data;
        // Check for internal missing data indicators
        if (name === "get_weather_forecast" && !execResult.data) {
          missingData.push("Weather forecast data unavailable");
        }
      } else {
        toolErrors.push(`${name} failed: ${execResult.error}`);
        missingData.push(`${name} output missing due to tool error`);
      }
    }

    return { results, summaries, toolErrors, missingData };
  }

  /**
   * Main copilot entry point: processes query, coordinates tools, explains situation,
   * enforces optimizer-only recommendations, and states uncertainty.
   */
  async processQuery(input: CopilotQueryInput): Promise<CopilotResponse> {
    // 1. Determine tools
    const toolsToCall = this.determineRequiredTools(input.query, input.explicitTools);

    // 2. Call tools
    const { results, summaries, toolErrors, missingData } = await this.executeTools(toolsToCall, {
      zoneId: input.zoneId,
      assetId: input.assetId,
      simulationArgs: input.simulationArgs,
    });

    // 3. Extract optimizer output if present
    const optResult: OptimizationResult | undefined = results.run_optimization;
    let solverStatus: "feasible" | "infeasible" | "not_run" = "not_run";
    let recommendedActions: OptimizationAction[] = [];

    if (optResult) {
      solverStatus = optResult.status === "infeasible" ? "infeasible" : "feasible";
      if (solverStatus === "feasible") {
        // Recommend actions ONLY from optimizer results
        recommendedActions = optResult.actions || [];
      } else {
        recommendedActions = [];
      }
    }

    // 4. Build prompt for LLM provider
    const userPrompt = buildCopilotUserPrompt(input.query, results, missingData, toolErrors);
    const provider = getLLMProvider();

    const llmResponse = await provider.generate({
      systemPrompt: COPILOT_SYSTEM_PROMPT,
      userPrompt,
      contextData: {
        ...results,
        query: input.query,
        solverStatus,
        recommendedActions,
      },
      temperature: 0.05,
    });

    // 5. Guardrail: Validate that LLM did not bypass optimizer or invent numerical dispatch
    const guardrailCheck = DispatchGuardrail.validate(llmResponse.text, optResult);

    // 6. Synthesize uncertainty statement
    const uncertaintyPoints: string[] = [];
    if (results.get_demand_forecast) {
      const p10 = results.get_demand_forecast.confidenceInterval?.p10Mw;
      const p90 = results.get_demand_forecast.confidenceInterval?.p90Mw;
      if (p10 !== undefined && p90 !== undefined) {
        uncertaintyPoints.push(`Demand forecast 80% confidence interval: [${p10} MW - ${p90} MW]`);
      }
      if (results.get_demand_forecast.spikeRisk) {
        uncertaintyPoints.push(
          `Spike probability: ${(results.get_demand_forecast.spikeRisk.probability * 100).toFixed(1)}% (${results.get_demand_forecast.spikeRisk.level})`
        );
      }
    }

    if (results.analyze_root_cause) {
      uncertaintyPoints.push(
        `Root cause diagnosis confidence: ${(results.analyze_root_cause.confidence * 100).toFixed(1)}%`
      );
    }

    if (solverStatus === "infeasible") {
      uncertaintyPoints.push("CRITICAL: Optimization solver could not find a feasible schedule within physical grid constraints.");
    }

    if (missingData.length > 0) {
      uncertaintyPoints.push(`Telemetry gaps: ${missingData.join("; ")}`);
    }

    const uncertainty =
      uncertaintyPoints.length > 0
        ? uncertaintyPoints.join(" | ")
        : "Operational telemetry within standard confidence limits.";

    return {
      query: input.query,
      toolsCalled: toolsToCall,
      toolSummaries: summaries,
      toolResults: results,
      explanation: guardrailCheck.sanitizedText || llmResponse.text,
      recommendedActions,
      uncertainty,
      solverStatus,
      missingData,
      toolErrors,
      guardrailVerified: guardrailCheck.passed,
      guardrailViolations: guardrailCheck.violations,
    };
  }
}
