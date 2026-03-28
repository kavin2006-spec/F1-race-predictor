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
            "surname": d["Driver"]["familyName"],
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

        # FORM CLASSIFICATION
        if pos <= 2:
            form = "elite"
            score = 95
        elif pos <= 5:
            form = "strong"
            score = 85
        elif pos <= 10:
            form = "competitive"
            score = 75
        else:
            form = "weak"
            score = 60

        # CONSISTENCY (based on wins + position)
        consistency = "high" if d["wins"] > 0 or pos <= 5 else "medium"

        signals[d["surname"]] = {
            "name": d["name"],
            "team": d["team"],
            "championship_position": pos,
            "points": d["points"],
            "wins": d["wins"],
            "form": form,
            "consistency": consistency,
            "base_score": score
        }

    return signals


# ----------------------------
# TEAM PERFORMANCE SIGNALS
# ----------------------------

def generate_team_signals(teams):
    signals = {}

    for t in teams:
        pos = t["position"]

        if pos == 1:
            tier = "dominant"
        elif pos <= 3:
            tier = "front_runner"
        elif pos <= 6:
            tier = "midfield"
        else:
            tier = "backmarker"

        signals[t["team"]] = {
            "position": pos,
            "points": t["points"],
            "wins": t["wins"],
            "tier": tier
        }

    return signals


# ----------------------------
# TRACK BIAS (30%)
# ----------------------------

def get_track_bias():
    return {
        "Japanese Grand Prix": {
            "circuit_type": "high-speed technical",
            "overtaking_difficulty": "hard",
            "importance_of_qualifying": "high",

            "driver_bias": [
                {
                    "driver": "Verstappen",
                    "boost": 12,
                    "reason": "Multiple Suzuka wins, strong high-speed performance"
                },
                {
                    "driver": "Hamilton",
                    "boost": 8,
                    "reason": "Historically strong at Suzuka"
                }
            ],

            "team_bias": [
                {
                    "team": "Red Bull Racing",
                    "boost": 10
                }
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
            "historical_track": 0.3
        },

        "drivers_standings": drivers,
        "constructors_standings": teams,

        "driver_signals": generate_driver_signals(drivers),
        "team_signals": generate_team_signals(teams),

        "track_bias": get_track_bias()
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
    existing["track_bias"]             = new_data["track_bias"]

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
        print("❌ Error updating context:")
        print(e)