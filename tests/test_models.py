import unittest

from promise_ledger.features.engineering import FEATURE_COLUMNS, TARGET_COLUMN, supervised_rows
from promise_ledger.features.evaluation import evaluate_binary_classification, temporal_train_test_split
from promise_ledger.models.training import MODEL_FEATURE_COLUMNS, train_and_evaluate


def make_row(identifier: int, target: int | None) -> dict:
    row = {
        "promise_id": identifier,
        "promise_created_date": f"2026-01-{identifier:02d}",
        TARGET_COLUMN: target,
    }
    # A stable, non-leaking signal plus varied numeric values make both models
    # exercise their complete training and probability paths.
    for index, column in enumerate(FEATURE_COLUMNS):
        row[column] = float((identifier * (index + 3)) % 17 + (8 if target else 0))
    return row


class ModelTrainingTests(unittest.TestCase):
    def setUp(self):
        rows = [make_row(identifier, identifier % 2) for identifier in range(1, 25)]
        self.train, self.test = temporal_train_test_split(rows, train_fraction=0.75)

    def test_models_train_and_probability_predictions_have_expected_shape(self):
        results = train_and_evaluate(self.train, self.test)
        self.assertEqual(set(results), {"Logistic Regression", "Random Forest"})
        for result in results.values():
            self.assertEqual(len(result.predictions), len(self.test))
            for prediction, row in zip(result.predictions, self.test):
                self.assertEqual(prediction["actual_outcome"], row[TARGET_COLUMN])
                self.assertIn(prediction["predicted_class"], (0, 1))
                self.assertGreaterEqual(prediction["predicted_break_probability"], 0.0)
                self.assertLessEqual(prediction["predicted_break_probability"], 1.0)

    def test_split_is_unchanged_and_training_is_deterministic(self):
        original_train, original_test = [dict(row) for row in self.train], [dict(row) for row in self.test]
        first, second = train_and_evaluate(self.train, self.test), train_and_evaluate(self.train, self.test)
        self.assertEqual(self.train, original_train)
        self.assertEqual(self.test, original_test)
        for name in first:
            self.assertEqual(first[name].predictions, second[name].predictions)
            self.assertEqual(first[name].metrics, second[name].metrics)
        self.assertLess(max(row["promise_created_date"] for row in self.train), min(row["promise_created_date"] for row in self.test))

    def test_scaler_is_fit_from_training_rows_only(self):
        results = train_and_evaluate(self.train, self.test)
        scaler = results["Logistic Regression"].estimator.scaler
        expected = sum(row[FEATURE_COLUMNS[0]] for row in self.train) / len(self.train)
        combined = sum(row[FEATURE_COLUMNS[0]] for row in self.train + self.test) / (len(self.train) + len(self.test))
        self.assertEqual(scaler.mean_[0], expected)
        self.assertNotEqual(scaler.mean_[0], combined)

    def test_feature_allowlist_has_no_target_or_simulator_parameters(self):
        self.assertEqual(MODEL_FEATURE_COLUMNS, FEATURE_COLUMNS)
        forbidden = {TARGET_COLUMN, "persona", "promise_keep_tendency", "eventual_payment_probability", "outcome", "actual_payment_date", "recovery_action"}
        self.assertTrue(forbidden.isdisjoint(MODEL_FEATURE_COLUMNS))

    def test_pending_rows_are_rejected_from_supervised_training(self):
        rows = self.train + [make_row(25, None)]
        self.assertEqual(len(supervised_rows(rows)), len(self.train))
        with self.assertRaisesRegex(ValueError, "pending"):
            train_and_evaluate(rows, self.test)

    def test_metrics_are_calculated_correctly(self):
        metrics = evaluate_binary_classification([1, 0, 1, 0], [0.9, 0.8, 0.4, 0.1])
        self.assertEqual(metrics["true_positive"], 1)
        self.assertEqual(metrics["false_positive"], 1)
        self.assertEqual(metrics["false_negative"], 1)
        self.assertEqual(metrics["true_negative"], 1)
        self.assertEqual(metrics["accuracy"], 0.5)
        self.assertEqual(metrics["precision"], 0.5)
        self.assertEqual(metrics["recall"], 0.5)
        self.assertEqual(metrics["f1"], 0.5)
        self.assertEqual(metrics["roc_auc"], 0.75)


if __name__ == "__main__":
    unittest.main()
