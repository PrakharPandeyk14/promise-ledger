"""Expected-recovery calculation and deterministic portfolio prioritization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from promise_ledger.risk.scoring import PromiseScore


@dataclass(frozen=True)
class RecoveryOpportunity:
    """A current unresolved promise ranked by expected financial recovery."""

    promise_id: int
    invoice_id: int
    customer_id: int
    outstanding_amount: float
    recovery_probability: float
    expected_recovery: float
    break_probability: float
    promise_credibility_score: float
    priority_rank: int
    priority_tier: str
    priority_score: float


def expected_recovery(outstanding_amount: float, recovery_probability: float) -> float:
    """Return expected recoverable value, clamped to valid financial bounds."""
    amount = max(0.0, float(outstanding_amount))
    probability = max(0.0, min(1.0, float(recovery_probability)))
    return round(amount * probability, 2)


def _tier(rank: int, total: int) -> str:
    if total <= 1:
        return "HIGH"
    # Divide the ranked portfolio into deterministic thirds. The highest-value
    # opportunity is always HIGH, and the lowest-value opportunity is LOW.
    high_cutoff = max(1, (total + 2) // 3)
    low_start = total - max(1, (total + 2) // 3) + 1
    if rank <= high_cutoff:
        return "HIGH"
    if rank >= low_start:
        return "LOW"
    return "MEDIUM"


def prioritize_opportunities(
    rows: Iterable[dict[str, Any]], scores: Iterable[PromiseScore]
) -> list[RecoveryOpportunity]:
    """Rank unresolved promises by expected recovery, highest first.

    Expected recovery is the primary ranking signal. Ties are resolved by
    outstanding balance, break probability, then promise ID for deterministic
    output. This function does not execute recovery actions or bypass merchant
    policies; Day 4's guardrail/decision layer will consume this ranking.
    """
    row_by_promise = {int(row["promise_id"]): row for row in rows}
    candidates: list[RecoveryOpportunity] = []
    for score in scores:
        row = row_by_promise.get(score.promise_id)
        if row is None:
            raise ValueError(f"missing feature row for promise {score.promise_id}")
        outstanding = max(0.0, float(row["outstanding_amount_at_promise_creation"]))
        candidates.append(
            RecoveryOpportunity(
                promise_id=score.promise_id,
                invoice_id=int(row["invoice_id"]),
                customer_id=int(row["customer_id"]),
                outstanding_amount=round(outstanding, 2),
                recovery_probability=round(float(score.recovery_probability), 4),
                expected_recovery=expected_recovery(outstanding, score.recovery_probability),
                break_probability=round(float(score.break_probability), 4),
                promise_credibility_score=round(float(score.promise_credibility_score), 2),
                priority_rank=0,
                priority_tier="",
                priority_score=0.0,
            )
        )

    candidates.sort(
        key=lambda item: (
            -item.expected_recovery,
            -item.outstanding_amount,
            -item.break_probability,
            item.promise_id,
        )
    )
    total = len(candidates)
    max_expected = max((item.expected_recovery for item in candidates), default=0.0)
    ranked: list[RecoveryOpportunity] = []
    for index, item in enumerate(candidates, start=1):
        score = round((item.expected_recovery / max_expected) * 100, 2) if max_expected else 0.0
        ranked.append(
            RecoveryOpportunity(
                **{**item.__dict__,
                   "priority_rank": index,
                   "priority_tier": _tier(index, total),
                   "priority_score": score}
            )
        )
    return ranked
