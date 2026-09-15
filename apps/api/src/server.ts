import { createServer, type IncomingMessage, type ServerResponse, type Server } from "node:http";
import { randomUUID } from "node:crypto";
import { loadConfig, type AppConfig } from "./config.ts";
import { logger } from "./logger.ts";
import { ServiceClient } from "./service-client.ts";
import type { RequestContext } from "./types.ts";

import { handleHealth } from "./routes/health.ts";
import { handleGrid } from "./routes/grid.ts";
import { handleForecast } from "./routes/forecast.ts";
import { handleRenewable } from "./routes/renewable.ts";
import { handleOptimization } from "./routes/optimization.ts";
import { handleScenario } from "./routes/scenario.ts";
import { handleAgent } from "./routes/agent.ts";

export interface CreateServerOptions {
  config?: AppConfig;
  serviceClient?: ServiceClient;
}

export function createApiServer(options: CreateServerOptions = {}): Server {
  const config = options.config || loadConfig();
  const serviceClient = options.serviceClient || new ServiceClient(config);

  return createServer(async (req: IncomingMessage, res: ServerResponse) => {
    const startTime = performance.now();
    const requestId = (req.headers["x-request-id"] as string) || randomUUID();
    const host = req.headers.host || "localhost";
    const fullUrl = new URL(req.url || "/", `http://${host}`);

    const ctx: RequestContext = {
      requestId,
      startTime,
      url: fullUrl,
      method: req.method || "GET",
    };

    // Global CORS headers
    res.setHeader("Access-Control-Allow-Origin", config.corsOrigin);
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID");
    res.setHeader("X-Request-ID", requestId);

    if (req.method === "OPTIONS") {
      res.writeHead(204);
      res.end();
      return;
    }

    // Log completion
    res.on("finish", () => {
      const durationMs = Math.round(performance.now() - startTime);
      logger.info(`${req.method} ${fullUrl.pathname} ${res.statusCode} [${durationMs}ms]`, {
        requestId,
        method: req.method,
        path: fullUrl.pathname,
        statusCode: res.statusCode,
        durationMs,
      });
    });

    try {
      // Parse JSON body if present
      let body: any = undefined;
      if (req.method === "POST" || req.method === "PUT") {
        const chunks: Buffer[] = [];
        for await (const chunk of req) {
          chunks.push(chunk as Buffer);
        }
        const rawBody = Buffer.concat(chunks).toString("utf-8");
        if (rawBody.trim().length > 0) {
          try {
            body = JSON.parse(rawBody);
          } catch {
            res.writeHead(400, { "Content-Type": "application/json" });
            res.end(
              JSON.stringify({
                success: false,
                requestId,
                timestamp: new Date().toISOString(),
                error: {
                  code: "MALFORMED_JSON",
                  message: "Invalid JSON format in request body",
                },
              })
            );
            return;
          }
        }
      }

      const pathname = fullUrl.pathname;

      if (pathname === "/health") {
        await handleHealth(res, ctx, config);
      } else if (pathname === "/api/grid" || pathname.startsWith("/api/grid/")) {
        await handleGrid(res, ctx, serviceClient);
      } else if (pathname === "/api/forecast" || pathname.startsWith("/api/forecast/")) {
        await handleForecast(res, ctx, serviceClient, body);
      } else if (pathname === "/api/renewable" || pathname.startsWith("/api/renewable/")) {
        await handleRenewable(res, ctx, serviceClient);
      } else if (pathname === "/api/optimization" || pathname.startsWith("/api/optimization/")) {
        await handleOptimization(res, ctx, serviceClient, body);
      } else if (pathname === "/api/scenario" || pathname.startsWith("/api/scenario/")) {
        await handleScenario(res, ctx, serviceClient, body);
      } else if (pathname === "/api/agent" || pathname.startsWith("/api/agent/")) {
        await handleAgent(res, ctx, serviceClient, body);
      } else {
        res.writeHead(404, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            success: false,
            requestId,
            timestamp: new Date().toISOString(),
            error: {
              code: "NOT_FOUND",
              message: `Endpoint ${req.method} ${pathname} not found`,
            },
          })
        );
      }
    } catch (err: any) {
      logger.error("Unhandled internal server error", {
        requestId,
        error: err?.message,
        stack: err?.stack,
      });

      if (!res.headersSent) {
        const statusCode = typeof err?.statusCode === "number" ? err.statusCode : 500;
        const errorCode = err?.code || "INTERNAL_SERVER_ERROR";
        res.writeHead(statusCode, { "Content-Type": "application/json" });
        res.end(
          JSON.stringify({
            success: false,
            requestId,
            timestamp: new Date().toISOString(),
            error: {
              code: errorCode,
              message: err?.message || "An unexpected internal server error occurred",
              details: err?.details || (config.nodeEnv === "development" ? err?.stack : undefined),
            },
          })
        );
      }
    }
  });
}
