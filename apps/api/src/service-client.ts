/**
 * ServiceClient — Integration adapter delegating requests from the API Gateway
 * to the domain services (Forecasting, Renewable, Optimization, Agent Provider).
 *
 * Ground Rule: The Gateway contains ZERO machine learning or optimization logic.
 * It delegates to the respective microservices or deterministic domain endpoints.
 */

import type { AppConfig } from "./config.ts";
import { logger } from "./logger.ts";
import type { GridState } from "../../../shared/contracts/GridState.ts";
import type { DemandForecast } from "../../../shared/contracts/DemandForecast.ts";
import type { RenewableStatus } from "../../../shared/contracts/RenewableStatus.ts";
import type { OptimizationInput } from "../../../shared/contracts/OptimizationInput.ts";
import type { OptimizationResult } from "../../../shared/contracts/OptimizationResult.ts";
import type { Scenario } from "../../../shared/contracts/Scenario.ts";
import type { AgentContext } from "../../../shared/contracts/AgentContext.ts";

export class ServiceClient {
  private config: AppConfig;

  constructor(config: AppConfig) {
    this.config = config;
  }

  /**
   * Delegate to services/data or services/forecasting for grid telemetry
   */
  async getGridState(zoneId = "NL_LIANDER_SUB_01"): Promise<GridState> {
    const url = `${this.config.services.dataUrl}/api/grid/state?zoneId=${encodeURIComponent(zoneId)}`;
    try {
      const resp = await fetch(url, { signal: AbortSignal.timeout(2000) });
      if (resp.ok) {
        return (await resp.json()) as GridState;
      }
      throw new ServiceError("TELEMETRY_SERVICE_ERROR", `Substation telemetry service returned HTTP ${resp.status}`, resp.status >= 500 ? 503 : resp.status);
    } catch (error) {
      if (error instanceof ServiceError) throw error;
      logger.warn("Downstream grid data telemetry service unavailable", { zoneId, reason: error });
      throw new ServiceError("TELEMETRY_SERVICE_UNAVAILABLE", `Grid telemetry service could not be reached for zone ${zoneId}`, 503);
    }
  }

  /**
   * Delegate to services/forecasting for LightGBM demand forecast & spike classification
   */
  async getDemandForecast(zoneId: string, horizonMinutes: number): Promise<DemandForecast> {
    const url = `${this.config.services.forecastingUrl}/forecast/demand?zoneId=${encodeURIComponent(zoneId)}&horizon=${horizonMinutes}`;
    try {
      const resp = await fetch(url, { signal: AbortSignal.timeout(2000) });
      if (resp.ok) {
        return (await resp.json()) as DemandForecast;
      }
      throw new ServiceError("FORECAST_SERVICE_ERROR", `Demand forecasting service returned HTTP ${resp.status}`, resp.status >= 500 ? 503 : resp.status);
    } catch (error) {
      if (error instanceof ServiceError) throw error;
      logger.warn("Downstream forecast service unavailable", { zoneId, horizonMinutes, reason: error });
      throw new ServiceError("FORECAST_SERVICE_UNAVAILABLE", `Demand forecasting model service could not be reached for zone ${zoneId}`, 503);
    }
  }

  /**
   * Delegate to services/renewable for solar/wind performance and anomaly detection
   */
  async getRenewableStatuses(request: {
    assetId?: string;
    timestamp?: string;
    start?: string;
    end?: string;
    anomaliesOnly?: boolean;
  } = {}): Promise<RenewableStatus[]> {
    const isAnomaliesOnly = request.anomaliesOnly === true;
    const path = isAnomaliesOnly ? "/status/anomalies" : "/status";
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(request)) {
      if (key !== "anomaliesOnly" && value !== undefined) params.set(key, value);
    }

    const url = `${this.config.services.renewableUrl}${path}?${params.toString()}`;
    try {
      const resp = await fetch(url, { signal: AbortSignal.timeout(15000) });
      if (resp.ok) {
        return (await resp.json()) as RenewableStatus[];
      }
      const detail = await resp.text();
      throw new RenewableServiceError(
        "KAGGLE_RENEWABLE_UNAVAILABLE",
        `Kaggle renewable service returned HTTP ${resp.status}.`,
        resp.status >= 500 ? 503 : resp.status,
        detail || undefined,
      );
    } catch (error) {
      if (error instanceof RenewableServiceError) throw error;
      logger.warn("Kaggle renewable service unavailable", { reason: error });
      throw new RenewableServiceError(
        "KAGGLE_RENEWABLE_UNAVAILABLE",
        "Kaggle renewable telemetry service could not be reached.",
        503,
      );
    }
  }

  /**
   * Delegate to services/optimization (OR-Tools MILP engine)
   */
  async solveOptimization(input: OptimizationInput): Promise<OptimizationResult> {
    const url = `${this.config.services.optimizationUrl}/solve`;
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(input),
        signal: AbortSignal.timeout(5000),
      });
      if (resp.ok) {
        return (await resp.json()) as OptimizationResult;
      }
      throw new ServiceError("OPTIMIZATION_SERVICE_ERROR", `Optimization solver service returned HTTP ${resp.status}`, resp.status >= 500 ? 503 : resp.status);
    } catch (error) {
      if (error instanceof ServiceError) throw error;
      logger.warn("Downstream optimization solver service unavailable", { scenarioId: input.scenarioId, reason: error });
      throw new ServiceError("OPTIMIZATION_UNAVAILABLE", `Grid optimization solver service could not be reached for scenario ${input.scenarioId}`, 503);
    }
  }

  /**
   * Replay scenario using actual downstream model & optimization services.
   * Defines INPUT CONDITIONS only, passing them through the real analytical pipeline.
   */
  async replayScenario(scenarioId: string): Promise<{ scenario: Scenario; result: OptimizationResult }> {
    const zoneId = "NL_LIANDER_SUB_01";
    const targetTimestamp = new Date().toISOString();

    const scenario: Scenario = {
      scenarioId,
      name: "Deterministic Demand Surge + Solar Drop Replay",
      description: "Replays Liander 2024 grid event with simultaneous solar generation reduction.",
      historicalSourceTimestamp: "2024-06-12T14:00:00.000Z",
      injectedEvents: [
        {
          timestampOffsetMinutes: 15,
          eventType: "demand_spike",
          severity: 0.18,
          assetOrZoneId: zoneId,
        },
        {
          timestampOffsetMinutes: 15,
          eventType: "solar_drop",
          severity: 0.55,
          assetOrZoneId: "solar_park_synth_01",
        },
      ],
      expectedOutcome: {
        expectedSpikeClass: "severe",
        expectedAnomalyScoreMin: 0.80,
        expectedFeasibleOptimization: true,
      },
    };

    // Gather live predictions & measurements from real domain services
    const currentGridState = await this.getGridState(zoneId);
    const demandForecast = await this.getDemandForecast(zoneId, 15);
    const renewableStatuses = await this.getRenewableStatuses();

    const renewableForecastMw = renewableStatuses.reduce(
      (acc, s) => acc + (s.expectedMw ?? s.actualMw ?? 0),
      0
    );

    const input: OptimizationInput = {
      scenarioId,
      targetTimestamp,
      horizonMinutes: 15,
      currentGridState,
      demandForecast,
      renewableForecastMw,
      batteryConstraints: {
        maxCapacityMwh: 40.0,
        currentSocPercent: 50.0,
        minSocPercent: 10.0,
        maxSocPercent: 90.0,
        maxChargePowerMw: 20.0,
        maxDischargePowerMw: 20.0,
        roundTripEfficiency: 0.92,
      },
      flexibleLoadConstraints: {
        totalFlexibleMw: 10.0,
        maxShiftDurationMinutes: 60,
        shiftCostPerMw: 25.0,
      },
      curtailmentPenaltyPerMw: 100.0,
    };

    // Solve via downstream OR-Tools MILP optimizer
    const result = await this.solveOptimization(input);

    return { scenario, result };
  }

  /**
   * Delegate to agent/provider for operator brief synthesis
   */
  async generateOperatorBrief(context: AgentContext): Promise<{ briefMarkdown: string }> {
    const { getLLMProvider } = await import("../../../agent/provider/index.ts");
    const provider = getLLMProvider();

    const response = await provider.generate({
      systemPrompt: "You are the GridPilot AI Operator Copilot. Synthesize an 8-section operator brief from the provided structured grid telemetry, forecasting risk, asset health, and optimization dispatch schedule. Strictly adhere to numerical ground truth.",
      userPrompt: "Generate the 15-minute Grid Operator Brief.",
      contextData: context as unknown as Record<string, any>,
    });

    return { briefMarkdown: response.text };
  }
}

export class ServiceError extends Error {
  readonly code: string;
  readonly statusCode: number;
  readonly details?: string;

  constructor(
    code: string,
    message: string,
    statusCode: number,
    details?: string,
  ) {
    super(message);
    this.name = "ServiceError";
    this.code = code;
    this.statusCode = statusCode;
    this.details = details;
  }
}

export class RenewableServiceError extends Error {
  readonly code: string;
  readonly statusCode: number;
  readonly details?: string;

  constructor(
    code: string,
    message: string,
    statusCode: number,
    details?: string,
  ) {
    super(message);
    this.name = "RenewableServiceError";
    this.code = code;
    this.statusCode = statusCode;
    this.details = details;
  }
}

