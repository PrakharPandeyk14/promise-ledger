"""Evaluate Day 4 recommendations against the existing merchant policy."""

from collections import Counter

from promise_ledger.config import DATABASE_PATH, SEED, SIMULATION_DATE
from promise_ledger.db.connection import connect
from promise_ledger.features.engineering import build_feature_dataset, supervised_rows
from promise_ledger.models.training import RandomForestModel, feature_matrix
from promise_ledger.recovery import RecoveryDecisionEngine
from promise_ledger.recovery.guardrails import GuardrailEngine, MerchantPolicy
from promise_ledger.risk.prioritization import prioritize_opportunities
from promise_ledger.risk.scoring import score_rows


_AUTOMATED_TYPES = ("SOFT_REMINDER", "FIRM_REMINDER", "PAYMENT_PLAN", "ESCALATE")


def main() -> None:
    connection = connect(DATABASE_PATH)
    try:
        rows = build_feature_dataset(connection)
        policy = MerchantPolicy.from_row(connection.execute("SELECT * FROM merchant_policies ORDER BY policy_id LIMIT 1").fetchone())
        invoices = {row["invoice_id"]: row for row in connection.execute("SELECT * FROM invoices")}
        promises = {row["promise_id"]: row for row in connection.execute("SELECT * FROM promises")}
        actions = connection.execute("SELECT * FROM recovery_actions ORDER BY action_date, action_id").fetchall()
        payments = connection.execute("SELECT invoice_id, SUM(amount) AS paid FROM payments GROUP BY invoice_id").fetchall()
    finally:
        connection.close()

    paid_by_invoice = {row["invoice_id"]: float(row["paid"] or 0.0) for row in payments}
    actions_by_invoice = {}
    for action in actions:
        actions_by_invoice.setdefault(action["invoice_id"], []).append(action)
    resolved = supervised_rows(rows)
    current = [row for row in rows if row["target_broken"] is None]
    if not current:
        print("No unresolved promises to evaluate.")
        return

    model = RandomForestModel(random_state=SEED).fit(feature_matrix(resolved), [row["target_broken"] for row in resolved])
    probabilities = [pair[1] for pair in model.predict_proba(feature_matrix(current))]
    opportunities = prioritize_opportunities(current, score_rows(current, probabilities))
    contexts = {int(row["promise_id"]): row for row in current}
    decision_engine = RecoveryDecisionEngine()
    guardrail_engine = GuardrailEngine(policy)
    evaluations = []
    for opportunity in opportunities:
        row = contexts[opportunity.promise_id]
        actions_for_invoice = actions_by_invoice.get(opportunity.invoice_id, [])
        automated_contacts = sum(action["action_type"] in _AUTOMATED_TYPES for action in actions_for_invoice)
        latest_action = actions_for_invoice[-1]["action_date"] if actions_for_invoice else None
        invoice = invoices[opportunity.invoice_id]
        context = {
            **row,
            "outstanding_amount": opportunity.outstanding_amount,
            "invoice_amount": invoice["amount"],
            "current_outstanding_amount": max(0.0, invoice["amount"] - paid_by_invoice.get(opportunity.invoice_id, 0.0)),
            "expected_recovery": opportunity.expected_recovery,
            "break_probability": opportunity.break_probability,
            "promise_outcome": promises[opportunity.promise_id]["outcome"],
            "invoice_status": invoice["status"],
            "automated_contact_count": automated_contacts,
            "latest_recovery_action_date": latest_action,
            "evaluation_date": SIMULATION_DATE.isoformat(),
        }
        recommendation = decision_engine.decide(opportunity, row)
        result = guardrail_engine.evaluate(recommendation.recommended_action, context)
        evaluations.append((recommendation, result))

    status_counts = Counter(result.status.value for _, result in evaluations)
    final_counts = Counter(result.final_action.value for _, result in evaluations)
    reason_counts = Counter(result.reason_code for _, result in evaluations)
    print("Promise Ledger guardrail evaluation")
    print(f"merchant policy: {policy.merchant_name}")
    print(f"promises evaluated: {len(evaluations)}")
    print("recommended actions: " + ", ".join(f"{key}={value}" for key, value in sorted(Counter(item.recommended_action.value for item, _ in evaluations).items())))
    print("final actions: " + ", ".join(f"{key}={value}" for key, value in sorted(final_counts.items())))
    print("statuses: " + ", ".join(f"{key}={value}" for key, value in sorted(status_counts.items())))
    print("reason codes: " + ", ".join(f"{key}={value}" for key, value in sorted(reason_counts.items())))
    print("\nExamples:")
    for recommendation, result in evaluations[:5]:
        print(f"- promise {recommendation.promise_id}: recommended={recommendation.recommended_action.value}, final={result.final_action.value}, status={result.status.value}, reason={result.reason_code}")
    print("No recovery action was executed.")


if __name__ == "__main__":
    main()
