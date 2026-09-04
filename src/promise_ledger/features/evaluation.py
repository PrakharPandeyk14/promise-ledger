"""Time-aware splitting and transparent binary-classification evaluation."""

from __future__ import annotations

from typing import Any

from .engineering import TARGET_COLUMN


def temporal_train_test_split(
    rows: list[dict[str, Any]], train_fraction: float = 0.80
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split chronologically, keeping a creation date wholly in one partition."""
    if not 0 < train_fraction < 1:
        raise ValueError("train_fraction must be between 0 and 1")
    ordered = sorted(rows, key=lambda row: (row["promise_created_date"], row["promise_id"]))
    if len(ordered) < 2:
        raise ValueError("at least two supervised rows are required for a split")
    target_index = max(1, min(len(ordered) - 1, int(len(ordered) * train_fraction)))
    cutoff_date = ordered[target_index]["promise_created_date"]
    train = [row for row in ordered if row["promise_created_date"] < cutoff_date]
    test = [row for row in ordered if row["promise_created_date"] >= cutoff_date]
    if not train or not test:
        raise ValueError("cannot create a non-empty date-separated temporal split")
    return train, test


def _validate(y_true: list[int], probabilities: list[float]) -> None:
    if not y_true:
        raise ValueError("evaluation requires at least one row")
    if len(y_true) != len(probabilities):
        raise ValueError("labels and probabilities must have equal lengths")
    if any(value not in (0, 1) for value in y_true):
        raise ValueError("labels must be binary 0/1 values")
    if any(not 0 <= value <= 1 for value in probabilities):
        raise ValueError("probabilities must be in [0, 1]")


def _roc_auc(y_true: list[int], probabilities: list[float]) -> float | None:
    positives, negatives = sum(y_true), len(y_true) - sum(y_true)
    if not positives or not negatives:
        return None
    ranked = sorted(enumerate(probabilities), key=lambda item: item[1])
    ranks = [0.0] * len(probabilities)
    position = 0
    while position < len(ranked):
        end = position
        while end + 1 < len(ranked) and ranked[end + 1][1] == ranked[position][1]:
            end += 1
        average_rank = (position + 1 + end + 1) / 2
        for index in range(position, end + 1):
            ranks[ranked[index][0]] = average_rank
        position = end + 1
    positive_rank_sum = sum(rank for rank, label in zip(ranks, y_true) if label == 1)
    return (positive_rank_sum - positives * (positives + 1) / 2) / (positives * negatives)


def evaluate_binary_classification(
    y_true: list[int], probabilities: list[float], threshold: float = 0.50
) -> dict[str, float | int | None]:
    """Return metrics; ROC-AUC is ``None`` if labels contain only one class."""
    _validate(y_true, probabilities)
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0, 1]")
    predictions = [int(probability >= threshold) for probability in probabilities]
    true_positive = sum(actual == 1 and predicted == 1 for actual, predicted in zip(y_true, predictions))
    false_positive = sum(actual == 0 and predicted == 1 for actual, predicted in zip(y_true, predictions))
    false_negative = sum(actual == 1 and predicted == 0 for actual, predicted in zip(y_true, predictions))
    true_negative = sum(actual == 0 and predicted == 0 for actual, predicted in zip(y_true, predictions))
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    return {
        "accuracy": (true_positive + true_negative) / len(y_true),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "roc_auc": _roc_auc(y_true, probabilities),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
    }


def labels(rows: list[dict[str, Any]]) -> list[int]:
    return [row[TARGET_COLUMN] for row in rows]
