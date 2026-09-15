import type { ServerResponse } from "node:http";
import type { RequestContext } from "../types.ts";
import type { ServiceClient } from "../service-client.ts";
import { validateScenario } from "../../../../shared/contracts/Scenario.ts";


export async function handleScenario(
  res: ServerResponse,
  ctx: RequestContext,
  serviceClient: ServiceClient,
  body?: any
): Promise<void> {
  if (ctx.method === "GET") {
    const list = [
      {
        scenarioId: "DEMAND_SPIKE_PLUS_RENEWABLE_DROP",
        name: "Deterministic Demand Surge with Cloud Cover Drop",
        description: "Replays Liander 2024 grid event with simultaneous solar generation reduction.",
        historicalSourceTimestamp: "2024-06-12T14:00:00.000Z",
        injectedEvents: [
          {
            timestampOffsetMinutes: 15,
            eventType: "demand_spike",
            severity: 0.18,
            assetOrZoneId: "NL_LIANDER_SUB_01",
          },
          {
            timestampOffsetMinutes: 15,
            eventType: "solar_drop",
            severity: 0.55,
            assetOrZoneId: "SOLAR_FARM_ZEELAND_03",
          },
        ],
        expectedOutcome: {
          expectedSpikeClass: "severe",
          expectedAnomalyScoreMin: 0.80,
          expectedFeasibleOptimization: true,
        },
      },
    ];

    res.writeHead(200, {
      "Content-Type": "application/json",
      "X-Request-ID": ctx.requestId,
    });
    res.end(
      JSON.stringify({
        success: true,
        requestId: ctx.requestId,
        timestamp: new Date().toISOString(),
        data: list,
      })
    );
    return;
  }

  if (ctx.method === "POST") {
    const scenarioId = body?.scenarioId || "DEMAND_SPIKE_PLUS_RENEWABLE_DROP";
    const { scenario, result } = await serviceClient.replayScenario(scenarioId);

    const val = validateScenario(scenario);
    if (!val.success) {
      res.writeHead(500, {
        "Content-Type": "application/json",
        "X-Request-ID": ctx.requestId,
      });
      res.end(
        JSON.stringify({
          success: false,
          requestId: ctx.requestId,
          timestamp: new Date().toISOString(),
          error: {
            code: "SCENARIO_SCHEMA_ERROR",
            message: "Scenario fixture failed schema validation",
            details: val.errors,
          },
        })
      );
      return;
    }

    res.writeHead(200, {
      "Content-Type": "application/json",
      "X-Request-ID": ctx.requestId,
    });
    res.end(
      JSON.stringify({
        success: true,
        requestId: ctx.requestId,
        timestamp: new Date().toISOString(),
        data: {
          scenario,
          optimizationResult: result,
        },
      })
    );
    return;
  }

  res.writeHead(405, { "Content-Type": "application/json", "X-Request-ID": ctx.requestId });
  res.end(
    JSON.stringify({
      success: false,
      requestId: ctx.requestId,
      timestamp: new Date().toISOString(),
      error: { code: "METHOD_NOT_ALLOWED", message: `Method ${ctx.method} not allowed` },
    })
  );
}
