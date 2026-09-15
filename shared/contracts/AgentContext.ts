import type { ValidationResult } from "../types/index.ts";
import { type GridState, validateGridState } from "./GridState.ts";
import { type DemandForecast, validateDemandForecast } from "./DemandForecast.ts";
import { type RenewableStatus, validateRenewableStatus } from "./RenewableStatus.ts";
import { type OptimizationResult, validateOptimizationResult } from "./OptimizationResult.ts";
import { type Recommendation, validateRecommendation } from "./Recommendation.ts";


export interface AgentChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
}

export interface AgentContext {
  sessionId: string;
  timestamp: string;
  currentGridState: GridState;
  demandForecast: DemandForecast;
  renewableStatuses: RenewableStatus[];
  optimizationResult?: OptimizationResult;
  recommendations: Recommendation[];
  conversationHistory?: AgentChatMessage[];
  operatorQuery?: string;
}

export function validateAgentContext(data: unknown): ValidationResult<AgentContext> {
  const errors: string[] = [];

  if (!data || typeof data !== "object") {
    return { success: false, errors: ["Data must be a non-null object"] };
  }

  const d = data as Record<string, any>;

  if (typeof d.sessionId !== "string" || d.sessionId.trim().length === 0) {
    errors.push("sessionId must be a non-empty string");
  }

  if (typeof d.timestamp !== "string" || isNaN(Date.parse(d.timestamp))) {
    errors.push("timestamp must be a valid ISO timestamp");
  }

  const gridStateValidation = validateGridState(d.currentGridState);
  if (!gridStateValidation.success) {
    errors.push(...(gridStateValidation.errors || []).map((e) => `currentGridState: ${e}`));
  }

  const demandForecastValidation = validateDemandForecast(d.demandForecast);
  if (!demandForecastValidation.success) {
    errors.push(...(demandForecastValidation.errors || []).map((e) => `demandForecast: ${e}`));
  }

  if (!Array.isArray(d.renewableStatuses)) {
    errors.push("renewableStatuses must be an array");
  } else {
    d.renewableStatuses.forEach((ren: any, idx: number) => {
      const renVal = validateRenewableStatus(ren);
      if (!renVal.success) {
        errors.push(...(renVal.errors || []).map((e) => `renewableStatuses[${idx}]: ${e}`));
      }
    });
  }

  if (d.optimizationResult !== undefined) {
    const optVal = validateOptimizationResult(d.optimizationResult);
    if (!optVal.success) {
      errors.push(...(optVal.errors || []).map((e) => `optimizationResult: ${e}`));
    }
  }

  if (!Array.isArray(d.recommendations)) {
    errors.push("recommendations must be an array");
  } else {
    d.recommendations.forEach((rec: any, idx: number) => {
      const recVal = validateRecommendation(rec);
      if (!recVal.success) {
        errors.push(...(recVal.errors || []).map((e) => `recommendations[${idx}]: ${e}`));
      }
    });
  }

  if (d.conversationHistory !== undefined) {
    if (!Array.isArray(d.conversationHistory)) {
      errors.push("conversationHistory must be an array");
    } else {
      const validRoles = ["user", "assistant", "system"];
      d.conversationHistory.forEach((msg: any, idx: number) => {
        if (!validRoles.includes(msg.role)) {
          errors.push(`conversationHistory[${idx}].role must be 'user', 'assistant', or 'system'`);
        }
        if (typeof msg.content !== "string") {
          errors.push(`conversationHistory[${idx}].content must be a string`);
        }
      });
    }
  }

  if (errors.length > 0) {
    return { success: false, errors };
  }

  return { success: true, data: d as AgentContext };
}
