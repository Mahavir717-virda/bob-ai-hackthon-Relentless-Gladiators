import test from "node:test";
import assert from "node:assert/strict";
import type { AddressInfo } from "node:net";

import { createApiServer } from "../../apps/api/src/server.ts";
import { loadConfig } from "../../apps/api/src/config.ts";

test("Dashboard Dynamicity & Data Integrity Suite", async (t) => {
  const config = loadConfig();
  const server = createApiServer({ config });

  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = (server.address() as AddressInfo).port;
  const baseUrl = `http://127.0.0.1:${port}`;

  t.after(() => {
    return new Promise<void>((resolve) => server.close(() => resolve()));
  });

  await t.test("Operational snapshot returns dynamic status for all dependencies", async () => {
    const res = await fetch(`${baseUrl}/api/grid/snapshot?zoneId=NL_LIANDER_SUB_01`);
    assert.equal(res.status, 200);

    const json = await res.json();
    assert.equal(json.success, true);
    const snapshot = json.data;

    assert.ok(snapshot.timestamp);
    assert.equal(snapshot.zoneId, "NL_LIANDER_SUB_01");

    // Check that availability status fields are explicitly populated
    assert.ok(["available", "unavailable"].includes(snapshot.currentDemand.status));
    assert.ok(["available", "unavailable"].includes(snapshot.forecastDemand.status));
    assert.ok(["available", "unavailable"].includes(snapshot.renewableGeneration.status));
    assert.ok(["available", "unavailable"].includes(snapshot.gridStress.status));

    if (snapshot.currentDemand.status === "available") {
      assert.equal(typeof snapshot.currentDemand.valueMw, "number");
    }
  });

  await t.test("Varying forecast horizons produce distinct dynamic step points", async () => {
    const res15 = await fetch(`${baseUrl}/api/forecast?zoneId=NL_LIANDER_SUB_01&horizon=15`);
    const json15 = await res15.json();
    assert.equal(json15.success, true);

    const res60 = await fetch(`${baseUrl}/api/forecast?zoneId=NL_LIANDER_SUB_01&horizon=60`);
    const json60 = await res60.json();
    assert.equal(json60.success, true);

    // 60-minute horizon must contain more data points than 15-minute horizon
    assert.ok(json60.data.points.length >= json15.data.points.length);
    assert.notDeepEqual(json15.data.points, json60.data.points);
  });

  await t.test("MILP solver returns dynamic optimization result depending on input constraints", async () => {
    const basePayload = {
      scenarioId: "DYNAMICAL_TEST_01",
      targetTimestamp: new Date().toISOString(),
      horizonMinutes: 15,
      currentGridState: {
        timestamp: new Date().toISOString(),
        zoneId: "NL_LIANDER_SUB_01",
        demandMw: 95.0,
        solarGenerationMw: 10.0,
        windGenerationMw: 5.0,
        netLoadMw: 80.0,
        batterySocPercent: 40.0,
        batteryPowerMw: 0.0,
        curtailmentMw: 0.0,
        gridFrequencyHz: 50.0,
        gridStressIndex: 0.85,
        activeAlertsCount: 1,
      },
      demandForecast: {
        zoneId: "NL_LIANDER_SUB_01",
        generatedAt: new Date().toISOString(),
        horizonMinutes: 15,
        points: [{ timestamp: new Date().toISOString(), demandMw: 95.0 }],
        spikeRisk: { level: "severe", probability: 0.75, predictedPeakMw: 95.0 },
        modelVersion: "v1",
      },
      renewableForecastMw: 15.0,
      batteryConstraints: {
        maxCapacityMwh: 40.0,
        currentSocPercent: 40.0,
        minSocPercent: 10.0,
        maxSocPercent: 90.0,
        maxChargePowerMw: 20.0,
        maxDischargePowerMw: 20.0,
        roundTripEfficiency: 0.9,
      },
      flexibleLoadConstraints: {
        totalFlexibleMw: 10.0,
        maxShiftDurationMinutes: 60,
        shiftCostPerMw: 15.0,
      },
      curtailmentPenaltyPerMw: 50.0,
    };

    // Run solver with 20 MW discharge capacity
    const resA = await fetch(`${baseUrl}/api/optimization`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(basePayload),
    });
    const jsonA = await resA.json();
    assert.equal(resA.status, 200, `Expected 200 but got ${resA.status}: ${JSON.stringify(jsonA)}`);
    assert.equal(jsonA.success, true);

    // Run solver with 0 MW discharge capacity (constrained)
    const resB = await fetch(`${baseUrl}/api/optimization`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...basePayload,
        batteryConstraints: {
          ...basePayload.batteryConstraints,
          maxDischargePowerMw: 0.0,
        },
        flexibleLoadConstraints: {
          ...basePayload.flexibleLoadConstraints,
          totalFlexibleMw: 0.0,
        },
      }),
    });
    const jsonB = await resB.json();
    assert.equal(resB.status, 200, `Expected 200 but got ${resB.status}: ${JSON.stringify(jsonB)}`);
    assert.equal(jsonB.success, true);

    // Results must differ dynamically based on physical constraints
    assert.notEqual(jsonA.data.after.gridStressIndex, jsonB.data.after.gridStressIndex);
  });
});
