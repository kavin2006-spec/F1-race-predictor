import requests
import json
import os
from datetime import datetime

# ----------------------------
# PATH SETUP (SAFE)
# ----------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "f1_context.json")


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

def save_context():
    # Load existing context to preserve drivers, tracks, regulations etc.
    existing = {}
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)

    # Build fresh standings data
    new_data = build_context()

    # Merge — update only the live data sections, preserve manual sections
    existing["metadata"]               = new_data["metadata"]
    existing["drivers_standings"]      = new_data["drivers_standings"]
    existing["constructors_standings"] = new_data["constructors_standings"]
    existing["driver_signals"]         = new_data["driver_signals"]
    existing["team_signals"]           = new_data["team_signals"]
    existing["track_context"]          = new_data["track_context"]

    # Update season results standings from live data
    if "season_2026_results" in existing:
        existing["season_2026_results"]["season_standings_live"] = {
            "drivers": new_data["drivers_standings"][:7],
            "constructors": new_data["constructors_standings"][:5]
        }

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)

    print("Context updated — standings refreshed, manual sections preserved")
    print(f"Drivers in standings: {len(new_data['drivers_standings'])}")
    print(f"Teams in standings: {len(new_data['constructors_standings'])}")

# ----------------------------
# RUN SCRIPT
# ----------------------------

if __name__ == "__main__":
    try:
        save_context()
    except Exception as e:
        print("Error updating context:")
        print(e)