"""ETL: Open-Meteo Air Quality API -> pandas -> Pydantic -> Supabase PostgreSQL.

Run:  python etl.py            (loads to Supabase if DATABASE_URL is set, else SQLite)
"""
import logging
import sqlite3
import time
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd
import requests
from pydantic import BaseModel, Field, ValidationError, field_validator

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("etl")


# ------------------------------------------------------------------ EXTRACT
def _get(params: dict, retries: int = 5) -> dict:
    """GET with exponential backoff (Open-Meteo returns 429 when rate limited)."""
    for attempt in range(retries):
        r = requests.get(config.API_URL, params=params, timeout=90)
        if r.status_code == 429 or r.status_code >= 500:
            wait = 2 ** attempt * 5
            log.warning("HTTP %s, retrying in %ss", r.status_code, wait)
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("Open-Meteo request failed after retries")


def date_chunks(start: date, end: date, days: int = 180):
    cur = start
    while cur <= end:
        nxt = min(cur + timedelta(days=days - 1), end)
        yield cur, nxt
        cur = nxt + timedelta(days=1)


def extract_city(city: str, lat: float, lon: float) -> dict:
    """Pull the full date range for one city, in chunks, and merge into one payload."""
    merged, meta = None, {}
    for s, e in date_chunks(config.START_DATE, config.END_DATE):
        payload = _get({
            "latitude": lat, "longitude": lon,
            "hourly": ",".join(config.VARIABLES.keys()),
            "start_date": s.isoformat(), "end_date": e.isoformat(),
            "timezone": config.TIMEZONE,
        })
        meta = {"latitude": payload["latitude"], "longitude": payload["longitude"]}
        if merged is None:
            merged = {k: list(v) for k, v in payload["hourly"].items()}
        else:
            for k, v in payload["hourly"].items():
                merged[k].extend(v)
        time.sleep(0.5)  # be polite to the free API
    log.info("Extracted %s (%d hours)", city, len(merged["time"]))
    return {**meta, "hourly": merged}


def extract_all() -> dict:
    return {c: extract_city(c, *xy) for c, xy in config.CITIES.items()}


# ---------------------------------------------------------------- TRANSFORM
def transform(raw: dict) -> pd.DataFrame:
    frames = []
    for city, payload in raw.items():
        df = pd.DataFrame(payload["hourly"]).rename(
            columns={"time": "timestamp", **config.VARIABLES})
        df["city"] = city
        df["latitude"] = payload["latitude"]
        df["longitude"] = payload["longitude"]
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    for col in config.VALUE_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["timestamp"])
    df = df.drop_duplicates(subset=["city", "timestamp"]).sort_values(["city", "timestamp"])
    df = df.dropna(subset=config.VALUE_COLS, how="all")  # rows with no data at all
    return df.reset_index(drop=True)


# ----------------------------------------------------------------- VALIDATE
class AirQualityRecord(BaseModel):
    city: str = Field(min_length=2)
    timestamp: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    pm2_5: Optional[float] = Field(default=None, ge=0, le=2000)
    pm10: Optional[float] = Field(default=None, ge=0, le=3000)
    co: Optional[float] = Field(default=None, ge=0, le=100000)
    no2: Optional[float] = Field(default=None, ge=0, le=2000)
    so2: Optional[float] = Field(default=None, ge=0, le=2000)
    o3: Optional[float] = Field(default=None, ge=0, le=1000)
    co2: Optional[float] = Field(default=None, ge=250, le=1000)      # ppm
    ch4: Optional[float] = Field(default=None, ge=0, le=5000)
    dust: Optional[float] = Field(default=None, ge=0, le=5000)
    aod: Optional[float] = Field(default=None, ge=0, le=10)
    us_aqi: Optional[float] = Field(default=None, ge=0, le=500)
    european_aqi: Optional[float] = Field(default=None, ge=0, le=500)

    @field_validator("city")
    @classmethod
    def known_city(cls, v: str) -> str:
        if v not in config.CITIES:
            raise ValueError(f"unknown city {v}")
        return v


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (valid_df, rejected_df). Rejected rows carry the error message."""
    good, bad = [], []
    records = df.astype(object).where(df.notna(), None).to_dict("records")
    for rec in records:
        try:
            good.append(AirQualityRecord(**rec).model_dump())
        except ValidationError as e:
            bad.append({**rec, "error": e.errors()[0]["msg"]})
    valid_df, rejected_df = pd.DataFrame(good), pd.DataFrame(bad)
    log.info("Validation: %d valid, %d rejected", len(valid_df), len(rejected_df))
    return valid_df, rejected_df


# --------------------------------------------------------------------- LOAD
COLS = ["city", "timestamp", "latitude", "longitude"] + config.VALUE_COLS

SCHEMA_SQL = (
    f"CREATE TABLE IF NOT EXISTS {config.TABLE_NAME} (\n"
    "    city TEXT NOT NULL,\n    timestamp TIMESTAMP NOT NULL,\n"
    "    latitude DOUBLE PRECISION,\n    longitude DOUBLE PRECISION,\n"
    + "".join(f"    {c} DOUBLE PRECISION,\n" for c in config.VALUE_COLS)
    + "    PRIMARY KEY (city, timestamp)\n);"
)


def load_postgres(df: pd.DataFrame, url: str) -> None:
    import psycopg2
    from psycopg2.extras import execute_values

    rows = [tuple(None if pd.isna(v) else v for v in r) for r in df[COLS].itertuples(index=False)]
    updates = ", ".join(f"{c}=EXCLUDED.{c}" for c in COLS[2:])
    sql = (f"INSERT INTO {config.TABLE_NAME} ({', '.join(COLS)}) VALUES %s "
           f"ON CONFLICT (city, timestamp) DO UPDATE SET {updates}")
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)
        execute_values(cur, sql, rows, page_size=1000)
    log.info("Loaded %d rows into Supabase PostgreSQL (upsert)", len(rows))


def load_sqlite(df: pd.DataFrame) -> None:
    path = config.DATA_DIR / "air_quality.db"
    with sqlite3.connect(path) as conn:
        df[COLS].assign(timestamp=df["timestamp"].astype(str)).to_sql(
            config.TABLE_NAME, conn, if_exists="replace", index=False)
    log.info("DATABASE_URL not set -> loaded %d rows into %s", len(df), path)


def load(df: pd.DataFrame) -> None:
    df.to_csv(config.DATA_DIR / "clean_air_quality.csv", index=False)
    if config.DATABASE_URL:
        load_postgres(df, config.DATABASE_URL)
    else:
        load_sqlite(df)


# --------------------------------------------------------------------- MAIN
def main(raw: Optional[dict] = None) -> pd.DataFrame:
    raw = raw or extract_all()
    df = transform(raw)
    valid, rejected = validate(df)
    if not rejected.empty:
        rejected.to_csv(config.DATA_DIR / "rejected_rows.csv", index=False)
    load(valid)
    return valid


if __name__ == "__main__":
    main()
