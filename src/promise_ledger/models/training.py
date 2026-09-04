"""Deterministic, time-safe training for promise-break classifiers.

These small standard-library estimators keep the project self-contained. The
caller supplies the established chronological split; neither estimator creates
or reshuffles a split.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, sqrt
from random import Random
from typing import Any

from promise_ledger.config import SEED
from promise_ledger.features.engineering import FEATURE_COLUMNS, TARGET_COLUMN
from promise_ledger.features.evaluation import evaluate_binary_classification, labels
from promise_ledger.models.prediction import prediction_records

MODEL_FEATURE_COLUMNS = FEATURE_COLUMNS
MODEL_NAMES = ("Logistic Regression", "Random Forest")


class StandardScaler:
    """Minimal scaler whose learned statistics are always training-only."""

    def fit(self, matrix: list[list[float]]) -> "StandardScaler":
        self.mean_ = [sum(row[index] for row in matrix) / len(matrix) for index in range(len(matrix[0]))]
        self.scale_ = [sqrt(sum((row[index] - self.mean_[index]) ** 2 for row in matrix) / len(matrix)) or 1.0 for index in range(len(matrix[0]))]
        return self

    def transform(self, matrix: list[list[float]]) -> list[list[float]]:
        return [[(value - self.mean_[index]) / self.scale_[index] for index, value in enumerate(row)] for row in matrix]


class LogisticModel:
    """L2-regularized logistic regression with deterministic batch descent."""

    def __init__(self, iterations: int = 1_500, learning_rate: float = 0.08, l2: float = 0.01):
        self.iterations, self.learning_rate, self.l2 = iterations, learning_rate, l2
        self.scaler = StandardScaler()

    @staticmethod
    def _sigmoid(score: float) -> float:
        return 1.0 / (1.0 + exp(-max(-35.0, min(35.0, score))))

    def fit(self, matrix: list[list[float]], outcomes: list[int]) -> "LogisticModel":
        scaled = self.scaler.fit(matrix).transform(matrix)
        self.coefficients_ = [0.0] * len(scaled[0])
        self.intercept_ = 0.0
        for _ in range(self.iterations):
            errors = [self._sigmoid(self.intercept_ + sum(weight * value for weight, value in zip(self.coefficients_, row))) - outcome for row, outcome in zip(scaled, outcomes)]
            count = len(scaled)
            gradients = [sum(error * row[index] for error, row in zip(errors, scaled)) / count + self.l2 * self.coefficients_[index] for index in range(len(self.coefficients_))]
            self.intercept_ -= self.learning_rate * sum(errors) / count
            self.coefficients_ = [weight - self.learning_rate * gradient for weight, gradient in zip(self.coefficients_, gradients)]
        return self

    def predict_proba(self, matrix: list[list[float]]) -> list[list[float]]:
        values = [self._sigmoid(self.intercept_ + sum(weight * value for weight, value in zip(self.coefficients_, row))) for row in self.scaler.transform(matrix)]
        return [[1.0 - probability, probability] for probability in values]


@dataclass
class _TreeNode:
    probability: float
    feature: int | None = None
    threshold: float | None = None
    left: "_TreeNode | None" = None
    right: "_TreeNode | None" = None


class _DecisionTree:
    def __init__(self, rng: Random, max_depth: int = 6, min_leaf: int = 10):
        self.rng, self.max_depth, self.min_leaf = rng, max_depth, min_leaf

    @staticmethod
    def _gini(outcomes: list[int]) -> float:
        probability = sum(outcomes) / len(outcomes)
        return 2 * probability * (1 - probability)

    def _candidate_thresholds(self, values: list[float]) -> list[float]:
        ordered = sorted(set(values))
        if len(ordered) <= 10:
            return [(ordered[index] + ordered[index + 1]) / 2 for index in range(len(ordered) - 1)]
        positions = sorted({int((len(ordered) - 1) * part / 10) for part in range(1, 10)})
        return [(ordered[index] + ordered[index + 1]) / 2 for index in positions]

    def _build(self, matrix: list[list[float]], outcomes: list[int], depth: int) -> _TreeNode:
        probability = sum(outcomes) / len(outcomes)
        node = _TreeNode(probability)
        if depth >= self.max_depth or len(outcomes) < self.min_leaf * 2 or probability in (0.0, 1.0):
            return node
        candidates = self.rng.sample(range(len(matrix[0])), max(1, int(sqrt(len(matrix[0])))))
        parent, best = self._gini(outcomes), None
        for feature in candidates:
            for threshold in self._candidate_thresholds([row[feature] for row in matrix]):
                left_indices = [index for index, row in enumerate(matrix) if row[feature] <= threshold]
                right_indices = [index for index, row in enumerate(matrix) if row[feature] > threshold]
                if len(left_indices) < self.min_leaf or len(right_indices) < self.min_leaf:
                    continue
                left_outcomes = [outcomes[index] for index in left_indices]
                right_outcomes = [outcomes[index] for index in right_indices]
                gain = parent - (len(left_outcomes) * self._gini(left_outcomes) + len(right_outcomes) * self._gini(right_outcomes)) / len(outcomes)
                if best is None or gain > best[0]:
                    best = (gain, feature, threshold, left_indices, right_indices)
        if best is None or best[0] <= 0:
            return node
        _, feature, threshold, left_indices, right_indices = best
        node.feature, node.threshold = feature, threshold
        node.left = self._build([matrix[index] for index in left_indices], [outcomes[index] for index in left_indices], depth + 1)
        node.right = self._build([matrix[index] for index in right_indices], [outcomes[index] for index in right_indices], depth + 1)
        return node

    def fit(self, matrix: list[list[float]], outcomes: list[int]) -> "_DecisionTree":
        self.root = self._build(matrix, outcomes, 0)
        return self

    def predict_probability(self, row: list[float]) -> float:
        node = self.root
        while node.feature is not None:
            node = node.left if row[node.feature] <= node.threshold else node.right
        return node.probability

    def importance(self, totals: list[float]) -> None:
        def visit(node: _TreeNode) -> None:
            if node.feature is not None:
                totals[node.feature] += 1.0
                visit(node.left)
                visit(node.right)
        visit(self.root)


class RandomForestModel:
    """Bootstrap aggregation of randomized, bounded CART-style trees."""

    def __init__(self, n_estimators: int = 150, random_state: int = SEED):
        self.n_estimators, self.random_state = n_estimators, random_state

    def fit(self, matrix: list[list[float]], outcomes: list[int]) -> "RandomForestModel":
        rng, self.trees_ = Random(self.random_state), []
        for _ in range(self.n_estimators):
            indices = [rng.randrange(len(matrix)) for _ in matrix]
            tree = _DecisionTree(Random(rng.randrange(2**31))).fit([matrix[index] for index in indices], [outcomes[index] for index in indices])
            self.trees_.append(tree)
        totals = [0.0] * len(matrix[0])
        for tree in self.trees_:
            tree.importance(totals)
        total = sum(totals) or 1.0
        self.feature_importances_ = [value / total for value in totals]
        return self

    def predict_proba(self, matrix: list[list[float]]) -> list[list[float]]:
        values = [sum(tree.predict_probability(row) for tree in self.trees_) / len(self.trees_) for row in matrix]
        return [[1.0 - probability, probability] for probability in values]


@dataclass
class ModelResult:
    name: str
    estimator: Any
    metrics: dict[str, float | int | None]
    brier_score: float
    predictions: list[dict[str, Any]]
    feature_effects: list[tuple[str, float]]


def feature_matrix(rows: list[dict[str, Any]]) -> list[list[float]]:
    return [[float(row[column]) for column in MODEL_FEATURE_COLUMNS] for row in rows]


def _validate_supervised(rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("model training requires rows")
    if TARGET_COLUMN in MODEL_FEATURE_COLUMNS:
        raise ValueError("the target must never be a model feature")
    if any(row[TARGET_COLUMN] not in (0, 1) for row in rows):
        raise ValueError("pending or otherwise unlabeled rows cannot be used for supervised modeling")


def _evaluate(name: str, estimator: Any, train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], effects: list[tuple[str, float]]) -> ModelResult:
    estimator.fit(feature_matrix(train_rows), labels(train_rows))
    predictions = prediction_records(estimator, test_rows, MODEL_FEATURE_COLUMNS)
    probabilities, actuals = [item["predicted_break_probability"] for item in predictions], labels(test_rows)
    brier = sum((actual - probability) ** 2 for actual, probability in zip(actuals, probabilities)) / len(actuals)
    return ModelResult(name, estimator, evaluate_binary_classification(actuals, probabilities), brier, predictions, effects)


def train_and_evaluate(train_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], seed: int = SEED) -> dict[str, ModelResult]:
    _validate_supervised(train_rows)
    _validate_supervised(test_rows)
    logistic = _evaluate("Logistic Regression", LogisticModel(), train_rows, test_rows, [])
    logistic.feature_effects = sorted(zip(MODEL_FEATURE_COLUMNS, logistic.estimator.coefficients_), key=lambda item: abs(item[1]), reverse=True)
    forest = _evaluate("Random Forest", RandomForestModel(random_state=seed), train_rows, test_rows, [])
    forest.feature_effects = sorted(zip(MODEL_FEATURE_COLUMNS, forest.estimator.feature_importances_), key=lambda item: item[1], reverse=True)
    return {logistic.name: logistic, forest.name: forest}


def select_model(results: dict[str, ModelResult]) -> ModelResult:
    """Prioritize ROC-AUC, F1, recall, precision, then probability calibration."""
    if set(results) != set(MODEL_NAMES):
        raise ValueError("model selection requires the complete required comparison")
    def rank(result: ModelResult) -> tuple[float, float, float, float, float]:
        metrics = result.metrics
        return (float(metrics["roc_auc"]) if metrics["roc_auc"] is not None else -1.0, float(metrics["f1"]), float(metrics["recall"]), float(metrics["precision"]), -result.brier_score)
    return max(results.values(), key=rank)
