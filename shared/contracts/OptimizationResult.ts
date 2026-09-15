import type { OptimizationActionType, SolverStatus, ValidationResult } from "../types/index.ts";


export interface OptimizationAction {
  resourceId: string;
  actionType: OptimizationActionType | string;
  powerMw: number;
  startTime: string;
  endTime: string;
}

export interface GridStressMetrics {
  demandMw: number;
  renewableMw: number;
  curtailmentMw: number;
  gridStressIndex: number;
}

export interface OptimizationResult {
  scenarioId: string;
  status: "feasible" | "infeasible";
  solverStatus?: SolverStatus;
  actions: OptimizationAction[];
  before: GridStressMetrics;
  after: GridStressMetrics;
  objectiveValue: number;
  solveDurationMs?: number;
}

export function validateOptimizationResult(data: unknown): ValidationResult<OptimizationResult> {
  const errors: string[] = [];

  if (!data || typeof data !== "object") {
    return { success: false, errors: ["Data must be a non-null object"] };
  }

  const d = data as Record<string, any>;

  if (typeof d.scenarioId !== "string" || d.scenarioId.trim().length === 0) {
    errors.push("scenarioId must be a non-empty string");
  }

  if (d.status !== "feasible" && d.status !== "infeasible") {
    errors.push("status must be either 'feasible' or 'infeasible'");
  }

  if (d.solverStatus !== undefined) {
    const validSolverStatuses: SolverStatus[] = ["optimal", "feasible", "infeasible"];
    if (!validSolverStatuses.includes(d.solverStatus)) {
      errors.push(`solverStatus must be one of: ${validSolverStatuses.join(", ")}`);
    }
  }

  if (!Array.isArray(d.actions)) {
    errors.push("actions must be an array");
  } else {
    d.actions.forEach((act: any, idx: number) => {
      if (typeof act.resourceId !== "string" || act.resourceId.trim().length === 0) {
        errors.push(`actions[${idx}].resourceId must be a non-empty string`);
      }
      if (typeof act.actionType !== "string" || act.actionType.trim().length === 0) {
        errors.push(`actions[${idx}].actionType must be a non-empty string`);
      }
      if (typeof act.powerMw !== "number" || act.powerMw < 0) {
        errors.push(`actions[${idx}].powerMw must be a non-negative number`);
      }
      if (typeof act.startTime !== "string" || isNaN(Date.parse(act.startTime))) {
        errors.push(`actions[${idx}].startTime must be a valid ISO timestamp`);
      }
      if (typeof act.endTime !== "string" || isNaN(Date.parse(act.endTime))) {
        errors.push(`actions[${idx}].endTime must be a valid ISO timestamp`);
      }
    });
  }

  const validateStressMetrics = (metrics: any, prefix: string) => {
    if (!metrics || typeof metrics !== "object") {
      errors.push(`${prefix} must be an object`);
      return;
    }
    if (typeof metrics.demandMw !== "number" || metrics.demandMw < 0) {
      errors.push(`${prefix}.demandMw must be a non-negative number`);
    }
    if (typeof metrics.renewableMw !== "number" || metrics.renewableMw < 0) {
      errors.push(`${prefix}.renewableMw must be a non-negative number`);
    }
    if (typeof metrics.curtailmentMw !== "number" || metrics.curtailmentMw < 0) {
      errors.push(`${prefix}.curtailmentMw must be a non-negative number`);
    }
    if (
      typeof metrics.gridStressIndex !== "number" ||
      metrics.gridStressIndex < 0 ||
      metrics.gridStressIndex > 1
    ) {
      errors.push(`${prefix}.gridStressIndex must be a number between 0 and 1`);
    }
  };

  validateStressMetrics(d.before, "before");
  validateStressMetrics(d.after, "after");

  if (typeof d.objectiveValue !== "number") {
    errors.push("objectiveValue must be a number");
  }

  if (d.solveDurationMs !== undefined && (typeof d.solveDurationMs !== "number" || d.solveDurationMs < 0)) {
    errors.push("solveDurationMs must be a non-negative number");
  }

  if (errors.length > 0) {
    return { success: false, errors };
  }

  return { success: true, data: d as OptimizationResult };
}
