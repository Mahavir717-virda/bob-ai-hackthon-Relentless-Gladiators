/**
 * GridPilot Dedicated Typed API Client
 *
 * Encapsulates all REST communication with the GridPilot API Gateway.
 * Strictly consumes typed contracts without client-side fake calculations.
 */

import type {
  OperationalSnapshot,
  GridState,
  DemandForecast,
  RenewableStatus,
  OptimizationResult,
  OperatorBrief,
  CopilotResponse,
  Scenario,
} from "./types.ts";

const API_BASE = "";

export class ApiClient {
  private static async fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        "X-Request-ID": `web-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        ...(options?.headers || {}),
      },
    });

    const body = await res.json();
    if (!res.ok || !body.success) {
      throw new Error(body.error?.message || `API error on ${endpoint} (${res.status})`);
    }

    return body.data as T;
  }

  // 1. Grid Telemetry & Snapshot
  static async getOperationalSnapshot(): Promise<OperationalSnapshot> {
    return this.fetchJson<OperationalSnapshot>("/api/grid/snapshot");
  }

  static async getGridState(zoneId = "NL_LIANDER_SUB_01"): Promise<GridState> {
    return this.fetchJson<GridState>(`/api/grid?zoneId=${encodeURIComponent(zoneId)}`);
  }

  // 2. Demand Forecast
  static async getDemandForecast(zoneId = "NL_LIANDER_SUB_01", horizon = 15): Promise<DemandForecast> {
    return this.fetchJson<DemandForecast>(`/api/forecast?zoneId=${encodeURIComponent(zoneId)}&horizon=${horizon}`);
  }

  // 3. Renewable Intelligence
  static async getRenewableStatuses(): Promise<RenewableStatus[]> {
    return this.fetchJson<RenewableStatus[]>("/api/renewable");
  }

  static async getRenewableAnomalies(): Promise<RenewableStatus[]> {
    return this.fetchJson<RenewableStatus[]>("/api/renewable/anomalies");
  }

  // 4. Mathematical Optimization
  static async runOptimization(payload: any): Promise<OptimizationResult> {
    return this.fetchJson<OptimizationResult>("/api/optimization", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  // 5. Scenarios
  static async getScenarios(): Promise<Scenario[]> {
    return this.fetchJson<Scenario[]>("/api/scenario");
  }

  static async replayScenario(scenarioId: string): Promise<{ scenario: Scenario; result: OptimizationResult }> {
    return this.fetchJson<{ scenario: Scenario; result: OptimizationResult }>(`/api/scenario/${encodeURIComponent(scenarioId)}/replay`, {
      method: "POST",
    });
  }

  // 6. AI Agent & Copilot
  static async generateOperatorBrief(input: any): Promise<OperatorBrief> {
    return this.fetchJson<OperatorBrief>("/api/agent/brief", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  static async queryCopilot(
    query: string,
    options: {
      zoneId?: string;
      assetId?: string;
      explicitTools?: string[];
      simulationArgs?: any;
    } = {}
  ): Promise<CopilotResponse> {
    return this.fetchJson<CopilotResponse>("/api/agent/copilot", {
      method: "POST",
      body: JSON.stringify({ query, ...options }),
    });
  }

  // Health
  static async checkHealth(): Promise<{ status: string; uptimeSeconds: number }> {
    const res = await fetch("/health");
    const json = await res.json();
    return json.data;
  }
}
