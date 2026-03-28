# F1 Race Predictor

A machine learning system that predicts Formula 1 race finishing positions before lights out, powered by FastF1 telemetry data, a Gradient Boosting model, and a local LLM analyst.

![Python](https://img.shields.io/badge/Python-3.14-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![React](https://img.shields.io/badge/React-18-61DAFB)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.8-orange)

## What it does

- Predicts finishing positions for every driver before a race starts
- Uses qualifying pace, recent form, track DNA, championship pressure and more
- Achieves **1.80 MAE** (positions off) with **81.9% of predictions within 3 positions**
- Includes an AI analyst (phi3:mini via Ollama) that explains predictions in plain English
- Archives pre-race predictions and compares them against actual results after the race

## Project structure
```
F1/
├── api/                    # FastAPI backend
│   ├── main.py             # API endpoints
│   └── requirements.txt
├── frontend/               # React UI
│   └── src/
│       ├── App.js
│       └── App.css
├── scripts/                # Data pipeline
│   ├── data_loader.py
│   ├── feature_engineering.py
│   ├── train_model.py
│   ├── predict.py
│   ├── build_track_dna.py
│   ├── fetch_quali_jolpica.py
│   ├── update_context.py
│   └── migrate_to_supabase.py
├── data/
│   ├── f1_context_static.json
│   └── f1_context_dynamic.json
├── models/
│   └── f1_model.pkl
└── docs/
    ├── DATA.md
    ├── MODEL.md
    ├── CHATBOT.md
    └── ROADMAP.md
```

## Stack

| Layer | Technology |
|---|---|
| Data source | FastF1, Jolpica (Ergast replacement) |
| Database | SQL Server (local) + Supabase (PostgreSQL, cloud) |
| ML model | scikit-learn Gradient Boosting Regressor |
| Backend API | FastAPI + uvicorn |
| Frontend | React |
| AI analyst | Mistral 7B via Ollama (local) |

## Installation

### Prerequisites

- Python 3.10+
- Node.js 18+
- SQL Server Management Studio (or SQLite as alternative)
- Ollama with phi3:mini pulled (`ollama pull mistral`)

### 1. Clone the repo
```bash
git clone https://github.com/kavin2006-spec/F1-race-predictor.git
cd F1-race-predictor
```

### 2. Set up Python environment
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 3. Set up environment variables

Create a `.env` file in the root:
```
DATABASE_URL=your_supabase_connection_string
```

### 4. Run the data pipeline
```bash
# Pull race data from FastF1 (takes 20-30 mins first run)
python scripts/data_loader.py

# Build track DNA from historical data
python scripts/build_track_dna.py

# Engineer features
python scripts/feature_engineering.py

# Train the model
python scripts/train_model.py
```

### 5. Start the API
```bash
cd api
uvicorn main:app --reload
```

### 6. Start the frontend
```bash
cd frontend
npm install
npm start
```

Open `http://localhost:3000`

## Race weekend workflow

After qualifying on Saturday:
```bash
# Fetch official qualifying times
python scripts/fetch_quali_jolpica.py

#If Jolpica doesn't load qualifying data on time, then manaully upload the gap percentage ratios in manual_entry.py and run it
python scripts/manual_entry.py

# Rebuild features with real grid positions
python scripts/feature_engineering.py
python scripts/train_model.py

# Push to Supabase
python scripts/migrate_to_supabase.py

# Save pre-race predictions to archive
curl -X POST http://localhost:8000/save-prediction/2026/{round}
```

After the race on Sunday:
```bash
# Pull race results
python scripts/data_loader.py

# Update context file with actual results
# Edit data/f1_context_dynamic.json by running update_context
python scripts/update_context.py

# Rebuild and push
python scripts/feature_engineering.py
python scripts/train_model.py
python scripts/migrate_to_supabase.py
```

## Model performance

| Metric | Value |
|---|---|
| MAE | 1.80 positions |
| Within 3 positions | 81.9% |
| Correct direction | 77.5% |
| Training data | 2022–2026 (85+ races) |

See [docs/MODEL.md](docs/MODEL.md) for full feature breakdown and methodology.

## Documentation

- [Data pipeline](docs/DATA.md) — how race data is collected, stored and migrated
- [Model](docs/MODEL.md) — feature engineering, target variable, training process
- [AI analyst](docs/CHATBOT.md) — how the LLM context system works
- [Roadmap](docs/ROADMAP.md) — planned improvements

## Developement notes
This project was built with significant assistance from Claude (Anthropic) as an AI pair programmer. Claude helped with architecture decisions, debugging, code generation, and feature engineering ideas throughout the build process.

The core ideas, design decisions, and domain knowledge (F1, mechanical engineering context, what features actually matter) came from me — Claude helped implement them faster and explained concepts along the way. I would like to repeat an analogy that I've seen often: 
the current state of coding is as of that to an architect and an builder, the architect being myself while the actual code is 'built' by AI. I believe this way of working will become increasingly normal. Rather than reducing creativity, it actually shifts the focus toward higher-level thinking:
designing systems, choosing the right features, and understanding the problem space deeply. The “what” and “why” become more important than the “how,” which enhances creativity rather than replacing it.

This is an honest reflection of how modern software development works, and I'd rather be upfront about it than pretend I wrote every line from scratch. The learning was real and I understand every part of this system and could rebuild it from scratch.
