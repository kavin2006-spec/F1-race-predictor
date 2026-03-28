import fastf1
import pandas as pd
from sqlalchemy import create_engine

fastf1.Cache.enable_cache("cache/")

engine = create_engine(
    "mssql+pyodbc://@MSI\\SQLEXPRESS/F1Database"
    "?driver=ODBC+Driver+17+for+SQL+Server"
    "&trusted_connection=yes"
    "&TrustServerCertificate=yes"
)

# Full calendar sizes per year
RACES_TO_PATCH = (
    [(2022, i) for i in range(1, 23)] +
    [(2023, i) for i in range(1, 23)] +
    [(2024, i) for i in range(1, 25)] +
    [(2025, i) for i in range(1, 25)]
)

def get_quali_data(year, round_number):
    try:
        session = fastf1.get_session(year, round_number, "Q")
        session.load(telemetry=False, weather=False, messages=False)

        results = session.results
        if results is None or results.empty:
            return None

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
            driver_time = None
            for q_col in ["Q3", "Q2", "Q1"]:
                if q_col in results.columns:
                    t = driver.get(q_col)
                    if pd.notna(t):
                        driver_time = t.total_seconds()
                        break

            if driver_time is None:
                continue

            # Percentage gap to pole rather than raw milliseconds
            # because circuit length and speed vary hugely —
            # 0.3s at Monaco (slow) vs 0.3s at Monza (fast) are
            # completely different levels of competitiveness
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
            grid   = driver["GridPosition"]
            finish = driver["Position"]

            status = str(driver["Status"]).strip()
            is_finish = (
                status == "Finished" or
                (status.startswith("+") and "Lap" in status)
            )
            if not is_finish:
                continue

            rows.append({
                "year":         year,
                "round":        round_number,
                "driver":       driver["Abbreviation"],
                "sprint_pos":   finish,
                "sprint_delta": grid - finish,
            })

        return pd.DataFrame(rows) if rows else None

    except Exception:
        return None


def get_existing_rounds(table, year):
    """Check which rounds we already have for a given year and table"""
    try:
        result = pd.read_sql(
            f"SELECT DISTINCT round FROM {table} WHERE year = {year}",
            engine
        )
        return set(result["round"].tolist())
    except Exception:
        return set()


def patch():
    all_quali  = []
    all_sprint = []

    for year, round_num in RACES_TO_PATCH:

        existing_quali  = get_existing_rounds("qualifying", year)
        existing_sprint = get_existing_rounds("sprint_results", year)

        if round_num not in existing_quali:
            quali_df = get_quali_data(year, round_num)
            if quali_df is None:
                quali_df = get_quali_data_v2(year, round_num)
            if quali_df is not None:
                all_quali.append(quali_df)
                print(f"  Quali fetched {year} round {round_num} "
                      f"— {len(quali_df)} drivers")

        if round_num not in existing_sprint:
            sprint_df = get_sprint_data(year, round_num)
            if sprint_df is not None:
                all_sprint.append(sprint_df)
                print(f"  Sprint fetched {year} round {round_num} "
                      f"— {len(sprint_df)} drivers")

    if all_quali:
        quali_combined = pd.concat(all_quali, ignore_index=True)
        quali_combined.to_sql(
            "qualifying", engine, if_exists="append", index=False
        )
        print(f"\nAdded {len(quali_combined)} new qualifying rows")
    else:
        print("\nNo new qualifying data to add")

    if all_sprint:
        sprint_combined = pd.concat(all_sprint, ignore_index=True)
        sprint_combined.to_sql(
            "sprint_results", engine, if_exists="append", index=False
        )
        print(f"Added {len(sprint_combined)} new sprint rows")
    else:
        print("\nNo new sprint data to add")

    print("\nPatch complete.")

def get_quali_data_v2(year, round_number):
    """Alternative quali loader — tries session by name instead of code"""
    try:
        event = fastf1.get_event(year, round_number)
        
        # Try loading by full session name rather than code
        session = event.get_session("Qualifying")
        session.load(telemetry=False, weather=False, messages=False)

        results = session.results
        if results is None or results.empty:
            return None

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
            driver_time = None
            for q_col in ["Q3", "Q2", "Q1"]:
                if q_col in results.columns:
                    t = driver.get(q_col)
                    if pd.notna(t):
                        driver_time = t.total_seconds()
                        break

            if driver_time is None:
                continue

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
        print(f"  v2 also failed {year} round {round_number}: {e}")
        return None

if __name__ == "__main__":
    patch()