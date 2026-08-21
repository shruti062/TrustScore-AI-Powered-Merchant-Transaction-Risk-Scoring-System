# TrustScore — AI-Powered Merchant Transaction Risk Scoring System
 **AI Risk Manager**

## What it does

TrustScore scores every payment transaction for fraud/risk in real
time (0–100), explains **why** it got that score in plain English,
and recommends an action: **Allow / Review / Block**. A live
dashboard shows recent transactions and flags merchants whose
transactions are trending risky.

This is the kind of tool a payments company would run
behind the scenes to catch fraud before it costs money — while still
giving a human reviewer a clear, explainable reason instead of a
black-box number.

## How it works

1. **`generate_data.py`** creates a synthetic dataset of 4,000
   transactions with realistic patterns (odd-hour transactions,
   location mismatches, new devices, transaction velocity) and
   labels ~12% of them as fraudulent.
2. **`model.py`** trains a Random Forest classifier on that data and
   saves it as `risk_model.pkl`. Random Forest was chosen because it
   handles tabular data well without heavy tuning, and its structure
   makes it easy to reason about which signals matter.
3. **`app.py`** is the Flask API. It loads the trained model once at
   startup and exposes endpoints to score transactions and serve
   dashboard data.
4. **`database.py`** stores every scored transaction in a local
   SQLite file so the dashboard has history to show.
5. On top of the model's raw probability, a small rule-based
   **explanation layer** (`explain_score` in `model.py`) turns the
   score into human-readable reasons like "Billing and shipping city
   don't match" — this is what actually makes the tool usable by a
   risk reviewer, not just accurate.

## Project structure

```
trustscore/
├── backend/
│   ├── app.py              Flask app + API routes
│   ├── model.py             Model training + scoring logic
│   ├── database.py          SQLite storage helpers
│   ├── generate_data.py     Synthetic dataset generator
│   └── requirements.txt
└── frontend/
    ├── index.html
    ├── style.css
    └── script.js
```

## Setup

```bash
cd backend
pip install -r requirements.txt

# One-time setup: generate data and train the model
python generate_data.py
python model.py

# Run the app
python app.py
```

Then open **http://127.0.0.1:5000** in your browser.

Click **"Simulate Transaction"** on the dashboard to generate and
score a new random transaction live.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/score-transaction` | Score a real transaction (send transaction details as JSON) |
| POST | `/api/simulate-transaction` | Generate + score a random demo transaction |
| GET | `/api/recent-transactions` | Get recent scored transactions |
| GET | `/api/merchant-summary` | Get per-merchant risk aggregates |

## Possible extensions

- Feed in real transaction data instead of synthetic data
- Add a feedback loop where reviewers confirm/reject flags to retrain the model
- Add email/Slack alerts when a merchant's average risk score spikes
- Track model drift over time as fraud patterns evolve
