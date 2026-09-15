import type { ServerResponse } from "node:http";
import type { RequestContext } from "../types.ts";
import type { ServiceClient } from "../service-client.ts";
import { validateDemandForecast } from "../../../../shared/contracts/DemandForecast.ts";


export async function handleForecast(
  res: ServerResponse,
  ctx: RequestContext,
  serviceClient: ServiceClient,
  body?: any
): Promise<void> {
  const zoneId = ctx.url.searchParams.get("zoneId") || body?.zoneId || "NL_LIANDER_SUB_01";
  const horizonParam = ctx.url.searchParams.get("horizon") || body?.horizonMinutes || "15";
  const horizonMinutes = parseInt(String(horizonParam), 10);

  if (isNaN(horizonMinutes) || horizonMinutes <= 0) {
    res.writeHead(400, {
      "Content-Type": "application/json",
      "X-Request-ID": ctx.requestId,
    });
    res.end(
      JSON.stringify({
        success: false,
        requestId: ctx.requestId,
        timestamp: new Date().toISOString(),
        error: {
          code: "INVALID_HORIZON",
          message: "horizon query parameter must be a positive integer in minutes (e.g. 15, 30, 60)",
          details: { received: horizonParam },
        },
      })
    );
    return;
  }

  const forecast = await serviceClient.getDemandForecast(zoneId, horizonMinutes);
  const validation = validateDemandForecast(forecast);

  if (!validation.success) {
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
          code: "CONTRACT_VALIDATION_ERROR",
          message: "Downstream forecast failed schema validation",
          details: validation.errors,
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
      data: forecast,
    })
  );
}
