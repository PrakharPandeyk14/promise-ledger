"""FastAPI routes for the read-only Promise Ledger backend."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from promise_ledger.config import DATABASE_PATH

from .models import (
    EvaluationResponse,
    ExperimentMetricsResponse,
    HealthResponse,
    OpportunityDetailResponse,
    OpportunityResponse,
    PortfolioSummaryResponse,
)
from .service import PromiseLedgerService


def _opportunity_response(
    snapshot,
    opportunity,
    recommendation: str | None = None,
    final_action: str | None = None,
    guardrail_status: str | None = None,
) -> OpportunityResponse:
    score = snapshot.scores[opportunity.promise_id]
    return OpportunityResponse(
        **opportunity.__dict__,
        explanation=list(score.explanation),
        recommended_action=recommendation,
        final_action=final_action,
        guardrail_status=guardrail_status,
    )


def _model_as_dict(model):
    dump = getattr(model, "model_dump", None)
    return dump() if dump else model.dict()


def create_app(database_path: Path = DATABASE_PATH) -> FastAPI:
    service = PromiseLedgerService(database_path)
    api = FastAPI(title="Promise Ledger API", version="1.0.0")

    @api.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok")

    @api.get("/portfolio/summary", response_model=PortfolioSummaryResponse)
    def portfolio_summary() -> PortfolioSummaryResponse:
        snapshot = service.snapshot()
        metrics = service.evaluate_portfolio(snapshot)
        tiers = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for opportunity in snapshot.opportunities:
            tiers[opportunity.priority_tier] = tiers.get(opportunity.priority_tier, 0) + 1
        exp_metrics = service.evaluate_experiment(snapshot)
        return PortfolioSummaryResponse(
            **metrics.as_dict(),
            priority_tiers=tiers,
            guardrail_outcomes={
                "ALLOW": metrics.guardrail_allow_count,
                "BLOCK": metrics.guardrail_block_count,
                "OVERRIDE": metrics.guardrail_override_count,
            },
            experiment=exp_metrics.as_dict(),
        )

    @api.get("/evaluation/experiment", response_model=ExperimentMetricsResponse)
    def evaluation_experiment() -> ExperimentMetricsResponse:
        snapshot = service.snapshot()
        exp_metrics = service.evaluate_experiment(snapshot)
        return ExperimentMetricsResponse(**exp_metrics.as_dict())

    @api.get("/opportunities", response_model=list[OpportunityResponse])
    def opportunities() -> list[OpportunityResponse]:
        snapshot = service.snapshot()
        orchestrations = {
            opp.promise_id: service.orchestrate(snapshot, opp)
            for opp in snapshot.opportunities
        }
        return [
            _opportunity_response(
                snapshot,
                item,
                recommendation=orchestrations[item.promise_id].decision.recommended_action.value,
                final_action=orchestrations[item.promise_id].execution.guardrail.final_action.value,
                guardrail_status=orchestrations[item.promise_id].execution.guardrail.status.value,
            )
            for item in snapshot.opportunities
        ]

    @api.get("/opportunities/{promise_id}", response_model=OpportunityDetailResponse)
    def opportunity_detail(promise_id: int) -> OpportunityDetailResponse:
        snapshot = service.snapshot()
        opportunity = next(
            (item for item in snapshot.opportunities if item.promise_id == promise_id), None
        )
        if opportunity is None:
            raise HTTPException(status_code=404, detail="Unresolved opportunity not found")
        orch = service.orchestrate(snapshot, opportunity)
        opp_resp = _opportunity_response(
            snapshot,
            opportunity,
            recommendation=orch.decision.recommended_action.value,
            final_action=orch.execution.guardrail.final_action.value,
            guardrail_status=orch.execution.guardrail.status.value,
        )
        invoice = snapshot.invoices[opportunity.invoice_id]
        promise = snapshot.promises[promise_id]
        return OpportunityDetailResponse(
            **_model_as_dict(opp_resp),
            promise_created_date=promise["promise_created_date"],
            promised_payment_date=promise["promised_payment_date"],
            promised_amount=float(promise["promised_amount"]),
            outcome=promise["outcome"],
            invoice_amount=float(invoice["amount"]),
            invoice_status=invoice["status"],
            invoice_due_date=invoice["due_date"],
            paid_amount=round(snapshot.paid_by_invoice.get(opportunity.invoice_id, 0.0), 2),
            current_outstanding_amount=round(
                max(0.0, float(invoice["amount"]) - snapshot.paid_by_invoice.get(opportunity.invoice_id, 0.0)),
                2,
            ),
        )

    @api.post("/opportunities/{promise_id}/evaluate", response_model=EvaluationResponse)
    def evaluate_opportunity(promise_id: int) -> EvaluationResponse:
        snapshot = service.snapshot()
        opportunity = next(
            (item for item in snapshot.opportunities if item.promise_id == promise_id), None
        )
        if opportunity is None:
            raise HTTPException(status_code=404, detail="Unresolved opportunity not found")
        result = service.orchestrate(snapshot, opportunity)
        audit = result.execution.audit.as_dict()
        return EvaluationResponse(
            promise_id=opportunity.promise_id,
            invoice_id=opportunity.invoice_id,
            customer_id=opportunity.customer_id,
            recommended_action=audit["recommended_action"],
            guardrail_status=audit["guardrail_status"],
            final_action=audit["final_action"],
            reason_code=audit["reason_code"],
            explanation=audit["reason"],
            expected_recovery=audit["expected_recovery"],
            break_probability=audit["break_probability"],
            promise_credibility=audit["promise_credibility"],
            recovery_probability=opportunity.recovery_probability,
            priority_tier=opportunity.priority_tier,
            audit=audit,
        )

    frontend_path = Path(__file__).resolve().parents[3] / "frontend"
    api.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

    return api


app = create_app()