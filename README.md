#  Predictive Maintenance Dashboard

> Real-time machine health monitoring, ML-driven failure prediction, and automated shift reporting for industrial manufacturing (CNC machines & welding robots).

<p align="left">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Dash-Plotly-3F4F75?logo=plotly&logoColor=white" />
  <img src="https://img.shields.io/badge/scikit--learn-ML-F7931E?logo=scikit-learn&logoColor=white" />
  <img src="https://img.shields.io/badge/pandas-Data-150458?logo=pandas&logoColor=white" />
  <img src="https://img.shields.io/badge/lifelines-Survival%20Analysis-8A2BE2" />
  <img src="https://img.shields.io/badge/License-MIT-green" />
  <img src="https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white" />
</p>

---

##  Overview

Unplanned downtime is the single most expensive failure mode on a factory floor. This project is an end-to-end **predictive maintenance** system that ingests machine telemetry (vibration, temperature, tool wear, spindle load, OEE), scores each asset's health in real time, predicts failure risk with a trained ML model, and pushes alerts + automated shift-handover reports to the maintenance team.

It models two very different asset classes with separate failure physics:

- **CNC machines** — tool wear, spindle load, X/Y vibration, coolant temperature
- **Welding / assembly robots (REP)** — joint backlash, weld quality, gripper force, positioning accuracy

The system is bilingual (English / Deutsch) and is designed to sit on top of SAP / Hydra-style MES exports.

##  Key Features

| Capability | Description |
|---|---|
| 🩺 **Health Scoring** | 0–100 health index per machine using weighted, *exponential degradation* curves — a reading near the critical threshold is penalized far more than a mid-range one. |
|  **Failure Prediction** | RandomForest / GradientBoosting classifiers with cross-validation and ROC-AUC evaluation. |
|  **Remaining Useful Life (RUL)** | Survival analysis (`lifelines`) to estimate time-to-failure. |
|  **Anomaly Detection** | IsolationForest flags abnormal sensor signatures the rules don't catch. |
|  **Alert Engine** | Threshold-based alerting with optional SMTP email delivery. |
|  **Shift Handover Reports** | Auto-generated PDF reports for the 6 AM / 2 PM / 10 PM shift changes. |
|  **Bilingual UI** | Full English / German translation layer. |
|  **Interactive Dashboard** | Plotly Dash UI with live KPIs, trend charts, and machine schematics. |

##  Architecture

```
                ┌──────────────────────┐
   SAP / Hydra  │   data_loader.py     │   raw telemetry
   Excel export │  (extract + clean)   │ ─────────────┐
                └──────────────────────┘              │
                                                       ▼
        ┌───────────────┐   features    ┌──────────────────────────┐
        │ health_score  │ ◀──────────── │     data_processor       │
        │  (CNC / REP)  │               │  (feature engineering)   │
        └───────┬───────┘               └────────────┬─────────────┘
                │ health 0-100                        │
                ▼                                      ▼
        ┌───────────────┐               ┌──────────────────────────┐
        │  analytics    │               │  models/train.py         │
        │ RUL + anomaly │               │  RandomForest / GBM       │
        └───────┬───────┘               └────────────┬─────────────┘
                │                                      │ failure_model.pkl
                └──────────────┬───────────────────────┘
                               ▼
                    ┌──────────────────────┐    ┌──────────────┐
                    │  Dash dashboard      │───▶│ alerts +     │
                    │  (layout + callbacks)│    │ shift PDF    │
                    └──────────────────────┘    └──────────────┘
```

##  Project Structure

```
predictive-maintenance-dashboard/
├── app.py                  # Entry point — launches the dashboard
├── dashboard.py            # Dash layout + callbacks (single-module version)
├── app/                    # Advanced modular package
│   ├── language.py         # Bilingual (EN/DE) translation system
│   ├── data_processor.py   # Loading & feature engineering
│   ├── analytics.py        # Health score, failure prediction, anomaly detection
│   ├── alerts.py           # Alert engine + email delivery
│   ├── visual_diagnostics.py  # Machine schematic generator
│   ├── shift_report.py     # Shift-handover PDF generator + scheduler
│   ├── layout.py           # Dash layout
│   └── callbacks.py        # Dash callbacks
├── data/generate_dataset.py   # Synthetic SAP-style dataset generator
├── models/train.py            # Train & evaluate the failure-prediction model
├── utils/
│   ├── data_loader.py      # SAP Excel → DataFrames
│   └── health_score.py     # Health score + RUL logic
├── tests/test_health_score.py
├── requirements.txt
└── .env.example
```

##  Quickstart

```bash
# 1. Clone
git clone https://github.com/harshalingawale/predictive-maintenance-dashboard.git
cd predictive-maintenance-dashboard

# 2. Create environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Generate a synthetic dataset (no real factory data required)
python data/generate_dataset.py

# 4. Train the failure-prediction model
python models/train.py

# 5. Launch the dashboard
python app.py
#  → open http://127.0.0.1:8050
```

Copy `.env.example` to `.env` to configure data source, ports, and (optional) email alerts.

##  Tests

```bash
pytest -q
```

##  ML Methodology

- **Labeling.** A machine is labeled *at-risk* when its computed health score drops below 60. This turns an unsupervised health index into a supervised classification target.
- **Models.** RandomForest and GradientBoosting are trained inside a `Pipeline` with `StandardScaler`, compared via 5-fold cross-validation, and evaluated with `classification_report` + ROC-AUC.
- **RUL.** Survival models estimate remaining useful life so planners can schedule maintenance *before* failure, not after.
- **Anomaly detection.** IsolationForest provides an unsupervised second opinion for novel failure signatures.

##  Tech Stack

**Python · Dash · Plotly · pandas · NumPy · scikit-learn · lifelines · pytest · python-dotenv**

##  Roadmap

- [ ] Containerize with Docker + docker-compose
- [ ] Stream live telemetry via MQTT/Kafka instead of batch Excel
- [ ] Model registry + drift monitoring
- [ ] Role-based authentication for the dashboard

##  License

MIT © [Harshal Ingawale](https://github.com/harshalingawale)

---

> *Note: This project simulates a real automotive-manufacturing environment. All datasets are synthetically generated — no proprietary or confidential data is included.*
