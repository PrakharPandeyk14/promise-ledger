"""Probability-first prediction helpers for promise-break models."""

from __future__ import annotations

from typing import Any

from promise_ledger.features.engineering import TARGET_COLUMN


def prediction_records(model: Any, rows: list[dict[str, Any]], feature_columns: tuple[str, ...]) -> list[dict[str, Any]]:
    """Return actual labels, break probabilities, and thresholded classes.

    This deliberately preserves the probability rather than making the binary
    prediction the primary output.  ``rows`` must be supervised rows.
    """
    matrix = [[row[column] for column in feature_columns] for row in rows]
    probabilities = [pair[1] for pair in model.predict_proba(matrix)]
    return [
        {
            "promise_id": row["promise_id"],
            "actual_outcome": row[TARGET_COLUMN],
            "predicted_break_probability": float(probability),
            "predicted_class": int(probability >= 0.50),
        }
        for row, probability in zip(rows, probabilities)
    ]
