# `agent/provider` — LLM Provider Abstraction Layer

## Module Overview
Encapsulates communication with foundation models and AI agent runtimes.

- **Primary Provider:** IBM watsonx.ai (Granite 3.0 / Llama 3) and IBM Bob (BobShell).
- **Secondary / Fallback:** Compatible OpenAI / Ollama interface for offline testing.
- **Architectural Rule (Rule C):** The LLM is responsible for **COMMUNICATION ONLY**.
  - Synthesizes structured 8-part operator briefs.
  - Answers operator questions about telemetry and optimization outputs.
  - NEVER invents dispatch figures, changes solver outputs, or acts as a source of truth for forecasts.
- **Owned By:** Member 1 (Team Leader)
- **Branch:** `leader/integration`
