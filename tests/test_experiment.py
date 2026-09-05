"""Focused tests for the control vs AI-treatment evaluation experiment."""

import unittest
from datetime import date

from promise_ledger.config import SIMULATION_DATE
from promise_ledger.evaluation.experiment import (
    ACTION_MULTIPLIERS,
    OutcomeClass,
    classify_outcome,
    control_recovered_amount,
    evaluate_experiment,
    treatment_recovered_amount,
)
from promise_ledger.recovery.executor import AuditRecord, ExecutionResult
from promise_ledger.recovery.guardrails import GuardrailResult, GuardrailStatus
from promise_ledger.recovery.orchestration import OrchestrationResult
from promise_ledger.recovery.types import RecoveryAction, RecoveryDecision
from promise_ledger.risk.prioritization import RecoveryOpportunity, expected_recovery


class ControlCalculationTests(unittest.TestCase):
    def test_control_uses_historical_recovery_rate_only(self):
        self.assertEqual(control_recovered_amount(1_000.0, 0.40), 400.0)

    def test_control_clamps_recovery_rate(self):
        self.assertEqual(control_recovered_amount(1_000.0, 1.50), 1_000.0)
        self.assertEqual(control_recovered_amount(1_000.0, -0.20), 0.0)


class TreatmentCalculationTests(unittest.TestCase):
    def test_treatment_multiplies_existing_probability(self):
        recovered = treatment_recovered_amount(
            1_000.0, 0.50, RecoveryAction.FIRM_REMINDER, "SIMULATED_EXECUTION"
        )
        self.assertEqual(recovered, expected_recovery(1_000.0, 0.55))

    def test_treatment_clamps_adjusted_probability(self):
        recovered = treatment_recovered_amount(
            1_000.0, 0.95, RecoveryAction.ESCALATE, "SIMULATED_EXECUTION"
        )
        self.assertEqual(recovered, 1_000.0)

    def test_simulated_human_review_uses_multiplier(self):
        recovered = treatment_recovered_amount(
            1_000.0, 0.50, RecoveryAction.HUMAN_REVIEW, "SIMULATED_EXECUTION"
        )
        self.assertEqual(recovered, expected_recovery(1_000.0, 0.54))


class ActionMultiplierTests(unittest.TestCase):
    def test_published_multipliers(self):
        self.assertEqual(ACTION_MULTIPLIERS[RecoveryAction.SOFT_REMINDER], 1.05)
        self.assertEqual(ACTION_MULTIPLIERS[RecoveryAction.FIRM_REMINDER], 1.10)
        self.assertEqual(ACTION_MULTIPLIERS[RecoveryAction.PAYMENT_PLAN], 1.15)
        self.assertEqual(ACTION_MULTIPLIERS[RecoveryAction.ESCALATE], 1.20)
        self.assertEqual(ACTION_MULTIPLIERS[RecoveryAction.HUMAN_REVIEW], 1.08)
        self.assertEqual(ACTION_MULTIPLIERS[RecoveryAction.STOP], 0.0)

    def test_each_simulated_action_applies_its_multiplier(self):
        outstanding = 1_000.0
        probability = 0.40
        expected = {
            RecoveryAction.SOFT_REMINDER: expected_recovery(outstanding, 0.42),
            RecoveryAction.FIRM_REMINDER: expected_recovery(outstanding, 0.44),
            RecoveryAction.PAYMENT_PLAN: expected_recovery(outstanding, 0.46),
            RecoveryAction.ESCALATE: expected_recovery(outstanding, 0.48),
            RecoveryAction.HUMAN_REVIEW: expected_recovery(outstanding, 0.432),
            RecoveryAction.STOP: 0.0,
        }
        for action, amount in expected.items():
            self.assertEqual(
                treatment_recovered_amount(outstanding, probability, action, "SIMULATED_EXECUTION"),
                amount,
                msg=action.value,
            )


class BlockedAndOverriddenTests(unittest.TestCase):
    def test_blocked_produces_zero_treatment_recovery(self):
        self.assertEqual(
            treatment_recovered_amount(
                1_000.0, 0.80, RecoveryAction.FIRM_REMINDER, "BLOCKED_NO_EXECUTION"
            ),
            0.0,
        )

    def test_overridden_produces_zero_treatment_recovery(self):
        self.assertEqual(
            treatment_recovered_amount(
                1_000.0, 0.80, RecoveryAction.HUMAN_REVIEW, "OVERRIDDEN_NO_EXECUTION"
            ),
            0.0,
        )

    def test_blocked_non_stop_is_human_review_outcome(self):
        self.assertEqual(
            classify_outcome(RecoveryAction.FIRM_REMINDER, "BLOCKED_NO_EXECUTION"),
            OutcomeClass.HUMAN_REVIEW,
        )
        self.assertEqual(
            classify_outcome(RecoveryAction.HUMAN_REVIEW, "OVERRIDDEN_NO_EXECUTION"),
            OutcomeClass.HUMAN_REVIEW,
        )


class StopTests(unittest.TestCase):
    def test_stop_produces_zero_treatment_recovery(self):
        self.assertEqual(
            treatment_recovered_amount(
                1_000.0, 0.90, RecoveryAction.STOP, "SIMULATED_EXECUTION"
            ),
            0.0,
        )

    def test_stop_is_stopped_even_when_simulated(self):
        self.assertEqual(
            classify_outcome(RecoveryAction.STOP, "SIMULATED_EXECUTION"),
            OutcomeClass.STOPPED,
        )

    def test_overridden_stop_is_still_stopped(self):
        self.assertEqual(
            classify_outcome(RecoveryAction.STOP, "OVERRIDDEN_NO_EXECUTION"),
            OutcomeClass.STOPPED,
        )


class ExperimentAggregationTests(unittest.TestCase):
    def _opportunity(self, promise_id: int, outstanding: float, recovery_probability: float) -> RecoveryOpportunity:
        return RecoveryOpportunity(
            promise_id=promise_id,
            invoice_id=promise_id + 100,
            customer_id=promise_id,
            outstanding_amount=outstanding,
            recovery_probability=recovery_probability,
            expected_recovery=expected_recovery(outstanding, recovery_probability),
            break_probability=0.20,
            promise_credibility_score=80.0,
            priority_rank=promise_id,
            priority_tier="HIGH",
            priority_score=100.0,
        )

    def _result(
        self,
        promise_id: int,
        outstanding: float,
        recovery_probability: float,
        final_action: RecoveryAction,
        execution_status: str,
        recommended_action: RecoveryAction | None = None,
    ) -> OrchestrationResult:
        recommended = recommended_action or final_action
        if execution_status == "SIMULATED_EXECUTION":
            status = GuardrailStatus.ALLOW
        elif execution_status == "BLOCKED_NO_EXECUTION":
            status = GuardrailStatus.BLOCK
        else:
            status = GuardrailStatus.OVERRIDE
        opportunity = self._opportunity(promise_id, outstanding, recovery_probability)
        decision = RecoveryDecision(
            promise_id=promise_id,
            customer_id=promise_id,
            recommended_action=recommended,
            reason_codes=("TEST",),
            explanation="Test decision.",
            confidence=0.80,
            expected_recovery=opportunity.expected_recovery,
            promise_credibility=80.0,
            recovery_probability=recovery_probability,
            priority_tier="HIGH",
        )
        guardrail = GuardrailResult(
            recommended_action=recommended,
            final_action=final_action,
            status=status,
            allowed=status is GuardrailStatus.ALLOW,
            reason_code="TEST",
            reason="Test guardrail.",
        )
        audit = AuditRecord(
            audit_id=f"test-{promise_id}",
            evaluation_date=SIMULATION_DATE.isoformat(),
            promise_id=promise_id,
            invoice_id=opportunity.invoice_id,
            customer_id=promise_id,
            recommended_action=recommended,
            guardrail_status=status,
            final_action=final_action,
            reason_code="TEST",
            reason="Test guardrail.",
            expected_recovery=opportunity.expected_recovery,
            break_probability=0.20,
            promise_credibility=80.0,
            priority_tier="HIGH",
            simulated=execution_status == "SIMULATED_EXECUTION",
            execution_status=execution_status,
        )
        return OrchestrationResult(
            opportunity=opportunity,
            decision=decision,
            execution=ExecutionResult(guardrail=guardrail, audit=audit),
            evaluation_timestamp=SIMULATION_DATE.isoformat(),
        )

    def test_mutually_exclusive_outcome_percentages_sum_to_100(self):
        results = [
            self._result(1, 1_000.0, 0.50, RecoveryAction.SOFT_REMINDER, "SIMULATED_EXECUTION"),
            self._result(2, 1_000.0, 0.50, RecoveryAction.HUMAN_REVIEW, "SIMULATED_EXECUTION"),
            self._result(3, 1_000.0, 0.50, RecoveryAction.STOP, "SIMULATED_EXECUTION"),
            self._result(4, 1_000.0, 0.50, RecoveryAction.FIRM_REMINDER, "BLOCKED_NO_EXECUTION"),
        ]
        rows = {i: {"historical_recovery_rate": 0.20} for i in range(1, 5)}
        metrics = evaluate_experiment(results, rows)
        self.assertEqual(metrics.evaluation_count, 4)
        self.assertEqual(metrics.automation_rate, 25.0)
        self.assertEqual(metrics.stopped_rate, 25.0)
        self.assertEqual(metrics.human_review_rate, 50.0)
        self.assertEqual(
            metrics.automation_rate + metrics.human_review_rate + metrics.stopped_rate,
            100.0,
        )

    def test_zero_control_recovery_sets_improvement_to_zero(self):
        results = [
            self._result(1, 1_000.0, 0.50, RecoveryAction.SOFT_REMINDER, "SIMULATED_EXECUTION"),
        ]
        metrics = evaluate_experiment(results, {1: {"historical_recovery_rate": 0.0}})
        self.assertEqual(metrics.control_recovered_amount, 0.0)
        self.assertGreater(metrics.treatment_recovered_amount, 0.0)
        self.assertEqual(metrics.treatment_improvement_percent, 0.0)

    def test_empty_results_are_zero(self):
        metrics = evaluate_experiment([], {})
        self.assertEqual(metrics.evaluation_count, 0)
        self.assertEqual(metrics.total_outstanding_amount, 0.0)
        self.assertEqual(metrics.control_recovered_amount, 0.0)
        self.assertEqual(metrics.treatment_recovered_amount, 0.0)
        self.assertEqual(metrics.treatment_improvement_percent, 0.0)
        self.assertEqual(metrics.automation_rate + metrics.human_review_rate + metrics.stopped_rate, 0.0)

    def test_recovery_rates_use_outstanding_denominator(self):
        results = [
            self._result(1, 800.0, 0.50, RecoveryAction.SOFT_REMINDER, "SIMULATED_EXECUTION"),
            self._result(2, 200.0, 0.50, RecoveryAction.STOP, "SIMULATED_EXECUTION"),
        ]
        rows = {
            1: {"historical_recovery_rate": 0.25},
            2: {"historical_recovery_rate": 0.25},
        }
        metrics = evaluate_experiment(results, rows)
        self.assertEqual(metrics.total_outstanding_amount, 1_000.0)
        self.assertEqual(metrics.control_recovered_amount, 250.0)
        self.assertEqual(metrics.control_recovery_rate, 0.25)
        treatment = expected_recovery(800.0, 0.525)
        self.assertEqual(metrics.treatment_recovered_amount, treatment)
        self.assertEqual(metrics.treatment_recovery_rate, round(treatment / 1_000.0, 4))

    def test_results_are_deterministic_and_use_simulation_date(self):
        results = [
            self._result(1, 1_000.0, 0.40, RecoveryAction.ESCALATE, "SIMULATED_EXECUTION"),
            self._result(2, 500.0, 0.60, RecoveryAction.HUMAN_REVIEW, "OVERRIDDEN_NO_EXECUTION"),
        ]
        rows = {
            1: {"historical_recovery_rate": 0.30},
            2: {"historical_recovery_rate": 0.10},
        }
        first = evaluate_experiment(results, rows)
        second = evaluate_experiment(results, rows)
        self.assertEqual(first, second)
        self.assertEqual(first.evaluation_date, SIMULATION_DATE.isoformat())
        self.assertEqual(first.evaluation_date, "2026-08-31")
        self.assertNotEqual(first.evaluation_date, date.today().isoformat())
        self.assertEqual(first.control_recovered_amount, 350.0)
        self.assertEqual(first.treatment_recovered_amount, expected_recovery(1_000.0, 0.48))


if __name__ == "__main__":
    unittest.main()
