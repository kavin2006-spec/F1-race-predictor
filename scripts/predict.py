import pandas as pd
import pickle
import requests
import json
import os
from sqlalchemy import create_engine

from api.main import BASE_DIR

engine = create_engine(
    "mssql+pyodbc://@MSI\\SQLEXPRESS/F1Database"
    "?driver=ODBC+Driver+17+for+SQL+Server"
    "&trusted_connection=yes"
    "&TrustServerCertificate=yes"
)

FEATURE_COLS = [
    "grid_pos",
    "quali_gap_pct",
    "avg_quali_gap_last_3",
    "avg_finish_last_1",
    "avg_finish_last_3",
    "avg_finish_last_5",
    "team_avg_finish_last_3",
    "avg_positions_gained",
    "sprint_delta",
    "avg_sprint_delta_last_3",
    "weighted_avg_finish",
    "wins_at_track",
    "track_id"
]

def load_model():
    with open("models/f1_model.pkl", "rb") as f:
        return pickle.load(f)

def load_f1_context():
    static_path  = os.path.join(BASE_DIR, "data", "f1_context_static.json")
    dynamic_path = os.path.join(BASE_DIR, "data", "f1_context_dynamic.json")

    with open(static_path, "r") as f:
        static = json.load(f)

    # Merge dynamic on top if it exists
    if os.path.exists(dynamic_path):
        with open(dynamic_path, "r") as f:
            dynamic = json.load(f)
        # Dynamic data overrides static for shared keys
        static.update(dynamic)

    return static

def get_race_features(year, round_number):
    query = f"""
        SELECT f.driver, f.team, f.track, f.track_id,
               f.grid_pos,
               f.quali_gap_pct,
               f.avg_quali_gap_last_3,
               f.avg_finish_last_1,
               f.avg_finish_last_3,
               f.avg_finish_last_5,
               f.team_avg_finish_last_3,
               f.avg_positions_gained,
               f.sprint_delta,
               f.avg_sprint_delta_last_3,
               f.weighted_avg_finish,
               f.wins_at_track
        FROM features f
        WHERE f.year = {year} AND f.round = {round_number}
    """
    df = pd.read_sql(query, engine)
    print(f"Query returned {len(df)} rows for {year} round {round_number}")
    return df


def predict_race(year, round_number):
    model = load_model()
    df = get_race_features(year, round_number)

    if df.empty:
        print(f"No data found for {year} round {round_number}")
        return None

    track_name = df["track"].iloc[0]

    # Fill NaN with -1 sentinel — same as during training
    X = df[FEATURE_COLS].fillna(-1)
    df["predicted_delta"] = model.predict(X)

    # Predicted finish = grid position minus predicted delta
    df["predicted_finish"] = df["grid_pos"] - df["predicted_delta"]
    df = df.sort_values("predicted_finish").reset_index(drop=True)
    df["predicted_position"] = range(1, len(df) + 1)

    print(f"\nPredicted results for {track_name} {year}")
    print("-" * 40)
    for _, row in df.iterrows():
        delta_str = (
            f"+{row['predicted_delta']:.1f}"
            if row["predicted_delta"] > 0
            else f"{row['predicted_delta']:.1f}"
        )
        print(
            f"P{int(row['predicted_position']):>2}  {row['driver']:<6}  "
            f"({row['team']})  "
            f"Grid: P{int(row['grid_pos'])}  "
            f"Delta: {delta_str}"
        )

    return df


def predict_sprint(year, round_number):
    """
    Predict sprint race finishing positions.
    Uses same model but scales delta by 0.6 — sprints are 100km vs 305km
    so drivers have less time to make up positions.
    """
    model = load_model()
    df = get_race_features(year, round_number)

    if df.empty:
        print(f"No data found for {year} round {round_number}")
        return None

    track_name = df["track"].iloc[0]

    X = df[FEATURE_COLS].fillna(-1)
    df["predicted_delta"] = model.predict(X)

    # Scale delta down — sprint is ~60% of race distance
    df["predicted_delta"] = df["predicted_delta"] * 0.6

    df["predicted_finish"] = df["grid_pos"] - df["predicted_delta"]
    df = df.sort_values("predicted_finish").reset_index(drop=True)
    df["predicted_position"] = range(1, len(df) + 1)

    print(f"\nPredicted SPRINT results for {track_name} {year}")
    print("-" * 40)
    for _, row in df.iterrows():
        delta_str = (
            f"+{row['predicted_delta']:.1f}"
            if row["predicted_delta"] > 0
            else f"{row['predicted_delta']:.1f}"
        )
        print(
            f"P{int(row['predicted_position']):>2}  {row['driver']:<6}  "
            f"({row['team']})  "
            f"Grid: P{int(row['grid_pos'])}  "
            f"Delta: {delta_str}"
        )

    return df


# Global conversation history — persists for the whole session
conversation_history = []

def ask_ollama(df, track_name, year, driver=None):
    """Ask Ollama to explain predictions — maintains conversation history"""

    if driver:
        if driver not in df["driver"].values:
            print(f"Driver {driver} not found in predictions")
            return

        row = df[df["driver"] == driver].iloc[0]
        prompt = f"""You are an F1 race analyst. Explain this prediction concisely.

Race: {track_name} {year}
Driver: {row['driver']} ({row['team']})
Grid position: P{int(row['grid_pos'])}
Predicted finish: P{int(row['predicted_position'])}
Predicted positions gained/lost: {row['predicted_delta']:.1f}
Recent avg finish (last 3 races): {row['avg_finish_last_3']:.1f}
Team avg finish (last 3 races): {row['team_avg_finish_last_3']:.1f}
Avg positions gained historically: {row['avg_positions_gained']:.1f}

Give a 3-4 sentence explanation of why this driver is predicted to finish here."""

    else:
        top5 = df.head(5)[
            ["driver", "team", "predicted_position", "grid_pos", "predicted_delta"]
        ].to_string(index=False)
        prompt = f"""You are an F1 race analyst. Briefly summarise the predicted top 5 for {track_name} {year}.

{top5}

Give a short paragraph summarising the predicted race outcome and any interesting storylines."""

    conversation_history.append({"role": "user", "content": prompt})

    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "mistral:latest",
            "messages": conversation_history,
            "stream": False
        },
        timeout=120
    )

    if response.status_code == 200:
        reply = response.json()["message"]["content"]
        conversation_history.append({"role": "assistant", "content": reply})
        print("\nAI Analysis:")
        print("-" * 40)
        print(reply)
    else:
        print(f"Ollama error: {response.status_code}")


def chat_with_analyst(df, track_name, year):
    """
    Interactive chat with full conversation memory.
    Seeds Ollama with race context then opens a question loop.
    Type 'exit' to quit.
    """
    context = load_f1_context()

    # Build driver identity string
    driver_info = []
    for _, row in df.iterrows():
        code = row["driver"]
        d = context.get("drivers", {}).get(code, {})
        name = d.get("name", code)
        note = f" — {d['note']}" if d.get("note") else ""
        driver_info.append(f"  {code} = {name}{note}")
    driver_info_str = "\n".join(driver_info)

    # Track context
    track_ctx = context.get("tracks", {}).get(track_name, {})
    track_str = (
        f"Type: {track_ctx.get('type','unknown')} — "
        f"{track_ctx.get('characteristics','')}"
        if track_ctx else "No track data available"
    )

    # Track records
    track_records = context.get("track_records", {}).get(track_name, {})
    track_record_str = ""
    if track_records:
        notable = track_records.get("notable", [])
        track_record_str = "Historical track records:\n" + "\n".join(
            f"  - {n}" for n in notable
        )

    # Regulation notes
    reg_note = context.get("regulation_notes", {}).get(str(year), "")

    # 2026 season results
    season_results = context.get("season_2026_results", {})
    races_so_far = season_results.get("races", [])
    standings = season_results.get("season_standings_after_round_2", {})

    results_str = ""
    for race in races_so_far:
        top5 = ", ".join([f"{r['pos']}. {r['name']}" for r in race["result"][:5]])
        results_str += f"\n  {race['name']}: {top5}"

    standings_str = ""
    if standings:
        standings_str = "Current standings: " + ", ".join([
            f"{d['pos']}. {d['name']} ({d['points']}pts)"
            for d in standings.get("drivers", [])[:7]
        ])

    # Full predicted grid
    race_summary = df[[
        "driver", "team", "predicted_position",
        "grid_pos", "predicted_delta", "avg_finish_last_3"
    ]].to_string(index=False)

    system_context = f"""You are an expert F1 race strategist for the 2026 season.

CRITICAL: Base all explanations on actual 2026 results. Do not speculate about 2025.
Always use full driver names. Be concise and data-driven.

2026 RESULTS SO FAR:{results_str}
{standings_str}

DRIVER IDENTITIES:
{driver_info_str}

TRACK — {track_name}:
{track_str}
{track_record_str}

REGULATIONS ({year}):
{reg_note}

PREDICTED GRID:
{race_summary}

Answer questions using the data above."""

    conversation_history.clear()
    conversation_history.append({"role": "user", "content": system_context})

    # Get acknowledgement
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "mistral:latest",
            "messages": conversation_history,
            "stream": False
        },
        timeout=120
    )

    if response.status_code == 200:
        ack = response.json()["message"]["content"]
        conversation_history.append({"role": "assistant", "content": ack})

    print(f"\nF1 Analyst ready — {track_name} {year}")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "exit":
            print("Ending analysis session.")
            break
        if not user_input:
            continue

        conversation_history.append({"role": "user", "content": user_input})

        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "mistral:latest",
                "messages": conversation_history,
                "stream": False
            },
            timeout=120
        )

        if response.status_code == 200:
            reply = response.json()["message"]["content"]
            conversation_history.append({"role": "assistant", "content": reply})
            print(f"\nAnalyst: {reply}\n")
        else:
            print(f"Ollama error: {response.status_code}")


if __name__ == "__main__":
    YEAR = 2026
    ROUND = 2

    df = predict_race(YEAR, ROUND)

    if df is not None:
        track = df["track"].iloc[0]

        ask_ollama(df, track, YEAR)

        print("\n--- Individual driver analysis ---")
        ask_ollama(df, track, YEAR, driver="NOR")

        print("\n--- Interactive analyst chat ---")
        chat_with_analyst(df, track, YEAR)