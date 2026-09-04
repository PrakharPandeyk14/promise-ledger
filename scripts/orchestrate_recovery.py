"""End-to-end recovery orchestration demonstration.

Demonstrates the complete Day 4 pipeline:
- Promise/risk information
- Recovery Decision Engine (Step 1)
- Guardrail Engine (Step 2)
- Action Executor (Step 3)
- Portfolio evaluation metrics

Uses the existing database and produces deterministic audit trails.
"""

from promise_ledger.config import DATABASE_PATH, SEED, SIMULATION_DATE
from promise_ledger.db.connection import connect
from promise_ledger.features.engineering import build_feature_dataset, supervised_rows
from promise_ledger.models.training import RandomForestModel, feature_matrix
from promise_ledger.recovery import (
    ActionExecutor,
    GuardrailEngine,
    MerchantPolicy,
    OrchestrationContext,
    PortfolioEvaluator,
    RecoveryDecisionEngine,
    RecoveryOrchestrator,
)
from promise_ledger.risk.prioritization import prioritize_opportunities
from promise_ledger.risk.scoring import score_rows

_AUTOMATED_TYPES = ("SOFT_REMINDER", "FIRM_REMINDER", "PAYMENT_PLAN", "ESCALATE")


def main() -> None:
    """Run end-to-end recovery orchestration and print portfolio summary."""
    connection = connect(DATABASE_PATH)
    try:
        # Fetch all supporting data
        rows = build_feature_dataset(connection)
        policy = MerchantPolicy.from_row(connection.execute("SELECT * FROM merchant_policies LIMIT 1").fetchone())
        invoices = {row["invoice_id"]: row for row in connection.execute("SELECT * FROM invoices")}
        promises = {row["promise_id"]: row for row in connection.execute("SELECT * FROM promises")}
        payments = connection.execute("SELECT invoice_id, SUM(amount) AS paid FROM payments GROUP BY invoice_id").fetchall()
        actions = connection.execute("SELECT * FROM recovery_actions ORDER BY action_date, action_id").fetchall()
    finally:
        connection.close()

    # Compute unresolved promises with recovery scores
    paid = {row["invoice_id"]: float(row["paid"] or 0.0) for row in payments}
    actions_by_invoice = {}
    for action in actions:
        actions_by_invoice.setdefault(action["invoice_id"], []).append(action)

    current = [row for row in rows if row["target_broken"] is None]
    rows_by_promise = {row["promise_id"]: row for row in current}
    resolved = supervised_rows(rows)

    # Train model to predict break probability
    model = RandomForestModel(random_state=SEED).fit(
        feature_matrix(resolved),
        [row["target_broken"] for row in resolved],
    )
    probabilities = [pair[1] for pair in model.predict_proba(feature_matrix(current))]

    # Prioritize opportunities by expected recovery
    opportunities = prioritize_opportunities(current, score_rows(current, probabilities))[:10]

    # Set up orchestration components
    decision_engine = RecoveryDecisionEngine()
    executor = ActionExecutor(GuardrailEngine(policy))
    orchestrator = RecoveryOrchestrator(decision_engine, executor)

    # Build orchestration contexts
    contexts = []
    for opportunity in opportunities:
        invoice = invoices[opportunity.invoice_id]
        invoice_actions = actions_by_invoice.get(opportunity.invoice_id, [])
        context = OrchestrationContext(
            opportunity=opportunity,
            invoice=invoice,
            promise=promises[opportunity.promise_id],
            paid_amount=paid.get(opportunity.invoice_id, 0.0),
            automated_contact_count=sum(item["action_type"] in _AUTOMATED_TYPES for item in invoice_actions),
            latest_recovery_action_date=invoice_actions[-1]["action_date"] if invoice_actions else None,
            additional_context={
                "evaluation_date": SIMULATION_DATE.isoformat(),
            },
        )
        contexts.append(context)

    # Orchestrate portfolio
    results = orchestrator.orchestrate_portfolio(contexts, rows_by_promise)

    # Evaluate portfolio metrics
    metrics = PortfolioEvaluator.evaluate(results)

    # Print portfolio summary
    print("=" * 80)
    print("END-TO-END RECOVERY ORCHESTRATION - PORTFOLIO EVALUATION")
    print("=" * 80)
    print()
    print("PORTFOLIO OVERVIEW")
    print("-" * 80)
    print(f"Total opportunities evaluated: {metrics.evaluation_count}")
    print(f"Total outstanding amount: ${metrics.total_outstanding_amount:,.2f}")
    print(f"Total expected recovery: ${metrics.total_expected_recovery:,.2f}")
    print(f"Average recovery per opportunity: ${metrics.average_expected_recovery():,.2f}")
    print()

    print("RECOMMENDED ACTIONS")
    print("-" * 80)
    for action, count in metrics.recommended_actions.as_dict().items():
        if count > 0:
            print(f"  {action}: {count}")
    print()

    print("FINAL ACTIONS (After Guardrails)")
    print("-" * 80)
    for action, count in metrics.final_actions.as_dict().items():
        if count > 0:
            print(f"  {action}: {count}")
    print()

    print("GUARDRAIL DECISIONS")
    print("-" * 80)
    print(f"  ALLOW (simulated): {metrics.guardrail_allow_count}")
    print(f"  BLOCK (no execution): {metrics.guardrail_block_count}")
    print(f"  OVERRIDE (to HUMAN_REVIEW): {metrics.guardrail_override_count}")
    print()

    print("EXECUTION OUTCOMES")
    print("-" * 80)
    print(f"  Simulated executions: {metrics.simulated_execution_count}")
    print(f"  Blocked (no execution): {metrics.blocked_no_execution_count}")
    print(f"  Overridden (no execution): {metrics.overridden_no_execution_count}")
    print()

    print("OPPORTUNITY CLASSIFICATION")
    print("-" * 80)
    print(f"  Stopped: {metrics.stopped_opportunity_count} ({metrics.percentage_stopped()}%)")
    print(f"  Human review: {metrics.human_review_opportunity_count}")
    print(f"  Automated: {metrics.simulated_execution_count} ({metrics.percentage_automated()}%)")
    print(f"  Requiring human intervention: {metrics.percentage_human_review()}%")
    print()

    print("EXPECTED RECOVERY BY FINAL ACTION")
    print("-" * 80)
    for action, recovery in metrics.expected_recovery_by_final_action.items():
        if recovery > 0:
            print(f"  {action}: ${recovery:,.2f}")
    print()

    print("OUTSTANDING AMOUNT BY FINAL ACTION")
    print("-" * 80)
    for action, amount in metrics.amount_by_final_action.items():
        if amount > 0:
            print(f"  {action}: ${amount:,.2f}")
    print()

    # Print representative audit records
    print("=" * 80)
    print("REPRESENTATIVE AUDIT RECORDS")
    print("=" * 80)

    audit_examples = {
        "ALLOWED": None,
        "BLOCKED": None,
        "OVERRIDDEN": None,
        "STOP": None,
        "HUMAN_REVIEW": None,
    }

    for result in results:
        audit = result.execution.audit
        status = result.execution.guardrail.status.value

        if status == "ALLOW" and audit_examples["ALLOWED"] is None:
            audit_examples["ALLOWED"] = (result, "Allowed Action (Simulated)")

        if status == "BLOCK" and audit_examples["BLOCKED"] is None:
            audit_examples["BLOCKED"] = (result, "Blocked Action (No Execution)")

        if status == "OVERRIDE" and audit_examples["OVERRIDDEN"] is None:
            audit_examples["OVERRIDDEN"] = (result, "Overridden Action (To HUMAN_REVIEW)")

        if audit.final_action.value == "STOP" and audit_examples["STOP"] is None:
            audit_examples["STOP"] = (result, "STOP Action")

        if audit.final_action.value == "HUMAN_REVIEW" and audit_examples["HUMAN_REVIEW"] is None:
            audit_examples["HUMAN_REVIEW"] = (result, "HUMAN_REVIEW Action")

    for example_type, example_data in audit_examples.items():
        if example_data is None:
            continue

        result, title = example_data
        audit = result.execution.audit

        print()
        print("-" * 80)
        print(f"{title}")
        print("-" * 80)
        print(f"Audit ID:             {audit.audit_id[:16]}...")
        print(f"Promise ID:           {audit.promise_id}")
        print(f"Customer ID:          {audit.customer_id}")
        print(f"Invoice ID:           {audit.invoice_id}")
        print(f"Expected Recovery:    ${audit.expected_recovery:,.2f}")
        print(f"Break Probability:    {audit.break_probability:.2%}")
        print(f"Promise Credibility:  {audit.promise_credibility:.1f}")
        print(f"Priority Tier:        {audit.priority_tier}")
        print()
        print(f"Recommended Action:   {audit.recommended_action.value}")
        print(f"Guardrail Status:     {audit.guardrail_status.value}")
        print(f"Final Action:         {audit.final_action.value}")
        print(f"Reason Code:          {audit.reason_code}")
        print(f"Reason:               {audit.reason}")
        print(f"Simulated:            {audit.simulated}")
        print(f"Execution Status:     {audit.execution_status}")

    print()
    print("=" * 80)
    print("No real recovery actions were executed.")
    print("All executions are simulated audit records only.")
    print("=" * 80)


if __name__ == "__main__":
    main()
