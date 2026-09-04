"""Build current Promise Ledger risk scores for unresolved promises."""

from promise_ledger.config import DATABASE_PATH, SEED
from promise_ledger.db.connection import connect
from promise_ledger.features.engineering import build_feature_dataset, supervised_rows
from promise_ledger.models.training import RandomForestModel, feature_matrix
from promise_ledger.risk.scoring import score_rows


def main() -> None:
    connection = connect(DATABASE_PATH)
    try:
        rows = build_feature_dataset(connection)
    finally:
        connection.close()

    resolved = supervised_rows(rows)
    current = [row for row in rows if row["target_broken"] is None]
    if not current:
        print("No unresolved promises to score.")
        return

    model = RandomForestModel(random_state=SEED).fit(
        feature_matrix(resolved),
        [row["target_broken"] for row in resolved],
    )
    probabilities = [pair[1] for pair in model.predict_proba(feature_matrix(current))]
    scores = score_rows(current, probabilities)

    print("Promise Ledger current risk scores")
    print(f"scored unresolved promises: {len(scores)}")
    print("promise_id | break_probability | credibility | recovery_probability | explanation")
    for score in sorted(scores, key=lambda item: item.recovery_probability, reverse=True):
        print(
            f"{score.promise_id} | {score.break_probability:.4f} | "
            f"{score.promise_credibility_score:.2f} | {score.recovery_probability:.4f} | "
            f"{' ; '.join(score.explanation)}"
        )
    print("recovery probability is a transparent heuristic, not a calibrated ML probability.")
    print("model training uses only resolved historical promises; unresolved promises are scoring-only.")


if __name__ == "__main__":
    main()
