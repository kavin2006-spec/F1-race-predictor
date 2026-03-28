import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(
    "mssql+pyodbc://@MSI\\SQLEXPRESS/F1Database"
    "?driver=ODBC+Driver+17+for+SQL+Server"
    "&trusted_connection=yes"
    "&TrustServerCertificate=yes"
)


def load_raw():
    races = pd.read_sql(
        "SELECT * FROM race_results ORDER BY year, round", engine
    )
    quali = pd.read_sql(
        "SELECT year, round, driver, quali_position, quali_gap_pct "
        "FROM qualifying", engine
    )
    sprint = pd.read_sql(
        "SELECT year, round, driver, sprint_pos, sprint_delta "
        "FROM sprint_results", engine
    )
    track_dna = pd.read_sql(
        "SELECT driver, track, weighted_avg_finish, wins_at_track, "
        "races_at_track, avg_sc_laps_pct FROM track_dna", engine
    )
    weather = pd.read_sql(
        "SELECT year, round, driver, start_compound_encoded, is_wet "
        "FROM race_weather", engine
    )
    
    # SAFE championship standings - create if missing (FIXED)
    try:
        champ = pd.read_sql(
            "SELECT year, round, driver, championship_rank_pre_race, "
            "points_gap_to_leader, is_title_contender "
            "FROM championship_standings", engine
        )
        print("Loaded championship_standings successfully")
    except Exception as e:
        print(f"championship_standings missing: {e}")
        # Create EMPTY DataFrame with correct structure
        champ = pd.DataFrame(columns=[
            'year', 'round', 'driver', 
            'championship_rank_pre_race', 
            'points_gap_to_leader', 
            'is_title_contender'
        ])
        print("Created empty championship_standings DataFrame")
    
    return races, quali, sprint, track_dna, weather, champ


def is_classified_finish(status):
    """
    Returns True only for classified finishes.
    Anything not Finished or lapped (Retired, Accident, Engine etc.)
    returns False and gets excluded from form calculations.
    """
    if pd.isna(status):
        return False
    status = str(status).strip()
    if status == "Finished":
        return True
    if status == "Lapped":
        return True
    if status == "":
        # Blank status = classified finish in FastF1
        return True
    if status.startswith("+") and "Lap" in status:
        return True
    return False


def build_features(races, quali, sprint, track_dna, weather, champ):

    # --- Basic cleaning ---
    races = races[races["grid_pos"] > 0].copy()
    races["final_pos"] = pd.to_numeric(races["final_pos"], errors="coerce")
    races["grid_pos"]  = pd.to_numeric(races["grid_pos"],  errors="coerce")
    races = races.dropna(subset=["final_pos", "grid_pos"])

    # --- Merge all data sources in order ---
    # Start with races as the base, then left join everything else
    df = races.merge(quali,  on=["year", "round", "driver"], how="left")
    df = df.merge(sprint,    on=["year", "round", "driver"], how="left")
    df = df.merge(weather,   on=["year", "round", "driver"], how="left")
    df = df.merge(champ,     on=["year", "round", "driver"], how="left")
    # Track DNA joins on driver + track (not round) — captures circuit history
    df = df.merge(track_dna, on=["driver", "track"],         how="left")

    # --- Teammate gap features (from quali) ---
    # After merging quali data, compute teammate gap
    df["teammate_quali_gap_pct"] = None

    for (year, round_num, team), group in df.groupby(["year", "round", "team"]):
        if len(group) < 2:
            continue
        drivers = group["driver"].values
        gaps    = group["quali_gap_pct"].values

        for i, driver in enumerate(drivers):
            # Teammate gap = this driver's gap minus their teammate's gap
            # Positive = slower than teammate, Negative = faster
            teammate_gaps = [gaps[j] for j in range(len(drivers)) if j != i]
            if len(teammate_gaps) > 0 and not pd.isna(gaps[i]):
                avg_teammate = sum(teammate_gaps) / len(teammate_gaps)
                df.loc[
                    (df["year"] == year) &
                    (df["round"] == round_num) &
                    (df["driver"] == driver),
                    "teammate_quali_gap_pct"
                ] = gaps[i] - avg_teammate

    # Rolling teammate gap — shift(1) prevents leakage
    df["avg_teammate_quali_gap_last_3"] = (
        df.groupby("driver")["teammate_quali_gap_pct"]
        .transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
    )

    # --- Regulation era flag ---
    # 2022-2025 = era 1 (ground effect regs introduced in 2022)
    # 2026+     = era 2 (new regs)
    df["reg_era"] = df["year"].apply(lambda y: 1 if y <= 2025 else 2)

    # --- Classified finish flag ---
    df["is_finish"] = df["status"].apply(is_classified_finish)

    # For rolling averages, DNFs become NaN so they don't
    # poison a driver's recent form score
    df["final_pos_clean"] = df.apply(
        lambda row: row["final_pos"] if row["is_finish"] else None, axis=1
    )

    # --- Sort chronologically per driver before rolling calculations ---
    df = df.sort_values(["driver", "year", "round"]).reset_index(drop=True)

    # --- Driver rolling form features ---
    # shift(1) ensures we only ever use PAST races, never the current one
    # This prevents data leakage — the model cannot peek at the answer
    df["avg_finish_last_1"] = (
        df.groupby("driver")["final_pos_clean"]
        .transform(lambda x: x.shift(1).rolling(1, min_periods=1).mean())
    )
    df["avg_finish_last_3"] = (
        df.groupby("driver")["final_pos_clean"]
        .transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
    )
    df["avg_finish_last_5"] = (
        df.groupby("driver")["final_pos_clean"]
        .transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
    )

    # --- Team rolling form ---
    df["team_avg_finish_last_3"] = (
        df.groupby("team")["final_pos_clean"]
        .transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
    )

    # --- Target variable ---
    df["position_delta"] = df["grid_pos"] - df["final_pos"]

    # Drop DNF rows from training — we are predicting performance not reliability
    df = df[df["is_finish"] == True].copy()

    # --- Avg positions gained historically ---
    df["avg_positions_gained"] = (
        df.groupby("driver")["position_delta"]
        .transform(lambda x: x.shift(1).rolling(5, min_periods=1).mean())
    )

    # --- Rolling qualifying gap ---
    # Average quali gap to pole over last 3 races
    # We use percentage gap (not ms) because circuit speeds vary hugely —
    # 0.3s at Monaco is nothing, 0.3s at Monza is massive
    df["avg_quali_gap_last_3"] = (
        df.groupby("driver")["quali_gap_pct"]
        .transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
    )

    # --- Sprint features ---
    # sprint_pos and sprint_delta are NaN for non-sprint weekends
    # The model will learn to use these when available and ignore when not
    df["avg_sprint_delta_last_3"] = (
        df.groupby("driver")["sprint_delta"]
        .transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
    )

    # --- Regulation improvement placeholder ---
    # Will be populated once enough 2026 data exists for meaningful comparison
    df["team_reg_improvement"] = None

    # Wet track performance — combines is_wet with track history
    # Captures Hamilton being elite at Silverstone WET specifically
    # not just elite at Silverstone in general
    df["wet_track_performance"] = df["is_wet"] * df["weighted_avg_finish"]

    # --- DNF rate per driver ---
    # Calculated from original races df before filtering
    # Some drivers are genuinely more crash prone — this captures that
    driver_total = races.groupby("driver")["round"].count()
    driver_dnf = races[
        ~races["status"].apply(is_classified_finish)
    ].groupby("driver")["round"].count()
    dnf_rate_map = (driver_dnf / driver_total).fillna(0)
    df["dnf_rate"] = df["driver"].map(dnf_rate_map).fillna(0)

    # --- Track encoding ---
    df["track_id"] = df["track"].astype("category").cat.codes

    # --- Debug output ---
    print(f"Rows before dropna: {len(df)}")
    print(f"2026 rows before dropna: {len(df[df['year'] == 2026])}")
    for col in ["avg_finish_last_1", "avg_finish_last_3",
                "avg_finish_last_5", "team_avg_finish_last_3"]:
        missing_2026 = df[df["year"] == 2026][col].isna().sum()
        print(f"  {col} missing in 2026: {missing_2026}")

    # --- Drop rows with no rolling history at all ---
    # Keep row if at least one rolling average has a value
    df = df[
        df[["avg_finish_last_1", "avg_finish_last_3",
            "avg_finish_last_5"]].notna().any(axis=1)
    ]

    return df


def save_features(df):
    features = df[[
        "year", "round", "track", "track_id",
        "driver", "team", "reg_era",
        "grid_pos",
        "quali_gap_pct",
        "avg_quali_gap_last_3",
        "avg_finish_last_1",
        "avg_finish_last_3",
        "avg_finish_last_5",
        "team_avg_finish_last_3",
        "avg_positions_gained",
        "sprint_pos",
        "sprint_delta",
        "avg_sprint_delta_last_3",
        "team_reg_improvement",
        "dnf_rate",
        "weighted_avg_finish",
        "races_at_track",
        "wins_at_track",
        "is_wet",
        "start_compound_encoded",
        "avg_sc_laps_pct",
        "teammate_quali_gap_pct",
        "avg_teammate_quali_gap_last_3",
        "championship_rank_pre_race",
        "points_gap_to_leader",
        "is_title_contender",
        "position_delta"
    ]]

    features.to_sql("features", engine, if_exists="replace", index=False)
    print(f"Saved {len(features)} rows to features table")

    print("\nFeature completeness check:")
    for col in features.columns:
        missing = features[col].isna().sum()
        pct = (missing / len(features)) * 100
        print(f"  {col:<30} {missing:>4} missing ({pct:.1f}%)")


def summarise_raw(races, quali, sprint):
    print(f"Race results:  {len(races)} rows")
    print(f"Qualifying:    {len(quali)} rows")
    print(f"Sprint:        {len(sprint)} rows")
    print("\nStatus values in race data:")
    print(races["status"].value_counts().to_string())


if __name__ == "__main__":
    races, quali, sprint, track_dna, weather, champ = load_raw()
    summarise_raw(races, quali, sprint)

    df = build_features(races, quali, sprint, track_dna, weather, champ)
    print(f"\nAfter feature engineering: {len(df)} rows")
    save_features(df)