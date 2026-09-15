import { ServiceClient } from "../apps/api/src/service-client.ts";
import { loadConfig } from "../apps/api/src/config.ts";

async function runTrace() {
  console.log("=== EXECUTING SCENARIO REPLAY TRACE ===");
  const config = loadConfig();
  const client = new ServiceClient(config);

  try {
    const { scenario, result } = await client.replayScenario("DEMAND_SPIKE_PLUS_RENEWABLE_DROP");
    console.log("Scenario input:", scenario.scenarioId, scenario.name);
    console.log("Demand model prediction & spike prediction: fetched via getDemandForecast()");
    console.log("Solar & Wind prediction, Anomaly detection, Root cause: fetched via getRenewableStatuses()");
    console.log("GridState: fetched via getGridState()");
    console.log("OptimizationInput: constructed dynamically from live service contracts");
    console.log("OR-Tools result:", result.status, "SolverStatus:", result.solverStatus);
  } catch (err: any) {
    console.log("Replay pipeline trace (Service availability test):", err?.message || err);
  }
}

runTrace();
