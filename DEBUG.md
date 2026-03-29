# Debugging guide

Common issues I've encountered during development and how to fix them.

---

## Database

### `TOP 1` syntax error on Supabase
**Error:** `psycopg2.errors.SyntaxError: syntax error at or near "1" LINE 2: SELECT TOP 1`

**Cause:** `TOP 1` is SQL Server syntax. Supabase uses PostgreSQL which uses `LIMIT 1`.

**Fix:** Replace all `SELECT TOP 1` with `SELECT ... LIMIT 1` in any query running against Supabase.

---

### `column does not exist` on Supabase after adding new features
**Error:** `psycopg2.errors.UndefinedColumn: column "f.is_wet" does not exist`

**Cause:** New columns were added to `feature_engineering.py` and the model was retrained locally, but `migrate_to_supabase.py` was not rerun so Supabase still has the old schema.

**Fix:**
```bash
python scripts/feature_engineering.py
python scripts/migrate_to_supabase.py
```

---

### `Expected string or URL object, got None`
**Error:** `sqlalchemy.exc.ArgumentError: Expected string or URL object, got None`

**Cause:** `DATABASE_URL` environment variable is not set. Usually means `.env` file is missing or `load_dotenv()` was not called.

**Fix:** Make sure `.env` exists in the root `F1/` folder with:
```
DATABASE_URL=your_supabase_connection_string
```
And add at the top of the script:
```python
from dotenv import load_dotenv
load_dotenv()
```

---

### RLS warning on Supabase tables
**Error:** `Detects cases where row level security (RLS) has not been enabled`

**Cause:** Tables are publicly readable without authentication.

**Fix:** Run in Supabase SQL editor:
```sql
ALTER TABLE race_results ENABLE ROW LEVEL SECURITY;
CREATE POLICY "allow public read" ON race_results FOR SELECT USING (true);
```
Repeat for each table.

---

## API

### `Feature names must be in the same order as they were in fit`
**Error:** `ValueError: The feature names should match those that were passed during fit.`

**Cause:** `FEATURE_COLS` in `api/main.py` is in a different order than when the model was trained.

**Fix:** Run this to see the exact order the model expects:
```bash
python -c "import pickle; m=pickle.load(open('models/f1_model.pkl','rb')); print(list(m.feature_names_in_))"
```
Then update `FEATURE_COLS` in `api/main.py` to exactly match that output.

---

### `wins_at_track not in index` after adding new features
**Error:** `KeyError: "['wins_at_track'] not in index"`

**Cause:** A new feature was added to `FEATURE_COLS` but the SQL query in the endpoint doesn't select that column, or the `rows.append()` dict doesn't include it.

**Fix:** Every time you add a feature you must update three places in `api/main.py`:
1. The main `features_query` SELECT statement
2. The `history_query` for missing drivers
3. The `rows.append()` dict in both `predict_race` and `get_next_race`

---

### `//next-race` returns 404
**Error:** `{"detail":"Not Found"}` when calling `/next-race`

**Cause:** The `API` variable in `App.js` has a trailing slash — `"http://localhost:8000/"` — which produces a double slash when combined with `/next-race`.

**Fix:** Remove trailing slash:
```jsx
const API = "http://localhost:8000";  // correct
const API = "http://localhost:8000/"; // wrong — causes //next-race
```

---

### `Method Not Allowed` when saving predictions
**Error:** `{"detail":"Method Not Allowed"}` on `/save-prediction`

**Cause:** The endpoint is a POST but you're hitting it via browser URL bar (GET request).

**Fix:** Use PowerShell or curl:
```powershell
Invoke-WebRequest -Method POST -Uri "http://localhost:8000/save-prediction/2026/3" 
If that does not work, try:
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/save-prediction/2026/3"
```
```bash
curl -X POST http://localhost:8000/save-prediction/2026/3
```
Or add a temporary GET version of the endpoint for convenience:
```python
@app.get("/save-prediction-get/{year}/{round_number}")
def save_prediction_get(year: int, round_number: int):
    return save_prediction(year, round_number)
```
Then visit `http://localhost:8000/save-prediction-get/2026/3` in browser.

---

### Duplicate rows in predictions archive
**Cause:** `/save-prediction` was called twice for the same round.

**Fix:** Delete duplicates in Supabase SQL editor:
```sql
DELETE FROM predictions_archive
WHERE year = 2026 AND round = 3
AND id NOT IN (
    SELECT MAX(id)
    FROM predictions_archive
    WHERE year = 2026 AND round = 3
    GROUP BY driver
)
```
The `save_prediction` endpoint now auto-deletes existing rows before saving to prevent this.

---

## Data pipeline

### `Cache directory does not exist`
**Error:** `NotADirectoryError: Cache directory does not exist`

**Cause:** FastF1 cache folder hasn't been created yet.

**Fix:**
```bash
mkdir cache
```

---

### `No data found for 2026 round X`
**Cause:** Either the race hasn't happened yet (features table has no row for that round) or the data hasn't been pulled from FastF1.

**Fix for upcoming races:** The `/next-race` endpoint handles this automatically using recent form as estimated grid positions.

**Fix for completed races:** Run:
```bash
python scripts/data_loader.py
python scripts/feature_engineering.py
python scripts/migrate_to_supabase.py
```

---

### `grid_pos = 0` for all drivers in a round
**Cause:** FastF1 sometimes takes several hours after a race to publish official results including grid positions. The race results (final positions) load first, grid positions come later.

**Fix:** Either wait for FastF1 to update and rerun `data_loader.py`, or manually set grid positions from the qualifying table:
```sql
UPDATE r
SET r.grid_pos = q.quali_position
FROM race_results r
JOIN qualifying q
    ON r.driver = q.driver
    AND r.year = q.year
    AND r.round = q.round
WHERE r.year = 2026 AND r.round = 3
```

---

### Qualifying data missing from local SQL Server
**Cause:** Qualifying was manually entered directly into Supabase via the API endpoint, bypassing local SQL Server.

**Fix:** Run `fetch_quali_jolpica.py` to pull official times from Jolpica API into local SQL Server, then rerun the pipeline.

---

## Git

### `Updates were rejected — remote contains work not available locally`
**Cause:** GitHub created the repo with a LICENSE file that doesn't exist locally.

**Fix:**
```bash
git pull origin main --allow-unrelated-histories
git push
```

### `frontend is a submodule` warning
**Cause:** `create-react-app` initialises its own git repo inside the `frontend/` folder, creating a nested repo.

**Fix:**
```bash
Remove-Item -Recurse -Force "frontend\.git"
git rm --cached frontend
git add frontend/
```

---

## Ollama / chatbot

### `Ollama error: 404`
**Cause:** Wrong model name in `api/main.py`. The model name must exactly match what `ollama list` shows.

**Fix:** Run `ollama list` and copy the exact name into the model field:
```python
"model": "mistral:latest",  # must match ollama list output exactly
```

### `Ollama error: 500`
**Cause:** Model is too large for available RAM, causing Ollama to crash mid-generation.

**Fix:** Switch to a smaller model. Mistral (4.4GB) is more reliable than larger models on most consumer hardware:
```bash
ollama pull mistral
```

### Chatbot not responding after idle
**Cause:** Ollama needs to be running. The desktop app being open does not mean the server is running.

**Fix:**
```bash
ollama serve
```
If you get `bind: Only one usage of each socket address` — Ollama is already running, ignore it.
