"""Deterministic customer-history baseline for promise-break probability."""

from __future__ import annotations

from typing import Any


MINIMUM_RESOLVED_PROMISES = 3
FALLBACK_BREAK_PROBABILITY = 0.50


def predict_break_probability(row: dict[str, Any]) -> float:
    """Predict with the customer's observed resolved-promise break rate.

    A customer needs at least three resolved prior promises. Otherwise a fixed
    0.50 fallback is used, avoiding use of future labels or a dataset-wide rate
    that could change with the evaluation period.
    """
    resolved = row["previous_promises_kept"] + row["previous_promises_broken"]
    if resolved < MINIMUM_RESOLVED_PROMISES:
        return FALLBACK_BREAK_PROBABILITY
    return row["previous_promises_broken"] / resolved


def predict_break_probabilities(rows: list[dict[str, Any]]) -> list[float]:
    return [predict_break_probability(row) for row in rows]
