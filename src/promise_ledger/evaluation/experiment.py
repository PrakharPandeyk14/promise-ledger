"""Deterministic control vs AI-treatment recovery experiment.

Control uses historical_recovery_rate only. Treatment applies the existing
Promise → Decision → Guardrail → Executor pipeline, then a simulated recovery
multiplier on the existing recovery_probability.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from promise_ledger.config import SIMULATION_DATE
from promise_ledger.recovery.orchestration import OrchestrationResult
from promise_ledger.recovery.types import RecoveryAction
from promise_ledger.risk.prioritization import expected_recovery


ACTION_MULTIPLIERS: dict[RecoveryAction, float] = {
    RecoveryAction.SOFT_REMINDER: 1.05,
    RecoveryAction.FIRM_REMINDER: 1.10,
    RecoveryAction.PAYMENT_PLAN: 1.15,
    RecoveryAction.ESCALATE: 1.20,
    RecoveryAction.HUMAN_REVIEW: 1.08,
    RecoveryAction.STOP: 0.0,
}

_SIMULATED = "SIMULATED_EXECUTION"
_BLOCKED = "BLOCKED_NO_EXECUTION"
_OVERRIDDEN = "OVERRIDDEN_NO_EXECUTION"


class OutcomeClass(str, Enum):
    AUTOMATED = "AUTOMATED"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    STOPPED = "STOPPED"


@dataclass(frozen=True)
class ExperimentMetrics:
    """Portfolio-level control vs treatment comparison."""

    evaluation_count: int
    total_outstanding_amount: float
    control_recovered_amount: float
    treatment_recovered_amount: float
    incremental_recovery_amount: float
    control_recovery_rate: float
    treatment_recovery_rate: float
    treatment_improvement_percent: float
    automation_rate: float
    human_review_rate: float
    stopped_rate: float
    evaluation_date: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "evaluation_date": self.evaluation_date,
            "evaluation_count": self.evaluation_count,
            "total_outstanding_amount": self.total_outstanding_amount,
            "control_recovered_amount": self.control_recovered_amount,
            "treatment_recovered_amount": self.treatment_recovered_amount,
            "incremental_recovery_amount": self.incremental_recovery_amount,
            "control_recovery_rate": self.control_recovery_rate,
            "treatment_recovery_rate": self.treatment_recovery_rate,
            "treatment_improvement_percent": self.treatment_improvement_percent,
            "automation_rate": self.automation_rate,
            "human_review_rate": self.human_review_rate,
            "stopped_rate": self.stopped_rate,
        }


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def control_recovered_amount(outstanding_amount: float, historical_recovery_rate: float) -> float:
    """Traditional baseline: outstanding × clamped historical recovery rate."""
    return expected_recovery(outstanding_amount, _clamp_unit(historical_recovery_rate))


def treatment_recovered_amount(
    outstanding_amount: float,
    recovery_probability: float,
    final_action: RecoveryAction,
    execution_status: str,
) -> float:
    """Simulated AI-pipeline recovery after the final guardrailed action."""
    if execution_status != _SIMULATED:
        return 0.0
    multiplier = ACTION_MULTIPLIERS[final_action]
    adjusted = _clamp_unit(float(recovery_probability) * multiplier)
    return expected_recovery(outstanding_amount, adjusted)


def classify_outcome(final_action: RecoveryAction, execution_status: str) -> OutcomeClass:
    """Assign one mutually exclusive outcome class to a pipeline result."""
    if final_action is RecoveryAction.STOP:
        return OutcomeClass.STOPPED
    if final_action is RecoveryAction.HUMAN_REVIEW or execution_status in {_BLOCKED, _OVERRIDDEN}:
        return OutcomeClass.HUMAN_REVIEW
    return OutcomeClass.AUTOMATED


def _exclusive_percentages(automated: int, human_review: int, stopped: int, total: int) -> tuple[float, float, float]:
    if total <= 0:
        return 0.0, 0.0, 0.0
    automation_rate = round((automated / total) * 100, 2)
    stopped_rate = round((stopped / total) * 100, 2)
    human_review_rate = round(100.0 - automation_rate - stopped_rate, 2)
    return automation_rate, human_review_rate, stopped_rate


def _historical_rate(feature_rows: Mapping[int, Mapping[str, Any]], promise_id: int) -> float:
    row = feature_rows.get(promise_id)
    if not row:
        return 0.0
    return _clamp_unit(float(row.get("historical_recovery_rate", 0.0)))


def evaluate_experiment(
    results: Sequence[OrchestrationResult],
    feature_rows: Mapping[int, Mapping[str, Any]],
    evaluation_date: str | None = None,
) -> ExperimentMetrics:
    """Compare control vs treatment on already-orchestrated pipeline results."""
    date_value = evaluation_date or SIMULATION_DATE.isoformat()
    if not results:
        return ExperimentMetrics(
            evaluation_count=0,
            total_outstanding_amount=0.0,
            control_recovered_amount=0.0,
            treatment_recovered_amount=0.0,
            incremental_recovery_amount=0.0,
            control_recovery_rate=0.0,
            treatment_recovery_rate=0.0,
            treatment_improvement_percent=0.0,
            automation_rate=0.0,
            human_review_rate=0.0,
            stopped_rate=0.0,
            evaluation_date=date_value,
        )

    total_outstanding = 0.0
    control_total = 0.0
    treatment_total = 0.0
    automated = 0
    human_review = 0
    stopped = 0

    for result in results:
        opportunity = result.opportunity
        audit = result.execution.audit
        outstanding = float(opportunity.outstanding_amount)
        total_outstanding += outstanding
        control_total += control_recovered_amount(
            outstanding,
            _historical_rate(feature_rows, opportunity.promise_id),
        )
        treatment_total += treatment_recovered_amount(
            outstanding,
            float(opportunity.recovery_probability),
            audit.final_action,
            audit.execution_status,
        )
        outcome = classify_outcome(audit.final_action, audit.execution_status)
        if outcome is OutcomeClass.AUTOMATED:
            automated += 1
        elif outcome is OutcomeClass.STOPPED:
            stopped += 1
        else:
            human_review += 1

    total_outstanding = round(total_outstanding, 2)
    control_total = round(control_total, 2)
    treatment_total = round(treatment_total, 2)
    incremental = round(treatment_total - control_total, 2)
    if total_outstanding > 0:
        control_rate = round(control_total / total_outstanding, 4)
        treatment_rate = round(treatment_total / total_outstanding, 4)
    else:
        control_rate = 0.0
        treatment_rate = 0.0
    if control_total == 0:
        improvement = 0.0
    else:
        improvement = round((incremental / control_total) * 100, 2)
    automation_rate, human_review_rate, stopped_rate = _exclusive_percentages(
        automated, human_review, stopped, len(results)
    )
    return ExperimentMetrics(
        evaluation_count=len(results),
        total_outstanding_amount=total_outstanding,
        control_recovered_amount=control_total,
        treatment_recovered_amount=treatment_total,
        incremental_recovery_amount=incremental,
        control_recovery_rate=control_rate,
        treatment_recovery_rate=treatment_rate,
        treatment_improvement_percent=improvement,
        automation_rate=automation_rate,
        human_review_rate=human_review_rate,
        stopped_rate=stopped_rate,
        evaluation_date=date_value,
    )


def run_experiment(service: Any | None = None) -> ExperimentMetrics:
    """Run control vs treatment on the existing unresolved opportunity batch."""
    if service is None:
        from promise_ledger.api.service import PromiseLedgerService

        service = PromiseLedgerService()
    snapshot = service.snapshot()
    results = [
        service.orchestrate(snapshot, opportunity)
        for opportunity in snapshot.opportunities
    ]
    return evaluate_experiment(
        results,
        snapshot.rows,
        evaluation_date=SIMULATION_DATE.isoformat(),
    )
