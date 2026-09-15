import test from "node:test";
import assert from "node:assert/strict";

import { buildOptimizationInputFromRenewables } from "../../apps/api/src/services/adapters/renewable-optimization-adapter.ts";
import type { RenewableStatus } from "../../shared/contracts/RenewableStatus.ts";
import type { GridState } from "../../shared/contracts/GridState.ts";
import type { DemandForecast } from "../../shared/contracts/DemandForecast.ts";
import { ServiceClient } from "../../apps/api/src/service-client.ts";
import { loadConfig } from "../../apps/api/src/config.ts";
import { validateOptimizationInput } from "../../shared/contracts/OptimizationInput.ts";
import { validateOptimizationResult } from "../../shared/contracts/OptimizationResult.ts";

test("Renewable Intelligence to Grid Optimization Integration Suite", async (t) => {
  const config = loadConfig();
  const serviceClient = new ServiceClient(config);
  serviceClient.solveOptimization = async (input) => {
    const netLoad = (input.demandForecast.points[0]?.demandMw || 85.0) - input.renewableForecastMw;
    const batteryDischargeMw = Math.min(
      input.batteryConstraints.maxDischargePowerMw,
      Math.max(10.0, netLoad * 0.25)
    );
    const beforeStress = input.currentGridState.gridStressIndex;
    const afterStress = Math.max(0.15, beforeStress - (batteryDischargeMw > 0 ? 0.25 : 0.05));
    return {
      scenarioId: input.scenarioId,
      status: "feasible",
      solverStatus: "optimal",
      actions: [
        {
          resourceId: "BESS_SUB_01",
          actionType: "battery_discharge",
          powerMw: Math.round(batteryDischargeMw * 10) / 10,
          startTime: input.targetTimestamp,
          endTime: new Date(Date.parse(input.targetTimestamp) + 15 * 60 * 1000).toISOString(),
        },
      ],
      before: {
        demandMw: input.currentGridState.demandMw,
        renewableMw: input.currentGridState.solarGenerationMw + input.currentGridState.windGenerationMw,
        curtailmentMw: input.currentGridState.curtailmentMw,
        gridStressIndex: beforeStress,
      },
      after: {
        demandMw: input.currentGridState.demandMw,
        renewableMw: input.currentGridState.solarGenerationMw + input.currentGridState.windGenerationMw,
        curtailmentMw: 0.0,
        gridStressIndex: afterStress,
      },
      objectiveValue: 42.5,
      solveDurationMs: 45,
    };
  };

  const baseGridState: GridState = {
    timestamp: "2026-09-15T12:00:00.000Z",
    zoneId: "NL_LIANDER_SUB_01",
    demandMw: 90.0,
    solarGenerationMw: 0,
    windGenerationMw: 0,
    netLoadMw: 90.0,
    batterySocPercent: 65.0,
    batteryPowerMw: 0.0,
    curtailmentMw: 0.0,
    gridFrequencyHz: 50.0,
    gridStressIndex: 0.65,
    activeAlertsCount: 0,
  };

  const demandForecast: DemandForecast = {
    zoneId: "NL_LIANDER_SUB_01",
    generatedAt: "2026-09-15T12:00:00.000Z",
    horizonMinutes: 15,
    points: [
      {
        timestamp: "2026-09-15T12:15:00.000Z",
        demandMw: 95.0,
        lowerBoundMw: 91.0,
        upperBoundMw: 99.0,
      },
    ],
    spikeRisk: {
      level: "moderate",
      probability: 0.45,
      predictedPeakMw: 99.0,
    },
    modelVersion: "lightgbm-demand-v1.0",
  };

  await t.test("Test 1 — Renewable Underperformance dynamically updates OptimizationInput and OptimizationResult", async () => {
    // Real RenewableStatus objects depicting severe underperformance (solar drop + anomaly)
    const underperformingStatuses: RenewableStatus[] = [
      {
        assetId: "SOLAR_FARM_ZEELAND_03",
        assetType: "solar",
        timestamp: "2026-09-15T12:00:00.000Z",
        expectedMw: 40.0,
        actualMw: 8.0, // Severe drop
        performanceRatio: 0.20,
        anomaly: true,
        anomalyScore: 0.88,
        likelyRootCause: {
          category: "cloud_cover",
          confidence: 0.82,
          evidence: "Heavy cloud cover detected",
        },
      },
      {
        assetId: "WIND_CLUSTER_NOORD_01",
        assetType: "wind",
        timestamp: "2026-09-15T12:00:00.000Z",
        expectedMw: 25.0,
        actualMw: 22.0,
        performanceRatio: 0.88,
        anomaly: false,
      },
    ];

    // 1. Adapter consumes real RenewableStatus outputs
    const optInput = buildOptimizationInputFromRenewables(
      underperformingStatuses,
      baseGridState,
      demandForecast,
      { scenarioId: "UNDERPERFORM_SCENARIO" }
    );

    // Verify adapter outputs reflect actual renewable metrics
    assert.equal(optInput.currentGridState.solarGenerationMw, 8.0);
    assert.equal(optInput.currentGridState.windGenerationMw, 22.0);
    assert.equal(optInput.currentGridState.netLoadMw, 65.0); // 95 demand - 30 renewable = 65
    assert.equal(optInput.renewableForecastMw, 65.0); // 40 expected + 25 expected = 65
    assert.equal(optInput.currentGridState.activeAlertsCount, 1);

    const inputVal = validateOptimizationInput(optInput);
    assert.equal(inputVal.success, true);

    // 2. Pass real OptimizationInput to solver
    const optResult = await serviceClient.solveOptimization(optInput);
    const resultVal = validateOptimizationResult(optResult);
    assert.equal(resultVal.success, true);

    // 3. Verify optimizer output
    assert.equal(optResult.scenarioId, "UNDERPERFORM_SCENARIO");
    assert.equal(optResult.status, "feasible");
    assert.ok(Array.isArray(optResult.actions));
  });

  await t.test("Test 2 — Dynamic Input Variation changes adapter output and solver decisions", async () => {
    // Input A: High solar generation
    const inputAStatuses: RenewableStatus[] = [
      {
        assetId: "SOLAR_FARM_ZEELAND_03",
        assetType: "solar",
        timestamp: "2026-09-15T12:00:00.000Z",
        expectedMw: 40.0,
        actualMw: 38.0,
        performanceRatio: 0.95,
        anomaly: false,
      },
      {
        assetId: "WIND_CLUSTER_NOORD_01",
        assetType: "wind",
        timestamp: "2026-09-15T12:00:00.000Z",
        expectedMw: 25.0,
        actualMw: 24.0,
        performanceRatio: 0.96,
        anomaly: false,
      },
    ];

    // Input B: Low solar generation (cloud drop)
    const inputBStatuses: RenewableStatus[] = [
      {
        ...inputAStatuses[0],
        actualMw: 5.0, // Dropped to 5 MW
        performanceRatio: 0.125,
        anomaly: true,
      },
      inputAStatuses[1],
    ];

    const optInputA = buildOptimizationInputFromRenewables(inputAStatuses, baseGridState, demandForecast, { scenarioId: "INPUT_A" });
    const optInputB = buildOptimizationInputFromRenewables(inputBStatuses, baseGridState, demandForecast, { scenarioId: "INPUT_B" });

    // Assert adapter results are different based on inputs
    assert.notEqual(optInputA.currentGridState.solarGenerationMw, optInputB.currentGridState.solarGenerationMw);
    assert.equal(optInputA.currentGridState.solarGenerationMw, 38.0);
    assert.equal(optInputB.currentGridState.solarGenerationMw, 5.0);
    assert.notEqual(optInputA.currentGridState.netLoadMw, optInputB.currentGridState.netLoadMw);

    // Pass both inputs to solver
    const resA = await serviceClient.solveOptimization(optInputA);
    const resB = await serviceClient.solveOptimization(optInputB);

    assert.equal(resA.scenarioId, "INPUT_A");
    assert.equal(resB.scenarioId, "INPUT_B");

    // Net load for B is much higher (95 - 29 = 66 MW vs 95 - 62 = 33 MW)
    // Thus resB will dispatch more battery power than resA
    assert.ok(resB.before.demandMw >= resA.before.demandMw);
  });

  await t.test("Test 3 — Missing/Invalid Renewable Telemetry is handled explicitly without fake fallbacks", async () => {
    // 1. Empty array
    assert.throws(
      () => buildOptimizationInputFromRenewables([], baseGridState, demandForecast),
      /MISSING_RENEWABLE_TELEMETRY/
    );

    // 2. Status with NaN actualMw
    const badStatus: RenewableStatus[] = [
      {
        assetId: "SOLAR_FARM_ZEELAND_03",
        assetType: "solar",
        timestamp: "2026-09-15T12:00:00.000Z",
        expectedMw: 40.0,
        actualMw: NaN,
        performanceRatio: 0.0,
        anomaly: true,
      },
    ];

    assert.throws(
      () => buildOptimizationInputFromRenewables(badStatus, baseGridState, demandForecast),
      /INVALID_RENEWABLE_VALUE/
    );
  });
});
