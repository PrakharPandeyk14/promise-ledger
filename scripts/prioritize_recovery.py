"""Score unresolved promises and rank them by expected recovery."""

from promise_ledger.config import DATABASE_PATH, SEED
from promise_ledger.db.connection import connect
from promise_ledger.features.engineering import build_feature_dataset, supervised_rows
from promise_ledger.models.training import RandomForestModel, feature_matrix
from promise_ledger.risk.prioritization import prioritize_opportunities
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
        print("No unresolved promises to prioritize.")
        return

    model = RandomForestModel(random_state=SEED).fit(
        feature_matrix(resolved),
        [row["target_broken"] for row in resolved],
    )
    probabilities = [pair[1] for pair in model.predict_proba(feature_matrix(current))]
    scores = score_rows(current, probabilities)
    opportunities = prioritize_opportunities(current, scores)

    print("Promise Ledger recovery opportunities")
    print(f"unresolved promises: {len(opportunities)}")
    print("rank | tier | promise_id | invoice_id | outstanding | recovery_prob | expected_recovery | break_prob")
    for item in opportunities:
        print(
            f"{item.priority_rank} | {item.priority_tier} | {item.promise_id} | {item.invoice_id} | "
            f"₹{item.outstanding_amount:,.2f} | {item.recovery_probability:.4f} | "
            f"₹{item.expected_recovery:,.2f} | {item.break_probability:.4f}"
        )
    print("Ranking is driven by expected recovery = outstanding amount × recovery probability.")
    print("This ranking does not execute actions or bypass merchant policies.")


if __name__ == "__main__":
    main()
