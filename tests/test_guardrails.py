import unittest

from promise_ledger.recovery.guardrails import (
    GuardrailEngine,
    GuardrailStatus,
    MerchantPolicy,
)
from promise_ledger.recovery.types import RecoveryAction


class GuardrailEngineTests(unittest.TestCase):
    def setUp(self):
        self.policy = MerchantPolicy(
            merchant_name="Test Merchant",
            maximum_automated_contacts=3,
            minimum_contact_cooldown_days=3,
            maximum_invoice_value_autonomous=15_000.0,
            maximum_payment_plan_duration_days=90,
            human_review_threshold=.70,
        )
        self.engine = GuardrailEngine(self.policy)
        self.context = {
            "current_outstanding_amount": 1_000.0,
            "expected_recovery": 500.0,
            "break_probability": .20,
            "invoice_status": "OVERDUE",
            "promise_outcome": "PENDING",
            "automated_contact_count": 0,
            "evaluation_date": "2026-08-31",
        }

    def evaluate(self, action=RecoveryAction.SOFT_REMINDER, **changes):
        context = {**self.context, **changes}
        return self.engine.evaluate(action, context)

    def test_safe_automated_action_is_allowed(self):
        result = self.evaluate()
        self.assertEqual(result.status, GuardrailStatus.ALLOW)
        self.assertTrue(result.allowed)
        self.assertEqual(result.final_action, RecoveryAction.SOFT_REMINDER)

    def test_maximum_contacts_blocks_automation(self):
        result = self.evaluate(automated_contact_count=3)
        self.assertFalse(result.allowed)
        self.assertEqual(result.final_action, RecoveryAction.HUMAN_REVIEW)
        self.assertEqual(result.reason_code, "MAX_CONTACTS_EXCEEDED")

    def test_contact_cooldown_blocks_automation(self):
        result = self.evaluate(latest_recovery_action_date="2026-08-30")
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason_code, "CONTACT_COOLDOWN_ACTIVE")
        self.assertEqual(result.observed_value, 1)

    def test_high_value_invoice_routes_to_human_review(self):
        result = self.evaluate(current_outstanding_amount=15_001)
        self.assertEqual(result.final_action, RecoveryAction.HUMAN_REVIEW)
        self.assertEqual(result.reason_code, "AUTONOMOUS_VALUE_LIMIT_EXCEEDED")

    def test_human_review_threshold_works(self):
        result = self.evaluate(break_probability=.70)
        self.assertEqual(result.final_action, RecoveryAction.HUMAN_REVIEW)
        self.assertEqual(result.reason_code, "HUMAN_REVIEW_THRESHOLD")

    def test_payment_plan_duration_is_enforced(self):
        result = self.evaluate(RecoveryAction.PAYMENT_PLAN, proposed_payment_plan_duration_days=91)
        self.assertEqual(result.final_action, RecoveryAction.HUMAN_REVIEW)
        self.assertEqual(result.reason_code, "PAYMENT_PLAN_LIMIT_EXCEEDED")

    def test_stop_balance_condition(self):
        result = self.evaluate(current_outstanding_amount=.01)
        self.assertEqual(result.final_action, RecoveryAction.STOP)
        self.assertEqual(result.reason_code, "STOP_BALANCE_TOO_LOW")

    def test_stop_expected_recovery_condition(self):
        result = self.evaluate(expected_recovery=1.0)
        self.assertEqual(result.final_action, RecoveryAction.STOP)
        self.assertEqual(result.reason_code, "STOP_EXPECTED_RECOVERY_TOO_LOW")

    def test_non_actionable_promise_cannot_trigger_recovery(self):
        result = self.evaluate(promise_outcome="BROKEN")
        self.assertEqual(result.final_action, RecoveryAction.STOP)
        self.assertEqual(result.reason_code, "PROMISE_NOT_ACTIONABLE")

    def test_result_contains_explicit_reason_code(self):
        result = self.evaluate()
        self.assertTrue(result.reason_code)
        self.assertIn("reason_code", result.as_dict())

    def test_result_is_deterministic(self):
        first = self.evaluate(latest_recovery_action_date="2026-08-20")
        second = self.evaluate(latest_recovery_action_date="2026-08-20")
        self.assertEqual(first, second)

    def test_blocked_action_has_no_execution_surface(self):
        result = self.evaluate(automated_contact_count=3)
        self.assertFalse(result.allowed)
        self.assertFalse(hasattr(result, "execute"))
        self.assertEqual(result.as_dict()["final_action"], "HUMAN_REVIEW")

    def test_stop_recommendation_cannot_become_automated(self):
        result = self.evaluate(RecoveryAction.STOP)
        self.assertFalse(result.allowed)
        self.assertEqual(result.final_action, RecoveryAction.STOP)

    def test_existing_policy_row_is_supported(self):
        policy = MerchantPolicy.from_row({
            "merchant_name": "Existing",
            "maximum_automated_contacts": 4,
            "minimum_contact_cooldown_days": 3,
            "maximum_invoice_value_autonomous": 15000,
            "maximum_payment_plan_duration_days": 90,
            "human_review_threshold": .70,
        })
        self.assertEqual(policy.maximum_automated_contacts, 4)


if __name__ == "__main__":
    unittest.main()
