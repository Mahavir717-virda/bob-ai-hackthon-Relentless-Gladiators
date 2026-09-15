import test from "node:test";
import assert from "node:assert/strict";
import type { AddressInfo } from "node:net";

import { createApiServer } from "../../apps/api/src/server.ts";
import { loadConfig } from "../../apps/api/src/config.ts";
import { resetLLMProvider, getLLMProvider, MockLLMProvider } from "../../agent/provider/index.ts";

test("API Gateway: End-to-end integration and routing suite", async (t) => {
  t.beforeEach(() => {
    getLLMProvider(new MockLLMProvider());
  });

  t.afterEach(() => {
    resetLLMProvider();
  });

  const config = loadConfig();
  const server = createApiServer({ config });

  // Bind to ephemeral port
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = (server.address() as AddressInfo).port;
  const baseUrl = `http://127.0.0.1:${port}`;

  t.after(() => {
    return new Promise<void>((resolve) => server.close(() => resolve()));
  });

  await t.test("GET /health returns 200 and status ok", async () => {
    const res = await fetch(`${baseUrl}/health`);
    assert.equal(res.status, 200);
    assert.ok(res.headers.get("x-request-id"));

    const json = await res.json();
    assert.equal(json.success, true);
    assert.equal(json.data.status, "ok");
    assert.equal(typeof json.data.uptimeSeconds, "number");
  });

  await t.test("GET /api/grid returns typed GridState", async () => {
    const res = await fetch(`${baseUrl}/api/grid?zoneId=NL_LIANDER_SUB_01`);
    assert.equal(res.status, 200);

    const json = await res.json();
    assert.equal(json.success, true);
    assert.equal(json.data.zoneId, "NL_LIANDER_SUB_01");
    assert.equal(typeof json.data.demandMw, "number");
    assert.equal(typeof json.data.gridStressIndex, "number");
  });

  await t.test("GET /api/forecast returns DemandForecast and validates horizon", async () => {
    // Valid request
    const validRes = await fetch(`${baseUrl}/api/forecast?zoneId=NL_LIANDER_SUB_01&horizon=30`);
    assert.equal(validRes.status, 200);
    const validJson = await validRes.json();
    assert.equal(validJson.success, true);
    assert.equal(validJson.data.horizonMinutes, 30);
    assert.ok(Array.isArray(validJson.data.points));

    // Invalid horizon request (negative)
    const invalidRes = await fetch(`${baseUrl}/api/forecast?horizon=-10`);
    assert.equal(invalidRes.status, 400);
    const invalidJson = await invalidRes.json();
    assert.equal(invalidJson.success, false);
    assert.equal(invalidJson.error.code, "INVALID_HORIZON");
  });

  await t.test("GET /api/renewable returns telemetry and anomalies", async () => {
    const res = await fetch(`${baseUrl}/api/renewable`);
    assert.equal(res.status, 200);
    const json = await res.json();
    assert.equal(json.success, true);
    assert.ok(Array.isArray(json.data));
    assert.ok(json.data.length >= 2);

    const anomaliesRes = await fetch(`${baseUrl}/api/renewable/anomalies`);
    assert.equal(anomaliesRes.status, 200);
    const anomaliesJson = await anomaliesRes.json();
    assert.equal(anomaliesJson.success, true);
    assert.ok(Array.isArray(anomaliesJson.data));
  });

  await t.test("POST /api/optimization validates input constraints and returns result", async () => {
    // Invalid payload: battery minSoc > maxSoc
    const invalidPayload = {
      scenarioId: "TEST_BAD_SOC",
      targetTimestamp: new Date().toISOString(),
      horizonMinutes: 15,
      currentGridState: {
        timestamp: new Date().toISOString(),
        zoneId: "NL_SUB_01",
        demandMw: 80,
        solarGenerationMw: 20,
        windGenerationMw: 10,
        netLoadMw: 50,
        batterySocPercent: 50,
        batteryPowerMw: 0,
        curtailmentMw: 0,
        gridFrequencyHz: 50.0,
        gridStressIndex: 0.5,
        activeAlertsCount: 0,
      },
      demandForecast: {
        zoneId: "NL_SUB_01",
        generatedAt: new Date().toISOString(),
        horizonMinutes: 15,
        points: [{ timestamp: new Date().toISOString(), demandMw: 80 }],
        spikeRisk: { level: "normal", probability: 0.1, predictedPeakMw: 80 },
        modelVersion: "v1",
      },
      renewableForecastMw: 30,
      batteryConstraints: {
        maxCapacityMwh: 20,
        currentSocPercent: 50,
        minSocPercent: 80, // Invalid: min > max
        maxSocPercent: 20,
        maxChargePowerMw: 10,
        maxDischargePowerMw: 10,
        roundTripEfficiency: 0.9,
      },
      flexibleLoadConstraints: {
        totalFlexibleMw: 5,
        maxShiftDurationMinutes: 30,
        shiftCostPerMw: 10,
      },
      curtailmentPenaltyPerMw: 50,
    };

    const failRes = await fetch(`${baseUrl}/api/optimization`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(invalidPayload),
    });
    assert.equal(failRes.status, 400);
    const failJson = await failRes.json();
    assert.equal(failJson.success, false);
    assert.equal(failJson.error.code, "INVALID_OPTIMIZATION_INPUT");

    // Valid payload
    const validPayload = {
      ...invalidPayload,
      batteryConstraints: {
        ...invalidPayload.batteryConstraints,
        minSocPercent: 10,
        maxSocPercent: 90,
      },
    };

    const passRes = await fetch(`${baseUrl}/api/optimization`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(validPayload),
    });
    assert.equal(passRes.status, 200);
    const passJson = await passRes.json();
    assert.equal(passJson.success, true);
    assert.equal(passJson.data.status, "feasible");
    assert.ok(passJson.data.actions !== undefined);
  });

  await t.test("POST /api/scenario/replay returns scenario trace", async () => {
    const res = await fetch(`${baseUrl}/api/scenario/replay`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenarioId: "DEMAND_SPIKE_PLUS_RENEWABLE_DROP" }),
    });
    assert.equal(res.status, 200);
    const json = await res.json();
    assert.equal(json.success, true);
    assert.equal(json.data.scenario.scenarioId, "DEMAND_SPIKE_PLUS_RENEWABLE_DROP");
    assert.equal(json.data.optimizationResult.status, "feasible");
  });

  await t.test("POST /api/agent validates context and returns operator brief", async () => {
    // Missing required fields
    const badRes = await fetch(`${baseUrl}/api/agent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId: "123" }),
    });
    assert.equal(badRes.status, 400);
    const badJson = await badRes.json();
    assert.equal(badJson.error.code, "INVALID_AGENT_CONTEXT");

    // Valid context
    const validContext = {
      sessionId: "OPERATOR_SESSION_42",
      timestamp: new Date().toISOString(),
      currentGridState: {
        timestamp: new Date().toISOString(),
        zoneId: "NL_LIANDER_SUB_01",
        demandMw: 92.4,
        solarGenerationMw: 18.0,
        windGenerationMw: 22.0,
        netLoadMw: 52.4,
        batterySocPercent: 60.0,
        batteryPowerMw: 0.0,
        curtailmentMw: 0.0,
        gridFrequencyHz: 50.0,
        gridStressIndex: 0.82,
        activeAlertsCount: 1,
      },
      demandForecast: {
        zoneId: "NL_LIANDER_SUB_01",
        generatedAt: new Date().toISOString(),
        horizonMinutes: 15,
        points: [{ timestamp: new Date().toISOString(), demandMw: 98.0 }],
        spikeRisk: { level: "severe", probability: 0.84, predictedPeakMw: 104.0 },
        modelVersion: "lightgbm-v1",
      },
      renewableStatuses: [
        {
          assetId: "SOLAR_FARM_ZEELAND_03",
          assetType: "solar",
          timestamp: new Date().toISOString(),
          expectedMw: 42.0,
          actualMw: 18.0,
          performanceRatio: 0.428,
          anomaly: true,
          likelyRootCause: {
            category: "cloud_cover",
            confidence: 0.86,
            evidence: "Cloud front passage detected",
          },
        },
      ],
      recommendations: [],
    };

    const passRes = await fetch(`${baseUrl}/api/agent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(validContext),
    });
    assert.equal(passRes.status, 200);
    const passJson = await passRes.json();
    assert.equal(passJson.success, true);
    assert.ok(passJson.data.briefMarkdown.includes("## 1. Current Situation"));
    assert.ok(passJson.data.briefMarkdown.includes("## 2. Risk Assessment"));
  });

  await t.test("Request ID propagation and custom header", async () => {
    const customReqId = "custom-uuid-test-999";
    const res = await fetch(`${baseUrl}/health`, {
      headers: { "X-Request-ID": customReqId },
    });
    assert.equal(res.headers.get("x-request-id"), customReqId);
    const json = await res.json();
    assert.equal(json.requestId, customReqId);
  });

  await t.test("Malformed JSON body returns 400", async () => {
    const res = await fetch(`${baseUrl}/api/optimization`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{ not valid json ...",
    });
    assert.equal(res.status, 400);
    const json = await res.json();
    assert.equal(json.error.code, "MALFORMED_JSON");
  });

  await t.test("404 on undefined endpoint returns structured error", async () => {
    const res = await fetch(`${baseUrl}/api/non-existent-route`);
    assert.equal(res.status, 404);
    const json = await res.json();
    assert.equal(json.success, false);
    assert.equal(json.error.code, "NOT_FOUND");
  });
});
