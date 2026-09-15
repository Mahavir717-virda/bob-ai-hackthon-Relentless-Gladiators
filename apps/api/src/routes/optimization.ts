import type { ServerResponse } from "node:http";
import type { RequestContext } from "../types.ts";
import type { ServiceClient } from "../service-client.ts";
import { validateOptimizationInput } from "../../../../shared/contracts/OptimizationInput.ts";
import { validateOptimizationResult } from "../../../../shared/contracts/OptimizationResult.ts";
import { buildOptimizationInputFromRenewables } from "../services/adapters/renewable-optimization-adapter.ts";


export async function handleOptimization(
  res: ServerResponse,
  ctx: RequestContext,
  serviceClient: ServiceClient,
  body?: any
): Promise<void> {
  if (ctx.method === "GET") {
    const defaultGrid = await serviceClient.getGridState();
    const defaultForecast = await serviceClient.getDemandForecast(defaultGrid.zoneId || "NL_LIANDER_SUB_01", 15);
    const renewableStatuses = await serviceClient.getRenewableStatuses();

    const dynamicInput = buildOptimizationInputFromRenewables(
      renewableStatuses,
      defaultGrid,
      defaultForecast,
      { scenarioId: "LATEST_SNAPSHOT" }
    );

    const optResult = await serviceClient.solveOptimization(dynamicInput);
    res.writeHead(200, {
      "Content-Type": "application/json",
      "X-Request-ID": ctx.requestId,
    });
    res.end(
      JSON.stringify({
        success: true,
        requestId: ctx.requestId,
        timestamp: new Date().toISOString(),
        data: optResult,
      })
    );
    return;
  }

  if (ctx.method === "POST") {
    const validation = validateOptimizationInput(body);
    if (!validation.success) {
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
            code: "INVALID_OPTIMIZATION_INPUT",
            message: "Request payload does not conform to OptimizationInput contract",
            details: validation.errors,
          },
        })
      );
      return;
    }

    const optResult = await serviceClient.solveOptimization(validation.data!);
    const resultValidation = validateOptimizationResult(optResult);

    if (!resultValidation.success) {
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
            code: "OPTIMIZER_CONTRACT_ERROR",
            message: "Solver response failed OptimizationResult schema validation",
            details: resultValidation.errors,
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
        data: optResult,
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
