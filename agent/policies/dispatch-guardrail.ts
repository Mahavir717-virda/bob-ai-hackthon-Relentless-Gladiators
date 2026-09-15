/**
 * Dispatch Guardrail Policy
 *
 * Enforces Architectural Rule B & Ground Rule 5:
 * - "Do not allow free-form numerical dispatch decisions by the LLM."
 * - "Do not bypass the optimizer."
 * - "The Optimizer is responsible for DECISIONS."
 */

import type { OptimizationResult, OptimizationAction } from "../../shared/contracts/OptimizationResult.ts";

export interface GuardrailValidationResult {
  passed: boolean;
  violations: string[];
  sanitizedText?: string;
}

export class DispatchGuardrail {
  /**
   * Regular expression detecting numerical dispatch statements
   * Examples: "discharge 15 MW", "charge 20MW", "curtail 5.5 MW", "shift 10 MW"
   */
  private static readonly DISPATCH_NUMERICAL_REGEX =
    /\b(discharge|charge|dispatch|curtail|curtailment|shift)\s+(\d+(\.\d+)?)\s*(mw|mwh)\b/gi;

  /**
   * Validate that generated text does not bypass the optimizer or invent dispatch quantities.
   */
  static validate(
    generatedText: string,
    optimizationResult?: OptimizationResult
  ): GuardrailValidationResult {
    const violations: string[] = [];

    // Case 1: Optimizer was NOT run or is undefined
    if (!optimizationResult) {
      const dispatchMatches = generatedText.match(this.DISPATCH_NUMERICAL_REGEX);
      if (dispatchMatches && dispatchMatches.length > 0) {
        violations.push(
          `Bypassed Optimizer: Generated text proposes numerical dispatch (${dispatchMatches.join(
            ", "
          )}) without executing the mathematical optimizer.`
        );
      }
    } else if (optimizationResult.status === "infeasible") {
      // Case 2: Optimizer ran but is INFEASIBLE
      // Text must not recommend new unverified numerical dispatch actions
      const dispatchMatches = generatedText.match(this.DISPATCH_NUMERICAL_REGEX);
      if (dispatchMatches && dispatchMatches.length > 0) {
        violations.push(
          `Infeasible Optimization Violation: Optimizer status is INFEASIBLE, but text proposes numerical dispatch (${dispatchMatches.join(
            ", "
          )}). Free-form dispatch under infeasible solver state is strictly prohibited.`
        );
      }
    } else {
      // Case 3: Optimizer ran and is FEASIBLE
      // Any numerical dispatch mentioned should match the solver's actions within rounding tolerance
      const allowedActions: OptimizationAction[] = optimizationResult.actions || [];
      const allowedPowers = new Set(allowedActions.map((a) => Math.round(a.powerMw * 10) / 10));

      let match: RegExpExecArray | null;
      const regex = new RegExp(this.DISPATCH_NUMERICAL_REGEX.source, "gi");
      while ((match = regex.exec(generatedText)) !== null) {
        const powerMw = Math.round(parseFloat(match[2]) * 10) / 10;
        if (!allowedPowers.has(powerMw) && powerMw > 0) {
          violations.push(
            `Unverified Numerical Dispatch: Proposed power ${powerMw} MW does not match any solver action [${Array.from(
              allowedPowers
            ).join(", ")} MW].`
          );
        }
      }
    }

    if (violations.length > 0) {
      // Sanitize output to prevent unauthorized dispatch execution
      const sanitized =
        `⚠️ [GUARDRAIL INTERVENTION: RULE B ENFORCEMENT]\n` +
        `Free-form numerical dispatch decisions by the LLM are strictly prohibited. ` +
        `Decisions must be computed by the OR-Tools mathematical optimization engine.\n\n` +
        generatedText;

      return {
        passed: false,
        violations,
        sanitizedText: sanitized,
      };
    }

    return {
      passed: true,
      violations: [],
      sanitizedText: generatedText,
    };
  }
}
