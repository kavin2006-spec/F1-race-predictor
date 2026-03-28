# Data pipeline

## Overview

The data pipeline has four stages: collection, storage, migration and enrichment. Each stage is a separate script so any part can be rerun independently.
```
FastF1 API
    ↓
data_loader.py — pulls race results, qualifying, sprint data
    ↓
SQL Server (local) — raw tables: race_results, qualifying, sprint_results
    ↓
build_track_dna.py — builds historical circuit performance table
feature_engineering.py — builds the features table
train_model.py — trains and saves the model
    ↓
migrate_to_supabase.py — pushes all tables to cloud PostgreSQL
    ↓
Supabase — production database read by the API
```

## Tables

### `race_results`
One row per driver per race. Source: FastF1 race session results.

| Column | Type | Description |
|---|---|---|
| year | int | Season year |
| round | int | Round number |
| track | str | Circuit name |
| driver | str | 3-letter driver code |
| team | str | Constructor name |
| grid_pos | float | Starting grid position |
| final_pos | float | Finishing position |
| status | str | Finished / Retired / Accident etc. |

### `qualifying`
One row per driver per race weekend. Source: FastF1 qualifying session or Jolpica API.

| Column | Type | Description |
|---|---|---|
| year | int | Season year |
| round | int | Round number |
| driver | str | 3-letter driver code |
| quali_position | int | Qualifying position |
| quali_gap_pct | float | % gap to pole position |

The gap is expressed as a percentage rather than raw milliseconds because a 0.3s gap means something very different at Monaco (slow circuit) vs Monza (fast circuit). As a percentage it normalises across all circuits.

### `sprint_results`
Only populated for sprint race weekends (~6 per season).

| Column | Type | Description |
|---|---|---|
| year | int | Season year |
| round | int | Round number |
| driver | str | 3-letter driver code |
| sprint_pos | float | Sprint finishing position |
| sprint_delta | float | Positions gained in sprint |

### `track_dna`
One row per driver per circuit across all history. Built by `build_track_dna.py`.

| Column | Type | Description |
|---|---|---|
| driver | str | 3-letter driver code |
| track | str | Circuit name |
| weighted_avg_finish | float | Recency-weighted average finish |
| wins_at_track | int | Career wins at this circuit |
| races_at_track | int | Total races at this circuit |
| avg_sc_laps_pct | float | Average % of laps under safety car |

The `weighted_avg_finish` uses these year weights: 2026=4.0, 2025=3.0, 2024=2.0, 2023=1.5, older=1.0. This means Hamilton's 5 Suzuka wins still factor in but recent seasons dominate.

### `features`
The main training table. One row per driver per race (DNFs excluded). Built by `feature_engineering.py`. See [MODEL.md](MODEL.md) for full column definitions.

### `predictions_archive`
Saves pre-race predictions before each round for post-race comparison.

### `championship_standings`
Pre-race championship points and rank for every driver at every round. Built from `race_results` using only rounds before the current one to prevent data leakage.

## Data sources

**FastF1** — Python library that pulls data from the official F1 timing feed. Used for race results, qualifying, sprint, tyre compounds, weather, and safety car data. Data is cached locally in `cache/` after first download.

**Jolpica API** — Community-maintained replacement for the deprecated Ergast API. Used to fetch official qualifying results quickly after each session. Base URL: `https://api.jolpi.ca/ergast/f1/`

## DNF handling

DNF rows (Retired, Accident, Engine, Collision etc.) are handled carefully:

- DNF finishing positions are excluded from rolling average calculations — a retirement shouldn't count as a bad performance
- DNF rows are dropped entirely from training data — the model predicts race performance not mechanical reliability
- The `is_classified_finish()` function defines a finish as: `Finished`, `Lapped`, blank status, or `+N Laps`

## Migration to Supabase

`migrate_to_supabase.py` copies all tables from local SQL Server to Supabase PostgreSQL. Run after any pipeline update to keep the cloud database in sync with local.

The API reads exclusively from Supabase — local SQL Server is the development database, Supabase is production.
