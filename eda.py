"""EDA on the loaded data. Reads from Supabase (DATABASE_URL) or the clean CSV.

Run:  python eda.py   -> charts/*.png and web/data.json (used by the interactive dashboard)
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

import config

sns.set_theme(style="whitegrid")
P = config.POLLUTANT_COLS
VALS = config.VALUE_COLS
WHO_PM25_24H = 15  # WHO 2021 24-hour guideline, ug/m3
SEASONS = ["Winter", "Spring", "Summer", "Autumn"]
SEASON_OF_MONTH = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring",
                   6: "Summer", 7: "Summer", 8: "Summer", 9: "Autumn", 10: "Autumn", 11: "Autumn"}


def read_data() -> pd.DataFrame:
    if config.DATABASE_URL:
        import psycopg2
        with psycopg2.connect(config.DATABASE_URL) as conn:
            df = pd.read_sql(f"SELECT * FROM {config.TABLE_NAME}", conn)
    else:
        df = pd.read_csv(config.DATA_DIR / "clean_air_quality.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["hour"] = df["timestamp"].dt.hour
    df["month"] = df["timestamp"].dt.to_period("M").astype(str)
    df["month_num"] = df["timestamp"].dt.month
    df["season"] = df["month_num"].map(SEASON_OF_MONTH)
    return df


def save(name: str) -> None:
    plt.tight_layout()
    plt.savefig(config.CHARTS_DIR / f"{name}.png", dpi=130)
    plt.close()


def r(x, n=2):
    return None if pd.isna(x) else round(float(x), n)


def main() -> None:
    df = read_data()
    key = "pm2_5"

    # 1. Missing / unusual values
    missing = (df[VALS].isna().mean() * 100).round(2)
    z = (df[P] - df[P].mean()) / df[P].std()
    outliers = (z.abs() > 4).sum()
    print("Missing % per variable:\n", missing, "\n\nOutliers (|z|>4):\n", outliers)

    plt.figure(figsize=(9, 4))
    missing.plot(kind="bar", color="#4f46e5")
    plt.ylabel("% missing"); plt.title("Missing values by variable")
    save("01_missing_values")

    # 2. Distributions
    fig, axes = plt.subplots(3, 4, figsize=(16, 9))
    for ax, col in zip(axes.ravel(), VALS):
        sns.histplot(df[col].dropna(), bins=40, kde=True, ax=ax, color="#0ea5e9")
        ax.set_title(col)
    save("02_distributions")

    # 3. City ranking (PM2.5)
    order = df.groupby("city")[key].mean().sort_values(ascending=False).index
    plt.figure(figsize=(10, 5))
    sns.boxplot(data=df, x="city", y=key, order=order, showfliers=False)
    plt.axhline(WHO_PM25_24H, color="red", ls="--", label="WHO 24h guideline (15)")
    plt.xticks(rotation=45); plt.legend(); plt.title("PM2.5 by city (ranked)")
    save("03_pm25_by_city")

    # 4. Hourly pattern
    hourly = df.groupby(["city", "hour"])[key].mean().reset_index()
    plt.figure(figsize=(10, 5))
    sns.lineplot(data=hourly, x="hour", y=key, hue="city")
    plt.title("Average PM2.5 by hour of day"); plt.legend(bbox_to_anchor=(1, 1))
    save("04_hourly_pm25")

    # 5. Seasonal trend (city x season heatmap)
    seas = df.pivot_table(index="city", columns="season", values=key, aggfunc="mean")[SEASONS].loc[order]
    plt.figure(figsize=(7, 5))
    sns.heatmap(seas, annot=True, fmt=".0f", cmap="YlOrRd")
    plt.title("Mean PM2.5 by season")
    save("05_seasonal_heatmap")

    # 6. Monthly trend
    monthly = df.groupby(["month", "city"])[key].mean().reset_index()
    plt.figure(figsize=(14, 5))
    sns.lineplot(data=monthly, x="month", y=key, hue="city")
    plt.xticks(rotation=90, fontsize=6); plt.title("Monthly mean PM2.5")
    plt.legend(bbox_to_anchor=(1, 1))
    save("06_monthly_trend")

    # 7. Correlations
    plt.figure(figsize=(9, 7))
    corr = df[VALS].corr()
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0, annot_kws={"size": 7})
    plt.title("Variable correlations")
    save("07_correlations")

    # JSON for the web dashboard
    cities = {}
    for c, g in df.groupby("city"):
        cities[c] = {
            "mean": {v: r(g[v].mean()) for v in VALS},
            "pct_hours_above_who": r((g[key] > WHO_PM25_24H).mean() * 100, 1),
            "hourly_pm25": [r(v) for v in g.groupby("hour")[key].mean()],
            "monthly": {"months": sorted(g["month"].unique()),
                        "pm25": [r(v) for v in g.groupby("month")[key].mean().sort_index()]},
            "seasonal_pm25": {s: r(g.loc[g["season"] == s, key].mean()) for s in SEASONS},
        }
    out = {
        "generated": str(pd.Timestamp.now().date()),
        "date_range": [str(df["timestamp"].min().date()), str(df["timestamp"].max().date())],
        "who_pm25": WHO_PM25_24H,
        "seasons": SEASONS,
        "ranking": list(order),
        "cities": cities,
        "variables": VALS,
        "correlation": {"labels": VALS, "matrix": [[r(x) for x in row] for row in corr.values]},
        "missing_pct": missing.to_dict(),
    }
    (config.WEB_DIR / "data.json").write_text(json.dumps(out))
    print("Saved charts/ and web/data.json")


if __name__ == "__main__":
    main()
