import unittest

from promise_ledger.recovery.executor import ActionExecutor
from promise_ledger.recovery.guardrails import GuardrailEngine, GuardrailStatus, MerchantPolicy
from promise_ledger.recovery.types import RecoveryAction, RecoveryDecision


class ActionExecutorTests(unittest.TestCase):
    def setUp(self):
        self.executor = ActionExecutor(GuardrailEngine(MerchantPolicy(
            merchant_name="Test Merchant",
            maximum_automated_contacts=3,
            minimum_contact_cooldown_days=3,
            maximum_invoice_value_autonomous=15_000,
            maximum_payment_plan_duration_days=90,
            human_review_threshold=.70,
        )))
        self.decision = RecoveryDecision(
            promise_id=7,
            customer_id=8,
            recommended_action=RecoveryAction.SOFT_REMINDER,
            reason_codes=("LOW_BREAK_RISK", "ACTIONABLE_BALANCE"),
            explanation="Recommend a soft reminder.",
            confidence=.8,
            expected_recovery=400.0,
            promise_credibility=80.0,
            recovery_probability=.4,
            priority_tier="HIGH",
        )
        self.context = {
            "invoice_id": 9,
            "invoice_amount": 1_000,
            "current_outstanding_amount": 1_000,
            "expected_recovery": 400,
            "break_probability": .2,
            "invoice_status": "OVERDUE",
            "promise_outcome": "PENDING",
            "evaluation_date": "2026-08-31",
            "automated_contact_count": 0,
        }

    def test_allow_produces_simulated_action(self):
        result = self.executor.execute(self.decision, self.context)
        self.assertEqual(result.guardrail.status, GuardrailStatus.ALLOW)
        self.assertTrue(result.audit.simulated)
        self.assertEqual(result.audit.execution_status, "SIMULATED_EXECUTION")
        self.assertEqual(result.audit.final_action, RecoveryAction.SOFT_REMINDER)

    def test_block_produces_no_simulated_execution(self):
        result = self.executor.execute(self.decision, {**self.context, "automated_contact_count": 3})
        self.assertEqual(result.guardrail.status, GuardrailStatus.BLOCK)
        self.assertFalse(result.audit.simulated)
        self.assertEqual(result.audit.execution_status, "BLOCKED_NO_EXECUTION")
        self.assertEqual(result.audit.reason_code, "MAX_CONTACTS_EXCEEDED")

    def test_override_records_original_and_final_actions(self):
        result = self.executor.execute(self.decision, {**self.context, "invoice_amount": 15_001})
        self.assertEqual(result.guardrail.status, GuardrailStatus.OVERRIDE)
        self.assertEqual(result.audit.recommended_action, RecoveryAction.SOFT_REMINDER)
        self.assertEqual(result.audit.final_action, RecoveryAction.HUMAN_REVIEW)
        self.assertEqual(result.audit.execution_status, "OVERRIDDEN_NO_EXECUTION")

    def test_executor_cannot_bypass_guardrails(self):
        result = self.executor.execute(self.decision, {**self.context, "automated_contact_count": 3})
        self.assertEqual(result.guardrail.final_action, RecoveryAction.HUMAN_REVIEW)
        self.assertNotEqual(result.audit.final_action, RecoveryAction.SOFT_REMINDER)

    def test_audit_contains_required_fields(self):
        audit = self.executor.execute(self.decision, self.context).audit.as_dict()
        required = {"audit_id", "evaluation_date", "promise_id", "invoice_id", "customer_id",
                    "recommended_action", "guardrail_status", "final_action", "reason_code",
                    "reason", "simulated", "execution_status", "expected_recovery",
                    "break_probability", "promise_credibility", "priority_tier"}
        self.assertTrue(required.issubset(audit))

    def test_execution_is_deterministic(self):
        first = self.executor.execute(self.decision, self.context)
        second = self.executor.execute(self.decision, self.context)
        self.assertEqual(first, second)
        self.assertEqual(len(first.audit.audit_id), 64)

    def test_missing_evaluation_date_is_rejected(self):
        with self.assertRaises(ValueError):
            self.executor.execute(self.decision, {**self.context, "evaluation_date": None})

    def test_no_side_effect_surface_exists(self):
        result = self.executor.execute(self.decision, self.context)
        self.assertFalse(hasattr(result, "send"))
        self.assertFalse(hasattr(result, "charge"))
        self.assertFalse(hasattr(result, "write_payment"))


if __name__ == "__main__":
    unittest.main()
