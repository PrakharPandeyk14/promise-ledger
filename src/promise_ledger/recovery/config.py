"""Centralized merchant-policy thresholds for recovery recommendations.

These defaults are illustrative policy values, not simulator parameters. A later
merchant-policy layer can replace this immutable configuration without changing
the decision hierarchy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionConfig:
    """All numeric policy thresholds used by the decision engine."""

    effectively_zero_amount: float = 0.01
    stop_recovery_probability: float = 0.05
    stop_expected_recovery: float = 1.00
    human_review_exposure: float = 100_000.00
    human_review_min_history: int = 4
    human_review_contradictory_keep_low: float = 0.35
    human_review_contradictory_keep_high: float = 0.65
    meaningful_balance: float = 100.00
    meaningful_expected_recovery: float = 25.00
    meaningful_break_probability: float = 0.55
    low_break_probability: float = 0.35
    payment_plan_max_credibility: float = 0.45
    payment_plan_min_recovery_probability: float = 0.30
    payment_plan_min_history: int = 1
    escalate_break_probability: float = 0.75
    escalate_min_recovery_probability: float = 0.40


DEFAULT_DECISION_CONFIG = DecisionConfig()
