import test from "node:test";
import assert from "node:assert/strict";

import {
  MockLLMProvider,
  WatsonxProvider,
  getLLMProvider,
  resetLLMProvider,
  WatsonxAuthError,
  WatsonxTimeoutError,
  type LLMProvider,
} from "../../agent/provider/index.ts";

test("LLM Provider Abstraction Suite", async (t) => {
  t.beforeEach(() => {
    resetLLMProvider();
  });

  await t.test("MockLLMProvider conforms to LLMProvider interface", () => {
    const provider: LLMProvider = new MockLLMProvider();
    assert.equal(provider.getProviderName(), "mock-provider");
    assert.equal(provider.getModelId(), "ibm/granite-3-8b-instruct-mock");
    assert.equal(provider.isConfigured(), true);
  });

  await t.test("MockLLMProvider synthesizes complete 8-section operator brief from structured context", async () => {
    const provider = new MockLLMProvider();

    const mockContext = {
      currentGridState: {
        zoneId: "NL_LIANDER_SUB_01",
        demandMw: 94.2,
        gridStressIndex: 0.86,
      },
      demandForecast: {
        spikeRisk: {
          level: "severe",
          probability: 0.88,
        },
      },
      renewableStatuses: [
        {
          assetId: "SOLAR_FARM_ZEELAND_03",
          assetType: "solar",
          anomaly: true,
          likelyRootCause: {
            category: "cloud_cover",
            evidence: "Cloud front passage across Zeeland",
          },
        },
      ],
      optimizationResult: {
        actions: [
          {
            resourceId: "BESS_SUB_01",
            actionType: "battery_discharge",
            powerMw: 15.0,
            startTime: "2026-09-15T14:15:00.000Z",
            endTime: "2026-09-15T14:30:00.000Z",
          },
        ],
        before: { gridStressIndex: 0.86 },
        after: { gridStressIndex: 0.41 },
      },
    };

    const response = await provider.generate({
      systemPrompt: "Synthesize the 15-minute Grid Operator Brief.",
      userPrompt: "Generate brief.",
      contextData: mockContext,
    });

    assert.ok(response.text.includes("## 1. Current Situation"));
    assert.ok(response.text.includes("94.2 MW"));
    assert.ok(response.text.includes("0.86"));
    assert.ok(response.text.includes("## 2. Risk Assessment"));
    assert.ok(response.text.includes("SEVERE"));
    assert.ok(response.text.includes("88.0%"));
    assert.ok(response.text.includes("## 3. Renewable Alert"));
    assert.ok(response.text.includes("## 4. Root Cause"));
    assert.ok(response.text.includes("Cloud front passage across Zeeland"));
    assert.ok(response.text.includes("## 5. Recommended Actions"));
    assert.ok(response.text.includes("BATTERY_DISCHARGE: 15 MW on BESS_SUB_01"));
    assert.ok(response.text.includes("## 6. Expected Impact"));
    assert.ok(response.text.includes("0.86 down to 0.41"));
    assert.ok(response.text.includes("## 7. Confidence & Uncertainty"));
    assert.ok(response.text.includes("## 8. Data Limitations"));

    assert.equal(response.provider, "mock-provider");
    assert.ok(response.durationMs >= 0);
  });

  await t.test("WatsonxProvider configuration check and authentication guard", async () => {
    // When unconfigured
    const unconfigured = new WatsonxProvider({ apiKey: "", projectId: "" });
    assert.equal(unconfigured.isConfigured(), false);
    assert.equal(unconfigured.getProviderName(), "ibm-watsonx");
    assert.equal(unconfigured.getModelId(), "ibm/granite-3-8b-instruct");

    await assert.rejects(
      async () => {
        await unconfigured.generate({
          systemPrompt: "test",
          userPrompt: "test",
        });
      },
      WatsonxAuthError
    );
  });

  await t.test("WatsonxProvider timeout handling", async () => {
    const provider = new WatsonxProvider({
      apiKey: "dummy_key",
      projectId: "dummy_project",
      url: "http://10.255.255.1", // Non-routable address to force timeout
    });

    await assert.rejects(
      async () => {
        await provider.generate({
          systemPrompt: "test",
          userPrompt: "test",
          timeoutMs: 50, // Ultra short timeout
        });
      },
      (err: any) => err instanceof WatsonxTimeoutError || err instanceof WatsonxAuthError
    );
  });

  await t.test("LLM Factory resolves provider and supports custom override", () => {
    // Unconfigured environment falls back to MockLLMProvider
    const defaultProvider = getLLMProvider();
    assert.equal(defaultProvider.getProviderName(), "mock-provider");

    // Custom override
    const custom = new MockLLMProvider("custom-granite-test");
    const active = getLLMProvider(custom);
    assert.equal(active.getModelId(), "custom-granite-test");
  });
});
