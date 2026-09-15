/**
 * Standardized system errors and contract validation errors for GridPilot AI
 */

export class GridPilotError extends Error {
  public readonly code: string;
  public readonly statusCode: number;
  public readonly details?: unknown;

  constructor(message: string, code = "INTERNAL_ERROR", statusCode = 500, details?: unknown) {
    super(message);
    this.name = "GridPilotError";
    this.code = code;
    this.statusCode = statusCode;
    this.details = details;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

export class ContractValidationError extends GridPilotError {
  public readonly validationErrors: string[];

  constructor(contractName: string, errors: string[]) {
    super(
      `Contract validation failed for '${contractName}': ${errors.join("; ")}`,
      "CONTRACT_VALIDATION_ERROR",
      400,
      { contractName, errors }
    );
    this.name = "ContractValidationError";
    this.validationErrors = errors;
  }
}

export class ModelInferenceError extends GridPilotError {
  constructor(modelName: string, reason: string) {
    super(
      `ML model inference failed for '${modelName}': ${reason}`,
      "MODEL_INFERENCE_ERROR",
      502,
      { modelName, reason }
    );
    this.name = "ModelInferenceError";
  }
}

export class OptimizationInfeasibleError extends GridPilotError {
  constructor(scenarioId: string, reason = "Constraints could not be satisfied") {
    super(
      `Optimization solver returned INFEASIBLE for scenario '${scenarioId}': ${reason}`,
      "OPTIMIZATION_INFEASIBLE",
      422,
      { scenarioId, reason }
    );
    this.name = "OptimizationInfeasibleError";
  }
}
