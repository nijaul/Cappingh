from __future__ import annotations

import numpy as np
import pandas as pd


WEIGHTS = {
    "prime_power": 0.32,
    "speed": 0.20,
    "late_speed": 0.13,
    "pace_speed": 0.08,
    "e1": 0.07,
    "e2": 0.07,
    "race_rating": 0.05,
    "avg_class": 0.04,
    "morning_line_decimal": 0.04,
}


def percentile(values: pd.Series, value: float) -> float:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if len(clean) <= 1 or not np.isfinite(value):
        return np.nan

    less = float((clean < value).sum())
    equal = float((clean == value).sum())
    return (less + equal / 2.0) / len(clean)


def handicap_horses(horses: pd.DataFrame) -> pd.DataFrame:
    data = horses.copy()

    data["market_signal"] = np.where(
        pd.to_numeric(data["morning_line_decimal"], errors="coerce") > 1,
        1.0 / pd.to_numeric(data["morning_line_decimal"], errors="coerce"),
        np.nan,
    )

    scored_rows: list[pd.DataFrame] = []

    for race_id, group in data.groupby("race_id", sort=False):
        group = group.copy()
        contributions = pd.DataFrame(index=group.index)

        for feature, weight in WEIGHTS.items():
            if feature == "morning_line_decimal":
                values = group["market_signal"]
                label_values = values
            else:
                values = pd.to_numeric(group[feature], errors="coerce")
                label_values = values

            pcts = pd.Series(
                [percentile(values, v) for v in values],
                index=group.index,
                dtype=float,
            )
            contributions[feature] = pcts * weight

        used_weight = contributions.notna().mul(
            pd.Series(WEIGHTS)
        ).sum(axis=1)
        raw_score = contributions.sum(axis=1)

        group["handicap_score"] = (
            raw_score / used_weight.replace(0, np.nan) * 100
        ).clip(0, 100).fillna(0)

        # Race-relative probability-like estimate.
        x = group["handicap_score"].to_numpy(dtype=float)
        x = x - np.nanmax(x)
        exp_x = np.exp(np.clip(x / 7.5, -40, 40))
        probs = exp_x / exp_x.sum()
        group["model_percent"] = probs * 100

        group = group.sort_values(
            "model_percent",
            ascending=False,
        )
        group["handicap_rank"] = np.arange(1, len(group) + 1)

        labels = {
            "prime_power": "Prime",
            "speed": "Speed",
            "late_speed": "Late",
            "pace_speed": "Pace",
            "e1": "E1",
            "e2": "E2",
            "race_rating": "Race",
            "avg_class": "Class",
            "morning_line_decimal": "Market",
        }

        factor_text = []
        for idx, row in group.iterrows():
            available = []
            for feature in WEIGHTS:
                value = (
                    row["market_signal"]
                    if feature == "morning_line_decimal"
                    else pd.to_numeric(row[feature], errors="coerce")
                )
                if pd.notna(value):
                    available.append((labels[feature], float(value)))
            available.sort(key=lambda x: x[1], reverse=True)
            factor_text.append(
                ", ".join(
                    f"{name} {value:g}"
                    for name, value in available[:3]
                )
            )

        group["top_factors"] = factor_text
        scored_rows.append(group)

    result = pd.concat(scored_rows, ignore_index=True)
    return result.sort_values(
        ["race_number", "handicap_rank"],
        key=lambda s: pd.to_numeric(s, errors="coerce"),
    ).reset_index(drop=True)
