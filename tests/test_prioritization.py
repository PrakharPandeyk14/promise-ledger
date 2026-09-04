import unittest

from promise_ledger.risk.prioritization import expected_recovery, prioritize_opportunities
from promise_ledger.risk.scoring import PromiseScore


class PrioritizationTests(unittest.TestCase):
    def _score(self, promise_id, recovery, break_probability=0.5):
        return PromiseScore(
            promise_id=promise_id,
            break_probability=break_probability,
            promise_credibility_score=(1 - break_probability) * 100,
            recovery_probability=recovery,
            explanation=(),
        )

    def test_expected_recovery_is_amount_times_probability(self):
        self.assertEqual(expected_recovery(500_000, 0.62), 310_000.00)

    def test_expected_recovery_is_clamped(self):
        self.assertEqual(expected_recovery(-100, 0.5), 0.0)
        self.assertEqual(expected_recovery(100, -1), 0.0)
        self.assertEqual(expected_recovery(100, 2), 100.0)

    def test_rank_uses_expected_recovery_not_raw_outstanding(self):
        rows = [
            {"promise_id": 1, "invoice_id": 11, "customer_id": 101, "outstanding_amount_at_promise_creation": 500_000},
            {"promise_id": 2, "invoice_id": 12, "customer_id": 102, "outstanding_amount_at_promise_creation": 200_000},
        ]
        scores = [self._score(1, 0.50), self._score(2, 0.95)]
        ranked = prioritize_opportunities(rows, scores)
        self.assertEqual([item.promise_id for item in ranked], [1, 2])
        self.assertEqual(ranked[0].expected_recovery, 250_000.0)
        self.assertEqual(ranked[1].expected_recovery, 190_000.0)

    def test_ties_are_deterministic(self):
        rows = [
            {"promise_id": 2, "invoice_id": 12, "customer_id": 102, "outstanding_amount_at_promise_creation": 100},
            {"promise_id": 1, "invoice_id": 11, "customer_id": 101, "outstanding_amount_at_promise_creation": 100},
        ]
        scores = [self._score(2, 0.5), self._score(1, 0.5)]
        ranked = prioritize_opportunities(rows, scores)
        self.assertEqual([item.promise_id for item in ranked], [1, 2])

    def test_rank_and_tier_are_assigned(self):
        rows = [
            {"promise_id": i, "invoice_id": 10 + i, "customer_id": 100 + i, "outstanding_amount_at_promise_creation": 1000 - i * 100}
            for i in range(1, 7)
        ]
        scores = [self._score(i, 0.5) for i in range(1, 7)]
        ranked = prioritize_opportunities(rows, scores)
        self.assertEqual([item.priority_rank for item in ranked], list(range(1, 7)))
        self.assertEqual(ranked[0].priority_tier, "HIGH")
        self.assertEqual(ranked[-1].priority_tier, "LOW")
        self.assertEqual(ranked[0].priority_score, 100.0)

    def test_missing_row_is_rejected(self):
        with self.assertRaises(ValueError):
            prioritize_opportunities([], [self._score(99, 0.5)])


if __name__ == "__main__":
    unittest.main()
