"""Recommend deterministic recovery actions for current unresolved promises."""

from collections import Counter

from promise_ledger.config import DATABASE_PATH, SEED
from promise_ledger.db.connection import connect
from promise_ledger.features.engineering import build_feature_dataset, supervised_rows
from promise_ledger.models.training import RandomForestModel, feature_matrix
from promise_ledger.recovery import RecoveryDecisionEngine
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
        print("No unresolved promises to decide.")
        return

    model = RandomForestModel(random_state=SEED).fit(
        feature_matrix(resolved),
        [row["target_broken"] for row in resolved],
    )
    probabilities = [pair[1] for pair in model.predict_proba(feature_matrix(current))]
    opportunities = prioritize_opportunities(current, score_rows(current, probabilities))
    contexts = {int(row["promise_id"]): row for row in current}
    decisions = [RecoveryDecisionEngine().decide(item, contexts[item.promise_id]) for item in opportunities]

    action_counts = Counter(item.recommended_action.value for item in decisions)
    tier_counts = Counter(item.priority_tier for item in decisions)
    print("Promise Ledger recovery decision recommendations")
    print(f"promises evaluated: {len(decisions)}")
    print("recommended actions: " + ", ".join(f"{key}={action_counts[key]}" for key in sorted(action_counts)))
    print("priority tiers: " + ", ".join(f"{key}={tier_counts[key]}" for key in ("HIGH", "MEDIUM", "LOW") if tier_counts[key]))
    print(f"total outstanding amount: ₹{sum(item.outstanding_amount for item in opportunities):,.2f}")
    print(f"total expected recovery: ₹{sum(item.expected_recovery for item in opportunities):,.2f}")
    print("\nExample recommendations:")
    for decision in decisions[:5]:
        print(
            f"- promise {decision.promise_id} / customer {decision.customer_id}: "
            f"{decision.recommended_action.value} ({', '.join(decision.reason_codes)}) — {decision.explanation}"
        )
    print("Recommendations only; no recovery action was executed.")


if __name__ == "__main__":
    main()
