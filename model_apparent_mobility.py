"""Estimate an apparent mobility-degradation index from SCT3080KL RDS(on).

IMPORTANT:
RDS(on) is total device on-resistance, not channel resistance alone. The
calculated quantity is therefore an *apparent mobility index* under the
explicit approximation RDS(on) proportional to 1/mu_eff. It is NOT a direct
measurement or extraction of channel carrier mobility. Raw transfer/output
curves, device geometry, and a channel-resistance decomposition are required
for a physically identified mobility model.
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
REFERENCE_C = 25.0
KELVIN_OFFSET = 273.15


def load_data(path):
    """Load measured data and retain missing values without imputation."""
    df = pd.read_csv(path)
    required = {"device_id", "temperature_C", "rds_on_mohm", "gfs_S"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    for column in required:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df


def fit_power_law(temperature_K, resistance):
    """Fit R(T)/R(T0) = (T/T0)^alpha using log-linear least squares."""
    temperature_K = np.asarray(temperature_K, dtype=float)
    resistance = np.asarray(resistance, dtype=float)
    valid = (
        np.isfinite(temperature_K)
        & np.isfinite(resistance)
        & (temperature_K > 0)
        & (resistance > 0)
    )
    temperature_K = temperature_K[valid]
    resistance = resistance[valid]
    if len(temperature_K) < 2 or len(np.unique(temperature_K)) < 2:
        return None

    # Normalize to the lowest measured temperature for interpretable ratios.
    order = np.argsort(temperature_K)
    temperature_K = temperature_K[order]
    resistance = resistance[order]
    t0 = temperature_K[0]
    r0 = resistance[0]
    x = np.log(temperature_K / t0)
    y = np.log(resistance / r0)
    alpha, intercept = np.polyfit(x, y, 1)
    predicted_log = alpha * x + intercept
    ss_res = float(np.sum((y - predicted_log) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r_squared = float(1 - ss_res / ss_tot) if ss_tot > 0 else None
    return {
        "reference_temperature_K": float(t0),
        "reference_resistance_mohm": float(r0),
        "alpha": float(alpha),
        "log_intercept": float(intercept),
        "r_squared": r_squared,
        "n_temperature_points": int(len(x)),
    }


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_data(INPUT_CSV)

    # Use the measured population mean at each temperature; do not fill missing data.
    summary = (
        df.dropna(subset=["rds_on_mohm"])
        .groupby("temperature_C")["rds_on_mohm"]
        .agg(n="count", mean="mean", std="std")
        .reset_index()
        .sort_values("temperature_C")
    )
    if len(summary) < 2:
        raise ValueError("At least two temperatures with RDS(on) data are required.")

    temperature_K = summary["temperature_C"].to_numpy(float) + KELVIN_OFFSET
    resistance = summary["mean"].to_numpy(float)
    model = fit_power_law(temperature_K, resistance)
    if model is None:
        raise ValueError("Could not fit the resistance temperature model.")

    t0 = model["reference_temperature_K"]
    r0 = model["reference_resistance_mohm"]
    alpha = model["alpha"]

    # Under the channel-dominant approximation, mobility varies inversely
    # with resistance. This is a normalized index, not mobility in cm^2/Vs.
    summary["temperature_K"] = summary["temperature_C"] + KELVIN_OFFSET
    summary["rds_normalized"] = summary["mean"] / r0
    summary["apparent_mobility_index_measured"] = 1.0 / summary["rds_normalized"]
    summary["apparent_mobility_index_model"] = (
        summary["temperature_K"] / t0
    ) ** (-alpha)
    summary["rds_model_mohm"] = r0 * (
        summary["temperature_K"] / t0
    ) ** alpha
    summary.to_csv(OUTPUT_DIR / "apparent_mobility_model.csv", index=False)

    # Fit each device independently when it has at least two valid temperatures.
    device_rows = []
    for device_id, group in df.dropna(subset=["rds_on_mohm"]).groupby("device_id"):
        fit = fit_power_law(
            group["temperature_C"].to_numpy(float) + KELVIN_OFFSET,
            group["rds_on_mohm"].to_numpy(float),
        )
        if fit is not None:
            device_rows.append({
                "device_id": int(device_id),
                "alpha": fit["alpha"],
                "r_squared": fit["r_squared"],
                "n_temperature_points": fit["n_temperature_points"],
            })
    device_fits = pd.DataFrame(device_rows)
    device_fits.to_csv(OUTPUT_DIR / "apparent_mobility_device_exponents.csv", index=False)

    # Plot the normalized apparent mobility index and fitted power law.
    plt.figure(figsize=(8, 5))
    plt.plot(
        summary["temperature_C"],
        summary["apparent_mobility_index_measured"],
        marker="o",
        linewidth=1.5,
        label="Measured RDS(on)-based index",
    )
    plt.plot(
        summary["temperature_C"],
        summary["apparent_mobility_index_model"],
        marker="s",
        linestyle="--",
        linewidth=1.5,
        label=f"Power-law model (alpha={alpha:.3f})",
    )
    plt.xlabel("Temperature (°C)")
    plt.ylabel("Normalized apparent mobility index (25°C reference)")
    plt.title("SCT3080KL apparent mobility degradation model")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "apparent_mobility_model.png", dpi=180, bbox_inches="tight")
    plt.close()

    # gfs is retained as a separate measured cross-check, never treated as mobility.
    gfs_summary = (
        df.dropna(subset=["gfs_S"])
        .groupby("temperature_C")["gfs_S"]
        .agg(n="count", mean="mean", std="std")
        .reset_index()
    )
    gfs_summary.to_csv(OUTPUT_DIR / "gfs_crosscheck_summary.csv", index=False)

    result = {
        "device": "ROHM SCT3080KL",
        "model_name": "RDS(on)-based apparent mobility index",
        "equation": "mu_app(T)/mu_app(T0) = (T/T0)^(-alpha)",
        "resistance_equation": "RDS(on,T)/RDS(on,T0) = (T/T0)^alpha",
        "temperature_unit": "Kelvin in the power law",
        "reference_temperature_C": float(t0 - KELVIN_OFFSET),
        "alpha": alpha,
        "r_squared_of_temperature_mean_fit": model["r_squared"],
        "mean_measurement_table": summary.to_dict(orient="records"),
        "device_exponent_summary": {
            "n_devices_fitted": int(len(device_fits)),
            "alpha_mean": float(device_fits["alpha"].mean()) if not device_fits.empty else None,
            "alpha_std": float(device_fits["alpha"].std()) if len(device_fits) > 1 else None,
            "alpha_median": float(device_fits["alpha"].median()) if not device_fits.empty else None,
        },
        "gfs_crosscheck": {
            "note": "gfs is transconductance and is not identical to carrier mobility.",
            "temperature_summary": gfs_summary.to_dict(orient="records"),
        },
        "assumptions_and_limitations": [
            "This is an apparent mobility index inferred from total RDS(on), not a direct carrier-mobility measurement.",
            "The approximation assumes RDS(on) is dominated by a resistance component inversely proportional to effective channel mobility.",
            "Total RDS(on) also contains drift, JFET, substrate, contact, and other resistance components; their temperature dependence is not separated.",
            "No raw transfer/output curves, channel geometry, oxide capacitance, or channel-resistance decomposition are available in the input workbook.",
            "gfs is analyzed separately and is not substituted for mobility.",
            "The fitted model is empirical and valid only over the measured 25–150°C range; do not extrapolate beyond it.",
            "The model must not be described as an experimentally extracted absolute mobility in cm^2/Vs."
        ],
    }
    with (OUTPUT_DIR / "apparent_mobility_model.json").open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logging.info(
        "Apparent mobility model complete: alpha=%.4f, R²=%s",
        alpha, model["r_squared"]
    )


if __name__ == "__main__":
    main()
