"""Deterministic policy checks for recovery recommendations.

This module only permits, blocks, or routes a recommendation. It performs no
recovery operation and has no external side effects.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from .config import DEFAULT_DECISION_CONFIG
from .types import RecoveryAction


class GuardrailStatus(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    OVERRIDE = "OVERRIDE"


@dataclass(frozen=True)
class MerchantPolicy:
    """Existing merchant_policies row represented without schema changes."""

    merchant_name: str
    maximum_automated_contacts: int
    minimum_contact_cooldown_days: int
    maximum_invoice_value_autonomous: float
    maximum_payment_plan_duration_days: int
    human_review_threshold: float

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "MerchantPolicy":
        return cls(
            merchant_name=str(row["merchant_name"]),
            maximum_automated_contacts=int(row["maximum_automated_contacts"]),
            minimum_contact_cooldown_days=int(row["minimum_contact_cooldown_days"]),
            maximum_invoice_value_autonomous=float(row["maximum_invoice_value_autonomous"]),
            maximum_payment_plan_duration_days=int(row["maximum_payment_plan_duration_days"]),
            human_review_threshold=float(row["human_review_threshold"]),
        )


@dataclass(frozen=True)
class GuardrailResult:
    recommended_action: RecoveryAction
    final_action: RecoveryAction
    status: GuardrailStatus
    allowed: bool
    reason_code: str
    reason: str
    policy_value: float | int | str | None = None
    observed_value: float | int | str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "recommended_action": self.recommended_action.value,
            "final_action": self.final_action.value,
            "status": self.status.value,
            "allowed": self.allowed,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "policy_value": self.policy_value,
            "observed_value": self.observed_value,
        }


_AUTOMATED_ACTIONS = frozenset({
    RecoveryAction.SOFT_REMINDER,
    RecoveryAction.FIRM_REMINDER,
    RecoveryAction.PAYMENT_PLAN,
    RecoveryAction.ESCALATE,
})


def _value(source: Mapping[str, Any], name: str, default: Any = None) -> Any:
    return source.get(name, default)


def _result(
    recommended: RecoveryAction,
    final: RecoveryAction,
    status: GuardrailStatus,
    allowed: bool,
    code: str,
    reason: str,
    policy_value: float | int | str | None = None,
    observed_value: float | int | str | None = None,
) -> GuardrailResult:
    return GuardrailResult(recommended, final, status, allowed, code, reason, policy_value, observed_value)


class GuardrailEngine:
    """Evaluate one recommendation against an existing merchant policy."""

    def __init__(self, policy: MerchantPolicy):
        self.policy = policy

    def evaluate(self, recommendation: RecoveryAction | str, context: Mapping[str, Any]) -> GuardrailResult:
        recommended = recommendation if isinstance(recommendation, RecoveryAction) else RecoveryAction(recommendation)
        policy = self.policy
        amount = max(0.0, float(_value(context, "current_outstanding_amount", _value(context, "outstanding_amount", 0.0))))
        invoice_value = max(0.0, float(_value(context, "invoice_amount", amount)))
        expected = max(0.0, float(_value(context, "expected_recovery", 0.0)))
        break_probability = min(1.0, max(0.0, float(_value(context, "break_probability", 0.0))))
        invoice_status = str(_value(context, "invoice_status", ""))
        promise_outcome = str(_value(context, "promise_outcome", "PENDING"))
        evaluation_date_value = _value(context, "evaluation_date")
        evaluation_date = date.fromisoformat(str(evaluation_date_value)) if evaluation_date_value else None
        latest_action_date = _value(context, "latest_recovery_action_date")
        contact_count = int(_value(context, "automated_contact_count", 0))
        duration = _value(context, "proposed_payment_plan_duration_days")

        # Safety hierarchy: STOP -> HUMAN_REVIEW -> ESCALATE -> PAYMENT_PLAN ->
        # FIRM_REMINDER -> SOFT_REMINDER. A non-automated recommendation is
        # never converted into an automated operation.
        if recommended is RecoveryAction.STOP:
            return _result(recommended, RecoveryAction.STOP, GuardrailStatus.ALLOW, False,
                           "STOP_RECOMMENDATION", "The recommendation is STOP; no automated recovery is permitted.")
        if amount <= DEFAULT_DECISION_CONFIG.effectively_zero_amount:
            return _result(recommended, RecoveryAction.STOP, GuardrailStatus.OVERRIDE, False,
                           "STOP_BALANCE_TOO_LOW", "Remaining balance is effectively zero; the promise is not actionable.", DEFAULT_DECISION_CONFIG.effectively_zero_amount, amount)
        if promise_outcome in {"KEPT", "BROKEN"} or invoice_status in {"PAID", "WRITTEN_OFF"}:
            return _result(recommended, RecoveryAction.STOP, GuardrailStatus.OVERRIDE, False,
                           "PROMISE_NOT_ACTIONABLE", "The promise or invoice is already resolved or written off.", "PENDING/OPEN", f"{promise_outcome}/{invoice_status}")
        if expected <= DEFAULT_DECISION_CONFIG.stop_expected_recovery:
            return _result(recommended, RecoveryAction.STOP, GuardrailStatus.OVERRIDE, False,
                           "STOP_EXPECTED_RECOVERY_TOO_LOW", "Expected recovery is negligible; no automated contact is permitted.", DEFAULT_DECISION_CONFIG.stop_expected_recovery, expected)
        if break_probability >= policy.human_review_threshold:
            return _result(recommended, RecoveryAction.HUMAN_REVIEW, GuardrailStatus.OVERRIDE, False,
                           "HUMAN_REVIEW_THRESHOLD", "Break risk meets the merchant threshold for human intervention.", policy.human_review_threshold, break_probability)
        if invoice_value > policy.maximum_invoice_value_autonomous:
            return _result(recommended, RecoveryAction.HUMAN_REVIEW, GuardrailStatus.OVERRIDE, False,
                           "AUTONOMOUS_VALUE_LIMIT_EXCEEDED", "Invoice value exceeds the merchant's autonomous-recovery limit.", policy.maximum_invoice_value_autonomous, invoice_value)
        if recommended is RecoveryAction.PAYMENT_PLAN and duration is not None and int(duration) > policy.maximum_payment_plan_duration_days:
            return _result(recommended, RecoveryAction.HUMAN_REVIEW, GuardrailStatus.BLOCK, False,
                           "PAYMENT_PLAN_LIMIT_EXCEEDED", "The proposed payment-plan duration exceeds the merchant limit.", policy.maximum_payment_plan_duration_days, int(duration))
        if recommended in _AUTOMATED_ACTIONS and contact_count >= policy.maximum_automated_contacts:
            return _result(recommended, RecoveryAction.HUMAN_REVIEW, GuardrailStatus.BLOCK, False,
                           "MAX_CONTACTS_EXCEEDED", "The merchant's maximum automated-contact count has been reached.", policy.maximum_automated_contacts, contact_count)
        if recommended in _AUTOMATED_ACTIONS and latest_action_date and evaluation_date:
            elapsed = (evaluation_date - date.fromisoformat(str(latest_action_date))).days
            if elapsed < policy.minimum_contact_cooldown_days:
                return _result(recommended, RecoveryAction.HUMAN_REVIEW, GuardrailStatus.BLOCK, False,
                               "CONTACT_COOLDOWN_ACTIVE", "The minimum contact cooldown has not elapsed since the latest recovery action.", policy.minimum_contact_cooldown_days, elapsed)
        if recommended is RecoveryAction.HUMAN_REVIEW:
            return _result(recommended, RecoveryAction.HUMAN_REVIEW, GuardrailStatus.ALLOW, True,
                           "HUMAN_REVIEW_REQUIRED", "The recommendation routes the case to human review; no automated contact is allowed.")
        return _result(recommended, recommended, GuardrailStatus.ALLOW, True,
                       "WITHIN_MERCHANT_POLICY", "The recommendation satisfies the merchant policy and current-state checks.")


def evaluate_guardrails(
    recommendation: RecoveryAction | str,
    context: Mapping[str, Any],
    policy: MerchantPolicy,
) -> GuardrailResult:
    return GuardrailEngine(policy).evaluate(recommendation, context)
