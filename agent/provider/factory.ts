import type { LLMProvider } from "./types.ts";
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

  const providerType = (process.env.LLM_PROVIDER || "ollama").toLowerCase();

  // Ollama is our local LLM engine (Qwen)
  if (providerType === "ollama") {
    activeProviderInstance = new OllamaProvider();
    return activeProviderInstance;
  }

  // Fallback to deterministic mock provider
  activeProviderInstance = new MockLLMProvider();
  return activeProviderInstance;
}

export function resetLLMProvider(): void {
  activeProviderInstance = null;
}
