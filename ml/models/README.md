# `ml/models` — Trained Model Registry & Artifacts

## Module Overview
Hosts exported model checkpoints, serializations, and metadata cards.

- **Subdirectories:**
  - `ml/models/demand/` — LightGBM demand forecaster & XGBoost spike classifier.
  - `ml/models/renewable/` — LightGBM solar/wind forecasters, Isolation Forest anomaly detector, XGBoost+SHAP root cause explainer.
- **Rule:** Every saved model must include training metadata, validation metrics (MAE, RMSE, F1, precision, recall), and feature list. Do not commit fake ML results.
- **Owned By:** Member 2 (Demand) & Member 3 (Renewable)
