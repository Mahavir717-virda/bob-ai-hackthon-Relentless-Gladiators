import { GridPilotError } from "../../shared/errors/index.ts";

export class LLMError extends GridPilotError {
  constructor(message: string, code = "LLM_ERROR", statusCode = 502, details?: unknown) {
    super(message, code, statusCode, details);
    this.name = "LLMError";
  }
}

export class WatsonxAuthError extends LLMError {
  constructor(message = "Authentication with IBM Cloud IAM failed. Verify WATSONX_API_KEY.") {
    super(message, "WATSONX_AUTH_ERROR", 401);
    this.name = "WatsonxAuthError";
  }
}

export class WatsonxTimeoutError extends LLMError {
  constructor(timeoutMs: number) {
    super(`watsonx.ai request timed out after ${timeoutMs}ms`, "WATSONX_TIMEOUT", 504);
    this.name = "WatsonxTimeoutError";
  }
}

export class WatsonxApiError extends LLMError {
  constructor(statusCode: number, message: string, details?: unknown) {
    super(`watsonx.ai API error (${statusCode}): ${message}`, "WATSONX_API_ERROR", statusCode, details);
    this.name = "WatsonxApiError";
  }
}

export class GroundTruthViolationError extends LLMError {
  constructor(message: string) {
    super(
      `Rule C Violation: LLM output deviated from ground truth: ${message}`,
      "GROUND_TRUTH_VIOLATION",
      500
    );
    this.name = "GroundTruthViolationError";
  }
}

export class OllamaError extends LLMError {
  constructor(message: string, statusCode = 502, details?: unknown) {
    super(message, "OLLAMA_ERROR", statusCode, details);
    this.name = "OllamaError";
  }
}

export class OllamaTimeoutError extends LLMError {
  constructor(timeoutMs: number) {
    super(`Ollama request timed out after ${timeoutMs}ms`, "OLLAMA_TIMEOUT", 504);
    this.name = "OllamaTimeoutError";
  }
}
