import type { ServerResponse } from "node:http";
import type { RequestContext } from "../types.ts";
import type { ServiceClient } from "../service-client.ts";
import { validateAgentContext } from "../../../../shared/contracts/AgentContext.ts";


export async function handleAgent(
  res: ServerResponse,
  ctx: RequestContext,
  serviceClient: ServiceClient,
  body?: any
): Promise<void> {
  if (ctx.method !== "POST") {
    res.writeHead(405, { "Content-Type": "application/json", "X-Request-ID": ctx.requestId });
    res.end(
      JSON.stringify({
        success: false,
        requestId: ctx.requestId,
        timestamp: new Date().toISOString(),
        error: { code: "METHOD_NOT_ALLOWED", message: `Method ${ctx.method} not allowed` },
      })
    );
    return;
  }

  // Validate incoming context
  const validation = validateAgentContext(body);
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
          code: "INVALID_AGENT_CONTEXT",
          message: "Request payload does not conform to AgentContext contract",
          details: validation.errors,
        },
      })
    );
    return;
  }

  const agentContext = validation.data!;
  const brief = await serviceClient.generateOperatorBrief(agentContext);

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
        sessionId: agentContext.sessionId,
        briefMarkdown: brief.briefMarkdown,
        operatorQuery: agentContext.operatorQuery,
      },
    })
  );
}
