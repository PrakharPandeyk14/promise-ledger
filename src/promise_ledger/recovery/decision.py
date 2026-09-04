"""Pure, deterministic recovery-action decision rules.

This module recommends one action. It does not send messages, alter ledger
records, call external services, or execute recovery.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from promise_ledger.risk.prioritization import RecoveryOpportunity

from .config import DEFAULT_DECISION_CONFIG, DecisionConfig
from .types import RecoveryAction, RecoveryDecision


_REQUIRED = (
    "promise_id",
    "customer_id",
    "outstanding_amount",
    "expected_recovery",
    "promise_credibility_score",
    "recovery_probability",
    "priority_tier",
    "break_probability",
)


def _value(opportunity: RecoveryOpportunity | Mapping[str, Any], name: str) -> Any:
    return opportunity[name] if isinstance(opportunity, Mapping) else getattr(opportunity, name)


def _history(context: Mapping[str, Any] | None, name: str, default: Any = None) -> Any:
    return default if context is None else context.get(name, default)


def _confidence(action: RecoveryAction, break_probability: float, recovery_probability: float, config: DecisionConfig) -> float:
    if action is RecoveryAction.STOP:
        return round(min(1.0, max(0.8, 1.0 - recovery_probability)), 2)
    if action is RecoveryAction.HUMAN_REVIEW:
        return 0.60
    if action is RecoveryAction.ESCALATE:
        return round(min(0.99, (break_probability + recovery_probability) / 2), 2)
    if action is RecoveryAction.PAYMENT_PLAN:
        return round(min(0.95, (1.0 - break_probability + recovery_probability) / 2), 2)
    if action is RecoveryAction.FIRM_REMINDER:
        return round(min(0.95, break_probability), 2)
    return round(min(0.95, 1.0 - break_probability), 2)


class RecoveryDecisionEngine:
    """Apply a fixed hierarchy to one Day 3 recovery opportunity."""

    def __init__(self, config: DecisionConfig = DEFAULT_DECISION_CONFIG):
        self.config = config

    def decide(
        self,
        opportunity: RecoveryOpportunity | Mapping[str, Any],
        context: Mapping[str, Any] | None = None,
    ) -> RecoveryDecision:
        """Return a recommendation using only prediction-point information.

        ``context`` may contain historical feature fields such as
        ``previous_promise_count``, ``historical_promise_keep_rate``,
        ``partial_payment_rate``, and ``payment_on_time_rate``. Current-promise
        outcome fields are deliberately not read.
        """
        for field in _REQUIRED:
            try:
                _value(opportunity, field)
            except (AttributeError, KeyError):
                raise ValueError(f"opportunity is missing required field: {field}") from None

        amount = max(0.0, float(_value(opportunity, "outstanding_amount")))
        expected = max(0.0, float(_value(opportunity, "expected_recovery")))
        recovery = min(1.0, max(0.0, float(_value(opportunity, "recovery_probability"))))
        break_probability = min(1.0, max(0.0, float(_value(opportunity, "break_probability"))))
        credibility = min(100.0, max(0.0, float(_value(opportunity, "promise_credibility_score"))))
        tier = str(_value(opportunity, "priority_tier"))
        c = self.config

        previous = _history(context, "previous_promise_count")
        keep_rate = _history(context, "historical_promise_keep_rate")
        has_contradictory_history = (
            previous is not None
            and keep_rate is not None
            and int(previous) >= c.human_review_min_history
            and c.human_review_contradictory_keep_low < float(keep_rate) < c.human_review_contradictory_keep_high
        )
        actionable = amount >= c.meaningful_balance and expected >= c.meaningful_expected_recovery

        # Fixed hierarchy: no opportunity, judgment required, high-risk priority,
        # structured repayment, firm reminder, then soft reminder.
        if amount <= c.effectively_zero_amount or (
            recovery <= c.stop_recovery_probability and expected <= c.stop_expected_recovery
        ):
            action = RecoveryAction.STOP
            reasons = ("NO_ACTIONABLE_RECOVERY",)
            explanation = "Recommend stopping because the balance or expected recovery is negligible."
        elif amount >= c.human_review_exposure or has_contradictory_history:
            action = RecoveryAction.HUMAN_REVIEW
            reasons = ("JUDGMENT_REQUIRED", "HIGH_EXPOSURE" if amount >= c.human_review_exposure else "CONTRADICTORY_HISTORY")
            explanation = "Recommend human review because the exposure or historical evidence requires judgment."
        elif (
            tier == "HIGH"
            and break_probability >= c.escalate_break_probability
            and recovery >= c.escalate_min_recovery_probability
        ):
            action = RecoveryAction.ESCALATE
            reasons = ("HIGH_BREAK_RISK", "HIGH_PRIORITY", "MEANINGFUL_EXPECTED_RECOVERY")
            explanation = "Recommend escalation because high break risk and high priority make ordinary reminders insufficient."
        elif (
            actionable
            and credibility <= c.payment_plan_max_credibility * 100
            and recovery >= c.payment_plan_min_recovery_probability
            and int(previous or 0) >= c.payment_plan_min_history
        ):
            action = RecoveryAction.PAYMENT_PLAN
            reasons = ("LOW_IMMEDIATE_CREDIBILITY", "MEANINGFUL_RECOVERY_PROBABILITY", "ACTIONABLE_BALANCE")
            explanation = "Recommend a payment plan because full immediate payment appears unlikely while structured recovery remains meaningful."
        elif actionable and break_probability >= c.meaningful_break_probability:
            action = RecoveryAction.FIRM_REMINDER
            reasons = ("HIGH_BREAK_RISK", "MEANINGFUL_EXPECTED_RECOVERY", "ACTIONABLE_BALANCE")
            explanation = "Recommend a firm reminder because break risk and expected recovery are meaningful while automated intervention remains suitable."
        else:
            action = RecoveryAction.SOFT_REMINDER
            reasons = ("LOW_BREAK_RISK", "ACTIONABLE_BALANCE")
            explanation = "Recommend a soft reminder because the balance is actionable and break risk is relatively low."

        return RecoveryDecision(
            promise_id=int(_value(opportunity, "promise_id")),
            customer_id=int(_value(opportunity, "customer_id")),
            recommended_action=action,
            reason_codes=reasons,
            explanation=explanation,
            confidence=_confidence(action, break_probability, recovery, c),
            expected_recovery=round(expected, 2),
            promise_credibility=round(credibility, 2),
            recovery_probability=round(recovery, 4),
            priority_tier=tier,
        )


def decide_recovery(
    opportunity: RecoveryOpportunity | Mapping[str, Any],
    context: Mapping[str, Any] | None = None,
    config: DecisionConfig = DEFAULT_DECISION_CONFIG,
) -> RecoveryDecision:
    """Convenience wrapper around :class:`RecoveryDecisionEngine`."""
    return RecoveryDecisionEngine(config).decide(opportunity, context)
