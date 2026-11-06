"""Shared configuration for the Air Quality ETL + EDA project."""
import os
from datetime import date, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CHARTS_DIR = BASE_DIR / "charts"
WEB_DIR = BASE_DIR / "web"
for d in (DATA_DIR, CHARTS_DIR, WEB_DIR):
    d.mkdir(exist_ok=True)

API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
TIMEZONE = "Asia/Karachi"

# Multi-year history so we can study seasonal trends (smog season is Nov-Feb).
START_DATE = date(2023, 1, 1)
END_DATE = date.today() - timedelta(days=1)

# Major cities of Pakistan: name -> (latitude, longitude)
CITIES = {
    "Lahore": (31.5497, 74.3436),
    "Karachi": (24.8607, 67.0011),
    "Islamabad": (33.6844, 73.0479),
    "Rawalpindi": (33.5651, 73.0169),
    "Faisalabad": (31.4504, 73.1350),
    "Multan": (30.1575, 71.5249),
    "Peshawar": (34.0151, 71.5249),
    "Quetta": (30.1798, 66.9750),
    "Gujranwala": (32.1877, 74.1945),
    "Sialkot": (32.4945, 74.5229),
}

# Open-Meteo hourly variable -> column name in our table
VARIABLES = {
    "pm2_5": "pm2_5",
    "pm10": "pm10",
    "carbon_monoxide": "co",
    "nitrogen_dioxide": "no2",
    "sulphur_dioxide": "so2",
    "ozone": "o3",
    "carbon_dioxide": "co2",
    "methane": "ch4",
    "dust": "dust",
    "aerosol_optical_depth": "aod",
    "us_aqi": "us_aqi",
    "european_aqi": "european_aqi",
}
VALUE_COLS = list(VARIABLES.values())
POLLUTANT_COLS = ["pm2_5", "pm10", "co", "no2", "so2", "o3", "co2", "ch4", "dust", "aod"]

TABLE_NAME = "air_quality_hourly"
# Supabase: Project Settings -> Database -> Connection string (URI)
DATABASE_URL = os.getenv("DATABASE_URL", "")
