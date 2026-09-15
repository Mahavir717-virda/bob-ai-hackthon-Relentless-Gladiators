# `ml/datasets` — Machine Learning Datasets & Feature Stores

## Module Overview
Stores training datasets, validation splits, and feature definitions.

- **Datasets:**
  - `openstef_demand_clean.parquet` — Processed 15-min substation load timeseries.
  - `solar_wind_features.parquet` — Weather-aligned renewable generation datasets.
  - `spike_classification_train.parquet` — Labeled demand spike events.
- **Rules:**
  - Large raw binary data files must not be committed to Git. Use DVC or download scripts in `scripts/download_datasets.py`.
  - Samples and fixtures must strictly reflect real data distributions (no fake numbers).
- **Owned By:** Member 2 (Demand) & Member 3 (Renewable)
