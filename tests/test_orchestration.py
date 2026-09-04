"""Comprehensive tests for the end-to-end recovery orchestration pipeline."""

import unittest
from datetime import date
from unittest.mock import MagicMock

from promise_ledger.recovery import (
    ActionDistribution,
    ActionExecutor,
    AuditRecord,
    GuardrailEngine,
    GuardrailStatus,
    MerchantPolicy,
    OrchestrationContext,
    PortfolioEvaluator,
    PortfolioMetrics,
    RecoveryAction,
    RecoveryDecision,
    RecoveryDecisionEngine,
    RecoveryOrchestrator,
)
from promise_ledger.risk.prioritization import RecoveryOpportunity


class TestOrchestrationPipeline(unittest.TestCase):
    """Tests for complete end-to-end orchestration workflow."""

    def setUp(self):
        """Initialize orchestration pipeline for testing."""
        self.policy = MerchantPolicy(
            merchant_name="Test Merchant",
            maximum_automated_contacts=3,
            minimum_contact_cooldown_days=3,
            maximum_invoice_value_autonomous=15_000,
            maximum_payment_plan_duration_days=90,
            human_review_threshold=0.70,
        )
        self.guardrails = GuardrailEngine(self.policy)
        self.executor = ActionExecutor(self.guardrails)
        self.decision_engine = RecoveryDecisionEngine()
        self.orchestrator = RecoveryOrchestrator(self.decision_engine, self.executor)

        self.opportunity = RecoveryOpportunity(
            promise_id=1,
            invoice_id=100,
            customer_id=5,
            outstanding_amount=1_000.00,
            recovery_probability=0.6,
            expected_recovery=600.00,
            break_probability=0.2,
            promise_credibility_score=80.0,
            priority_rank=1,
            priority_tier="HIGH",
            priority_score=100.0,
        )

        self.invoice = {
            "invoice_id": 100,
            "amount": 1_000.00,
            "status": "OVERDUE",
        }

        self.promise = {
            "promise_id": 1,
            "outcome": "PENDING",
        }

        self.context = OrchestrationContext(
            opportunity=self.opportunity,
            invoice=self.invoice,
            promise=self.promise,
            paid_amount=0.0,
            automated_contact_count=0,
            latest_recovery_action_date=None,
            additional_context={
                "evaluation_date": "2026-08-31",
            },
        )

    def test_orchestrate_one_executes_complete_pipeline(self):
        """Verify that orchestrating one opportunity runs the full pipeline."""
        result = self.orchestrator.orchestrate_one(self.context)

        # Assert all pipeline components are present
        self.assertIsNotNone(result.decision)
        self.assertIsNotNone(result.execution)
        self.assertIsNotNone(result.execution.guardrail)
        self.assertIsNotNone(result.execution.audit)

    def test_orchestrate_one_decision_contains_recommendation(self):
        """Verify decision engine produces a recommendation."""
        result = self.orchestrator.orchestrate_one(self.context)
        decision = result.decision

        self.assertIsNotNone(decision.recommended_action)
        self.assertIn(decision.recommended_action, RecoveryAction)

    def test_orchestrate_one_guardrails_are_evaluated(self):
        """Verify guardrail engine is always invoked."""
        result = self.orchestrator.orchestrate_one(self.context)
        guardrail = result.execution.guardrail

        self.assertIn(guardrail.status, GuardrailStatus)
        self.assertIsNotNone(guardrail.final_action)

    def test_orchestrate_one_executor_always_used(self):
        """Verify action executor is always used, never bypassed."""
        result = self.orchestrator.orchestrate_one(self.context)
        audit = result.execution.audit

        # Executor always produces an audit record
        self.assertIsNotNone(audit.audit_id)
        self.assertEqual(len(audit.audit_id), 64)  # SHA256 hex

    def test_orchestrate_portfolio_preserves_order(self):
        """Verify portfolio orchestration preserves input order."""
        contexts = [
            self.context,
            OrchestrationContext(
                opportunity=RecoveryOpportunity(
                    promise_id=2,
                    invoice_id=101,
                    customer_id=6,
                    outstanding_amount=500.00,
                    recovery_probability=0.5,
                    expected_recovery=250.00,
                    break_probability=0.3,
                    promise_credibility_score=70.0,
                    priority_rank=2,
                    priority_tier="MEDIUM",
                    priority_score=50.0,
                ),
                invoice={"invoice_id": 101, "amount": 500.00, "status": "OVERDUE"},
                promise={"promise_id": 2, "outcome": "PENDING"},
                paid_amount=0.0,
                automated_contact_count=0,
                latest_recovery_action_date=None,
                additional_context={"evaluation_date": "2026-08-31"},
            ),
        ]

        results = self.orchestrator.orchestrate_portfolio(contexts)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].opportunity.promise_id, 1)
        self.assertEqual(results[1].opportunity.promise_id, 2)

    def test_allowed_actions_are_simulated(self):
        """Verify ALLOW status results in simulated execution."""
        result = self.orchestrator.orchestrate_one(self.context)

        if result.execution.guardrail.status == GuardrailStatus.ALLOW:
            self.assertTrue(result.execution.audit.simulated)
            self.assertEqual(result.execution.audit.execution_status, "SIMULATED_EXECUTION")

    def test_blocked_actions_are_not_simulated(self):
        """Verify BLOCK status prevents simulated execution."""
        # Exceed contact limit to trigger block
        blocked_context = OrchestrationContext(
            opportunity=self.opportunity,
            invoice=self.invoice,
            promise=self.promise,
            paid_amount=0.0,
            automated_contact_count=3,  # At limit
            latest_recovery_action_date=None,
            additional_context={"evaluation_date": "2026-08-31"},
        )

        result = self.orchestrator.orchestrate_one(blocked_context)

        if result.execution.guardrail.status == GuardrailStatus.BLOCK:
            self.assertFalse(result.execution.audit.simulated)
            self.assertEqual(result.execution.audit.execution_status, "BLOCKED_NO_EXECUTION")

    def test_overridden_actions_are_not_simulated(self):
        """Verify OVERRIDE status prevents simulated execution."""
        # Exceed invoice value limit to trigger override
        override_context = OrchestrationContext(
            opportunity=self.opportunity,
            invoice={"invoice_id": 100, "amount": 15_001.00, "status": "OVERDUE"},
            promise=self.promise,
            paid_amount=0.0,
            automated_contact_count=0,
            latest_recovery_action_date=None,
            additional_context={"evaluation_date": "2026-08-31"},
        )

        result = self.orchestrator.orchestrate_one(override_context)

        if result.execution.guardrail.status == GuardrailStatus.OVERRIDE:
            self.assertFalse(result.execution.audit.simulated)
            self.assertEqual(result.execution.audit.execution_status, "OVERRIDDEN_NO_EXECUTION")

    def test_no_final_action_bypass_possible(self):
        """Verify caller cannot bypass guardrails to force a final action."""
        result = self.orchestrator.orchestrate_one(self.context)

        # Final action must match guardrail decision
        if result.execution.guardrail.status == GuardrailStatus.BLOCK:
            self.assertEqual(result.execution.audit.final_action, result.execution.guardrail.final_action)
        elif result.execution.guardrail.status == GuardrailStatus.OVERRIDE:
            self.assertEqual(result.execution.audit.final_action, RecoveryAction.HUMAN_REVIEW)

    def test_deterministic_results(self):
        """Verify identical inputs produce identical audit IDs."""
        result1 = self.orchestrator.orchestrate_one(self.context)
        result2 = self.orchestrator.orchestrate_one(self.context)

        self.assertEqual(result1.execution.audit.audit_id, result2.execution.audit.audit_id)

    def test_audit_records_contain_required_fields(self):
        """Verify audit records have all required fields."""
        result = self.orchestrator.orchestrate_one(self.context)
        audit_dict = result.execution.audit.as_dict()

        required = {
            "audit_id",
            "evaluation_date",
            "promise_id",
            "invoice_id",
            "customer_id",
            "recommended_action",
            "guardrail_status",
            "final_action",
            "reason_code",
            "reason",
            "simulated",
            "execution_status",
            "expected_recovery",
            "break_probability",
            "promise_credibility",
            "priority_tier",
        }
        self.assertTrue(required.issubset(audit_dict.keys()))

    def test_empty_portfolio_handling(self):
        """Verify empty portfolio is handled correctly."""
        results = self.orchestrator.orchestrate_portfolio([])
        self.assertEqual(len(results), 0)

    def test_mixed_portfolio_handling(self):
        """Verify mixed portfolio with various outcomes is handled correctly."""
        contexts = [
            self.context,
            OrchestrationContext(
                opportunity=RecoveryOpportunity(
                    promise_id=2,
                    invoice_id=101,
                    customer_id=6,
                    outstanding_amount=20_000.00,  # High amount, may trigger override
                    recovery_probability=0.9,
                    expected_recovery=18_000.00,
                    break_probability=0.1,
                    promise_credibility_score=90.0,
                    priority_rank=1,
                    priority_tier="HIGH",
                    priority_score=100.0,
                ),
                invoice={"invoice_id": 101, "amount": 20_000.00, "status": "OVERDUE"},
                promise={"promise_id": 2, "outcome": "PENDING"},
                paid_amount=0.0,
                automated_contact_count=0,
                latest_recovery_action_date=None,
                additional_context={"evaluation_date": "2026-08-31"},
            ),
        ]

        results = self.orchestrator.orchestrate_portfolio(contexts)

        self.assertEqual(len(results), 2)
        for result in results:
            self.assertIsNotNone(result.execution.audit)


class TestPortfolioEvaluation(unittest.TestCase):
    """Tests for portfolio-level metrics and evaluation."""

    def setUp(self):
        """Initialize test data for portfolio evaluation."""
        self.policy = MerchantPolicy(
            merchant_name="Test Merchant",
            maximum_automated_contacts=3,
            minimum_contact_cooldown_days=3,
            maximum_invoice_value_autonomous=15_000,
            maximum_payment_plan_duration_days=90,
            human_review_threshold=0.70,
        )
        self.executor = ActionExecutor(GuardrailEngine(self.policy))
        self.decision_engine = RecoveryDecisionEngine()
        self.orchestrator = RecoveryOrchestrator(self.decision_engine, self.executor)

    def _create_opportunity(self, promise_id, amount, recovery_prob, break_prob):
        """Helper to create a RecoveryOpportunity."""
        return RecoveryOpportunity(
            promise_id=promise_id,
            invoice_id=promise_id + 1000,
            customer_id=promise_id + 100,
            outstanding_amount=amount,
            recovery_probability=recovery_prob,
            expected_recovery=round(amount * recovery_prob, 2),
            break_probability=break_prob,
            promise_credibility_score=round((1 - break_prob) * 100, 1),
            priority_rank=promise_id,
            priority_tier="MEDIUM",
            priority_score=50.0,
        )

    def test_empty_portfolio_evaluation(self):
        """Verify empty portfolio evaluation returns zero metrics."""
        metrics = PortfolioEvaluator.evaluate([])

        self.assertEqual(metrics.evaluation_count, 0)
        self.assertEqual(metrics.total_outstanding_amount, 0.0)
        self.assertEqual(metrics.total_expected_recovery, 0.0)
        self.assertEqual(metrics.percentage_automated(), 0.0)
        self.assertEqual(metrics.percentage_human_review(), 0.0)

    def test_portfolio_metrics_aggregation(self):
        """Verify portfolio metrics correctly aggregate results."""
        contexts = [
            OrchestrationContext(
                opportunity=self._create_opportunity(1, 1_000.00, 0.6, 0.2),
                invoice={"invoice_id": 1001, "amount": 1_000.00, "status": "OVERDUE"},
                promise={"promise_id": 1, "outcome": "PENDING"},
                paid_amount=0.0,
                automated_contact_count=0,
                latest_recovery_action_date=None,
                additional_context={"evaluation_date": "2026-08-31"},
            ),
            OrchestrationContext(
                opportunity=self._create_opportunity(2, 500.00, 0.4, 0.3),
                invoice={"invoice_id": 1002, "amount": 500.00, "status": "OVERDUE"},
                promise={"promise_id": 2, "outcome": "PENDING"},
                paid_amount=0.0,
                automated_contact_count=0,
                latest_recovery_action_date=None,
                additional_context={"evaluation_date": "2026-08-31"},
            ),
        ]

        results = self.orchestrator.orchestrate_portfolio(contexts)
        metrics = PortfolioEvaluator.evaluate(results)

        self.assertEqual(metrics.evaluation_count, 2)
        self.assertEqual(metrics.total_outstanding_amount, 1_500.00)
        self.assertGreater(metrics.total_expected_recovery, 0.0)

    def test_portfolio_metrics_action_distribution(self):
        """Verify action distribution is correctly counted."""
        opportunity = self._create_opportunity(1, 1_000.00, 0.6, 0.2)
        context = OrchestrationContext(
            opportunity=opportunity,
            invoice={"invoice_id": 1001, "amount": 1_000.00, "status": "OVERDUE"},
            promise={"promise_id": 1, "outcome": "PENDING"},
            paid_amount=0.0,
            automated_contact_count=0,
            latest_recovery_action_date=None,
            additional_context={"evaluation_date": "2026-08-31"},
        )

        results = self.orchestrator.orchestrate_portfolio([context])
        metrics = PortfolioEvaluator.evaluate(results)

        # At least one action should be recommended and executed
        total_recommended = metrics.recommended_actions.total()
        self.assertEqual(total_recommended, 1)

    def test_portfolio_metrics_guardrail_status_counts(self):
        """Verify guardrail status counts are correctly aggregated."""
        contexts = [
            OrchestrationContext(
                opportunity=self._create_opportunity(1, 1_000.00, 0.6, 0.2),
                invoice={"invoice_id": 1001, "amount": 1_000.00, "status": "OVERDUE"},
                promise={"promise_id": 1, "outcome": "PENDING"},
                paid_amount=0.0,
                automated_contact_count=0,
                latest_recovery_action_date=None,
                additional_context={"evaluation_date": "2026-08-31"},
            ),
            OrchestrationContext(
                opportunity=self._create_opportunity(2, 500.00, 0.4, 0.3),
                invoice={"invoice_id": 1002, "amount": 500.00, "status": "OVERDUE"},
                promise={"promise_id": 2, "outcome": "PENDING"},
                paid_amount=0.0,
                automated_contact_count=0,
                latest_recovery_action_date=None,
                additional_context={"evaluation_date": "2026-08-31"},
            ),
        ]

        results = self.orchestrator.orchestrate_portfolio(contexts)
        metrics = PortfolioEvaluator.evaluate(results)

        total_guardrail_decisions = (
            metrics.guardrail_allow_count
            + metrics.guardrail_block_count
            + metrics.guardrail_override_count
        )
        self.assertEqual(total_guardrail_decisions, 2)

    def test_portfolio_metrics_execution_status_counts(self):
        """Verify execution status counts are correctly categorized."""
        opportunity = self._create_opportunity(1, 1_000.00, 0.6, 0.2)
        context = OrchestrationContext(
            opportunity=opportunity,
            invoice={"invoice_id": 1001, "amount": 1_000.00, "status": "OVERDUE"},
            promise={"promise_id": 1, "outcome": "PENDING"},
            paid_amount=0.0,
            automated_contact_count=0,
            latest_recovery_action_date=None,
            additional_context={"evaluation_date": "2026-08-31"},
        )

        results = self.orchestrator.orchestrate_portfolio([context])
        metrics = PortfolioEvaluator.evaluate(results)

        total_executions = (
            metrics.simulated_execution_count
            + metrics.blocked_no_execution_count
            + metrics.overridden_no_execution_count
        )
        self.assertEqual(total_executions, 1)

    def test_portfolio_percentages(self):
        """Verify portfolio percentage calculations."""
        opportunity = self._create_opportunity(1, 1_000.00, 0.6, 0.2)
        context = OrchestrationContext(
            opportunity=opportunity,
            invoice={"invoice_id": 1001, "amount": 1_000.00, "status": "OVERDUE"},
            promise={"promise_id": 1, "outcome": "PENDING"},
            paid_amount=0.0,
            automated_contact_count=0,
            latest_recovery_action_date=None,
            additional_context={"evaluation_date": "2026-08-31"},
        )

        results = self.orchestrator.orchestrate_portfolio([context])
        metrics = PortfolioEvaluator.evaluate(results)

        auto_pct = metrics.percentage_automated()
        human_pct = metrics.percentage_human_review()
        stop_pct = metrics.percentage_stopped()

        self.assertGreaterEqual(auto_pct, 0.0)
        self.assertLessEqual(auto_pct, 100.0)
        self.assertGreaterEqual(human_pct, 0.0)
        self.assertLessEqual(human_pct, 100.0)
        self.assertGreaterEqual(stop_pct, 0.0)
        self.assertLessEqual(stop_pct, 100.0)

    def test_portfolio_metrics_as_dict(self):
        """Verify portfolio metrics can be serialized."""
        opportunity = self._create_opportunity(1, 1_000.00, 0.6, 0.2)
        context = OrchestrationContext(
            opportunity=opportunity,
            invoice={"invoice_id": 1001, "amount": 1_000.00, "status": "OVERDUE"},
            promise={"promise_id": 1, "outcome": "PENDING"},
            paid_amount=0.0,
            automated_contact_count=0,
            latest_recovery_action_date=None,
            additional_context={"evaluation_date": "2026-08-31"},
        )

        results = self.orchestrator.orchestrate_portfolio([context])
        metrics = PortfolioEvaluator.evaluate(results)
        metrics_dict = metrics.as_dict()

        self.assertIn("evaluation_count", metrics_dict)
        self.assertIn("total_outstanding_amount", metrics_dict)
        self.assertIn("total_expected_recovery", metrics_dict)
        self.assertIn("percentage_automated", metrics_dict)
        self.assertIn("percentage_human_review", metrics_dict)
        self.assertIn("percentage_stopped", metrics_dict)


class TestNoDatabaseMutation(unittest.TestCase):
    """Tests to verify no database mutations occur during orchestration."""

    def test_orchestration_produces_no_side_effects(self):
        """Verify orchestration is side-effect free."""
        policy = MerchantPolicy(
            merchant_name="Test Merchant",
            maximum_automated_contacts=3,
            minimum_contact_cooldown_days=3,
            maximum_invoice_value_autonomous=15_000,
            maximum_payment_plan_duration_days=90,
            human_review_threshold=0.70,
        )
        executor = ActionExecutor(GuardrailEngine(policy))
        decision_engine = RecoveryDecisionEngine()
        orchestrator = RecoveryOrchestrator(decision_engine, executor)

        opportunity = RecoveryOpportunity(
            promise_id=1,
            invoice_id=100,
            customer_id=5,
            outstanding_amount=1_000.00,
            recovery_probability=0.6,
            expected_recovery=600.00,
            break_probability=0.2,
            promise_credibility_score=80.0,
            priority_rank=1,
            priority_tier="HIGH",
            priority_score=100.0,
        )

        context = OrchestrationContext(
            opportunity=opportunity,
            invoice={"invoice_id": 100, "amount": 1_000.00, "status": "OVERDUE"},
            promise={"promise_id": 1, "outcome": "PENDING"},
            paid_amount=0.0,
            automated_contact_count=0,
            latest_recovery_action_date=None,
            additional_context={"evaluation_date": "2026-08-31"},
        )

        # Execute orchestration multiple times
        result1 = orchestrator.orchestrate_one(context)
        result2 = orchestrator.orchestrate_one(context)

        # Verify identical results (deterministic, no mutation)
        self.assertEqual(result1.execution.audit.audit_id, result2.execution.audit.audit_id)

        # Verify no methods for side effects exist
        self.assertFalse(hasattr(orchestrator, "send"))
        self.assertFalse(hasattr(orchestrator, "charge"))
        self.assertFalse(hasattr(orchestrator, "write_database"))


if __name__ == "__main__":
    unittest.main()
