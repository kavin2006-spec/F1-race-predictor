import requests
import json
import os
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

# ----------------------------
# PATH SETUP (SAFE)
# ----------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "f1_context_dynamic.json")


# ----------------------------
# API CONFIG
# ----------------------------

ERGAST_BASE = "https://api.jolpi.ca/ergast/f1/current"

# ----------------------------
# FETCH FUNCTIONS
# ----------------------------

def fetch_driver_standings():
    url = f"{ERGAST_BASE}/driverStandings.json"
    response = requests.get(url)
    response.raise_for_status()

    data = response.json()
    standings = data["MRData"]["StandingsTable"]["StandingsLists"][0]["DriverStandings"]

    drivers = []
    for d in standings:
        drivers.append({
            "position": int(d["position"]),
            "code": d["Driver"]["code"],
            "name": f"{d['Driver']['givenName']} {d['Driver']['familyName']}",
            "points": float(d["points"]),
            "team": d["Constructors"][0]["name"],
            "wins": int(d["wins"])
        })

    return drivers


def fetch_constructor_standings():
    url = f"{ERGAST_BASE}/constructorStandings.json"
    response = requests.get(url)
    response.raise_for_status()

    data = response.json()
    standings = data["MRData"]["StandingsTable"]["StandingsLists"][0]["ConstructorStandings"]

    teams = []
    for t in standings:
        teams.append({
            "position": int(t["position"]),
            "team": t["Constructor"]["name"],
            "points": float(t["points"]),
            "wins": int(t["wins"])
        })

    return teams


# ----------------------------
# SIGNAL GENERATION (70%)
# ----------------------------

def generate_driver_signals(drivers):
    signals = {}

    for d in drivers:
        pos = d["position"]

        # NUMERIC FORM SCORE (no vague labels)
        form_score = max(0, 100 - pos * 3)

        # CONSISTENCY SCORE (simple proxy)
        consistency_score = min(100, d["wins"] * 10 + (25 if pos <= 5 else 10))

        signals[d["code"]] = {
            "name": d["name"],
            "team": d["team"],
            "championship_position": pos,
            "points": d["points"],
            "wins": d["wins"],

            # Replace vague labels with numbers
            "form_score": round(form_score, 2),
            "consistency_score": round(consistency_score, 2),

            # Add uncertainty
            "confidence": "medium" if pos <= 10 else "low"
        }

    return signals  


# ----------------------------
# TEAM PERFORMANCE SIGNALS
# ----------------------------

def generate_team_signals(teams):
    signals = {}

    for t in teams:
        pos = t["position"]

        # Numeric strength instead of tiers
        strength_score = max(0, 100 - pos * 5)

        signals[t["team"]] = {
            "position": pos,
            "points": t["points"],
            "wins": t["wins"],
            "strength_score": round(strength_score, 2),

            # Add uncertainty
            "confidence": "high" if pos <= 3 else "medium"
        }

    return signals
# ----------------------------
# Track CONTEXT
# ----------------------------

def get_track_context():
    return {
        "Japanese Grand Prix": {
            "circuit_type": "high-speed technical",
            "overtaking_difficulty": "hard",
            "importance_of_qualifying": "high",

            # NO driver bias
            # NO team bias

            "notes": [
                "Track position is important",
                "High-speed corners favor aerodynamic efficiency"
            ]
        }
    }

# ----------------------------
# Track CONTEXT
# ----------------------------

def fetch_race_results_from_db(engine):
    """
    Pull actual race results from the database and format them
    for the dynamic context — no manual entry needed.
    """
    results_query = """
        SELECT r.year, r.round, r.track, r.driver, r.final_pos, r.grid_pos, r.status,
               f.team
        FROM race_results r
        LEFT JOIN features f ON r.driver = f.driver 
            AND r.year = f.year AND r.round = f.round
        WHERE r.year = 2026
        AND r.status IN ('Finished', 'Lapped', '+1 Lap', '+2 Laps', '')
        ORDER BY r.round, r.final_pos
    """
    
    try:
        df = pd.read_sql(results_query, engine)
    except Exception as e:
        print(f"Could not fetch race results: {e}")
        return {}

    # Driver name lookup
    driver_names = {
        "VER": "Max Verstappen",     "NOR": "Lando Norris",
        "LEC": "Charles Leclerc",    "HAM": "Lewis Hamilton",
        "RUS": "George Russell",     "ANT": "Kimi Antonelli",
        "PIA": "Oscar Piastri",      "SAI": "Carlos Sainz",
        "ALB": "Alexander Albon",    "GAS": "Pierre Gasly",
        "OCO": "Esteban Ocon",       "BEA": "Oliver Bearman",
        "STR": "Lance Stroll",       "ALO": "Fernando Alonso",
        "LAW": "Liam Lawson",        "HAD": "Isack Hadjar",
        "LIN": "Arvid Lindblad",     "COL": "Franco Colapinto",
        "HUL": "Nico Hülkenberg",    "BOR": "Gabriel Bortoleto",
        "PER": "Sergio Pérez",       "BOT": "Valtteri Bottas",
    }

    races = {}
    for (round_num, track), group in df.groupby(["round", "track"]):
        top5 = group.sort_values("final_pos").head(5)
        races[round_num] = {
            "round":  int(round_num),
            "name":   track,
            "result": [
                {
                    "pos":    int(row["final_pos"]),
                    "driver": row["driver"],
                    "name":   driver_names.get(row["driver"], row["driver"]),
                    "grid":   int(row["grid_pos"]),
                }
                for _, row in top5.iterrows()
            ]
        }

    return {
        "races": list(races.values()),
        "last_updated": datetime.utcnow().isoformat()
    }
# ----------------------------
# BUILD CONTEXT
# ----------------------------

def build_context():
    drivers = fetch_driver_standings()
    teams = fetch_constructor_standings()

    context = {
        "metadata": {
            "last_updated": datetime.utcnow().isoformat(),
            "season": 2026,
            "data_source": "Ergast API"
        },

        "weights": {
            "current_form": 0.7,
            "track_characteristics": 0.3
        },

        "drivers_standings": drivers,
        "constructors_standings": teams,

        "driver_signals": generate_driver_signals(drivers),
        "team_signals": generate_team_signals(teams),

        "track_context": get_track_context(),

        # anti-hallucination layer
        "model_constraints": {
            "description": "This system predicts expected race outcomes based on statistical trends.",
            "limitations": [
                "No real-time race simulation",
                "No pit strategy modeling",
                "No weather effects included"
            ],
            "instruction": "Use cautious, probabilistic reasoning. Do not assume certainty."
        }
    }

    return context


# ----------------------------
# SAVE FILE
# ----------------------------

DYNAMIC_PATH = os.path.join(BASE_DIR, "data", "f1_context_dynamic.json")

def save_context():
    from sqlalchemy import create_engine as ce
    from dotenv import load_dotenv
    load_dotenv()

    # Connect to local SQL Server for race results
    local_engine = ce(
        "mssql+pyodbc://@MSI\\SQLEXPRESS/F1Database"
        "?driver=ODBC+Driver+17+for+SQL+Server"
        "&trusted_connection=yes"
        "&TrustServerCertificate=yes"
    )

    context = build_context()

    # Add auto-pulled race results
    context["season_2026_results_auto"] = fetch_race_results_from_db(local_engine)

    with open(DYNAMIC_PATH, "w", encoding="utf-8") as f:
        json.dump(context, f, indent=2)

    print("Dynamic context updated including 2026 race results")

# ----------------------------
# RUN SCRIPT
# ----------------------------

if __name__ == "__main__":
    try:
        save_context()
    except Exception as e:
        print("Error updating context:")
        print(e)