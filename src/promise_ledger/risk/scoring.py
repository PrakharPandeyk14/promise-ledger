"""Explainable promise credibility and recovery-propensity scoring.

This module deliberately keeps the two concepts separate:

* promise credibility = confidence that the promised payment will be kept;
* recovery probability = heuristic propensity that the outstanding balance will
  eventually be recovered, even if the current promise is broken.

The recovery figure is a transparent heuristic, not a calibrated ML
probability. All inputs are observable at the promise prediction point.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


RECOVERY_PRIOR = 0.50
RECOVERY_WEIGHTS = {
    "historical_recovery_rate": 0.55,
    "payment_on_time_rate": 0.20,
    "promise_credibility": 0.25,
}


@dataclass(frozen=True)
class PromiseScore:
    promise_id: int
    break_probability: float
    promise_credibility_score: float
    recovery_probability: float
    explanation: tuple[str, ...]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def build_explanation(row: dict[str, Any], break_probability: float) -> tuple[str, ...]:
    """Return deterministic, human-readable reasons tied to observable history."""
    reasons: list[str] = []
    previous = int(row["previous_promise_count"])
    broken = int(row["previous_promises_broken"])
    kept = int(row["previous_promises_kept"])
    recent_break = float(row["recent_promise_break_rate"])
    avg_late = float(row["average_days_late"])
    partial = float(row["partial_payment_rate"])
    on_time = float(row["payment_on_time_rate"])

    if previous:
        reasons.append(f"Previous promises: {kept} kept / {broken} broken")
        if broken > kept:
            reasons.append(f"Historical break rate is {_pct(1 - float(row['historical_promise_keep_rate']))}")
    else:
        reasons.append("No prior promise history; using the neutral prior")

    if recent_break >= 0.50:
        reasons.append(f"Recent promise break rate is {_pct(recent_break)}")
    elif recent_break <= 0.20 and previous >= 2:
        reasons.append(f"Recent promise break rate is low at {_pct(recent_break)}")

    if avg_late >= 10:
        reasons.append(f"Average historical payment delay is {avg_late:.1f} days")
    elif avg_late <= 2 and previous:
        reasons.append(f"Average historical payment delay is low at {avg_late:.1f} days")

    if partial >= 0.40:
        reasons.append(f"Partial-payment rate is {_pct(partial)}")
    if on_time >= 0.80 and previous:
        reasons.append(f"Historical on-time payment rate is {_pct(on_time)}")

    if not reasons:
        reasons.append(f"Model break probability is {_pct(break_probability)}")
    return tuple(reasons[:4])


def score_promise(row: dict[str, Any], break_probability: float) -> PromiseScore:
    """Score one promise from a model/baseline break probability.

    Credibility is the complement of predicted break probability. Recovery
    probability is intentionally different: it blends historical invoice
    recovery, on-time payment behavior, and credibility. This captures the
    fact that a broken promise can still be followed by eventual recovery.
    """
    break_probability = _clamp(break_probability)
    credibility = 1.0 - break_probability

    historical_recovery = _clamp(float(row["historical_recovery_rate"]))
    on_time = _clamp(float(row["payment_on_time_rate"]))
    if int(row["historical_invoice_count"]) == 0:
        historical_recovery = RECOVERY_PRIOR
        on_time = RECOVERY_PRIOR

    recovery = (
        RECOVERY_WEIGHTS["historical_recovery_rate"] * historical_recovery
        + RECOVERY_WEIGHTS["payment_on_time_rate"] * on_time
        + RECOVERY_WEIGHTS["promise_credibility"] * credibility
    )
    return PromiseScore(
        promise_id=int(row["promise_id"]),
        break_probability=break_probability,
        promise_credibility_score=round(credibility * 100, 2),
        recovery_probability=round(_clamp(recovery), 4),
        explanation=build_explanation(row, break_probability),
    )


def score_rows(rows: list[dict[str, Any]], break_probabilities: list[float]) -> list[PromiseScore]:
    if len(rows) != len(break_probabilities):
        raise ValueError("rows and break probabilities must have equal lengths")
    return [score_promise(row, probability) for row, probability in zip(rows, break_probabilities)]
