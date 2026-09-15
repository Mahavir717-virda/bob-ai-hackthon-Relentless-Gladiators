/**
 * Deterministic Mock LLM Provider
 * Used for offline verification, CI/CD, and local development.
 *
 * Implements Rule C: Strictly formats provided structured context
 * without inventing quantities or modifying optimization results.
 */

import type { LLMProvider, LLMGenerationRequest, LLMGenerationResponse } from "./types.ts";

export class MockLLMProvider implements LLMProvider {
  private modelId: string;

  constructor(modelId = "ibm/granite-3-8b-instruct-mock") {
    this.modelId = modelId;
  }

  getProviderName(): string {
    return "mock-provider";
  }

  getModelId(): string {
    return this.modelId;
  }

  isConfigured(): boolean {
    return true;
  }

  async generate(request: LLMGenerationRequest): Promise<LLMGenerationResponse> {
    const startTime = performance.now();
    const ctx = request.contextData || {};

    let responseText = "";

    // If synthesizing an Operator Brief
    if (request.userPrompt.toLowerCase().includes("brief") || request.systemPrompt.toLowerCase().includes("brief")) {
      const demand = ctx.currentGridState?.demandMw ?? ctx.currentDemand?.valueMw ?? 85.0;
      const zoneId = ctx.currentGridState?.zoneId ?? ctx.currentDemand?.zoneId ?? "NL_LIANDER_SUB_01";
      const stress = ctx.currentGridState?.gridStressIndex ?? ctx.gridStress?.stressIndex ?? 0.42;
      const spike = ctx.demandForecast?.spikeRisk?.level ?? ctx.forecastDemand?.spikeRiskLevel ?? "normal";
      const spikeProb = ctx.demandForecast?.spikeRisk?.probability ?? ctx.forecastDemand?.spikeProbability ?? 0.12;

      const actions = ctx.optimizationResult?.actions || [];
      const hasAnomaly = ctx.renewableStatuses?.some((r: any) => r.anomaly) ?? false;
      const anomalyEvidence = ctx.renewableStatuses?.find((r: any) => r.anomaly)?.likelyRootCause?.evidence ?? "No asset performance anomalies detected.";

      responseText = [
        "## 1. Current Situation",
        `Substation ${zoneId} is operating at ${demand} MW load with a composite grid stress index of ${Number(stress).toFixed(2)}.`,
        "",
        "## 2. Risk Assessment",
        `Short-term demand spike risk is evaluated as **${String(spike).toUpperCase()}** with a calculated probability of ${(Number(spikeProb) * 100).toFixed(1)}%.`,
        "",
        "## 3. Renewable Alert",
        hasAnomaly
          ? "Alert: Asset underperformance detected. Telemetry deviates significantly from expected generation curve."
          : "Renewable solar and wind generation are tracking within nominal performance envelopes.",
        "",
        "## 4. Root Cause",
        anomalyEvidence,
        "",
        "## 5. Recommended Actions",
        actions.length > 0
          ? actions.map((a: any) => `- ${String(a.actionType).toUpperCase()}: ${a.powerMw} MW on ${a.resourceId} from ${a.startTime} to ${a.endTime}`).join("\n")
          : "- No battery dispatch or load shifting required at this timestamp.",
        "",
        "## 6. Expected Impact",
        ctx.optimizationResult
          ? `Executing recommended MILP schedule will transition grid stress from ${ctx.optimizationResult.before.gridStressIndex.toFixed(2)} down to ${ctx.optimizationResult.after.gridStressIndex.toFixed(2)}.`
          : "Grid parameters remain stable within operational boundaries.",
        "",
        "## 7. Confidence & Uncertainty",
        "Forecast variance bound: ±4.2 MW across 15-minute horizon. Zero dispatch quantities have been inferred outside the OR-Tools solver.",
        "",
        "## 8. Data Limitations",
        "Analysis based on 15-minute sampled SCADA telemetry and OpenSTEF grid topology.",
      ].join("\n");
    } else {
      // General Operator Query answering
      responseText = `[Operator Assistant Analysis]\nIn response to your query ("${request.userPrompt}"), the system state indicates current demand at ${ctx.currentGridState?.demandMw ?? "nominal"} MW with stress index ${ctx.currentGridState?.gridStressIndex ?? 0.42}. Mathematical optimization recommends following the feasible schedule without manual override.`;
    }

    const durationMs = Math.round(performance.now() - startTime);

    return {
      text: responseText,
      model: this.modelId,
      provider: this.getProviderName(),
      tokensUsed: {
        prompt: Math.round(request.userPrompt.length / 4),
        completion: Math.round(responseText.length / 4),
        total: Math.round((request.userPrompt.length + responseText.length) / 4),
      },
      durationMs,
    };
  }
}
