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
    assert.equal(typeof snapshot.forecastDemand.horizon60mMw, "number");

    assert.equal(snapshot.renewableGeneration.status, "available");
    assert.equal(typeof snapshot.renewableGeneration.totalMw, "number");

    assert.equal(snapshot.curtailment.status, "available");
    assert.equal(snapshot.gridStress.status, "available");
    assert.equal(typeof snapshot.gridStress.stressIndex, "number");

    assert.equal(snapshot.systemHealth.isDegraded, false);
    assert.equal(snapshot.systemHealth.unavailableDependencies.length, 0);
  });

  await t.test("Correctly flags 'unavailable' when forecasting dependency fails without inventing data", async () => {
    const serviceClient = new ServiceClient(config);
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
    const server = createApiServer({ config });
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
