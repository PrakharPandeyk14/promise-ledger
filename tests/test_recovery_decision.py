import inspect
import unittest

from promise_ledger.recovery.config import DEFAULT_DECISION_CONFIG, DecisionConfig
from promise_ledger.recovery.decision import RecoveryDecisionEngine
from promise_ledger.recovery.types import RecoveryAction, RecoveryDecision


class RecoveryDecisionTests(unittest.TestCase):
    def opportunity(self, **changes):
        value = {
            "promise_id": 1,
            "customer_id": 10,
            "outstanding_amount": 1000.0,
            "expected_recovery": 500.0,
            "promise_credibility_score": 50.0,
            "recovery_probability": 0.50,
            "break_probability": 0.50,
            "priority_tier": "MEDIUM",
        }
        value.update(changes)
        return value

    def test_low_risk_actionable_promise_is_soft_reminder(self):
        decision = RecoveryDecisionEngine().decide(self.opportunity(
            expected_recovery=700, promise_credibility_score=85,
            recovery_probability=.70, break_probability=.15,
        ))
        self.assertEqual(decision.recommended_action, RecoveryAction.SOFT_REMINDER)

    def test_elevated_risk_actionable_promise_is_firm_reminder(self):
        decision = RecoveryDecisionEngine().decide(self.opportunity(
            expected_recovery=500, promise_credibility_score=35,
            recovery_probability=.50, break_probability=.65,
        ))
        self.assertEqual(decision.recommended_action, RecoveryAction.FIRM_REMINDER)

    def test_low_immediate_credibility_with_history_is_payment_plan(self):
        decision = RecoveryDecisionEngine().decide(
            self.opportunity(promise_credibility_score=40, break_probability=.60, recovery_probability=.50),
            {"previous_promise_count": 2},
        )
        self.assertEqual(decision.recommended_action, RecoveryAction.PAYMENT_PLAN)

    def test_high_exposure_ambiguous_case_is_human_review(self):
        decision = RecoveryDecisionEngine().decide(
            self.opportunity(outstanding_amount=150_000, expected_recovery=75_000),
            {"previous_promise_count": 4, "historical_promise_keep_rate": .50},
        )
        self.assertEqual(decision.recommended_action, RecoveryAction.HUMAN_REVIEW)

    def test_high_risk_high_priority_case_is_escalated(self):
        decision = RecoveryDecisionEngine().decide(self.opportunity(
            break_probability=.80, recovery_probability=.50,
            promise_credibility_score=20, priority_tier="HIGH",
        ))
        self.assertEqual(decision.recommended_action, RecoveryAction.ESCALATE)

    def test_negligible_recovery_is_stop(self):
        decision = RecoveryDecisionEngine().decide(self.opportunity(
            outstanding_amount=10, expected_recovery=.50, recovery_probability=.01,
        ))
        self.assertEqual(decision.recommended_action, RecoveryAction.STOP)

    def test_zero_balance_is_stop(self):
        decision = RecoveryDecisionEngine().decide(self.opportunity(
            outstanding_amount=0, expected_recovery=0,
        ))
        self.assertEqual(decision.recommended_action, RecoveryAction.STOP)

    def test_output_contains_required_fields(self):
        result = RecoveryDecisionEngine().decide(self.opportunity())
        self.assertTrue({"promise_id", "customer_id", "recommended_action", "reason_codes",
                         "explanation", "confidence", "expected_recovery", "promise_credibility",
                         "recovery_probability", "priority_tier"}.issubset(result.as_dict()))

    def test_reason_codes_match_decision(self):
        cases = {
            RecoveryAction.STOP: (self.opportunity(outstanding_amount=0, expected_recovery=0), None, {"NO_ACTIONABLE_RECOVERY"}),
            RecoveryAction.HUMAN_REVIEW: (self.opportunity(outstanding_amount=200_000), None, {"HIGH_EXPOSURE"}),
            RecoveryAction.ESCALATE: (self.opportunity(break_probability=.8, recovery_probability=.5, priority_tier="HIGH"), None, {"HIGH_BREAK_RISK", "HIGH_PRIORITY"}),
            RecoveryAction.PAYMENT_PLAN: (self.opportunity(promise_credibility_score=40, break_probability=.6), {"previous_promise_count": 2}, {"LOW_IMMEDIATE_CREDIBILITY", "ACTIONABLE_BALANCE"}),
            RecoveryAction.FIRM_REMINDER: (self.opportunity(break_probability=.65), None, {"HIGH_BREAK_RISK", "ACTIONABLE_BALANCE"}),
            RecoveryAction.SOFT_REMINDER: (self.opportunity(break_probability=.1, promise_credibility_score=90), None, {"LOW_BREAK_RISK", "ACTIONABLE_BALANCE"}),
        }
        for action, (opportunity, context, expected_reasons) in cases.items():
            decision = RecoveryDecisionEngine().decide(opportunity, context)
            self.assertEqual(decision.recommended_action, action)
            self.assertTrue(expected_reasons.issubset(set(decision.reason_codes)))
            self.assertTrue(decision.explanation)

    def test_repeated_identical_input_is_identical(self):
        engine = RecoveryDecisionEngine()
        first = engine.decide(self.opportunity(), {"previous_promise_count": 2})
        second = engine.decide(self.opportunity(), {"previous_promise_count": 2})
        self.assertEqual(first, second)

    def test_thresholds_are_centralized(self):
        fields = set(DecisionConfig.__dataclass_fields__)
        self.assertGreaterEqual(len(fields), 10)
        self.assertIs(DEFAULT_DECISION_CONFIG.__class__, DecisionConfig)
        self.assertNotIn("100000", inspect.getsource(RecoveryDecisionEngine.decide))

    def test_current_promise_outcome_does_not_change_decision(self):
        engine = RecoveryDecisionEngine()
        base = engine.decide(self.opportunity(), {"previous_promise_count": 2})
        altered = engine.decide(self.opportunity(), {"previous_promise_count": 2, "outcome": "BROKEN", "target_broken": 1})
        self.assertEqual(base, altered)

    def test_simulator_parameters_and_persona_labels_are_not_inputs(self):
        signature = inspect.signature(RecoveryDecisionEngine.decide)
        self.assertEqual(list(signature.parameters), ["self", "opportunity", "context"])
        self.assertNotIn("persona", inspect.getsource(RecoveryDecisionEngine.decide).lower())
        self.assertNotIn("tendency", inspect.getsource(RecoveryDecisionEngine.decide).lower())


if __name__ == "__main__":
    unittest.main()
