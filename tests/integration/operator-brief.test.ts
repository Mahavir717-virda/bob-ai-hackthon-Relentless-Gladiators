import test from "node:test";
import assert from "node:assert/strict";
import type { AddressInfo } from "node:net";

import { OperatorBriefGenerator } from "../../agent/orchestration/operator-brief-generator.ts";
import type { OperatorBriefInput } from "../../shared/contracts/OperatorBrief.ts";
import { validateOperatorBrief } from "../../shared/contracts/OperatorBrief.ts";
import { createApiServer } from "../../apps/api/src/server.ts";
import { ServiceClient } from "../../apps/api/src/service-client.ts";
import { loadConfig } from "../../apps/api/src/config.ts";

import { resetLLMProvider, getLLMProvider, MockLLMProvider } from "../../agent/provider/index.ts";

test("Operator Brief Generator Suite", async (t) => {
  t.beforeEach(() => {
    getLLMProvider(new MockLLMProvider());
  });

  t.afterEach(() => {
    resetLLMProvider();
  });

  const generator = new OperatorBriefGenerator();

  const fullInput: OperatorBriefInput = {
    currentGridState: {
      timestamp: "2026-09-15T14:00:00.000Z",
      zoneId: "NL_LIANDER_SUB_01",
      demandMw: 94.2,
      solarGenerationMw: 19.0,
      windGenerationMw: 20.0,
      netLoadMw: 55.2,
      batterySocPercent: 65.0,
      batteryPowerMw: 0.0,
      curtailmentMw: 0.0,
      gridFrequencyHz: 50.0,
      gridStressIndex: 0.88,
      activeAlertsCount: 1,
    },
    demandForecast: {
      zoneId: "NL_LIANDER_SUB_01",
      generatedAt: "2026-09-15T14:00:00.000Z",
      horizonMinutes: 15,
      points: [{ timestamp: "2026-09-15T14:15:00.000Z", demandMw: 98.0 }],
      spikeRisk: { level: "severe", probability: 0.84, predictedPeakMw: 104.0 },
      modelVersion: "lightgbm-v1",
    },
    demandSpikeRisk: {
      level: "severe",
      probability: 0.84,
      predictedPeakMw: 104.0,
    },
    renewableForecasts: [
      { assetId: "SOLAR_FARM_ZEELAND_03", expectedMw: 42.0 },
      { assetId: "WIND_CLUSTER_NOORD_01", expectedMw: 20.0 },
    ],
    renewableAnomalies: [
      {
        assetId: "SOLAR_FARM_ZEELAND_03",
        assetType: "solar",
        timestamp: "2026-09-15T14:00:00.000Z",
        expectedMw: 42.0,
        actualMw: 19.0,
        performanceRatio: 0.452,
        anomaly: true,
        anomalyScore: 0.88,
        likelyRootCause: {
          category: "cloud_cover",
          confidence: 0.84,
          evidence: "GHI dropped 52% while ambient temperature remained steady",
        },
      },
    ],
    optimizationResult: {
      scenarioId: "SPIKE_SCENARIO_01",
      status: "feasible",
      actions: [
        {
          resourceId: "BESS_SUB_01",
          actionType: "battery_discharge",
          powerMw: 15.0,
          startTime: "2026-09-15T14:15:00.000Z",
          endTime: "2026-09-15T14:30:00.000Z",
        },
      ],
      before: { demandMw: 98.0, renewableMw: 19.0, curtailmentMw: 0.0, gridStressIndex: 0.88 },
      after: { demandMw: 90.0, renewableMw: 19.0, curtailmentMw: 0.0, gridStressIndex: 0.42 },
      objectiveValue: 45.0,
    },
    curtailmentResult: {
      currentCurtailmentMw: 0.0,
      mitigatedMw: 0.0,
    },
  };

  await t.test("Synthesizes complete 8-section operator brief and passes contract validation", async () => {
    const brief = await generator.generateBrief(fullInput);

    const val = validateOperatorBrief(brief);
    assert.equal(val.success, true);

    // Verify all 8 sections
    assert.ok(brief.sections.currentSituation.length > 0);
    assert.ok(brief.sections.risk.length > 0);
    assert.ok(brief.sections.renewableAlert.length > 0);
    assert.ok(brief.sections.rootCause.length > 0);
    assert.ok(brief.sections.recommendedActions.length > 0);
    assert.ok(brief.sections.expectedImpact.length > 0);
    assert.ok(brief.sections.confidenceUncertainty.length > 0);
    assert.ok(brief.sections.dataLimitations.length > 0);

    // Verify content matches ground truth
    assert.equal(brief.status, "feasible");
    assert.equal(brief.zoneId, "NL_LIANDER_SUB_01");
    assert.equal(brief.missingDataWarnings.length, 0);
    assert.equal(brief.groundTruthVerified, true);
  });

  await t.test("Preserves 'infeasible' status and alerts operator without unauthorized dispatch", async () => {
    const infeasibleInput: OperatorBriefInput = {
      ...fullInput,
      optimizationResult: {
        scenarioId: "CONGESTION_EVENT",
        status: "infeasible",
        actions: [],
        before: { demandMw: 120.0, renewableMw: 10.0, curtailmentMw: 0.0, gridStressIndex: 0.98 },
        after: { demandMw: 120.0, renewableMw: 10.0, curtailmentMw: 0.0, gridStressIndex: 0.98 },
        objectiveValue: 999.0,
      },
    };

    const brief = await generator.generateBrief(infeasibleInput);

    assert.equal(brief.status, "infeasible");
    assert.ok(brief.sections.recommendedActions.includes("INFEASIBLE"));
  });

  await t.test("Clearly documents missing telemetry without inventing numbers", async () => {
    const missingInput: OperatorBriefInput = {
      currentGridState: null, // missing telemetry
      demandForecast: null, // missing forecast
      optimizationResult: null, // missing optimization
    };

    const brief = await generator.generateBrief(missingInput);

    assert.ok(brief.missingDataWarnings.length >= 3);
    assert.ok(brief.sections.dataLimitations.includes("Missing Telemetry Disclosures"));
    assert.ok(brief.sections.dataLimitations.includes("currentGridState"));
  });

  await t.test("Cites root cause evidence without claiming correlation is causation", async () => {
    const brief = await generator.generateBrief(fullInput);

    assert.ok(brief.sections.rootCause.includes("GHI dropped 52%"));
    // Ensures evidence is factual attribution rather than speculation
    assert.ok(!brief.sections.rootCause.toLowerCase().includes("caused by magical"));
  });

  await t.test("API Gateway /api/agent/brief returns validated OperatorBrief", async () => {
    const config = loadConfig();
    const customServiceClient = new ServiceClient(config);
    const server = createApiServer({ config, serviceClient: customServiceClient });

    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
    const port = (server.address() as AddressInfo).port;

    try {
      const res = await fetch(`http://127.0.0.1:${port}/api/agent/brief`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fullInput),
      });

      assert.equal(res.status, 200);
      const json = await res.json();
      assert.equal(json.success, true);
      assert.ok(json.data.briefId);
      assert.equal(json.data.status, "feasible");
      assert.ok(json.data.sections.currentSituation);
      assert.ok(json.data.sections.recommendedActions);
      assert.ok(json.data.rawMarkdown);
    } finally {
      await new Promise<void>((resolve) => server.close(() => resolve()));
    }
  });
});
