import test from "node:test";
import assert from "node:assert/strict";
import type { AddressInfo } from "node:net";

import { GridStateAggregator } from "../../apps/api/src/services/grid-state-aggregator.ts";
import { ServiceClient } from "../../apps/api/src/service-client.ts";
import { loadConfig } from "../../apps/api/src/config.ts";
import { validateAggregatedGridSnapshot } from "../../shared/contracts/AggregatedGridSnapshot.ts";
import { createApiServer } from "../../apps/api/src/server.ts";

test("Grid State Aggregator Service", async (t) => {
  const config = loadConfig();

  await t.test("Generates complete operational snapshot when all dependencies are healthy", async () => {
    const serviceClient = new ServiceClient(config);
    serviceClient.getGridState = async (zoneId = "NL_LIANDER_SUB_01") => ({
      timestamp: new Date().toISOString(),
      zoneId,
      demandMw: 85.4,
      solarGenerationMw: 32.1,
      windGenerationMw: 24.5,
      netLoadMw: 28.8,
      batterySocPercent: 65.0,
      batteryPowerMw: 0.0,
      curtailmentMw: 0.0,
      gridFrequencyHz: 50.01,
      gridStressIndex: 0.42,
      activeAlertsCount: 0,
    });
    serviceClient.getDemandForecast = async (zoneId = "NL_LIANDER_SUB_01", horizonMinutes = 15) => ({
      zoneId,
      generatedAt: new Date().toISOString(),
      horizonMinutes,
      points: [
        { timestamp: new Date().toISOString(), demandMw: 88.0, lowerBoundMw: 84.0, upperBoundMw: 92.0 },
      ],
      spikeRisk: { level: "normal", probability: 0.12, predictedPeakMw: 88.0 },
      modelVersion: "lightgbm-demand-v1.0",
    });
    serviceClient.getRenewableStatuses = async () => [
      {
        assetId: "SOLAR_FARM_ALPHA",
        assetType: "solar",
        timestamp: new Date().toISOString(),
        expectedMw: 28.5,
        actualMw: 28.0,
        performanceRatio: 0.98,
        anomaly: false,
      },
    ];
    serviceClient.solveOptimization = async (input) => ({
      scenarioId: input.scenarioId,
      status: "feasible",
      solverStatus: "optimal",
      actions: [],
      before: { demandMw: 85.4, renewableMw: 56.6, curtailmentMw: 0, gridStressIndex: 0.42 },
      after: { demandMw: 85.4, renewableMw: 56.6, curtailmentMw: 0, gridStressIndex: 0.35 },
      objectiveValue: 10.0,
      solveDurationMs: 15,
    });

    const aggregator = new GridStateAggregator({ serviceClient });

    const snapshot = await aggregator.getSnapshot("NL_LIANDER_SUB_01");
    const val = validateAggregatedGridSnapshot(snapshot);

    assert.equal(val.success, true);
    assert.equal(snapshot.zoneId, "NL_LIANDER_SUB_01");

    // Check all fields are available
    assert.equal(snapshot.currentDemand.status, "available");
    assert.equal(typeof snapshot.currentDemand.valueMw, "number");

    assert.equal(snapshot.forecastDemand.status, "available");
    assert.equal(typeof snapshot.forecastDemand.horizon15mMw, "number");

    assert.equal(snapshot.renewableGeneration.status, "available");
    assert.equal(typeof snapshot.renewableGeneration.totalMw, "number");

    assert.equal(snapshot.gridStress.status, "available");
    assert.equal(typeof snapshot.gridStress.stressIndex, "number");

    assert.equal(snapshot.systemHealth.isDegraded, false);
    assert.equal(snapshot.systemHealth.unavailableDependencies.length, 0);
  });

  await t.test("Correctly flags 'unavailable' when forecasting dependency fails without inventing data", async () => {
    const serviceClient = new ServiceClient(config);
    serviceClient.getGridState = async () => ({
      timestamp: new Date().toISOString(),
      zoneId: "NL_LIANDER_SUB_01",
      demandMw: 85.4,
      solarGenerationMw: 32.1,
      windGenerationMw: 24.5,
      netLoadMw: 28.8,
      batterySocPercent: 65.0,
      batteryPowerMw: 0.0,
      curtailmentMw: 0.0,
      gridFrequencyHz: 50.01,
      gridStressIndex: 0.42,
      activeAlertsCount: 0,
    });
    serviceClient.getRenewableStatuses = async () => [
      {
        assetId: "SOLAR_FARM_ALPHA",
        assetType: "solar",
        timestamp: new Date().toISOString(),
        expectedMw: 28.5,
        actualMw: 28.0,
        performanceRatio: 0.98,
        anomaly: false,
      },
    ];
    // Simulate forecasting failure by stubbing
    serviceClient.getDemandForecast = async () => {
      throw new Error("Forecasting service connection timeout");
    };

    const aggregator = new GridStateAggregator({ serviceClient });
    const snapshot = await aggregator.getSnapshot("NL_LIANDER_SUB_01");

    assert.equal(snapshot.forecastDemand.status, "unavailable");
    assert.equal(snapshot.forecastDemand.horizon15mMw, undefined);
    assert.equal(snapshot.forecastDemand.spikeRiskLevel, undefined);

    // Other fields must remain available
    assert.equal(snapshot.currentDemand.status, "available");
    assert.equal(snapshot.renewableGeneration.status, "available");

    // System health must reflect degradation
    assert.equal(snapshot.systemHealth.isDegraded, true);
    assert.ok(snapshot.systemHealth.unavailableDependencies.includes("forecasting"));
  });

  await t.test("Correctly flags 'unavailable' when renewable dependency fails", async () => {
    const serviceClient = new ServiceClient(config);
    serviceClient.getGridState = async () => ({
      timestamp: new Date().toISOString(),
      zoneId: "NL_LIANDER_SUB_01",
      demandMw: 85.4,
      solarGenerationMw: 32.1,
      windGenerationMw: 24.5,
      netLoadMw: 28.8,
      batterySocPercent: 65.0,
      batteryPowerMw: 0.0,
      curtailmentMw: 0.0,
      gridFrequencyHz: 50.01,
      gridStressIndex: 0.42,
      activeAlertsCount: 0,
    });
    serviceClient.getDemandForecast = async () => ({
      zoneId: "NL_LIANDER_SUB_01",
      generatedAt: new Date().toISOString(),
      horizonMinutes: 15,
      points: [{ timestamp: new Date().toISOString(), demandMw: 88.0 }],
      spikeRisk: { level: "normal", probability: 0.12, predictedPeakMw: 88.0 },
      modelVersion: "lightgbm-demand-v1.0",
    });
    serviceClient.getRenewableStatuses = async () => {
      throw new Error("Renewable SCADA gateway down");
    };

    const aggregator = new GridStateAggregator({ serviceClient });
    const snapshot = await aggregator.getSnapshot("NL_LIANDER_SUB_01");

    assert.equal(snapshot.renewableGeneration.status, "unavailable");
    assert.equal(snapshot.renewableGeneration.totalMw, undefined);
    assert.equal(snapshot.renewableAnomalies.status, "unavailable");

    assert.equal(snapshot.systemHealth.isDegraded, true);
    assert.ok(snapshot.systemHealth.unavailableDependencies.includes("renewable"));
  });

  await t.test("Correctly flags 'unavailable' when data telemetry layer fails", async () => {
    const serviceClient = new ServiceClient(config);
    serviceClient.getDemandForecast = async () => ({
      zoneId: "NL_LIANDER_SUB_01",
      generatedAt: new Date().toISOString(),
      horizonMinutes: 15,
      points: [{ timestamp: new Date().toISOString(), demandMw: 88.0 }],
      spikeRisk: { level: "normal", probability: 0.12, predictedPeakMw: 88.0 },
      modelVersion: "lightgbm-demand-v1.0",
    });
    serviceClient.getRenewableStatuses = async () => [
      {
        assetId: "SOLAR_FARM_ALPHA",
        assetType: "solar",
        timestamp: new Date().toISOString(),
        expectedMw: 28.5,
        actualMw: 28.0,
        performanceRatio: 0.98,
        anomaly: false,
      },
    ];
    serviceClient.getGridState = async () => {
      throw new Error("Substation telemetry polling failed");
    };

    const aggregator = new GridStateAggregator({ serviceClient });
    const snapshot = await aggregator.getSnapshot("NL_LIANDER_SUB_01");

    assert.equal(snapshot.currentDemand.status, "unavailable");
    assert.equal(snapshot.currentDemand.valueMw, undefined);
    assert.equal(snapshot.gridStress.status, "unavailable");

    assert.equal(snapshot.systemHealth.isDegraded, true);
    assert.ok(snapshot.systemHealth.unavailableDependencies.includes("data_telemetry"));
  });

  await t.test("API Gateway /api/grid/snapshot endpoint returns aggregated snapshot", async () => {
    const customServiceClient = new ServiceClient(config);
    customServiceClient.getGridState = async () => ({
      timestamp: new Date().toISOString(),
      zoneId: "NL_LIANDER_SUB_01",
      demandMw: 85.4,
      solarGenerationMw: 32.1,
      windGenerationMw: 24.5,
      netLoadMw: 28.8,
      batterySocPercent: 65.0,
      batteryPowerMw: 0.0,
      curtailmentMw: 0.0,
      gridFrequencyHz: 50.01,
      gridStressIndex: 0.42,
      activeAlertsCount: 0,
    });
    customServiceClient.getDemandForecast = async () => ({
      zoneId: "NL_LIANDER_SUB_01",
      generatedAt: new Date().toISOString(),
      horizonMinutes: 15,
      points: [{ timestamp: new Date().toISOString(), demandMw: 88.0 }],
      spikeRisk: { level: "normal", probability: 0.12, predictedPeakMw: 88.0 },
      modelVersion: "lightgbm-demand-v1.0",
    });
    customServiceClient.getRenewableStatuses = async () => [
      {
        assetId: "SOLAR_FARM_ALPHA",
        assetType: "solar",
        timestamp: new Date().toISOString(),
        expectedMw: 28.5,
        actualMw: 28.0,
        performanceRatio: 0.98,
        anomaly: false,
      },
    ];
    customServiceClient.solveOptimization = async (input) => ({
      scenarioId: input.scenarioId,
      status: "feasible",
      solverStatus: "optimal",
      actions: [],
      before: { demandMw: 85.4, renewableMw: 56.6, curtailmentMw: 0, gridStressIndex: 0.42 },
      after: { demandMw: 85.4, renewableMw: 56.6, curtailmentMw: 0, gridStressIndex: 0.35 },
      objectiveValue: 10.0,
      solveDurationMs: 15,
    });
    const server = createApiServer({ config, serviceClient: customServiceClient });
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
    const port = (server.address() as AddressInfo).port;

    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/grid/snapshot?zoneId=NL_LIANDER_SUB_01`);
      assert.equal(res.status, 200);

      const json = await res.json();
      assert.equal(json.success, true);
      assert.equal(json.data.zoneId, "NL_LIANDER_SUB_01");
      assert.equal(json.data.currentDemand.status, "available");
      assert.equal(json.data.forecastDemand.status, "available");
      assert.equal(json.data.renewableGeneration.status, "available");
      assert.equal(json.data.gridStress.status, "available");
    } finally {
      await new Promise<void>((resolve) => server.close(() => resolve()));
    }
  });
});
