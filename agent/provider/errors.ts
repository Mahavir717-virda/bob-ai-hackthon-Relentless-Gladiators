import { GridPilotError } from "../../shared/errors/index.ts";

export class LLMError extends GridPilotError {
  constructor(message: string, code = "LLM_ERROR", statusCode = 502, details?: unknown) {
    super(message, code, statusCode, details);
    this.name = "LLMError";
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
