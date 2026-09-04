import unittest

from promise_ledger.risk.scoring import score_promise, score_rows


class RiskScoringTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "promise_id": 10,
            "previous_promise_count": 6,
            "previous_promises_kept": 2,
            "previous_promises_broken": 4,
            "historical_promise_keep_rate": 2 / 6,
            "recent_promise_break_rate": 2 / 3,
            "average_days_late": 14.0,
            "partial_payment_rate": 0.5,
            "payment_on_time_rate": 0.3,
            "historical_recovery_rate": 0.7,
            "historical_invoice_count": 8,
        }

    def test_credibility_is_complement_of_break_probability(self):
        score = score_promise(self.row, 0.72)
        self.assertEqual(score.promise_credibility_score, 28.0)
        self.assertAlmostEqual(score.break_probability, 0.72)

    def test_recovery_probability_is_not_just_credibility(self):
        score = score_promise(self.row, 0.72)
        self.assertNotEqual(score.recovery_probability, 0.28)
        self.assertGreater(score.recovery_probability, 0.0)
        self.assertLessEqual(score.recovery_probability, 1.0)

    def test_no_history_uses_neutral_recovery_prior(self):
        row = dict(self.row)
        row.update({
            "previous_promise_count": 0,
            "previous_promises_kept": 0,
            "previous_promises_broken": 0,
            "historical_promise_keep_rate": 0.0,
            "recent_promise_break_rate": 0.0,
            "average_days_late": 0.0,
            "partial_payment_rate": 0.0,
            "payment_on_time_rate": 0.0,
            "historical_recovery_rate": 0.0,
            "historical_invoice_count": 0,
        })
        score = score_promise(row, 0.50)
        self.assertAlmostEqual(score.recovery_probability, 0.5)
        self.assertIn("neutral prior", " ".join(score.explanation))

    def test_probability_is_clamped(self):
        low = score_promise(self.row, -1)
        high = score_promise(self.row, 2)
        self.assertEqual(low.promise_credibility_score, 100.0)
        self.assertEqual(high.promise_credibility_score, 0.0)
        self.assertTrue(0.0 <= low.recovery_probability <= 1.0)
        self.assertTrue(0.0 <= high.recovery_probability <= 1.0)

    def test_batch_length_is_checked(self):
        with self.assertRaises(ValueError):
            score_rows([self.row], [])


if __name__ == "__main__":
    unittest.main()
