/**
 * LLM Provider Abstraction Types
 *
 * Architectural Rule C:
 * The LLM is responsible for COMMUNICATION ONLY.
 * It interprets structured system outputs and answers operator questions.
 * It must NEVER be the source of numerical forecasts or optimization quantities.
 */

export interface LLMGenerationRequest {
  systemPrompt: string;
  userPrompt: string;
  contextData?: Record<string, any>;
  temperature?: number;
  maxTokens?: number;
  timeoutMs?: number;
}

export interface LLMTokenUsage {
  prompt?: number;
  completion?: number;
  total?: number;
}

export interface LLMGenerationResponse {
  text: string;
  model: string;
  provider: string;
  tokensUsed?: LLMTokenUsage;
  durationMs: number;
}

export interface LLMProvider {
  /**
   * Generates natural language explanation or summary from structured prompt input.
   */
  generate(request: LLMGenerationRequest): Promise<LLMGenerationResponse>;

  /**
   * Provider identifier (e.g. "ibm-watsonx", "mock-provider", "openai")
   */
  getProviderName(): string;

  /**
   * Foundation model identifier (e.g. "ibm/granite-3-8b-instruct")
   */
  getModelId(): string;

  /**
   * Whether valid credentials and configuration exist for this provider.
   */
  isConfigured(): boolean;
}
