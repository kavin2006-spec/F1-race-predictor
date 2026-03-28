from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import pickle
import os
import json
from sqlalchemy import create_engine
from datetime import datetime, timezone

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres.wvwcylvveasvgakzhppy:F2CP2Wb$Kcfv2Ds@aws-1-eu-central-1.pooler.supabase.com:5432/postgres",
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"sslmode": "require"}
)

# Must exactly match FEATURE_COLS in train_model.py
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
    "track_id",
    "is_wet",
    "start_compound_encoded",
    "avg_sc_laps_pct",
    "avg_teammate_quali_gap_last_3",
    "championship_rank_pre_race",
    "points_gap_to_leader",
    "wins_at_track",
]

CALENDAR_2026 = [
    {"round": 1,  "name": "Australian Grand Prix",   "date": "2026-03-08"},
    {"round": 2,  "name": "Chinese Grand Prix",       "date": "2026-03-15"},
    {"round": 3,  "name": "Japanese Grand Prix",      "date": "2026-03-29"},
    {"round": 4,  "name": "Miami Grand Prix",         "date": "2026-05-03"},
    {"round": 5,  "name": "Canadian Grand Prix",      "date": "2026-05-24"},
    {"round": 6,  "name": "Monaco Grand Prix",        "date": "2026-06-07"},
    {"round": 7,  "name": "Barcelona Grand Prix",     "date": "2026-06-14"},
    {"round": 8,  "name": "Austrian Grand Prix",      "date": "2026-06-28"},
    {"round": 9,  "name": "British Grand Prix",       "date": "2026-07-05"},
    {"round": 10, "name": "Belgian Grand Prix",       "date": "2026-07-19"},
    {"round": 11, "name": "Hungarian Grand Prix",     "date": "2026-07-26"},
    {"round": 12, "name": "Dutch Grand Prix",         "date": "2026-08-23"},
    {"round": 13, "name": "Italian Grand Prix",       "date": "2026-09-06"},
    {"round": 14, "name": "Madrid Grand Prix",        "date": "2026-09-13"},
    {"round": 15, "name": "Azerbaijan Grand Prix",    "date": "2026-09-26"},
    {"round": 16, "name": "Singapore Grand Prix",     "date": "2026-10-11"},
    {"round": 17, "name": "United States Grand Prix", "date": "2026-10-25"},
    {"round": 18, "name": "Mexico City Grand Prix",   "date": "2026-11-01"},
    {"round": 19, "name": "São Paulo Grand Prix",     "date": "2026-11-08"},
    {"round": 20, "name": "Las Vegas Grand Prix",     "date": "2026-11-21"},
    {"round": 21, "name": "Qatar Grand Prix",         "date": "2026-11-29"},
    {"round": 22, "name": "Abu Dhabi Grand Prix",     "date": "2026-12-06"},
]


def load_model():
    with open(os.path.join(BASE_DIR, "models", "f1_model.pkl"), "rb") as f:
        return pickle.load(f)


def load_context():
    with open(os.path.join(BASE_DIR, "data", "f1_context.json"), "r") as f:
        return json.load(f)


def build_driver_row(driver, team, track_name, track_id, grid_pos, h=None):
    """
    Build a feature row for one driver.
    h = history Series from features table (can be None for rookies).
    New features default to safe values when missing.
    """
    if h is not None:
        return {
            "driver":                        driver,
            "team":                          team,
            "track":                         track_name,
            "track_id":                      track_id,
            "grid_pos":                      float(grid_pos),
            "quali_gap_pct":                 h.get("quali_gap_pct"),
            "avg_quali_gap_last_3":          h.get("avg_quali_gap_last_3"),
            "avg_finish_last_1":             h.get("avg_finish_last_1"),
            "avg_finish_last_3":             h.get("avg_finish_last_3"),
            "avg_finish_last_5":             h.get("avg_finish_last_5"),
            "team_avg_finish_last_3":        h.get("team_avg_finish_last_3"),
            "avg_positions_gained":          h.get("avg_positions_gained"),
            "sprint_delta":                  None,
            "avg_sprint_delta_last_3":       h.get("avg_sprint_delta_last_3"),
            "weighted_avg_finish":           h.get("weighted_avg_finish"),
            "wins_at_track":                 h.get("wins_at_track", 0),
            "is_wet":                        0,
            "start_compound_encoded":        2,
            "avg_sc_laps_pct":               h.get("avg_sc_laps_pct", 0.15),
            "avg_teammate_quali_gap_last_3": h.get("avg_teammate_quali_gap_last_3"),
            "championship_rank_pre_race":    h.get("championship_rank_pre_race", 10),
            "points_gap_to_leader":          h.get("points_gap_to_leader", 0),
        }
    else:
        # Complete rookie — use grid position as proxy for everything
        return {
            "driver":                        driver,
            "team":                          team,
            "track":                         track_name,
            "track_id":                      track_id,
            "grid_pos":                      float(grid_pos),
            "quali_gap_pct":                 None,
            "avg_quali_gap_last_3":          None,
            "avg_finish_last_1":             float(grid_pos),
            "avg_finish_last_3":             float(grid_pos),
            "avg_finish_last_5":             float(grid_pos),
            "team_avg_finish_last_3":        None,
            "avg_positions_gained":          0.0,
            "sprint_delta":                  None,
            "avg_sprint_delta_last_3":       None,
            "weighted_avg_finish":           float(grid_pos),
            "wins_at_track":                 0,
            "is_wet":                        0,
            "start_compound_encoded":        2,
            "avg_sc_laps_pct":               0.15,
            "avg_teammate_quali_gap_last_3": None,
            "championship_rank_pre_race":    10,
            "points_gap_to_leader":          0,
        }


def get_driver_history(driver, year, round_number):
    """Fetch most recent feature row for a driver before this race."""
    query = f"""
        SELECT f.avg_finish_last_1, f.avg_finish_last_3, f.avg_finish_last_5,
               f.team_avg_finish_last_3, f.avg_positions_gained,
               f.avg_quali_gap_last_3, f.quali_gap_pct,
               f.weighted_avg_finish, f.wins_at_track, f.track_id,
               f.sprint_delta, f.avg_sprint_delta_last_3,
               f.avg_sc_laps_pct, f.avg_teammate_quali_gap_last_3,
               f.championship_rank_pre_race, f.points_gap_to_leader
        FROM features f
        WHERE f.driver = '{driver}'
        AND (f.year < {year} OR (f.year = {year} AND f.round < {round_number}))
        ORDER BY f.year DESC, f.round DESC
        LIMIT 1
    """
    result = pd.read_sql(query, engine)
    return result.iloc[0] if not result.empty else None


def run_model(df):
    """Apply model to dataframe and return with predicted positions."""
    model = load_model()

    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = -1

    for col in FEATURE_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    X = df[FEATURE_COLS].fillna(-1)
    df["predicted_delta"]    = model.predict(X)
    df["predicted_finish"]   = df["grid_pos"] - df["predicted_delta"]
    df = df.sort_values("predicted_finish").reset_index(drop=True)
    df["predicted_position"] = range(1, len(df) + 1)
    df["predicted_delta"]    = df["predicted_delta"].round(2)
    df["predicted_finish"]   = df["predicted_finish"].round(2)
    return df


@app.get("/")
def root():
    return {"status": "F1 Prediction API running"}


@app.get("/races")
def get_available_races():
    df = pd.read_sql(
        "SELECT DISTINCT year, round, track FROM features ORDER BY year, round",
        engine
    )
    return df.to_dict(orient="records")


@app.get("/predict/{year}/{round_number}")
def predict_race(year: int, round_number: int):
    try:
        # Get all drivers who started this race
        all_drivers = pd.read_sql(f"""
            SELECT r.driver, r.team, r.grid_pos, r.track
            FROM race_results r
            WHERE r.year = {year} AND r.round = {round_number}
            AND r.grid_pos > 0
        """, engine)

        if all_drivers.empty:
            raise HTTPException(status_code=404, detail=f"No data for {year} round {round_number}")

        track_name = all_drivers["track"].iloc[0]

        # Load engineered features for this round
        df = pd.read_sql(f"""
            SELECT f.driver, f.team, f.track, f.track_id,
                   f.grid_pos, f.quali_gap_pct, f.avg_quali_gap_last_3,
                   f.avg_finish_last_1, f.avg_finish_last_3, f.avg_finish_last_5,
                   f.team_avg_finish_last_3, f.avg_positions_gained,
                   f.sprint_delta, f.avg_sprint_delta_last_3,
                   f.weighted_avg_finish, f.wins_at_track,
                   f.is_wet, f.start_compound_encoded, f.avg_sc_laps_pct,
                   f.avg_teammate_quali_gap_last_3,
                   f.championship_rank_pre_race, f.points_gap_to_leader
            FROM features f
            WHERE f.year = {year} AND f.round = {round_number}
        """, engine)

        # Fill in any drivers missing from features table
        missing = all_drivers[~all_drivers["driver"].isin(df["driver"])]
        track_id = int(df["track_id"].iloc[0]) if not df.empty else 0

        missing_rows = []
        for _, row in missing.iterrows():
            h = get_driver_history(row["driver"], year, round_number)
            missing_rows.append(
                build_driver_row(row["driver"], row["team"],
                                 track_name, track_id, row["grid_pos"], h)
            )

        if missing_rows:
            df = pd.concat([df, pd.DataFrame(missing_rows)], ignore_index=True)

        df = run_model(df)

        return {
            "track":       track_name,
            "year":        year,
            "round":       round_number,
            "predictions": df[[
                "driver", "team", "predicted_position",
                "grid_pos", "predicted_delta"
            ]].to_dict(orient="records")
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/next-race")
def get_next_race():
    try:
        now = datetime.now(timezone.utc)
        upcoming = [
            r for r in CALENDAR_2026
            if datetime.fromisoformat(r["date"]).replace(tzinfo=timezone.utc) > now
        ]
        next_race    = upcoming[0] if upcoming else CALENDAR_2026[-1]
        round_number = next_race["round"]
        race_name    = next_race["name"]

        # If race already happened just use predict_race
        results_df = pd.read_sql(f"""
            SELECT driver FROM race_results
            WHERE year = 2026 AND round = {round_number} AND grid_pos > 0
        """, engine)
        if not results_df.empty:
            result = predict_race(2026, round_number)
            result["grid_source"] = "race results"
            return result

        # Check for qualifying data
        quali_df = pd.read_sql(f"""
            SELECT driver, quali_position as grid_pos
            FROM qualifying
            WHERE year = 2026 AND round = {round_number}
            ORDER BY quali_position
        """, engine)

        # Get latest driver lineup from most recent completed race
        drivers_df = pd.read_sql("""
            SELECT DISTINCT driver, team FROM race_results
            WHERE year = 2026
            AND round = (SELECT MAX(round) FROM race_results WHERE year = 2026)
        """, engine)

        if drivers_df.empty:
            raise HTTPException(status_code=404, detail="No 2026 data available")

        # Get track_id for this circuit
        track_id_df = pd.read_sql(f"""
            SELECT track_id FROM features
            WHERE track = '{race_name}'
            LIMIT 1
        """, engine)
        track_id = int(track_id_df.iloc[0]["track_id"]) if not track_id_df.empty else 0

        grid_source = "qualifying" if not quali_df.empty else "estimated from recent form"

        rows = []
        for _, driver_row in drivers_df.iterrows():
            driver = driver_row["driver"]
            team   = driver_row["team"]

            h = get_driver_history(driver, 2026, round_number)
            if h is None:
                continue

            # Use qualifying position if available
            if not quali_df.empty and driver in quali_df["driver"].values:
                grid = float(quali_df[quali_df["driver"] == driver]["grid_pos"].iloc[0])
            else:
                grid = float(h["avg_finish_last_3"]) if pd.notna(h.get("avg_finish_last_3")) else 10.0

            rows.append(build_driver_row(driver, team, race_name, track_id, grid, h))

        if not rows:
            raise HTTPException(status_code=404, detail="Could not build prediction")

        df = pd.DataFrame(rows)
        df = run_model(df)

        return {
            "track":       race_name,
            "year":        2026,
            "round":       round_number,
            "grid_source": grid_source,
            "predictions": df[[
                "driver", "team", "predicted_position",
                "grid_pos", "predicted_delta"
            ]].to_dict(orient="records")
        }

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/save-prediction/{year}/{round_number}")
def save_prediction(year: int, round_number: int):
    try:
        # Try predict_race first (works for completed races)
        # Fall back to next-race logic for upcoming races
        try:
            prediction = predict_race(year, round_number)
        except HTTPException as e:
            if e.status_code == 404:
                # Race hasn't happened yet — use next-race prediction
                prediction = get_next_race()
            else:
                raise

        rows = []
        for p in prediction["predictions"]:
            rows.append({
                "year":               year,
                "round":              round_number,
                "track":              prediction["track"],
                "driver":             p["driver"],
                "team":               p["team"],
                "predicted_position": p["predicted_position"],
                "grid_pos":           p["grid_pos"],
                "predicted_delta":    p["predicted_delta"],
                "saved_at":           datetime.now(timezone.utc).isoformat()
            })

        pd.DataFrame(rows).to_sql(
            "predictions_archive", engine,
            if_exists="append", index=False
        )
        return {"saved": len(rows), "track": prediction["track"]}

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/archive/{year}/{round_number}")
def get_archive(year: int, round_number: int):
    try:
        pred_df = pd.read_sql(f"""
            SELECT driver, team, predicted_position, grid_pos, predicted_delta
            FROM predictions_archive
            WHERE year = {year} AND round = {round_number}
            ORDER BY predicted_position
        """, engine)

        if pred_df.empty:
            result = predict_race(year, round_number)
            result["has_actual"] = False
            return result

        actual_df = pd.read_sql(f"""
            SELECT driver, final_pos as actual_position, track
            FROM race_results
            WHERE year = {year} AND round = {round_number}
        """, engine)

        merged = pred_df.merge(actual_df, on="driver", how="left")
        merged["actual_position"] = pd.to_numeric(merged["actual_position"], errors="coerce")
        merged["position_error"]  = (merged["predicted_position"] - merged["actual_position"]).abs()
        merged["position_error"]  = merged["position_error"].fillna(-1)
        merged["actual_position"] = merged["actual_position"].fillna(-1)

        track_name = (
            actual_df["track"].iloc[0]
            if not actual_df.empty else f"Round {round_number}"
        )

        return {
            "track":       track_name,
            "year":        year,
            "round":       round_number,
            "has_actual":  not actual_df.empty,
            "predictions": merged.to_dict(orient="records")
        }

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
async def chat(body: dict):
    messages    = body.get("messages", [])
    track_name  = body.get("track", "")
    year        = body.get("year", "")
    predictions = body.get("predictions", [])

    context = load_context()

    # Driver identity lines
    identity_lines = []
    for code, d in context.get("drivers", {}).items():
        name = d.get("name", code)
        note = f" — {d['note']}" if d.get("note") else ""
        identity_lines.append(f"  {code} = {name}{note}")
    driver_str = "\n".join(identity_lines)

    # Prediction lines
    pred_lines = []
    for p in predictions:
        code = p["driver"]
        name = context.get("drivers", {}).get(code, {}).get("name", code)
        pred_lines.append(
            f"  P{p['predicted_position']} {name} ({code}): "
            f"Grid P{p['grid_pos']} → delta {p['predicted_delta']:+.1f}"
        )
    driver_str_predictions = "\n".join(pred_lines)

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
    races_so_far   = season_results.get("races", [])
    standings      = season_results.get("season_standings_after_round_2", {})

    results_str = ""
    for race in races_so_far:
        top5 = ", ".join([
            f"{r['pos']}. {r['name']}" for r in race["result"][:5]
        ])
        results_str += f"\n  {race['name']}: {top5}"

    standings_str = ""
    if standings:
        standings_str = "Current championship standings: " + ", ".join([
            f"{d['pos']}. {d['name']} ({d['points']}pts)"
            for d in standings.get("drivers", [])[:7]
        ])

    # Use live standings if available
    live_standings = context.get("drivers_standings", [])
    if live_standings:
        standings_str = "Current championship standings (live): " + ", ".join([
            f"{d['position']}. {d['name']} ({d['points']}pts, {d['wins']} wins)"
            for d in live_standings[:7]
        ])

    system_message = {
        "role": "user",
        "content": f"""You are an expert F1 race strategist for the 2026 season.

CRITICAL RULES:
- Base ALL explanations on actual 2026 results below — do not speculate about 2025
- Always use full driver names, never abbreviations
- Be concise and data-driven — reference specific numbers when relevant
- Hamilton has a podium in China (P3) — factor this into explanations about him
- Verstappen has charged from difficult grid slots (P6 from P20 in Australia, P6 from P10 in China)

2026 RACE RESULTS SO FAR:{results_str}

{standings_str}

DRIVER IDENTITIES:
{driver_str}

TRACK CONTEXT — {track_name}:
{track_str}

{track_record_str}

REGULATION CONTEXT ({year}):
{reg_note if reg_note else "No regulation notes available"}

PREDICTED GRID FOR {track_name} {year}:
{driver_str_predictions}

You have full context. Answer the user's questions using the data above."""
    }

    if not messages or messages[0].get("content", "")[:30] != system_message["content"][:30]:
        full_messages = [system_message] + messages
    else:
        full_messages = messages

    import requests as req
    response = req.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "phi3:mini",
            "messages": full_messages,
            "stream": False
        },
        timeout=120
    )

    if response.status_code == 200:
        return {"reply": response.json()["message"]["content"]}
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Ollama error: {response.status_code}"
        )