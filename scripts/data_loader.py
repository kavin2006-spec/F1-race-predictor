import fastf1
import pandas as pd
import os
from sqlalchemy import create_engine


fastf1.Cache.enable_cache("cache/")


engine = create_engine(
    "mssql+pyodbc://@MSI\\SQLEXPRESS/F1Database"
    "?driver=ODBC+Driver+17+for+SQL+Server"
    "&trusted_connection=yes"
    "&TrustServerCertificate=yes"
)


RACES = (
    [(2022, i) for i in range(1, 23)] +
    [(2023, i) for i in range(1, 23)] +
    [(2024, i) for i in range(1, 25)] +
    [(2025, i) for i in range(1, 25)] +
    [(2026, i) for i in range(1, 5)]
)


def get_race_data(year, round_number):
    try:
        session = fastf1.get_session(year, round_number, "R")
        session.load(telemetry=False, weather=False, messages=False)

        results = session.results
        if results is None or results.empty:
            return None

        rows = []
        for _, driver in results.iterrows():
            rows.append({
                "year":      year,
                "round":     round_number,
                "track":     session.event["EventName"],
                "driver":    driver["Abbreviation"],
                "team":      driver["TeamName"],
                "grid_pos":  driver["GridPosition"],
                "final_pos": driver["Position"],
                "status":    driver["Status"],
            })

        return pd.DataFrame(rows)

    except Exception as e:
        print(f"  Skipping race {year} round {round_number}: {e}")
        return None


def get_weather_and_tyre_data(year, round_number):
    try:
        session = fastf1.get_session(year, round_number, "R")
        session.load(telemetry=False, weather=True, messages=False)

        laps = session.laps

        # --- is_wet_race ---
        # 1 if any driver used INT or WET compound during the race
        wet_compounds = {"INTERMEDIATE", "WET"}
        is_wet = int(
            laps["Compound"].str.upper().isin(wet_compounds).any()
        )

        # --- start compound per driver ---
        # First lap compound for each driver
        first_laps = (
            laps.sort_values("LapNumber")
            .groupby("Driver")
            .first()
            .reset_index()[["Driver", "Compound"]]
        )
        first_laps.columns = ["driver", "start_compound"]

        # Ordinal encoding
        compound_map = {
            "HARD": 1, "MEDIUM": 2, "SOFT": 3,
            "INTERMEDIATE": 4, "WET": 5
        }
        first_laps["start_compound_encoded"] = (
            first_laps["start_compound"]
            .str.upper()
            .map(compound_map)
            .fillna(2)  # default MEDIUM if unknown
            .astype(int)
        )

        first_laps["year"]     = year
        first_laps["round"]    = round_number
        first_laps["is_wet"]   = is_wet

        return first_laps[["year","round","driver",
                            "start_compound_encoded","is_wet"]]

    except Exception as e:
        print(f"  Skipping weather/tyre {year} round {round_number}: {e}")
        return None


def get_quali_data(year, round_number):
    try:
        session = fastf1.get_session(year, round_number, "Q")
        session.load(telemetry=False, weather=True, messages=False)

        results = session.results
        if results is None or results.empty:
            return None

        # Find the pole position time (fastest Q3 or best available time)
        # We use Q3 first, then fall back to Q2, then Q1
        # because not all drivers make it to Q3
        pole_time = None
        for q_col in ["Q3", "Q2", "Q1"]:
            if q_col in results.columns:
                valid_times = results[q_col].dropna()
                if not valid_times.empty:
                    pole_time = valid_times.min().total_seconds()
                    break

        if pole_time is None or pole_time == 0:
            return None

        rows = []
        for _, driver in results.iterrows():

            # Get this driver's best qualifying time using same Q3 > Q2 > Q1 fallback
            driver_time = None
            for q_col in ["Q3", "Q2", "Q1"]:
                if q_col in results.columns:
                    t = driver.get(q_col)
                    if pd.notna(t):
                        driver_time = t.total_seconds()
                        break

            if driver_time is None:
                # Driver didn't set a time (DNQ, penalty etc.) — skip
                continue

            # quali_gap_pct = percentage slower than pole
            # We use percentage rather than raw milliseconds because
            # a 0.3s gap at Monaco (slow circuit, ~75s lap) is very different
            # from a 0.3s gap at Monza (fast circuit, ~80s lap but much higher
            # speed sensitivity). As a percentage, the gap normalises across
            # all circuits and becomes a true measure of relative pace.
            quali_gap_pct = ((driver_time - pole_time) / pole_time) * 100

            rows.append({
                "year":           year,
                "round":          round_number,
                "driver":         driver["Abbreviation"],
                "quali_position": driver["Position"],
                "quali_gap_pct":  round(quali_gap_pct, 4),
            })

        return pd.DataFrame(rows)

    except Exception as e:
        print(f"  Skipping quali {year} round {round_number}: {e}")
        return None


def get_sprint_data(year, round_number):
    try:
        session = fastf1.get_session(year, round_number, "S")
        session.load(telemetry=False, weather=False, messages=False)

        results = session.results
        if results is None or results.empty:
            return None

        rows = []
        for _, driver in results.iterrows():
            grid  = driver["GridPosition"]
            finish = driver["Position"]

            # Only include classified sprint finishes
            status = str(driver["Status"]).strip()
            is_finish = (
                status == "Finished" or
                (status.startswith("+") and "Lap" in status)
            )
            if not is_finish:
                continue

            rows.append({
                "year":          year,
                "round":         round_number,
                "driver":        driver["Abbreviation"],
                "sprint_pos":    finish,
                # Positions gained in sprint — same logic as main race delta
                # Positive = moved forward, negative = dropped back
                "sprint_delta":  grid - finish,
            })

        if not rows:
            return None

        return pd.DataFrame(rows)

    except Exception as e:
        # Most rounds have no sprint — this is expected, not an error
        # so we silently return None rather than printing a warning
        return None


def get_safety_car_data(year, round_number):
    try:
        session = fastf1.get_session(year, round_number, "R")
        session.load(telemetry=False, weather=False, messages=False)

        laps = session.laps

        # TrackStatus codes:
        # 1=green, 2=yellow, 4=SC, 5=red flag, 6=VSC, 7=VSC ending
        total_laps = laps["LapNumber"].max()

        # Count laps where any driver was under SC or VSC
        sc_laps = laps[
            laps["TrackStatus"].isin(["4", "6", "7", 4, 6, 7])
        ]["LapNumber"].nunique()

        sc_pct = round(sc_laps / total_laps, 4) if total_laps > 0 else 0.0

        track = session.event["EventName"]

        return pd.DataFrame([{
            "year":       year,
            "round":      round_number,
            "track":      track,
            "sc_laps":    sc_laps,
            "total_laps": total_laps,
            "sc_laps_pct": sc_pct
        }])

    except Exception as e:
        print(f"  Skipping SC data {year} round {round_number}: {e}")
        return None


def build_championship_standings(engine):
    """
    Build pre-race championship standings for every driver at every round.
    Uses only points from rounds BEFORE the current one — no leakage.
    """
    df = pd.read_sql("SELECT * FROM race_results ORDER BY year, round", engine)

    # Points system — 25,18,15,12,10,8,6,4,2,1 for P1-P10
    points_map = {
        1:25, 2:18, 3:15, 4:12, 5:10,
        6:8,  7:6,  8:4,  9:2,  10:1
    }

    df["final_pos"] = pd.to_numeric(df["final_pos"], errors="coerce")
    df["points_earned"] = df["final_pos"].map(points_map).fillna(0)

    rows = []
    for year in df["year"].unique():
        yr_df = df[df["year"] == year].copy()
        rounds = sorted(yr_df["round"].unique())

        for round_num in rounds:
            # Points accumulated BEFORE this round only
            pre_race = yr_df[yr_df["round"] < round_num]

            if pre_race.empty:
                # Round 1 — everyone starts at 0
                drivers = yr_df[yr_df["round"] == round_num]["driver"].unique()
                for i, d in enumerate(drivers):
                    rows.append({
                        "year": year, "round": round_num,
                        "driver": d,
                        "championship_points_pre_race": 0,
                        "championship_rank_pre_race": i + 1,
                        "points_gap_to_leader": 0,
                        "is_title_contender": 0
                    })
                continue

            standings = (
                pre_race.groupby("driver")["points_earned"]
                .sum()
                .reset_index()
                .sort_values("points_earned", ascending=False)
                .reset_index(drop=True)
            )
            standings["rank"] = standings.index + 1
            max_points = standings["points_earned"].max()

            # Title contender = within 50 points of leader
            # or within mathematical chance (rough heuristic)
            remaining_races = len(rounds) - rounds.index(round_num)
            max_available = remaining_races * 25

            for _, row in standings.iterrows():
                gap = max_points - row["points_earned"]
                is_contender = int(gap <= max_available and gap <= 100)
                rows.append({
                    "year":   year,
                    "round":  round_num,
                    "driver": row["driver"],
                    "championship_points_pre_race": row["points_earned"],
                    "championship_rank_pre_race":   row["rank"],
                    "points_gap_to_leader":         gap,
                    "is_title_contender":           is_contender
                })

    result = pd.DataFrame(rows)
    result.to_sql(
        "championship_standings", engine,
        if_exists="replace", index=False
    )
    print(f"Built championship standings: {len(result)} rows")
    return result


def load_all_races():
    all_race    = []
    all_quali   = []
    all_sprint  = []
    all_weather = []
    all_sc_data = []
    
    for year, round_num in RACES:
        print(f"Loading {year} round {round_num}...")

        race_df = get_race_data(year, round_num)
        if race_df is not None:
            all_race.append(race_df)

        quali_df = get_quali_data(year, round_num)
        if quali_df is not None:
            all_quali.append(quali_df)

        # Sprint silently skips if no sprint that weekend
        sprint_df = get_sprint_data(year, round_num)
        if sprint_df is not None:
            all_sprint.append(sprint_df)

        # Weather / tyre data
        weather_df = get_weather_and_tyre_data(year, round_num)
        if weather_df is not None:
            all_weather.append(weather_df)

        #Safety car data
        sc_df = get_safety_car_data(year, round_num)
        if sc_df is not None:
            all_sc_data.append(sc_df)

    # Save race results
    race_combined = pd.concat(all_race, ignore_index=True)
    race_combined.to_sql(
        "race_results", engine, if_exists="replace", index=False
    )
    print(f"\nSaved {len(race_combined)} rows to race_results")

    # Save qualifying data
    if all_quali:
        quali_combined = pd.concat(all_quali, ignore_index=True)
        quali_combined.to_sql(
            "qualifying", engine, if_exists="replace", index=False
        )
        print(f"Saved {len(quali_combined)} rows to qualifying")

    # Save sprint data
    if all_sprint:
        sprint_combined = pd.concat(all_sprint, ignore_index=True)
        sprint_combined.to_sql(
            "sprint_results", engine, if_exists="replace", index=False
        )
        print(f"Saved {len(sprint_combined)} rows to sprint_results")

    if all_weather:
        weather_combined = pd.concat(all_weather, ignore_index=True)
        weather_combined.to_sql(
            "race_weather", engine, if_exists="replace", index=False
        )
        print(f"Saved {len(weather_combined)} rows to race_weather")

    if all_sc_data:
        sc_combined = pd.concat(all_sc_data, ignore_index=True)
        sc_combined.to_sql("race_sc_data", engine, if_exists="replace", index=False)
        print(f"Saved {len(sc_combined)} rows to race_sc_data")

    return race_combined


    if all_weather:
       weather_combined = pd.concat(all_weather, ignore_index=True)
       weather_combined.to_sql(
        "race_weather", engine, if_exists="replace", index=False
       )
       print(f"Saved {len(weather_combined)} rows to race_weather")


if __name__ == "__main__":
    race_combined = load_all_races()
    
    # Build championship standings after race_results is created
    print("\nBuilding championship standings...")
    build_championship_standings(engine)