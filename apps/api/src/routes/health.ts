import type { ServerResponse } from "node:http";
import type { RequestContext } from "../types.ts";
import type { AppConfig } from "../config.ts";

export async function handleHealth(
  res: ServerResponse,
  ctx: RequestContext,
  config: AppConfig
): Promise<void> {
  const payload = {
    success: true,
    requestId: ctx.requestId,
    timestamp: new Date().toISOString(),
    data: {
      status: "ok",
      uptimeSeconds: Math.floor(process.uptime()),
      environment: config.nodeEnv,
      version: "0.1.0",
      services: {
        apiGateway: "healthy",
        watsonxConfigured: Boolean(config.watsonx.apiKey),
      },
    },
  };

  res.writeHead(200, {
    "Content-Type": "application/json",
    "X-Request-ID": ctx.requestId,
  });
  res.end(JSON.stringify(payload));
}
