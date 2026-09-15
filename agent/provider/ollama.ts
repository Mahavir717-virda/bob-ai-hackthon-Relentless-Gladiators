/**
 * Ollama Local LLM Provider (Qwen 2.5 / Granite)
 *
 * Implements Rule C: Local inference without external cloud credentials.
 * Runs completely on-premise / offline via local Ollama daemon.
 */

import type { LLMProvider, LLMGenerationRequest, LLMGenerationResponse } from "./types.ts";
import { LLMError, OllamaError, OllamaTimeoutError } from "./errors.ts";

export interface OllamaConfig {
  baseUrl?: string;
  modelId?: string;
  defaultTimeoutMs?: number;
}

export class OllamaProvider implements LLMProvider {
  private baseUrl: string;
  private modelId: string;
  private defaultTimeoutMs: number;

  constructor(config: OllamaConfig = {}) {
    this.baseUrl = config.baseUrl || process.env.OLLAMA_BASE_URL || "http://127.0.0.1:11434";
    this.modelId = config.modelId || process.env.OLLAMA_MODEL || "qwen2.5:1.5b";
    this.defaultTimeoutMs = config.defaultTimeoutMs || 30000;
  }

  getProviderName(): string {
    return "ollama";
  }

  getModelId(): string {
    return this.modelId;
  }

  isConfigured(): boolean {
    return true;
  }

  async generate(request: LLMGenerationRequest): Promise<LLMGenerationResponse> {
    const startTime = performance.now();
    const timeoutMs = request.timeoutMs || this.defaultTimeoutMs;

    const payload = {
      model: this.modelId,
      messages: [
        {
          role: "system",
          content: request.systemPrompt,
        },
        {
          role: "user",
          content: request.userPrompt,
        },
      ],
      stream: false,
      options: {
        temperature: request.temperature ?? 0.1,
        num_predict: request.maxTokens ?? 1024,
      },
    };

    try {
      const response = await fetch(`${this.baseUrl}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
        signal: AbortSignal.timeout(timeoutMs),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new OllamaError(
          `Ollama returned HTTP ${response.status}: ${errorText}`,
          response.status
        );
      }

      const json = (await response.json()) as any;
      const responseText = json.message?.content || "";
      const durationMs = Math.round(performance.now() - startTime);

      return {
        text: responseText,
        model: this.modelId,
        provider: this.getProviderName(),
        tokensUsed: {
          prompt: json.prompt_eval_count,
          completion: json.eval_count,
          total: (json.prompt_eval_count || 0) + (json.eval_count || 0),
        },
        durationMs,
      };
    } catch (err: any) {
      if (err?.name === "TimeoutError" || err?.name === "AbortError") {
        throw new OllamaTimeoutError(timeoutMs);
      }

      if (err instanceof OllamaError) {
        throw err;
      }

      throw new OllamaError(
        `Failed to communicate with local Ollama service: ${err?.message}`
      );
    }
  }
}
