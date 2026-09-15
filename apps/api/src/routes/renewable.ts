import type { ServerResponse } from "node:http";
import type { RequestContext } from "../types.ts";
import type { ServiceClient } from "../service-client.ts";
import { validateRenewableStatus } from "../../../../shared/contracts/RenewableStatus.ts";


export async function handleRenewable(
  res: ServerResponse,
  ctx: RequestContext,
  serviceClient: ServiceClient
): Promise<void> {
  const isAnomaliesOnly = ctx.url.pathname.endsWith("/anomalies");
  const statuses = await serviceClient.getRenewableStatuses();

  // Validate all elements against the contract
  for (const s of statuses) {
    const val = validateRenewableStatus(s);
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
            code: "CONTRACT_VALIDATION_ERROR",
            message: "Renewable status item failed schema validation",
            details: val.errors,
          },
        })
      );
      return;
    }
  }

  const responseData = isAnomaliesOnly ? statuses.filter((s) => s.anomaly) : statuses;

  res.writeHead(200, {
    "Content-Type": "application/json",
    "X-Request-ID": ctx.requestId,
  });
  res.end(
    JSON.stringify({
      success: true,
      requestId: ctx.requestId,
      timestamp: new Date().toISOString(),
      data: responseData,
    })
  );
}
