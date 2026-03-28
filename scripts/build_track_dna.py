import pandas as pd
from sqlalchemy import create_engine

# We use local SQL Server to build this — it has all our race data
source_engine = create_engine(
 "mssql+pyodbc://@MSI\\SQLEXPRESS/F1Database?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes")


supabase_engine = create_engine(
    "postgresql://postgres.wvwcylvveasvgakzhppy:F2CP2Wb$Kcfv2Ds@aws-1-eu-central-1.pooler.supabase.com:5432/postgres",
    connect_args={"sslmode": "require"}
)

def build_track_dna():
    """
    Build a track_dna table that captures each driver's historical
    performance at each circuit, weighted by recency.
    Uses all available race data — the further back the race,
    the less weight it carries. This gives us Hamilton's Suzuka
    dominance without letting 2015 results distort 2026 predictions.
    """
    df = pd.read_sql("""
        SELECT driver, track, year, final_pos, grid_pos, status
        FROM race_results
        WHERE grid_pos > 0
        AND status IN ('Finished', 'Lapped', '+1 Lap', '+2 Laps', '')
        ORDER BY driver, track, year
    """, source_engine)

    df["final_pos"] = pd.to_numeric(df["final_pos"], errors="coerce")
    df = df.dropna(subset=["final_pos"])

    # Recency weight — more recent years count more
    # 2026 = weight 4.0, 2025 = 3.0, 2024 = 2.0, 2023 = 1.5, older = 1.0
    weight_map = {2026: 4.0, 2025: 3.0, 2024: 2.0, 2023: 1.5}
    df["weight"] = df["year"].map(weight_map).fillna(1.0)

    # Weighted average finish per driver per track
    def weighted_avg(group):
        return (group["final_pos"] * group["weight"]).sum() / group["weight"].sum()

    track_dna = (
        df.groupby(["driver", "track"])
        .apply(weighted_avg, include_groups=False)
        .reset_index()
    )
    track_dna.columns = ["driver", "track", "weighted_avg_finish"]

    # Also calculate number of races at this track (more races = more reliable)
    race_counts = (
        df.groupby(["driver", "track"])
        .size()
        .reset_index(name="races_at_track")
    )

    # Best finish ever at this track
    best_finish = (
        df.groupby(["driver", "track"])["final_pos"]
        .min()
        .reset_index(name="best_finish_ever")
    )

    # Win rate at this track
    wins = (
        df[df["final_pos"] == 1]
        .groupby(["driver", "track"])
        .size()
        .reset_index(name="wins_at_track")
    )

    # Merge everything together
    result = track_dna.merge(race_counts, on=["driver", "track"])
    result = result.merge(best_finish, on=["driver", "track"])
    result = result.merge(wins, on=["driver", "track"], how="left")
    result["wins_at_track"] = result["wins_at_track"].fillna(0).astype(int)

    result["weighted_avg_finish"] = result["weighted_avg_finish"].round(2)

    # --- NEW: add track-level safety car stats ---
    sc_df = pd.read_sql("SELECT * FROM race_sc_data", source_engine)

    track_sc = (
        sc_df.groupby("track")["sc_laps_pct"]
        .mean()
        .reset_index()
        .rename(columns={"sc_laps_pct": "avg_sc_laps_pct"})
    )
    track_sc["avg_sc_laps_pct"] = track_sc["avg_sc_laps_pct"].round(4)

    # Merge into track_dna result
    result = result.merge(track_sc, on="track", how="left")
    # 0.15 = rough average across all circuits as default
    result["avg_sc_laps_pct"] = result["avg_sc_laps_pct"].fillna(0.15)

    print(result.head(20).to_string())
    print(f"\nBuilt track DNA for {len(result)} driver-track combinations")

    # Save to both databases
    result.to_sql("track_dna", source_engine, if_exists="replace", index=False)
    result.to_sql("track_dna", supabase_engine, if_exists="replace", index=False)
    print("Saved to both SQL Server and Supabase")

    return result


if __name__ == "__main__":
    build_track_dna()