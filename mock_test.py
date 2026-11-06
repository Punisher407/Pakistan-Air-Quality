"""Offline test: feeds a fake Open-Meteo response (14 months, all variables) through the full pipeline."""
import numpy as np
import pandas as pd

import config, etl, eda


def fake_payload(lat, lon, seed):
    rng = np.random.default_rng(seed)
    times = pd.date_range("2025-01-01", periods=24 * 425, freq="h")
    hr, mo = times.hour.values, times.month.values
    winter = np.where(np.isin(mo, [11, 12, 1, 2]), 2.2, 1.0)        # smog season
    pm25 = np.clip(40 + 25 * np.cos((hr - 7) / 24 * 2 * np.pi) + rng.normal(0, 8, len(times)), 1, None) * winter * rng.uniform(0.6, 1.8)
    n = len(times)
    h = {
        "time": [t.strftime("%Y-%m-%dT%H:%M") for t in times],
        "pm2_5": list(pm25), "pm10": list(pm25 * 1.8),
        "carbon_monoxide": list(rng.uniform(200, 1500, n)),
        "nitrogen_dioxide": list(rng.uniform(5, 60, n)),
        "sulphur_dioxide": list(rng.uniform(1, 40, n)),
        "ozone": list(rng.uniform(10, 120, n)),
        "carbon_dioxide": list(rng.uniform(410, 440, n)),
        "methane": list(rng.uniform(1800, 2200, n)),
        "dust": list(rng.uniform(0, 80, n)),
        "aerosol_optical_depth": list(rng.uniform(0.1, 1.5, n)),
        "us_aqi": list(np.clip(pm25 * 2.2, 0, 500)),
        "european_aqi": list(np.clip(pm25 * 1.5, 0, 500)),
    }
    h["pm2_5"][5] = None          # missing value
    h["pm10"][10] = -5.0          # invalid value -> must be rejected
    return {"latitude": lat, "longitude": lon, "hourly": h}


raw = {c: fake_payload(*xy, seed=i) for i, (c, xy) in enumerate(config.CITIES.items())}
df = etl.main(raw)
print("rows loaded:", len(df))
eda.main()
