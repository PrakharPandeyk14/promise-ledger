"""Demonstrate side-effect-free guarded recovery execution."""

from promise_ledger.config import DATABASE_PATH, SEED, SIMULATION_DATE
from promise_ledger.db.connection import connect
from promise_ledger.features.engineering import build_feature_dataset, supervised_rows
from promise_ledger.models.training import RandomForestModel, feature_matrix
from promise_ledger.recovery import ActionExecutor, GuardrailEngine, MerchantPolicy, RecoveryDecisionEngine
from promise_ledger.risk.prioritization import prioritize_opportunities
from promise_ledger.risk.scoring import score_rows

_AUTOMATED_TYPES = ("SOFT_REMINDER", "FIRM_REMINDER", "PAYMENT_PLAN", "ESCALATE")


def main() -> None:
    connection = connect(DATABASE_PATH)
    try:
        rows = build_feature_dataset(connection)
        policy = MerchantPolicy.from_row(connection.execute("SELECT * FROM merchant_policies LIMIT 1").fetchone())
        invoices = {row["invoice_id"]: row for row in connection.execute("SELECT * FROM invoices")}
        promises = {row["promise_id"]: row for row in connection.execute("SELECT * FROM promises")}
        payments = connection.execute("SELECT invoice_id, SUM(amount) AS paid FROM payments GROUP BY invoice_id").fetchall()
        actions = connection.execute("SELECT * FROM recovery_actions ORDER BY action_date, action_id").fetchall()
    finally:
        connection.close()

    paid = {row["invoice_id"]: float(row["paid"] or 0.0) for row in payments}
    actions_by_invoice = {}
    for action in actions:
        actions_by_invoice.setdefault(action["invoice_id"], []).append(action)
    current = [row for row in rows if row["target_broken"] is None]
    rows_by_promise = {row["promise_id"]: row for row in current}
    resolved = supervised_rows(rows)
    model = RandomForestModel(random_state=SEED).fit(feature_matrix(resolved), [row["target_broken"] for row in resolved])
    probabilities = [pair[1] for pair in model.predict_proba(feature_matrix(current))]
    opportunities = prioritize_opportunities(current, score_rows(current, probabilities))[:5]
    decisions = RecoveryDecisionEngine()
    executor = ActionExecutor(GuardrailEngine(policy))

    print("Promise Ledger simulated action execution")
    for opportunity in opportunities:
        invoice = invoices[opportunity.invoice_id]
        invoice_actions = actions_by_invoice.get(opportunity.invoice_id, [])
        context = {
            "invoice_id": opportunity.invoice_id,
            "invoice_amount": invoice["amount"],
            "current_outstanding_amount": max(0.0, invoice["amount"] - paid.get(opportunity.invoice_id, 0.0)),
            "outstanding_amount": opportunity.outstanding_amount,
            "expected_recovery": opportunity.expected_recovery,
            "break_probability": opportunity.break_probability,
            "invoice_status": invoice["status"],
            "promise_outcome": promises[opportunity.promise_id]["outcome"],
            "automated_contact_count": sum(item["action_type"] in _AUTOMATED_TYPES for item in invoice_actions),
            "latest_recovery_action_date": invoice_actions[-1]["action_date"] if invoice_actions else None,
            "evaluation_date": SIMULATION_DATE.isoformat(),
        }
        decision = decisions.decide(opportunity, rows_by_promise[opportunity.promise_id])
        result = executor.execute(decision, context)
        print(
            f"promise={opportunity.promise_id} invoice={opportunity.invoice_id} "
            f"recommended={decision.recommended_action.value} "
            f"guardrail={result.guardrail.status.value} final={result.audit.final_action.value} "
            f"reason={result.audit.reason_code} simulated={result.audit.simulated}"
        )
    print("No real recovery action was executed.")


if __name__ == "__main__":
    main()
