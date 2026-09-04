"""Train and compare leakage-safe promise-break ML models."""

from promise_ledger.config import DATABASE_PATH
from promise_ledger.db.connection import connect
from promise_ledger.features.baseline import predict_break_probabilities
from promise_ledger.features.engineering import build_feature_dataset, supervised_rows
from promise_ledger.features.evaluation import evaluate_binary_classification, labels, temporal_train_test_split
from promise_ledger.models.training import MODEL_FEATURE_COLUMNS, select_model, train_and_evaluate


def _metric(value):
    return "N/A" if value is None else f"{value:.4f}"


def main() -> None:
    database = connect(DATABASE_PATH)
    try:
        all_rows = build_feature_dataset(database)
    finally:
        database.close()
    usable = supervised_rows(all_rows)
    train, test = temporal_train_test_split(usable)
    baseline = evaluate_binary_classification(labels(test), predict_break_probabilities(test))
    results = train_and_evaluate(train, test)
    selected = select_model(results)

    print("Promise-break ML model comparison")
    print(f"usable promises: {len(usable)}; pending excluded: {len(all_rows) - len(usable)}")
    print(f"temporal split: {len(train)} train / {len(test)} test")
    print("Model | Accuracy | Precision | Recall | F1 | ROC-AUC | Brier")
    print("Baseline | " + " | ".join(_metric(baseline[name]) for name in ("accuracy", "precision", "recall", "f1", "roc_auc")) + " | N/A")
    for name, result in results.items():
        print(name + " | " + " | ".join(_metric(result.metrics[key]) for key in ("accuracy", "precision", "recall", "f1", "roc_auc")) + f" | {result.brier_score:.4f}")
    print(f"selected model: {selected.name} (ROC-AUC, F1, recall, precision, then Brier; not accuracy)")
    print("top influential features (random-forest split-frequency importance; association, not causation):")
    for feature, effect in selected.feature_effects[:10]:
        print(f"  {feature}: {effect:+.6f}")
    print(f"probability output: {len(selected.predictions)} test promises; fields=actual_outcome, predicted_break_probability, predicted_class")
    print("promise_id | actual_outcome | predicted_break_probability | predicted_class")
    for prediction in selected.predictions:
        actual = "BROKEN" if prediction["actual_outcome"] else "KEPT"
        print(f"{prediction['promise_id']} | {actual} | {prediction['predicted_break_probability']:.6f} | {prediction['predicted_class']}")
    print("leakage safety: existing chronological split reused; pending excluded; target/metadata absent from feature list; logistic scaler fitted only on training rows.")
    print("model feature columns: " + ", ".join(MODEL_FEATURE_COLUMNS))


if __name__ == "__main__":
    main()
