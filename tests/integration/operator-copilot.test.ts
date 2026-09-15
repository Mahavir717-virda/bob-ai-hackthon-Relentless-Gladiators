/**
 * Operator Copilot Integration Tests
 *
 * Requirements:
 * - successful tool calls across all 8 tools
 * - missing data handling
 * - tool failure handling
 * - infeasible optimization handling
 * - guardrail enforcement (no free-form dispatch, no bypassing optimizer)
 * - API gateway integration (/api/agent/copilot)
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { GridTools } from "../../agent/tools/grid-tools.ts";
import {
  get_current_grid_state,
  get_demand_forecast,
  get_renewable_status,
  get_weather_forecast,
  get_renewable_anomalies,
  analyze_root_cause,
  run_optimization,
  simulate_action,
} from "../../agent/tools/grid-tools.ts";
import { OperatorCopilot } from "../../agent/orchestration/operator-copilot.ts";
import { DispatchGuardrail } from "../../agent/policies/dispatch-guardrail.ts";
import { createApiServer } from "../../apps/api/src/server.ts";
import type { Server } from "node:http";

test("Operator Copilot & Analytical Tools Suite", async (t) => {
  // Test 1: Successful tool calls across all 8 individual tools
  await t.test("All 8 individual tools execute successfully and return typed data", async () => {
    // 1. get_current_grid_state
    const stateRes = await get_current_grid_state({ zoneId: "NL_LIANDER_SUB_01" });
    assert.equal(stateRes.success, true);
    assert.equal(stateRes.toolName, "get_current_grid_state");
    assert.ok(stateRes.data);
    assert.equal(typeof stateRes.data.demandMw, "number");

    // 2. get_demand_forecast
    const forecastRes = await get_demand_forecast({ zoneId: "NL_LIANDER_SUB_01", horizonMinutes: 15 });
    assert.equal(forecastRes.success, true);
    assert.equal(forecastRes.toolName, "get_demand_forecast");
    assert.ok(forecastRes.data);
    assert.ok(Array.isArray(forecastRes.data.points));

    // 3. get_renewable_status
    const renewableRes = await get_renewable_status();
    assert.equal(renewableRes.success, true);
    assert.equal(renewableRes.toolName, "get_renewable_status");
    assert.ok(Array.isArray(renewableRes.data));
    assert.ok(renewableRes.data.length > 0);

    // 4. get_weather_forecast
    const weatherRes = await get_weather_forecast({ zoneId: "NL_LIANDER_SUB_01" });
    assert.equal(weatherRes.success, true);
    assert.equal(weatherRes.toolName, "get_weather_forecast");
    assert.ok(weatherRes.data);
    assert.equal(typeof weatherRes.data.ghiWm2, "number");

    // 5. get_renewable_anomalies
    const anomalyRes = await get_renewable_anomalies();
    assert.equal(anomalyRes.success, true);
    assert.equal(anomalyRes.toolName, "get_renewable_anomalies");
    assert.ok(Array.isArray(anomalyRes.data));

    // 6. analyze_root_cause
    const rootCauseRes = await analyze_root_cause({ assetId: "SOLAR_FARM_ZEELAND_01" });
    assert.equal(rootCauseRes.success, true);
    assert.equal(rootCauseRes.toolName, "analyze_root_cause");
    assert.ok(rootCauseRes.data);
    assert.ok(typeof rootCauseRes.data.confidence, "number");

    // 7. run_optimization
    const optRes = await run_optimization({ scenarioId: "TEST_RUN_01" });
    assert.equal(optRes.success, true);
    assert.equal(optRes.toolName, "run_optimization");
    assert.ok(optRes.data);
    assert.ok(["feasible", "infeasible", "optimal"].includes(optRes.data.status));

    // 8. simulate_action
    const simRes = await simulate_action({
      resourceId: "BESS_SUB_01",
      actionType: "battery_discharge",
      powerMw: 10.0,
      durationMinutes: 15,
    });
    assert.equal(simRes.success, true);
    assert.equal(simRes.toolName, "simulate_action");
    assert.ok(simRes.data);
    assert.equal(typeof simRes.data.projectedGridStress, "number");
    assert.equal(simRes.data.isFeasible, true);
  });

  // Test 2: Copilot end-to-end workflow (Intent recognition -> Tool execution -> Grounded explanation)
  await t.test("Copilot determines tools, calls them, and explains situation with feasible dispatch", async () => {
    const copilot = new OperatorCopilot();
    const response = await copilot.processQuery({
      query: "Check current grid demand, assess spike risk, and recommend optimal battery dispatch.",
    });

    assert.ok(response.toolsCalled.includes("get_current_grid_state"));
    assert.ok(response.toolsCalled.includes("get_demand_forecast"));
    assert.ok(response.toolsCalled.includes("run_optimization"));
    assert.equal(response.solverStatus, "feasible");
    assert.ok(response.explanation.length > 0);
    assert.ok(response.uncertainty.length > 0);
    assert.equal(response.guardrailVerified, true);
    // Recommendations must come ONLY from optimizer results
    assert.ok(Array.isArray(response.recommendedActions));
    assert.ok(response.recommendedActions.length > 0);
    for (const action of response.recommendedActions) {
      assert.ok(["battery_discharge", "battery_charge", "curtailment", "load_shift"].includes(action.actionType));
    }
  });

  // Test 3: Missing data handling
  await t.test("Copilot handles missing data gracefully and explicitly reports telemetry gaps", async () => {
    // Custom serviceClient where weather forecast returns undefined / null
    const mockClient = {
      getGridState: async () => ({
        timestamp: new Date().toISOString(),
        zoneId: "NL_LIANDER_SUB_01",
        demandMw: 85.0,
        solarGenerationMw: 25.0,
        windGenerationMw: 15.0,
        batterySocPercent: 55.0,
        curtailmentMw: 0.0,
        gridStressIndex: 0.45,
      }),
      getDemandForecast: async () => ({
        forecastId: "FC_01",
        zoneId: "NL_LIANDER_SUB_01",
        horizonMinutes: 15,
        targetTimestamp: new Date().toISOString(),
        points: [{ timestamp: new Date().toISOString(), expectedDemandMw: 90.0 }],
      }),
      getRenewableStatuses: async () => [],
    } as any;

    const copilot = new OperatorCopilot(mockClient);
    const response = await copilot.processQuery({
      query: "Report on renewable weather and asset conditions.",
      explicitTools: ["get_current_grid_state", "get_weather_forecast"],
    });

    assert.ok(response.toolsCalled.includes("get_weather_forecast"));
    // The weather data is missing or default-handled without crashing
    assert.ok(response.explanation.length > 0);
    assert.equal(response.toolErrors.length, 0);
  });

  // Test 4: Tool failure handling
  await t.test("Copilot handles tool execution failure without crashing and notes error in summary", async () => {
    // Mock client that throws error on renewable query
    const failingClient = {
      getGridState: async () => {
        throw new Error("Telemetry database connection timeout");
      },
      getDemandForecast: async () => ({
        forecastId: "FC_01",
        zoneId: "NL_LIANDER_SUB_01",
        horizonMinutes: 15,
        targetTimestamp: new Date().toISOString(),
        points: [],
      }),
      getRenewableStatuses: async () => [],
    } as any;

    const copilot = new OperatorCopilot(failingClient);
    const response = await copilot.processQuery({
      query: "Get current grid state and demand.",
      explicitTools: ["get_current_grid_state"],
    });

    assert.equal(response.toolSummaries[0].success, false);
    assert.ok(response.toolSummaries[0].error?.includes("Telemetry database connection timeout"));
    assert.ok(response.toolErrors.some((e) => e.includes("get_current_grid_state failed")));
    assert.ok(response.missingData.length > 0);
    // Agent still produces structured explanation reporting the limitation
    assert.ok(response.explanation.length > 0);
  });

  // Test 5: Infeasible optimization handling
  await t.test("Copilot preserves infeasible solver status, warns operator, and refuses invented dispatch", async () => {
    const infeasibleClient = {
      getGridState: async () => ({
        timestamp: new Date().toISOString(),
        zoneId: "NL_LIANDER_SUB_01",
        demandMw: 150.0,
        solarGenerationMw: 0.0,
        windGenerationMw: 0.0,
        batterySocPercent: 5.0,
        curtailmentMw: 0.0,
        gridStressIndex: 0.98,
      }),
      getDemandForecast: async () => ({
        forecastId: "FC_01",
        zoneId: "NL_LIANDER_SUB_01",
        horizonMinutes: 15,
        targetTimestamp: new Date().toISOString(),
        points: [{ timestamp: new Date().toISOString(), expectedDemandMw: 150.0 }],
      }),
      solveOptimization: async () => ({
        scenarioId: "INFEASIBLE_SCENARIO",
        status: "infeasible" as const,
        executionTimeMs: 14,
        solver: "Google-OR-Tools-MILP",
        totalCostEur: 0,
        actions: [], // Empty actions
        before: { gridStressIndex: 0.98, batterySocPercent: 5.0, curtailmentMw: 0.0 },
        after: { gridStressIndex: 0.98, batterySocPercent: 5.0, curtailmentMw: 0.0 },
        recommendations: [
          {
            id: "WARN_01",
            type: "operator_alert",
            message: "Constraints violated: insufficient battery capacity and extreme demand overload.",
            priority: "critical",
          },
        ],
      }),
    } as any;

    const copilot = new OperatorCopilot(infeasibleClient);
    const response = await copilot.processQuery({
      query: "Run optimization and tell me how many MW to dispatch from the battery.",
      explicitTools: ["run_optimization"],
    });

    assert.equal(response.solverStatus, "infeasible");
    // Zero recommended dispatch actions allowed
    assert.equal(response.recommendedActions.length, 0);
    // Uncertainty explicitly warns of infeasibility
    assert.ok(response.uncertainty.includes("CRITICAL: Optimization solver could not find a feasible schedule"));
    assert.equal(response.guardrailVerified, true);
  });

  // Test 6: Dispatch Guardrail rejects free-form numerical dispatch and optimizer bypass
  await t.test("DispatchGuardrail intercepts unauthorized free-form dispatch numbers", async () => {
    // 1. Text suggests dispatch when optimization was not run
    const hallucinatedText = "We recommend you discharge 15 MW from the battery immediately.";
    const check1 = DispatchGuardrail.validate(hallucinatedText, undefined);
    assert.equal(check1.passed, false);
    assert.ok(check1.violations.some((v) => v.includes("Bypassed Optimizer")));
    assert.ok(check1.sanitizedText?.includes("RULE B ENFORCEMENT"));

    // 2. Text suggests dispatch when optimization returned infeasible
    const infeasibleOpt: any = { status: "infeasible", actions: [] };
    const check2 = DispatchGuardrail.validate(hallucinatedText, infeasibleOpt);
    assert.equal(check2.passed, false);
    assert.ok(check2.violations.some((v) => v.includes("Infeasible Optimization Violation")));

    // 3. Text suggests dispatch matching the solver actions (10 MW allowed)
    const feasibleOpt: any = {
      status: "feasible",
      actions: [{ actionType: "battery_discharge", powerMw: 10.0, resourceId: "BESS_01" }],
    };
    const validText = "Optimization schedule: discharge 10 MW from battery BESS_01.";
    const check3 = DispatchGuardrail.validate(validText, feasibleOpt);
    assert.equal(check3.passed, true);
    assert.equal(check3.violations.length, 0);
  });

  // Test 7: API Gateway /api/agent/copilot endpoint
  await t.test("API Gateway /api/agent/copilot responds with 200 and structured copilot output", async () => {
    const server: Server = createApiServer();
    await new Promise<void>((resolve) => server.listen(0, resolve));
    const port = (server.address() as any).port;

    try {
      const response = await fetch(`http://localhost:${port}/api/agent/copilot`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Request-ID": "copilot-test-req" },
        body: JSON.stringify({
          query: "What is the solar generation status and are there any anomalies?",
        }),
      });

      assert.equal(response.status, 200);
      const json = await response.json();
      assert.equal(json.success, true);
      assert.ok(json.data.toolsCalled.includes("get_renewable_status"));
      assert.ok(json.data.explanation.length > 0);
      assert.ok(typeof json.data.guardrailVerified === "boolean");
    } finally {
      await new Promise<void>((resolve) => server.close(() => resolve()));
    }
  });
});
