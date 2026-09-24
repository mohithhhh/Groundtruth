"""Phase 3, step 1: fit an interpretable model of surface temperature as a
function of NDVI, built fraction, elevation and distance to water, with
spatial block cross-validation and bootstrap effect ranges.

CLAUDE.md is explicit that this must be labeled as an association, not a
guaranteed outcome, and that a weak held-out score must be surfaced, not
hidden -- see the "Label everything" note in Section 6, Phase 3, item 1.

Run:
    source .venv/bin/activate
    python model/cooling_model.py
"""

import json
import subprocess

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

CSV_PATH = "model/grid_sample_2025.csv"
FEATURES = ["ndvi", "built_frac", "elevation_m", "dist_water_m"]
TARGET = "lst_c"
RIDGE_ALPHA = 1.0  # fixed, not tuned -- see model/README.md for why
SPATIAL_BLOCK_DEGREES = 0.009  # roughly 1km at this latitude
N_SPLITS = 5
N_BOOTSTRAP = 500
BOOTSTRAP_SEED = 42
PROJECT = "penumbra-509416"
DATASET = "penumbra"


def load_data() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH)
    before = len(df)
    df = df.dropna(subset=FEATURES + [TARGET])
    if len(df) < before:
        print(f"Dropped {before - len(df)} rows with missing values ({len(df)} remain).")
    return df


def assign_spatial_blocks(df: pd.DataFrame) -> np.ndarray:
    block_lat = (df["lat"] // SPATIAL_BLOCK_DEGREES).astype(int)
    block_lon = (df["lon"] // SPATIAL_BLOCK_DEGREES).astype(int)
    return (block_lat.astype(str) + "_" + block_lon.astype(str)).values


def spatial_cv_score(X: np.ndarray, y: np.ndarray, groups: np.ndarray) -> dict:
    gkf = GroupKFold(n_splits=N_SPLITS)
    residuals = []
    fold_r2 = []
    for train_idx, test_idx in gkf.split(X, y, groups):
        scaler = StandardScaler().fit(X[train_idx])
        model = Ridge(alpha=RIDGE_ALPHA).fit(scaler.transform(X[train_idx]), y[train_idx])
        pred = model.predict(scaler.transform(X[test_idx]))
        resid = y[test_idx] - pred
        residuals.extend(resid)
        ss_res = np.sum(resid ** 2)
        ss_tot = np.sum((y[test_idx] - y[test_idx].mean()) ** 2)
        fold_r2.append(1 - ss_res / ss_tot)
    residuals = np.array(residuals)
    return {
        "held_out_r2_mean": float(np.mean(fold_r2)),
        "held_out_r2_per_fold": [round(float(r), 4) for r in fold_r2],
        "held_out_rmse_c": float(np.sqrt(np.mean(residuals ** 2))),
        "n_folds": N_SPLITS,
        "n_spatial_blocks": int(len(np.unique(groups))),
    }


def fit_full_model(X: np.ndarray, y: np.ndarray) -> tuple[Ridge, StandardScaler]:
    scaler = StandardScaler().fit(X)
    model = Ridge(alpha=RIDGE_ALPHA).fit(scaler.transform(X), y)
    return model, scaler


def bootstrap_effect(X: np.ndarray, y: np.ndarray, feature_idx: int, unit_change: float) -> dict:
    """Effect on LST (°C) of `unit_change` in one raw-scale feature, holding
    others fixed, via bootstrap resampling of the training rows."""
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    n = len(y)
    effects = []
    for _ in range(N_BOOTSTRAP):
        idx = rng.integers(0, n, n)
        scaler = StandardScaler().fit(X[idx])
        model = Ridge(alpha=RIDGE_ALPHA).fit(scaler.transform(X[idx]), y[idx])
        # dy/dx_raw = coef_standardized / std_of_that_feature
        effect_per_unit = model.coef_[feature_idx] / scaler.scale_[feature_idx]
        effects.append(effect_per_unit * unit_change)
    effects = np.array(effects)
    return {
        "unit_change": unit_change,
        "effect_low_c": float(np.percentile(effects, 5)),
        "effect_mid_c": float(np.percentile(effects, 50)),
        "effect_high_c": float(np.percentile(effects, 95)),
    }


def write_effect_model_table(rows: list[dict]) -> None:
    structs = ",\n".join(
        "STRUCT("
        f"'{r['intervention']}' AS intervention, {r['unit_change']} AS unit_change, "
        f"{r['effect_low_c']} AS effect_low_c, {r['effect_mid_c']} AS effect_mid_c, "
        f"{r['effect_high_c']} AS effect_high_c, {r['held_out_r2_mean']} AS held_out_r2, "
        f"{r['held_out_rmse_c']} AS held_out_rmse_c, {r['n_samples']} AS n_samples, "
        f"'{r['model_type']}' AS model_type, '{r['fitted_date']}' AS fitted_date, "
        f"{'TRUE' if r['usable'] else 'FALSE'} AS usable, '{r['note']}' AS note)"
        for r in rows
    )
    sql = (
        f"CREATE OR REPLACE TABLE `{PROJECT}.{DATASET}.effect_model` AS\n"
        f"SELECT * FROM UNNEST([\n{structs}\n])"
    )
    subprocess.run(["bq", "--quiet", "query", "--use_legacy_sql=false", sql], check=True)


def main():
    df = load_data()
    X = df[FEATURES].values
    y = df[TARGET].values
    groups = assign_spatial_blocks(df)

    print(f"Fitting on {len(df)} grid points, {len(np.unique(groups))} spatial blocks.")
    cv_result = spatial_cv_score(X, y, groups)
    print("Spatial block CV:", json.dumps(cv_result, indent=2))

    ndvi_idx = FEATURES.index("ndvi")
    built_idx = FEATURES.index("built_frac")
    ndvi_effect = bootstrap_effect(X, y, ndvi_idx, unit_change=0.1)
    built_effect = bootstrap_effect(X, y, built_idx, unit_change=-0.1)
    print("NDVI +0.1 effect (C):", ndvi_effect)
    print("Built fraction -0.1 effect (C):", built_effect)

    from datetime import date
    today = date.today().isoformat()
    rows = [
        {
            "intervention": "ndvi_increase_0.1",
            "unit_change": ndvi_effect["unit_change"],
            "effect_low_c": ndvi_effect["effect_low_c"],
            "effect_mid_c": ndvi_effect["effect_mid_c"],
            "effect_high_c": ndvi_effect["effect_high_c"],
            "held_out_r2_mean": cv_result["held_out_r2_mean"],
            "held_out_rmse_c": cv_result["held_out_rmse_c"],
            "n_samples": len(df),
            "model_type": "ridge_alpha1.0",
            "fitted_date": today,
            "usable": True,
            "note": "Stable, intuitive-direction coefficient across univariate and multivariate fits.",
        },
        {
            "intervention": "built_frac_decrease_0.1",
            "unit_change": built_effect["unit_change"],
            "effect_low_c": built_effect["effect_low_c"],
            "effect_mid_c": built_effect["effect_mid_c"],
            "effect_high_c": built_effect["effect_high_c"],
            "held_out_r2_mean": cv_result["held_out_r2_mean"],
            "held_out_rmse_c": cv_result["held_out_rmse_c"],
            "n_samples": len(df),
            "model_type": "ridge_alpha1.0",
            "fitted_date": today,
            "usable": False,
            "note": "Sign-unstable due to collinearity with NDVI (r=-0.48); see model/README.md. Do not use for planning.",
        },
    ]
    write_effect_model_table(rows)
    print("Wrote penumbra.effect_model")

    return {"cv_result": cv_result, "ndvi_effect": ndvi_effect, "built_effect": built_effect, "n_samples": len(df)}


if __name__ == "__main__":
    main()
