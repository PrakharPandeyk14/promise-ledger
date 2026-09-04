"""Portfolio-level recovery evaluation metrics and analysis.

Provides comprehensive statistical summaries of orchestrated recovery
opportunities, including action distribution, guardrail outcomes, and
financial metrics for portfolio assessment.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from promise_ledger.recovery.executor import AuditRecord
from promise_ledger.recovery.types import RecoveryAction

from .orchestration import OrchestrationResult


@dataclass(frozen=True)
class ActionDistribution:
    """Count of outcomes by recovery action."""

    soft_reminder: int = 0
    firm_reminder: int = 0
    payment_plan: int = 0
    escalate: int = 0
    human_review: int = 0
    stop: int = 0

    def total(self) -> int:
        """Total count across all actions."""
        return (
            self.soft_reminder
            + self.firm_reminder
            + self.payment_plan
            + self.escalate
            + self.human_review
            + self.stop
        )

    def as_dict(self) -> dict[str, int]:
        """Return serializable representation."""
        return {
            "SOFT_REMINDER": self.soft_reminder,
            "FIRM_REMINDER": self.firm_reminder,
            "PAYMENT_PLAN": self.payment_plan,
            "ESCALATE": self.escalate,
            "HUMAN_REVIEW": self.human_review,
            "STOP": self.stop,
        }


@dataclass(frozen=True)
class PortfolioMetrics:
    """Complete portfolio-level evaluation summary."""

    evaluation_count: int
    total_outstanding_amount: float
    total_expected_recovery: float
    recommended_actions: ActionDistribution
    final_actions: ActionDistribution
    guardrail_allow_count: int
    guardrail_block_count: int
    guardrail_override_count: int
    simulated_execution_count: int
    blocked_no_execution_count: int
    overridden_no_execution_count: int
    stopped_opportunity_count: int
    human_review_opportunity_count: int
    expected_recovery_by_final_action: dict[str, float] = field(default_factory=dict)
    amount_by_final_action: dict[str, float] = field(default_factory=dict)

    def percentage_automated(self) -> float:
        """Percentage of opportunities that were simulated (not blocked/overridden)."""
        if self.evaluation_count == 0:
            return 0.0
        return round((self.simulated_execution_count / self.evaluation_count) * 100, 2)

    def percentage_human_review(self) -> float:
        """Percentage requiring human review (HUMAN_REVIEW + BLOCK/OVERRIDE)."""
        if self.evaluation_count == 0:
            return 0.0
        human_count = (
            self.human_review_opportunity_count
            + self.blocked_no_execution_count
            + self.overridden_no_execution_count
        )
        return round((human_count / self.evaluation_count) * 100, 2)

    def percentage_stopped(self) -> float:
        """Percentage of opportunities marked STOP."""
        if self.evaluation_count == 0:
            return 0.0
        return round((self.stopped_opportunity_count / self.evaluation_count) * 100, 2)

    def average_expected_recovery(self) -> float:
        """Average expected recovery per opportunity."""
        if self.evaluation_count == 0:
            return 0.0
        return round(self.total_expected_recovery / self.evaluation_count, 2)

    def as_dict(self) -> dict[str, Any]:
        """Return serialization-friendly representation."""
        return {
            "evaluation_count": self.evaluation_count,
            "total_outstanding_amount": self.total_outstanding_amount,
            "total_expected_recovery": self.total_expected_recovery,
            "average_expected_recovery_per_opportunity": self.average_expected_recovery(),
            "recommended_actions": self.recommended_actions.as_dict(),
            "final_actions": self.final_actions.as_dict(),
            "guardrail_allow_count": self.guardrail_allow_count,
            "guardrail_block_count": self.guardrail_block_count,
            "guardrail_override_count": self.guardrail_override_count,
            "simulated_execution_count": self.simulated_execution_count,
            "blocked_no_execution_count": self.blocked_no_execution_count,
            "overridden_no_execution_count": self.overridden_no_execution_count,
            "stopped_opportunity_count": self.stopped_opportunity_count,
            "human_review_opportunity_count": self.human_review_opportunity_count,
            "percentage_automated": self.percentage_automated(),
            "percentage_human_review": self.percentage_human_review(),
            "percentage_stopped": self.percentage_stopped(),
            "expected_recovery_by_final_action": self.expected_recovery_by_final_action,
            "amount_by_final_action": self.amount_by_final_action,
        }


class PortfolioEvaluator:
    """Analyze complete portfolio results from orchestration."""

    @staticmethod
    def evaluate(results: list[OrchestrationResult]) -> PortfolioMetrics:
        """Generate comprehensive portfolio metrics from orchestration results.

        Args:
            results: List of OrchestrationResults to analyze

        Returns:
            PortfolioMetrics with all summary statistics
        """
        if not results:
            return PortfolioMetrics(
                evaluation_count=0,
                total_outstanding_amount=0.0,
                total_expected_recovery=0.0,
                recommended_actions=ActionDistribution(),
                final_actions=ActionDistribution(),
                guardrail_allow_count=0,
                guardrail_block_count=0,
                guardrail_override_count=0,
                simulated_execution_count=0,
                blocked_no_execution_count=0,
                overridden_no_execution_count=0,
                stopped_opportunity_count=0,
                human_review_opportunity_count=0,
            )

        # Aggregate counts
        recommended_counts = defaultdict(int)
        final_counts = defaultdict(int)
        allow_count = 0
        block_count = 0
        override_count = 0
        simulated_count = 0
        blocked_count = 0
        overridden_count = 0
        stopped_count = 0
        human_review_count = 0

        total_outstanding = 0.0
        total_expected_recovery = 0.0
        recovery_by_action = defaultdict(float)
        amount_by_action = defaultdict(float)

        for result in results:
            audit = result.execution.audit
            opportunity = result.opportunity

            # Recommended and final actions
            recommended_counts[audit.recommended_action.value] += 1
            final_counts[audit.final_action.value] += 1

            # Guardrail status
            status = result.execution.guardrail.status.value
            if status == "ALLOW":
                allow_count += 1
            elif status == "BLOCK":
                block_count += 1
            else:  # OVERRIDE
                override_count += 1

            # Execution status
            exec_status = audit.execution_status
            if exec_status == "SIMULATED_EXECUTION":
                simulated_count += 1
            elif exec_status == "BLOCKED_NO_EXECUTION":
                blocked_count += 1
            else:  # OVERRIDDEN_NO_EXECUTION
                overridden_count += 1

            # Opportunity categorization
            if audit.final_action == RecoveryAction.STOP:
                stopped_count += 1
            if audit.final_action == RecoveryAction.HUMAN_REVIEW:
                human_review_count += 1

            # Financial aggregates
            total_outstanding += opportunity.outstanding_amount
            total_expected_recovery += opportunity.expected_recovery
            recovery_by_action[audit.final_action.value] += audit.expected_recovery or 0.0
            amount_by_action[audit.final_action.value] += opportunity.outstanding_amount

        # Build action distributions
        recommended_dist = ActionDistribution(
            soft_reminder=recommended_counts.get("SOFT_REMINDER", 0),
            firm_reminder=recommended_counts.get("FIRM_REMINDER", 0),
            payment_plan=recommended_counts.get("PAYMENT_PLAN", 0),
            escalate=recommended_counts.get("ESCALATE", 0),
            human_review=recommended_counts.get("HUMAN_REVIEW", 0),
            stop=recommended_counts.get("STOP", 0),
        )

        final_dist = ActionDistribution(
            soft_reminder=final_counts.get("SOFT_REMINDER", 0),
            firm_reminder=final_counts.get("FIRM_REMINDER", 0),
            payment_plan=final_counts.get("PAYMENT_PLAN", 0),
            escalate=final_counts.get("ESCALATE", 0),
            human_review=final_counts.get("HUMAN_REVIEW", 0),
            stop=final_counts.get("STOP", 0),
        )

        return PortfolioMetrics(
            evaluation_count=len(results),
            total_outstanding_amount=round(total_outstanding, 2),
            total_expected_recovery=round(total_expected_recovery, 2),
            recommended_actions=recommended_dist,
            final_actions=final_dist,
            guardrail_allow_count=allow_count,
            guardrail_block_count=block_count,
            guardrail_override_count=override_count,
            simulated_execution_count=simulated_count,
            blocked_no_execution_count=blocked_count,
            overridden_no_execution_count=overridden_count,
            stopped_opportunity_count=stopped_count,
            human_review_opportunity_count=human_review_count,
            expected_recovery_by_final_action=dict(recovery_by_action),
            amount_by_final_action=dict(amount_by_action),
        )
