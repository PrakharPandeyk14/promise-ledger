"""Build and evaluate the leakage-safe promise-break feature foundation."""

from promise_ledger.config import DATABASE_PATH
from promise_ledger.db.connection import connect
from promise_ledger.features.baseline import predict_break_probabilities
from promise_ledger.features.engineering import FEATURE_COLUMNS, build_feature_dataset, supervised_rows
from promise_ledger.features.evaluation import evaluate_binary_classification, labels, temporal_train_test_split


def main() -> None:
    database = connect(DATABASE_PATH)
    try:
        all_rows = build_feature_dataset(database)
    finally:
        database.close()
    usable = supervised_rows(all_rows)
    train, test = temporal_train_test_split(usable)
    metrics = evaluate_binary_classification(labels(test), predict_break_probabilities(test))
    kept = sum(row["target_broken"] == 0 for row in usable)
    broken = sum(row["target_broken"] == 1 for row in usable)
    print("Promise-break feature foundation")
    print(f"usable promises: {len(usable)} (kept: {kept}, broken: {broken})")
    print(f"excluded pending promises: {len(all_rows) - len(usable)}")
    print("feature columns: " + ", ".join(FEATURE_COLUMNS))
    print(f"train size: {len(train)}; test size: {len(test)}")
    print("baseline metrics: " + ", ".join(f"{key}={value}" for key, value in metrics.items()))
    print("assumptions: all history uses strictly earlier dated events; prior promise outcomes require a strictly earlier promised date; baseline uses the customer's unsmoothed break rate after 3 resolved promises, otherwise 0.50.")


if __name__ == "__main__":
    main()
