"""Analyze temperature-dependent measured parameters of SCT3080KL devices.

Input: data/sct3080kl_measurements.csv (long format, one device-temperature row).
The source workbook contains summary parameters, not raw transfer/output curves.
"""
from pathlib import Path
import json
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
INPUT_CSV = ROOT / "data" / "sct3080kl_measurements.csv"
OUTPUT_DIR = ROOT / "outputs"

METRICS = {
    "idss_uA": ("Drain leakage current IDSS", "IDSS (µA)"),
    "igss_plus_nA": ("Positive gate leakage current IGSS+", "IGSS+ (nA)"),
    "igss_minus_nA": ("Negative gate leakage current IGSS−", "IGSS− (nA)"),
    "vgs_th_V": ("Threshold voltage VGS(th)", "VGS(th) (V)"),
    "rds_on_mohm": ("On-resistance RDS(on)", "RDS(on) (mΩ)"),
    "gfs_S": ("Forward transconductance gfs", "gfs (S)"),
}
TEMPERATURES = [25, 100, 150]


def load_data(path):
    """Read normalized measurements and validate IDs, temperatures, and units."""
    if not path.exists():
        raise FileNotFoundError(f"Input data not found: {path}")
    df = pd.read_csv(path)
    required = {"device_id", "temperature_C", "vbr_dss_V", *METRICS.keys()}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing CSV columns: {sorted(missing)}")
    df["device_id"] = pd.to_numeric(df["device_id"], errors="coerce")
    df["temperature_C"] = pd.to_numeric(df["temperature_C"], errors="coerce")
    for col in METRICS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[["device_id", "temperature_C"]].isna().any().any():
        raise ValueError("device_id and temperature_C must be numeric and non-empty.")
    if df.duplicated(["device_id", "temperature_C"]).any():
        raise ValueError("Duplicate device_id-temperature_C rows detected.")
    return df.sort_values(["device_id", "temperature_C"])


def save_plot(path):
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    plt.close()


def analyze_metric(df, metric, title, ylabel):
    """Create device-level trajectories and temperature summary for one metric."""
    data = df.dropna(subset=[metric]).copy()
    if data.empty:
        logging.warning("No valid values for %s", metric)
        return None

    # Summaries are calculated from measured values only; missing cells are not imputed.
    summary = data.groupby("temperature_C")[metric].agg(
        n="count", mean="mean", std="std", median="median", minimum="min", maximum="max"
    ).reset_index()
    summary.to_csv(OUTPUT_DIR / f"{metric}_summary.csv", index=False)

    # Plot each device separately to show within-device temperature changes.
    plt.figure(figsize=(8, 5))
    for device, group in data.groupby("device_id"):
        group = group.sort_values("temperature_C")
        plt.plot(group["temperature_C"], group[metric], marker="o", alpha=0.45, linewidth=1)
    plt.xlabel("Temperature (°C)")
    plt.ylabel(ylabel)
    plt.title(f"{title} — individual devices")
    plt.grid(True, alpha=0.3)
    save_plot(OUTPUT_DIR / f"{metric}_individual.png")

    # Plot mean and standard deviation across devices at each temperature.
    plt.figure(figsize=(7, 5))
    x = summary["temperature_C"].to_numpy(float)
    mean = summary["mean"].to_numpy(float)
    std = summary["std"].fillna(0).to_numpy(float)
    plt.errorbar(x, mean, yerr=std, marker="o", capsize=4, linewidth=1.5)
    plt.xlabel("Temperature (°C)")
    plt.ylabel(ylabel)
    plt.title(f"{title} — mean ± 1 SD")
    plt.xticks(TEMPERATURES)
    plt.grid(True, alpha=0.3)
    save_plot(OUTPUT_DIR / f"{metric}_mean_sd.png")

    # Paired percentage change compares only devices measured at both temperatures.
    paired_rows = []
    for base_temp, target_temp in [(25, 100), (25, 150), (100, 150)]:
        pair = data[data["temperature_C"].isin([base_temp, target_temp])].pivot(
            index="device_id", columns="temperature_C", values=metric
        ).dropna()
        if base_temp not in pair or target_temp not in pair or pair.empty:
            continue
        delta = pair[target_temp] - pair[base_temp]
        pct = delta / pair[base_temp].replace(0, np.nan) * 100
        paired_rows.append({
            "from_temperature_C": base_temp,
            "to_temperature_C": target_temp,
            "n_paired_devices": int(len(pair)),
            "mean_change": float(delta.mean()),
            "mean_percent_change": float(pct.mean()),
        })
    paired = pd.DataFrame(paired_rows)
    paired.to_csv(OUTPUT_DIR / f"{metric}_paired_change.csv", index=False)

    # Linear fit is descriptive and restricted to the measured temperature range.
    if summary["temperature_C"].nunique() >= 2:
        slope, intercept = np.polyfit(x, mean, 1)
        predicted = slope * x + intercept
        ss_res = float(np.sum((mean - predicted) ** 2))
        ss_tot = float(np.sum((mean - mean.mean()) ** 2))
        r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else None
        fit = {"slope_per_C": float(slope), "intercept": float(intercept), "r_squared_of_temperature_means": r2}
    else:
        fit = None

    return {
        "title": title,
        "unit": ylabel,
        "temperature_summary": summary.to_dict(orient="records"),
        "paired_changes": paired.to_dict(orient="records"),
        "linear_fit_to_temperature_means": fit,
    }


def analyze_breakdown(df):
    """Treat >1200 V as right-censored, not as an exact 1200 V breakdown result."""
    text = df["vbr_dss_V"].astype(str).str.strip()
    censored = text.str.startswith(">")
    numeric = pd.to_numeric(text.str.replace(">", "", regex=False), errors="coerce")
    result = {
        "measurement_note": "All reported values are >1200 V; the exact breakdown voltage was not measured.",
        "n_censored_above_1200V": int(censored.sum()),
        "n_exact_numeric_values": int(numeric.notna().sum()),
        "interpretation": "Do not calculate a mean breakdown voltage by substituting 1200 V for >1200 V."
    }
    return result


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_data(INPUT_CSV)
    logging.info("Loaded %d device-temperature rows from %d devices.", len(df), df["device_id"].nunique())

    results = {}
    for metric, (title, ylabel) in METRICS.items():
        results[metric] = analyze_metric(df, metric, title, ylabel)

    # Count actual non-missing measurements at each temperature.
    availability = {}
    for temp, group in df.groupby("temperature_C"):
        availability[str(int(temp))] = {
            "rows": int(len(group)),
            "devices_with_any_measurement": int(group[list(METRICS)].notna().any(axis=1).sum()),
            "valid_values_by_metric": {m: int(group[m].notna().sum()) for m in METRICS},
        }

    summary = {
        "device": "SCT3080KL",
        "device_count": int(df["device_id"].nunique()),
        "temperature_C": sorted(float(x) for x in df["temperature_C"].unique()),
        "data_source": "SCT3080KL_소자별_측정값.xlsx / 소자별 sheet, normalized to CSV",
        "measurement_availability": availability,
        "metrics": results,
        "breakdown_voltage": analyze_breakdown(df),
        "limitations": [
            "Input values are summary measurements, not raw transfer or output curve points.",
            "Transfer curves and output curves cannot be reconstructed from this workbook.",
            "VGS(th) is the workbook's reported threshold voltage based on its stated 5 mA criterion; it is not re-extracted here.",
            "RDS(on) and gfs are reported measurements under the workbook's stated test conditions.",
            "The 20th device has no valid 100 °C measurements; missing values are excluded, not imputed.",
            "Linear fits describe only the measured 25–150 °C interval and should not be extrapolated.",
            "Values reported as >1200 V are right-censored and are not exact breakdown-voltage values."
        ]
    }
    with (OUTPUT_DIR / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logging.info("Analysis complete. Results: %s", OUTPUT_DIR)


if __name__ == "__main__":
    main()
