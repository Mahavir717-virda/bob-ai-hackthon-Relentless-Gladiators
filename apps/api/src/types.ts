import type { IncomingMessage, ServerResponse } from "node:http";

export interface ApiResponse<T> {
  success: true;
  requestId: string;
  timestamp: string;
  data: T;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: unknown;
}

export interface ApiErrorResponse {
  success: false;
  requestId: string;
  timestamp: string;
  error: ApiErrorDetail;
}

export interface RequestContext {
  requestId: string;
  startTime: number;
  url: URL;
  method: string;
}

export type RouteHandler = (
  req: IncomingMessage,
  res: ServerResponse,
  ctx: RequestContext,
  body?: any
) => Promise<void>;
