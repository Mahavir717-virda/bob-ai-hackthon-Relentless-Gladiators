/**
 * IBM watsonx.ai Foundation Model Provider
 * Implements LLMProvider using Granite 3.0 via watsonx.ai REST APIs.
 */

import type { LLMProvider, LLMGenerationRequest, LLMGenerationResponse } from "./types.ts";
import { WatsonxAuthError, WatsonxTimeoutError, WatsonxApiError } from "./errors.ts";

export interface WatsonxConfig {
  apiKey?: string;
  projectId?: string;
  url?: string;
  modelId?: string;
  apiVersion?: string;
}

export class WatsonxProvider implements LLMProvider {
  private apiKey?: string;
  private projectId?: string;
  private url: string;
  private modelId: string;
  private apiVersion: string;

  private cachedToken?: string;
  private tokenExpiresAt = 0;

  constructor(config: WatsonxConfig = {}) {
    this.apiKey = config.apiKey || process.env.WATSONX_API_KEY;
    this.projectId = config.projectId || process.env.WATSONX_PROJECT_ID;
    this.url = (config.url || process.env.WATSONX_URL || "https://us-south.ml.cloud.ibm.com").replace(/\/$/, "");
    this.modelId = config.modelId || process.env.WATSONX_MODEL_ID || "ibm/granite-3-8b-instruct";
    this.apiVersion = config.apiVersion || "2023-05-29";
  }

  getProviderName(): string {
    return "ibm-watsonx";
  }

  getModelId(): string {
    return this.modelId;
  }

  isConfigured(): boolean {
    return Boolean(this.apiKey && this.apiKey.trim().length > 0 && this.projectId && this.projectId.trim().length > 0);
  }

  /**
   * Acquire or reuse IAM Bearer token
   */
  private async getIamToken(signal?: AbortSignal): Promise<string> {
    if (this.cachedToken && Date.now() < this.tokenExpiresAt) {
      return this.cachedToken;
    }

    if (!this.apiKey) {
      throw new WatsonxAuthError("WATSONX_API_KEY is not configured.");
    }

    const tokenUrl = "https://iam.cloud.ibm.com/identity/token";
    const bodyParams = new URLSearchParams({
      grant_type: "urn:ibm:params:oauth:grant-type:apikey",
      apikey: this.apiKey,
    });

    let resp: Response;
    try {
      resp = await fetch(tokenUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          Accept: "application/json",
        },
        body: bodyParams.toString(),
        signal,
      });
    } catch (err: any) {
      if (err.name === "TimeoutError" || err.name === "AbortError") {
        throw new WatsonxTimeoutError(5000);
      }
      throw new WatsonxAuthError(`Network error reaching IBM Cloud IAM: ${err.message}`);
    }

    if (!resp.ok) {
      const errText = await resp.text().catch(() => "");
      throw new WatsonxAuthError(`IAM authentication failed (${resp.status}): ${errText}`);
    }

    const tokenData = (await resp.json()) as { access_token: string; expires_in: number };
    this.cachedToken = tokenData.access_token;
    // Expire 60s before actual expiry
    this.tokenExpiresAt = Date.now() + (tokenData.expires_in - 60) * 1000;
    return this.cachedToken;
  }

  /**
   * Build complete prompt with structured context
   */
  private formatPrompt(request: LLMGenerationRequest): string {
    const parts: string[] = [];

    parts.push(`[SYSTEM INSTRUCTION]\n${request.systemPrompt}`);
    parts.push(
      "CRITICAL RULE: You are an analytical decision-support copilot. You must ONLY interpret and explain the provided structured telemetry. Never invent numbers, modify dispatch schedules, or claim correlation is causation."
    );

    if (request.contextData && Object.keys(request.contextData).length > 0) {
      parts.push(`[STRUCTURED TELEMETRY & OPTIMIZER GROUND TRUTH]\n${JSON.stringify(request.contextData, null, 2)}`);
    }

    parts.push(`[OPERATOR QUERY / TASK]\n${request.userPrompt}`);
    parts.push("[OPERATOR RESPONSE]");

    return parts.join("\n\n");
  }

  async generate(request: LLMGenerationRequest): Promise<LLMGenerationResponse> {
    const startTime = performance.now();
    const timeoutMs = request.timeoutMs || 10000;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    try {
      const token = await this.getIamToken(controller.signal);

      const endpoint = `${this.url}/ml/v1/text/generation?version=${this.apiVersion}`;
      const prompt = this.formatPrompt(request);

      const payload = {
        input: prompt,
        parameters: {
          decoding_method: "greedy",
          max_new_tokens: request.maxTokens || 1024,
          min_new_tokens: 1,
          temperature: request.temperature ?? 0.1,
          repetition_penalty: 1.05,
        },
        model_id: this.modelId,
        project_id: this.projectId,
      };

      const resp = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (!resp.ok) {
        const errorText = await resp.text().catch(() => "");
        throw new WatsonxApiError(resp.status, errorText);
      }

      const data = (await resp.json()) as {
        results: Array<{
          generated_text: string;
          input_token_count?: number;
          generated_token_count?: number;
        }>;
      };

      const generatedText = data.results[0]?.generated_text?.trim() || "";
      const durationMs = Math.round(performance.now() - startTime);

      return {
        text: generatedText,
        model: this.modelId,
        provider: this.getProviderName(),
        tokensUsed: {
          prompt: data.results[0]?.input_token_count,
          completion: data.results[0]?.generated_token_count,
          total: (data.results[0]?.input_token_count || 0) + (data.results[0]?.generated_token_count || 0),
        },
        durationMs,
      };
    } catch (err: any) {
      if (err.name === "AbortError" || err.name === "TimeoutError") {
        throw new WatsonxTimeoutError(timeoutMs);
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }
}
