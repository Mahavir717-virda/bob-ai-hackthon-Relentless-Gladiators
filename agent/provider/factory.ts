/**
 * LLM Provider Factory
 * Resolves the active provider based on environment configuration.
 */

import type { LLMProvider } from "./types.ts";
import { WatsonxProvider } from "./watsonx.ts";
import { MockLLMProvider } from "./mock.ts";
import { OllamaProvider } from "./ollama.ts";

let activeProviderInstance: LLMProvider | null = null;

export function getLLMProvider(forcedProvider?: LLMProvider): LLMProvider {
  if (forcedProvider) {
    activeProviderInstance = forcedProvider;
    return activeProviderInstance;
  }

  if (activeProviderInstance) {
    return activeProviderInstance;
  }

  const providerType = process.env.LLM_PROVIDER?.toLowerCase();

  // If explicitly configured for local Ollama / Qwen
  if (providerType === "ollama" || process.env.USE_LOCAL_LLM === "true") {
    activeProviderInstance = new OllamaProvider();
    return activeProviderInstance;
  }

  const watsonx = new WatsonxProvider();
  if (watsonx.isConfigured()) {
    activeProviderInstance = watsonx;
    return activeProviderInstance;
  }

  // Fallback to deterministic mock provider
  activeProviderInstance = new MockLLMProvider();
  return activeProviderInstance;
}

export function resetLLMProvider(): void {
  activeProviderInstance = null;
}
