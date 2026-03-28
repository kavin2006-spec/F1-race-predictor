import pandas as pd
import pickle
from sqlalchemy import create_engine
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error
import numpy as np

engine = create_engine(
    "mssql+pyodbc://@MSI\\SQLEXPRESS/F1Database"
    "?driver=ODBC+Driver+17+for+SQL+Server"
    "&trusted_connection=yes"
    "&TrustServerCertificate=yes"
)

def load_features():
    df = pd.read_sql("SELECT * FROM features", engine)
    return df

def train(df):
    feature_cols = [
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
        # dnf_rate and reg_era removed — zero importance, adding noise
    ]

    target_col = "position_delta"

    X = df[feature_cols].fillna(-1)
    y = df[target_col]

    # Weight recent races more heavily than older ones
    # A 2025 race is more relevant to predicting 2026 than a 2022 race
    # We assign a weight multiplier based on year
    year_weights = df["year"].map({
        2022: 1.0,
        2023: 1.5,
        2024: 2.0,
        2025: 3.0
    }).fillna(1.0)

    X_train, X_test, y_train, y_test, w_train, w_test = train_test_split(
        X, y, year_weights, test_size=0.2, random_state=42
    )

    # --- Model 1: Tuned Random Forest ---
    rf = RandomForestRegressor(
        n_estimators=500,      # more trees = more stable
        max_depth=8,           # shallower than before to reduce overfitting
        min_samples_leaf=5,    # each leaf needs at least 5 samples
        max_features=0.7,      # use 70% of features per split — adds diversity
        random_state=42
    )
    rf.fit(X_train, y_train, sample_weight=w_train)
    rf_preds = rf.predict(X_test)
    rf_mae = mean_absolute_error(y_test, rf_preds)

    # --- Model 2: Gradient Boosting (sklearn's built-in XGBoost equivalent) ---
    # Builds trees sequentially, each one correcting the previous one's errors
    # Often outperforms Random Forest on tabular data like this
    gb = GradientBoostingRegressor(
        n_estimators=300,
        max_depth=4,           # shallower trees work better for boosting
        learning_rate=0.05,    # slow learning rate = more robust generalisation
        min_samples_leaf=5,
        subsample=0.8,         # use 80% of data per tree — reduces overfitting
        random_state=42
    )
    gb.fit(X_train, y_train, sample_weight=w_train)
    gb_preds = gb.predict(X_test)
    gb_mae = mean_absolute_error(y_test, gb_preds)

    print(f"Trained on {len(X_train)} samples, tested on {len(X_test)}")
    print(f"\nRandom Forest MAE:        {rf_mae:.2f} positions")
    print(f"Gradient Boosting MAE:    {gb_mae:.2f} positions")

    # Pick the better model
    if gb_mae < rf_mae:
        print("\nGradient Boosting wins — saving that model")
        best_model = gb
        best_preds = gb_preds
        best_name  = "Gradient Boosting"
        importances = gb.feature_importances_
    else:
        print("\nRandom Forest wins — saving that model")
        best_model = rf
        best_preds = rf_preds
        best_name  = "Random Forest"
        importances = rf.feature_importances_

    print(f"\nFinal MAE: {mean_absolute_error(y_test, best_preds):.2f} positions")

    print(f"\nFeature importance ({best_name}):")
    for feat, imp in sorted(
        zip(feature_cols, importances),
        key=lambda x: x[1],
        reverse=True
    ):
        bar = "█" * int(imp * 40)
        print(f"  {feat:<30} {bar} {imp:.3f}")
    evaluate_predictions(y_test, best_preds, X_test)

    return best_model

def evaluate_predictions(y_test, preds, df_test):
    """
    Beyond MAE — show metrics that actually mean something to F1 fans
    """
    results = pd.DataFrame({
        "actual_delta":    y_test.values,
        "predicted_delta": preds
    })

    # How often did we predict the right direction (gain vs lose positions)
    results["correct_direction"] = (
        (results["actual_delta"] > 0) == (results["predicted_delta"] > 0)
    )
    direction_acc = results["correct_direction"].mean() * 100

    # How often was predicted position within 3 places of actual
    results["within_3"] = abs(
        results["actual_delta"] - results["predicted_delta"]
    ) <= 3

    within_3_acc = results["within_3"].mean() * 100

    print(f"\nBeyond MAE:")
    print(f"  Correct direction (gain vs lose): {direction_acc:.1f}%")
    print(f"  Prediction within 3 positions:    {within_3_acc:.1f}%")
    

def save_model(model):
    import os
    os.makedirs("models", exist_ok=True)
    with open("models/f1_model.pkl", "wb") as f:
        pickle.dump(model, f)
    print("\nModel saved to models/f1_model.pkl")

if __name__ == "__main__":
    df = load_features()
    print(f"Loaded {len(df)} rows from features table")
    model = train(df)
    save_model(model)

