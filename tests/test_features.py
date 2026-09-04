import tempfile
import unittest
from pathlib import Path

from promise_ledger.db.connection import connect, recreate_database
from promise_ledger.features.baseline import FALLBACK_BREAK_PROBABILITY, predict_break_probability
from promise_ledger.features.engineering import FEATURE_COLUMNS, build_feature_dataset, supervised_rows
from promise_ledger.features.evaluation import evaluate_binary_classification, temporal_train_test_split


class FeatureEngineeringTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "ledger.db"
        self.db = recreate_database(self.path)
        self.addCleanup(self.db.close)
        self.db.execute("INSERT INTO customers VALUES (1, 'C-1', 'One', 'RELIABLE_PAYER', '2026-01-01', 1000)")
        self.db.executemany("INSERT INTO invoices VALUES (?, 1, ?, ?, ?, 100, 'OPEN', NULL)", [
            (1, 'I-1', '2026-01-10', '2026-01-20'),
            (2, 'I-2', '2026-01-25', '2026-02-05'),
            (3, 'I-3', '2026-02-20', '2026-03-01'),
        ])
        self.db.executemany("INSERT INTO payments VALUES (?, ?, 1, ?, ?, 'UPI')", [
            (1, 1, '2026-01-15', 50),
            (2, 1, '2026-03-10', 50),  # Future relative to promise 3.
            (3, 2, '2026-02-13', 25),  # Current-invoice prior payment for promise 3.
        ])
        self.db.executemany("INSERT INTO promises VALUES (?, ?, 1, ?, ?, 50, ?)", [
            (1, 1, '2026-02-01', '2026-02-05', 'KEPT'),
            (2, 2, '2026-02-06', '2026-02-10', 'BROKEN'),
            (3, 2, '2026-02-15', '2026-02-20', 'BROKEN'),
            (4, 3, '2026-03-05', '2026-03-10', 'PENDING'),
        ])
        self.db.commit()

    def _rows(self):
        return {row['promise_id']: row for row in build_feature_dataset(self.db)}

    def test_historical_features_do_not_use_future_events(self):
        row = self._rows()[3]
        # Payment 2 occurs after this prediction point and must not turn the
        # historical invoice recovery ratio into 0.625. Only the two earlier
        # payments (50 + 25) across 200 invoiced are observable.
        self.assertEqual(row['historical_payment_completion_ratio'], 0.375)
        self.assertEqual(row['outstanding_amount_at_promise_creation'], 75.0)

    def test_current_promise_is_excluded_from_its_history(self):
        row = self._rows()[3]
        self.assertEqual(row['previous_promise_count'], 2)
        self.assertEqual(row['previous_promises_kept'], 1)
        self.assertEqual(row['previous_promises_broken'], 1)

    def test_pending_promises_are_excluded_from_supervised_rows(self):
        rows = build_feature_dataset(self.db)
        self.assertEqual(len(rows), 4)
        self.assertEqual(len(supervised_rows(rows)), 3)
        self.assertIsNone(self._rows()[4]['target_broken'])

    def test_baseline_uses_history_or_documented_fallback(self):
        self.assertEqual(predict_break_probability(self._rows()[3]), FALLBACK_BREAK_PROBABILITY)
        with_history = dict(self._rows()[3], previous_promises_kept=3, previous_promises_broken=1)
        self.assertEqual(predict_break_probability(with_history), 0.25)

    def test_temporal_split_is_deterministic_and_date_separated(self):
        rows = supervised_rows(build_feature_dataset(self.db))
        # Add a distinct historical row shape only to exercise a non-empty split.
        copied = [dict(row) for row in rows]
        copied.append(dict(rows[-1], promise_id=99, promise_created_date='2026-04-01'))
        first = temporal_train_test_split(copied, train_fraction=0.5)
        second = temporal_train_test_split(copied, train_fraction=0.5)
        self.assertEqual(first, second)
        self.assertLess(max(row['promise_created_date'] for row in first[0]), min(row['promise_created_date'] for row in first[1]))

    def test_feature_columns_exclude_leakage_and_simulator_parameters(self):
        expected = {
            'previous_promise_count', 'previous_promises_kept', 'previous_promises_broken',
            'historical_promise_keep_rate', 'recent_promise_break_rate', 'average_days_late',
            'median_days_late', 'payment_on_time_rate', 'partial_payment_rate',
            'historical_payment_completion_ratio', 'invoice_amount',
            'outstanding_amount_at_promise_creation', 'days_overdue_at_promise_creation',
            'invoice_age_at_promise_creation', 'customer_tenure_at_promise',
            'historical_invoice_count', 'historical_average_invoice_amount', 'historical_recovery_rate',
        }
        self.assertEqual(set(FEATURE_COLUMNS), expected)
        forbidden = {'persona', 'promise_keep_tendency', 'eventual_payment_probability',
                     'partial_payment_probability', 'outcome', 'status',
                     'actual_payment_date', 'actual_payment_amount'}
        self.assertTrue(forbidden.isdisjoint(FEATURE_COLUMNS))

    def test_roc_auc_is_explicitly_not_applicable_for_one_class(self):
        metrics = evaluate_binary_classification([1, 1], [0.4, 0.8])
        self.assertIsNone(metrics['roc_auc'])


if __name__ == '__main__':
    unittest.main()
