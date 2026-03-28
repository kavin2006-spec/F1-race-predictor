import requests
import pandas as pd
from sqlalchemy import create_engine

def fetch_qualifying_from_jolpica(year, round_number):
    url = f"https://api.jolpi.ca/ergast/f1/{year}/{round_number}/qualifying.json"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None

    data = response.json()
    races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    if not races:
        return None

    qualifying = races[0].get("QualifyingResults", [])
    if not qualifying:
        return None

    rows = []
    for q in qualifying:
        driver_code = q.get("Driver", {}).get("code")
        position    = q.get("position")
        if not driver_code or not position:
            continue

        times = []
        for session in ["Q1", "Q2", "Q3"]:
            t = q.get(session)
            if not t:
                continue
            try:
                minutes, seconds = t.split(":")
                times.append(float(minutes) * 60 + float(seconds))
            except Exception:
                continue

        if not times:
            continue

        rows.append({
            "driver":        driver_code,
            "quali_position": int(position),
            "best_time_seconds": min(times)
        })

    if not rows:
        return None

    df = pd.DataFrame(rows)
    pole_time = df["best_time_seconds"].min()
    df["quali_gap_pct"] = ((df["best_time_seconds"] - pole_time) / pole_time * 100).round(4)
    df["year"]  = year
    df["round"] = round_number

    return df[["year", "round", "driver", "quali_position", "quali_gap_pct"]]


if __name__ == "__main__":
    YEAR  = 2026
    ROUND = 3

    engine = create_engine(
        "mssql+pyodbc://@MSI\\SQLEXPRESS/F1Database"
        "?driver=ODBC+Driver+17+for+SQL+Server"
        "&trusted_connection=yes"
        "&TrustServerCertificate=yes"
    )

    df = fetch_qualifying_from_jolpica(YEAR, ROUND)

    if df is not None:
        existing = pd.read_sql(
            f"SELECT COUNT(*) as n FROM qualifying WHERE year={YEAR} AND round={ROUND}",
            engine
        )
        if existing["n"].iloc[0] > 0:
            print(f"Already exists — delete first if you want to overwrite:")
            print(f"DELETE FROM qualifying WHERE year={YEAR} AND round={ROUND}")
        else:
            df.to_sql("qualifying", engine, if_exists="append", index=False)
            print(f"Saved {len(df)} rows")
            print(df.to_string())
    else:
        print("No data yet — qualifying may not have happened")