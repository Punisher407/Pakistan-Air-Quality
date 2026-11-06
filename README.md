# Air Quality & Smog Analysis Across Major Cities of Pakistan Using ETL and EDA

Analyzes air pollution and smog patterns in Lahore, Karachi, Islamabad, Rawalpindi, Faisalabad,
Multan, Peshawar, Quetta, Gujranwala and Sialkot using the free Open-Meteo Air Quality API.

## Pipeline
1. **Extract** (`etl.py`): hourly PM2.5, PM10, CO, NO2, SO2, O3, CO2, methane, dust, aerosol optical depth, US AQI and European AQI, from 2023-01-01 to yesterday. Requests are chunked (180 days) with retry/backoff for rate limits.
2. **Transform** (pandas): type coercion, de-duplication, tidy long table, drop rows with no data.
3. **Validate** (Pydantic): required fields, known city, coordinate ranges, plausible non-negative measurement values. Bad rows go to `data/rejected_rows.csv`.
4. **Load**: upsert into Supabase PostgreSQL (`air_quality_hourly`, primary key `city + timestamp`). Falls back to local SQLite if `DATABASE_URL` is not set.
5. **EDA** (`eda.py`): missing/unusual values, distributions, city ranking, hourly pattern, seasonal and monthly trends, correlations -> `charts/` and `web/data.json`.
6. **Web app** (`web/`): interactive dashboard (Chart.js): city selector, hourly/seasonal/monthly charts, city ranking, WHO exceedance, correlation heatmap.

## Run
```bash
pip install -r requirements.txt
export DATABASE_URL="postgresql://postgres:PASSWORD@db.xxxx.supabase.co:5432/postgres"   # optional
python etl.py      # first run takes a few minutes (10 cities x ~4 years)
python eda.py
python -m http.server -d web 8000   # open http://localhost:8000
```
`python mock_test.py` runs the whole pipeline offline on fake data (overwrites outputs; re-run `etl.py` and `eda.py` afterwards).

## Notes
- CO2 and methane are model (CAMS) variables and may be missing for some periods; missing values are kept as NULL and reported in the EDA.
- Seasons: Winter Dec-Feb, Spring Mar-May, Summer Jun-Aug, Autumn Sep-Nov. Smog peaks in Nov-Feb.

## Supabase
Create a project -> Project Settings -> Database -> copy the connection string (URI) into `DATABASE_URL`.
If the direct connection fails (IPv6), use the "Session pooler" string instead.

## Deploy to Vercel
Push to GitHub, import the repo in Vercel, set **Root Directory** to `web`, framework "Other". Commit `web/data.json` after running `eda.py`.
