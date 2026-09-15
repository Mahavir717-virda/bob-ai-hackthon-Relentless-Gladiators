"""
GridPilot AI — Forecasting Service Data Contracts
=================================================
Matches the frozen TypeScript contracts in shared/contracts/DemandForecast.ts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class DemandForecastPoint:
    """A single timestamped forecast interval point."""
    timestamp: str
    demandMw: float
    lowerBoundMw: Optional[float] = None
    upperBoundMw: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "timestamp": self.timestamp,
            "demandMw": round(max(0.0, float(self.demandMw)), 4),
        }
        if self.lowerBoundMw is not None:
            d["lowerBoundMw"] = round(max(0.0, float(self.lowerBoundMw)), 4)
        if self.upperBoundMw is not None:
            d["upperBoundMw"] = round(max(0.0, float(self.upperBoundMw)), 4)
        return d


@dataclass
class SpikeRisk:
    """Spike risk classification output."""
    level: Literal["normal", "moderate", "severe"] = "normal"
    probability: float = 0.05
    predictedPeakMw: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "probability": round(float(self.probability), 4),
            "predictedPeakMw": round(max(0.0, float(self.predictedPeakMw)), 4),
        }


@dataclass
class DemandForecast:
    """
    Contract-compliant DemandForecast response matching shared/contracts/DemandForecast.ts.
    """
    zoneId: str
    generatedAt: str
    horizonMinutes: int
    points: List[DemandForecastPoint]
    spikeRisk: SpikeRisk
    modelVersion: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zoneId": self.zoneId,
            "generatedAt": self.generatedAt,
            "horizonMinutes": int(self.horizonMinutes),
            "points": [p.to_dict() for p in self.points],
            "spikeRisk": self.spikeRisk.to_dict(),
            "modelVersion": self.modelVersion,
        }
