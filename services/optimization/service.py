"""
GridPilot AI — Optimization Service Interface
================================================
Clean service interface that the API gateway and other services call.
Delegates to the OR-Tools optimizer and scenario simulator.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from services.optimization.models import (
    BatteryResource,
    EVResource,
    IndustrialFlexLoad,
    OptimizationInput,
    OptimizationResult,
    OptimizationWeights,
)
from services.optimization.optimizer import GridOptimizer
from services.optimization.scenarios import (
    ScenarioName,
    ScenarioSimulator,
    ScenarioComparison,
    build_scenario,
)
from services.optimization.constraints import (
    validate_optimization_input,
    has_errors,
)


class OptimizationService:
    """
    High-level service interface for the optimization module.

    Provides:
      - solve_dispatch(): Run optimization on arbitrary input
      - simulate_scenario(): Run a predefined scenario
      - compare_scenarios(): Compare two scenario results
      - run_all_scenarios(): Run all 8 predefined scenarios
      - get_available_scenarios(): List scenario names

    Conforms to the API interface:
      runOptimization() → OptimizationResult
      simulateAction(scenario) → OptimizationResult
      compareScenario(base, modified) → ScenarioComparison
    """

    def __init__(self) -> None:
        self.optimizer = GridOptimizer()
        self.simulator = ScenarioSimulator(self.optimizer)

    def solve_dispatch(
        self, inp: OptimizationInput
    ) -> OptimizationResult:
        """
        Solve the grid optimization problem with the given input.

        Parameters
        ----------
        inp : OptimizationInput
            Full problem specification.

        Returns
        -------
        OptimizationResult
            Matching the shared/contracts/OptimizationResult contract.
        """
        return self.optimizer.solve(inp)

    def simulate_scenario(
        self,
        scenario_name: str,
        start_time: Optional[datetime] = None,
    ) -> OptimizationResult:
        """
        Run a predefined scenario through the optimizer.

        Parameters
        ----------
        scenario_name : str
            Name of the scenario (e.g., 'EVENING_DEMAND_SPIKE').
        start_time : datetime, optional
            Override the start time.

        Returns
        -------
        OptimizationResult
        """
        name = ScenarioName(scenario_name)
        return self.simulator.simulate_action(name, start_time)

    def compare_scenarios(
        self,
        base_scenario: str,
        modified_scenario: str,
        start_time: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Compare two scenarios and return the results side by side.

        Returns
        -------
        dict
            Contains baseResult and modifiedResult.
        """
        base = ScenarioName(base_scenario)
        modified = ScenarioName(modified_scenario)
        comparison = self.simulator.compare_scenario(base, modified, start_time)
        return comparison.to_dict()

    def run_all_scenarios(
        self, start_time: Optional[datetime] = None
    ) -> dict[str, dict[str, Any]]:
        """Run all 8 scenarios and return results as dicts."""
        results = self.simulator.run_all_scenarios(start_time)
        return {name: result.to_dict() for name, result in results.items()}

    @staticmethod
    def get_available_scenarios() -> list[str]:
        """Return names of all predefined scenarios."""
        return [s.value for s in ScenarioName]

    def validate_input(self, inp: OptimizationInput) -> dict[str, Any]:
        """
        Validate an optimization input and return any issues.

        Returns
        -------
        dict with 'valid' (bool) and 'violations' (list of dicts).
        """
        violations = validate_optimization_input(inp)
        return {
            "valid": not has_errors(violations),
            "violations": [v.to_dict() for v in violations],
        }
