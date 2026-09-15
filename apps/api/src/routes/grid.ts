import type { ServerResponse } from "node:http";
import type { RequestContext } from "../types.ts";
import type { ServiceClient } from "../service-client.ts";
import { validateGridState } from "../../../../shared/contracts/GridState.ts";
import { validateAggregatedGridSnapshot } from "../../../../shared/contracts/AggregatedGridSnapshot.ts";
import { GridStateAggregator } from "../services/grid-state-aggregator.ts";

export async function handleGrid(
  res: ServerResponse,
  ctx: RequestContext,
  serviceClient: ServiceClient
): Promise<void> {
  const zoneId = ctx.url.searchParams.get("zoneId") || "NL_LIANDER_SUB_01";

  // Route: /api/grid/snapshot — Read-only operational snapshot from GridStateAggregator
  if (ctx.url.pathname.endsWith("/snapshot")) {
    const aggregator = new GridStateAggregator({ serviceClient });
    const snapshot = await aggregator.getSnapshot(zoneId);

    const validation = validateAggregatedGridSnapshot(snapshot);
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
            code: "SNAPSHOT_VALIDATION_ERROR",
            message: "Aggregated grid snapshot failed schema validation",
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
        data: snapshot,
      })
    );
    return;
  }

  // Default Route: /api/grid or /api/grid/state
  const gridState = await serviceClient.getGridState(zoneId);
  const validation = validateGridState(gridState);

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
          message: "Grid state failed schema validation",
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
      data: gridState,
    })
  );
}
