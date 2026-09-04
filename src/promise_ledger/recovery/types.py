"""Public types for recovery recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RecoveryAction(str, Enum):
    SOFT_REMINDER = "SOFT_REMINDER"
    FIRM_REMINDER = "FIRM_REMINDER"
    PAYMENT_PLAN = "PAYMENT_PLAN"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    ESCALATE = "ESCALATE"
    STOP = "STOP"


@dataclass(frozen=True)
class RecoveryDecision:
    promise_id: int
    customer_id: int
    recommended_action: RecoveryAction
    reason_codes: tuple[str, ...]
    explanation: str
    confidence: float
    expected_recovery: float
    promise_credibility: float
    recovery_probability: float
    priority_tier: str

    def as_dict(self) -> dict[str, object]:
        """Return a serialization-friendly representation without execution data."""
        return {
            "promise_id": self.promise_id,
            "customer_id": self.customer_id,
            "recommended_action": self.recommended_action.value,
            "reason_codes": list(self.reason_codes),
            "explanation": self.explanation,
            "confidence": self.confidence,
            "expected_recovery": self.expected_recovery,
            "promise_credibility": self.promise_credibility,
            "recovery_probability": self.recovery_probability,
            "priority_tier": self.priority_tier,
        }
