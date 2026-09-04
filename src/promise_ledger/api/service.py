"""Read-only service adapter for the existing Promise Ledger pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
from promise_ledger.risk.prioritization import RecoveryOpportunity, prioritize_opportunities
from promise_ledger.risk.scoring import PromiseScore, score_rows


_AUTOMATED_TYPES = frozenset(("SOFT_REMINDER", "FIRM_REMINDER", "PAYMENT_PLAN", "ESCALATE"))


@dataclass(frozen=True)
class PortfolioSnapshot:
    opportunities: list[RecoveryOpportunity]
    scores: dict[int, PromiseScore]
    rows: dict[int, dict[str, Any]]
    invoices: dict[int, dict[str, Any]]
    promises: dict[int, dict[str, Any]]
    paid_by_invoice: dict[int, float]
    automated_contacts_by_invoice: dict[int, int]
    latest_action_by_invoice: dict[int, str | None]
    policy: MerchantPolicy


class PromiseLedgerService:
    """Assemble API views from the existing deterministic intelligence code."""

    def __init__(self, database_path: Path = DATABASE_PATH):
        self.database_path = Path(database_path)
        self._snapshot_cache: PortfolioSnapshot | None = None

    def snapshot(self) -> PortfolioSnapshot:
        if self._snapshot_cache is not None:
            return self._snapshot_cache

        connection = connect(self.database_path)
        try:
            feature_rows = build_feature_dataset(connection)
            policy_row = connection.execute(
                "SELECT * FROM merchant_policies ORDER BY policy_id LIMIT 1"
            ).fetchone()
            invoices = {
                row["invoice_id"]: dict(row)
                for row in connection.execute("SELECT * FROM invoices ORDER BY invoice_id")
            }
            promises = {
                row["promise_id"]: dict(row)
                for row in connection.execute("SELECT * FROM promises ORDER BY promise_id")
            }
            actions = connection.execute(
                "SELECT * FROM recovery_actions ORDER BY action_date, action_id"
            ).fetchall()
            payments = connection.execute(
                "SELECT invoice_id, SUM(amount) AS paid FROM payments GROUP BY invoice_id"
            ).fetchall()
        finally:
            connection.close()

        resolved = supervised_rows(feature_rows)
        current = [row for row in feature_rows if row["target_broken"] is None]
        policy = MerchantPolicy.from_row(policy_row)
        if not current:
            snapshot = PortfolioSnapshot([], {}, {}, invoices, promises, {}, {}, {}, policy)
            self._snapshot_cache = snapshot
            return snapshot

        model = RandomForestModel(random_state=SEED).fit(
            feature_matrix(resolved),
            [row["target_broken"] for row in resolved],
        )
        scores = score_rows(
            current,
            [pair[1] for pair in model.predict_proba(feature_matrix(current))],
        )
        opportunities = prioritize_opportunities(current, scores)
        actions_by_invoice: dict[int, list[dict[str, Any]]] = {}
        for action in actions:
            actions_by_invoice.setdefault(action["invoice_id"], []).append(dict(action))
        paid_by_invoice = {
            row["invoice_id"]: float(row["paid"] or 0.0) for row in payments
        }
        automated_contacts = {
            invoice_id: sum(item["action_type"] in _AUTOMATED_TYPES for item in invoice_actions)
            for invoice_id, invoice_actions in actions_by_invoice.items()
        }
        latest_action = {
            invoice_id: invoice_actions[-1]["action_date"] if invoice_actions else None
            for invoice_id, invoice_actions in actions_by_invoice.items()
        }
        snapshot = PortfolioSnapshot(
            opportunities=opportunities,
            scores={score.promise_id: score for score in scores},
            rows={int(row["promise_id"]): row for row in current},
            invoices=invoices,
            promises=promises,
            paid_by_invoice=paid_by_invoice,
            automated_contacts_by_invoice=automated_contacts,
            latest_action_by_invoice=latest_action,
            policy=policy,
        )
        self._snapshot_cache = snapshot
        return snapshot

    def invalidate_snapshot(self) -> None:
        """Clear the cached snapshot after an external database change."""
        self._snapshot_cache = None

    def orchestrate(self, snapshot: PortfolioSnapshot, opportunity: RecoveryOpportunity):
        row = snapshot.rows[opportunity.promise_id]
        invoice = snapshot.invoices[opportunity.invoice_id]
        promise = snapshot.promises[opportunity.promise_id]
        context = OrchestrationContext(
            opportunity=opportunity,
            invoice=invoice,
            promise=promise,
            paid_amount=snapshot.paid_by_invoice.get(opportunity.invoice_id, 0.0),
            automated_contact_count=snapshot.automated_contacts_by_invoice.get(opportunity.invoice_id, 0),
            latest_recovery_action_date=snapshot.latest_action_by_invoice.get(opportunity.invoice_id),
            additional_context={"evaluation_date": SIMULATION_DATE.isoformat()},
        )
        orchestrator = RecoveryOrchestrator(
            RecoveryDecisionEngine(), ActionExecutor(GuardrailEngine(snapshot.policy))
        )
        return orchestrator.orchestrate_one(context, row)

    def evaluate_portfolio(self, snapshot: PortfolioSnapshot):
        return PortfolioEvaluator.evaluate([
            self.orchestrate(snapshot, opportunity) for opportunity in snapshot.opportunities
        ])