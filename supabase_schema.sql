-- Optional: run once in the Supabase SQL editor (etl.py also creates it automatically).
CREATE TABLE IF NOT EXISTS air_quality_hourly (
    city TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    pm2_5 DOUBLE PRECISION,
    pm10 DOUBLE PRECISION,
    co DOUBLE PRECISION,
    no2 DOUBLE PRECISION,
    so2 DOUBLE PRECISION,
    o3 DOUBLE PRECISION,
    co2 DOUBLE PRECISION,
    ch4 DOUBLE PRECISION,
    dust DOUBLE PRECISION,
    aod DOUBLE PRECISION,
    us_aqi DOUBLE PRECISION,
    european_aqi DOUBLE PRECISION,
    PRIMARY KEY (city, timestamp)
);
