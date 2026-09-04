"""End-to-end recovery pipeline orchestration for portfolio evaluation.

This module orchestrates the complete recovery workflow:
1. Decision Engine (recommends an action)
2. Guardrail Engine (permits, blocks, or overrides)
3. Action Executor (records the audit trail)

The orchestrator does not bypass or invent decisions. It chains the existing
components deterministically and collects audit records for portfolio analysis.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from promise_ledger.risk.prioritization import RecoveryOpportunity

from .decision import RecoveryDecisionEngine
from .executor import ActionExecutor, ExecutionResult
from .types import RecoveryDecision


@dataclass(frozen=True)
class OrchestrationContext:
    """Immutable context for one opportunity evaluation."""

    opportunity: RecoveryOpportunity
    invoice: Mapping[str, Any]
    promise: Mapping[str, Any]
    paid_amount: float
    automated_contact_count: int
    latest_recovery_action_date: str | None
    additional_context: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class OrchestrationResult:
    """Result of orchestrating one opportunity through the complete pipeline."""

    opportunity: RecoveryOpportunity
    decision: RecoveryDecision
    execution: ExecutionResult
    evaluation_timestamp: str


class RecoveryOrchestrator:
    """Process unresolved promises through the complete recovery pipeline.

    Does not make its own decisions, does not bypass guardrails, does not
    modify databases or send messages. Records audit trails for all decisions.
    """

    def __init__(
        self,
        decision_engine: RecoveryDecisionEngine,
        executor: ActionExecutor,
    ):
        self.decision_engine = decision_engine
        self.executor = executor

    def orchestrate_one(
        self,
        context: OrchestrationContext,
        row_context: Mapping[str, Any] | None = None,
    ) -> OrchestrationResult:
        """Process one opportunity: decide → guardrail → execute → audit.

        Args:
            context: Opportunity and supporting data
            row_context: Optional historical feature context for the decision

        Returns:
            OrchestrationResult with decision and execution audit
        """
        opportunity = context.opportunity

        # Step 1: Decision Engine recommends an action
        decision = self.decision_engine.decide(opportunity, row_context)

        # Step 2 & 3: Guardrail Engine (via Executor) validates and records
        # Handle both dict and sqlite3.Row objects
        invoice = dict(context.invoice) if hasattr(context.invoice, "keys") else context.invoice
        promise = dict(context.promise) if hasattr(context.promise, "keys") else context.promise

        invoice_status = invoice.get("status", "UNKNOWN")
        promise_outcome = promise.get("outcome", "UNKNOWN")
        current_outstanding = max(
            0.0,
            float(invoice.get("amount", 0.0)) - context.paid_amount,
        )

        # Get evaluation_date from additional_context if available
        evaluation_date = None
        if context.additional_context:
            evaluation_date = context.additional_context.get("evaluation_date")

        if not evaluation_date:
            raise ValueError(
                "evaluation_date is required in additional_context for deterministic audit records"
            )

        executor_context = {
            "invoice_id": opportunity.invoice_id,
            "invoice_amount": float(invoice.get("amount", 0.0)),
            "current_outstanding_amount": current_outstanding,
            "outstanding_amount": opportunity.outstanding_amount,
            "expected_recovery": opportunity.expected_recovery,
            "break_probability": opportunity.break_probability,
            "invoice_status": invoice_status,
            "promise_outcome": promise_outcome,
            "automated_contact_count": context.automated_contact_count,
            "latest_recovery_action_date": context.latest_recovery_action_date,
            "evaluation_date": evaluation_date,
        }

        # Add any additional context (but don't override the fields we've already set)
        if context.additional_context:
            for key, value in context.additional_context.items():
                if key not in executor_context:
                    executor_context[key] = value

        execution = self.executor.execute(decision, executor_context)

        return OrchestrationResult(
            opportunity=opportunity,
            decision=decision,
            execution=execution,
            evaluation_timestamp=executor_context.get("evaluation_date", ""),
        )

    def orchestrate_portfolio(
        self,
        contexts: Sequence[OrchestrationContext],
        row_contexts: Mapping[int, Mapping[str, Any]] | None = None,
    ) -> list[OrchestrationResult]:
        """Process all opportunities in the portfolio deterministically.

        Args:
            contexts: Sequence of opportunities to evaluate
            row_contexts: Optional map of promise_id to historical feature context

        Returns:
            List of OrchestrationResults in input order
        """
        results: list[OrchestrationResult] = []
        row_contexts = row_contexts or {}

        for context in contexts:
            promise_id = context.opportunity.promise_id
            row_context = row_contexts.get(promise_id)
            result = self.orchestrate_one(context, row_context)
            results.append(result)

        return results
