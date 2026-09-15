"""
services/renewable/constants.py
================================
Central constants for the Renewable Intelligence Service.

RULES:
- All generation values from OpenSTEF arrive in Watts (W).
- RenewableStatus contract fields (expectedMw, actualMw) are in Megawatts (MW).
- Always use W_TO_MW for conversion; never hardcode 1e-6 in business logic.
"""

# ── Unit Conversion ────────────────────────────────────────────────────────────
W_TO_MW: float = 1e-6          # Watts → Megawatts
MW_TO_W: float = 1e6           # Megawatts → Watts

# ── Forecast horizon ───────────────────────────────────────────────────────────
FORECAST_HORIZON_STEPS: int = 96   # 24 h @ 15-min intervals
TIMESTEP_MINUTES: int = 15

# ── Dataset geography (Liander / Netherlands) ─────────────────────────────────
DEFAULT_TIMEZONE: str = "UTC"

# ── Solar physics ──────────────────────────────────────────────────────────────
# Minimum solar elevation angle (degrees) below which generation is clamped to 0
MIN_SOLAR_ELEVATION_DEG: float = 0.0

# ── Anomaly / performance thresholds ──────────────────────────────────────────
# Performance ratio below this → candidate for anomaly flagging
PERFORMANCE_RATIO_LOWER_WARN: float = 0.7
# Performance ratio above this can indicate data / sensor issue
PERFORMANCE_RATIO_UPPER_WARN: float = 1.3

# ── Curtailment-aware diagnostics ────────────────────────────────────────────
# Ratios in this band are treated as ordinary production variation.
PERFORMANCE_RATIO_NORMAL_LOWER: float = 0.90
PERFORMANCE_RATIO_NORMAL_UPPER: float = 1.10
# Low output must persist for this many consecutive intervals before a
# weather-blind physical-fault diagnostic can be raised.
PERSISTENT_LOW_PERFORMANCE_INTERVALS: int = 4
# Weather evidence thresholds.  These are deliberately conservative proxies,
# not substitutes for an explicit curtailment or equipment-status signal.
HIGH_CLOUD_COVER_PERCENT: float = 80.0
LOW_WIND_SPEED_MPS: float = 3.0

# ── Model versioning ──────────────────────────────────────────────────────────
SOLAR_MODEL_VERSION: str = "1.0.0"
WIND_MODEL_VERSION: str  = "1.0.0"

# ── Random seed for reproducibility ───────────────────────────────────────────
RANDOM_SEED: int = 42
