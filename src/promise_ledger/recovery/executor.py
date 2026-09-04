"""Side-effect-free simulated action execution and audit records."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .guardrails import GuardrailEngine, GuardrailResult, GuardrailStatus
from .types import RecoveryAction, RecoveryDecision


@dataclass(frozen=True)
class AuditRecord:
    """Immutable record of a simulated or blocked action decision."""

    audit_id: str
    evaluation_date: str
    promise_id: int
    invoice_id: int
    customer_id: int
    recommended_action: RecoveryAction
    guardrail_status: GuardrailStatus
    final_action: RecoveryAction
    reason_code: str
    reason: str
    expected_recovery: float | None
    break_probability: float | None
    promise_credibility: float | None
    priority_tier: str | None
    simulated: bool
    execution_status: str

    def as_dict(self) -> dict[str, object]:
        return {
            "audit_id": self.audit_id,
            "evaluation_date": self.evaluation_date,
            "promise_id": self.promise_id,
            "invoice_id": self.invoice_id,
            "customer_id": self.customer_id,
            "recommended_action": self.recommended_action.value,
            "guardrail_status": self.guardrail_status.value,
            "final_action": self.final_action.value,
            "reason_code": self.reason_code,
            "reason": self.reason,
            "expected_recovery": self.expected_recovery,
            "break_probability": self.break_probability,
            "promise_credibility": self.promise_credibility,
            "priority_tier": self.priority_tier,
            "simulated": self.simulated,
            "execution_status": self.execution_status,
        }


@dataclass(frozen=True)
class ExecutionResult:
    """Guardrail result plus its corresponding audit record."""

    guardrail: GuardrailResult
    audit: AuditRecord


class ActionExecutor:
    """Record what would happen after guardrails, without performing it."""

    def __init__(self, guardrails: GuardrailEngine):
        self.guardrails = guardrails

    def execute(self, decision: RecoveryDecision, context: Mapping[str, Any]) -> ExecutionResult:
        """Evaluate and record a decision; never send, pay, or mutate a ledger."""
        evaluation_date = context.get("evaluation_date")
        if not evaluation_date:
            raise ValueError("execution context requires a deterministic evaluation_date")

        guardrail = self.guardrails.evaluate(decision.recommended_action, context)
        simulated = guardrail.status is GuardrailStatus.ALLOW
        if guardrail.status is GuardrailStatus.ALLOW:
            execution_status = "SIMULATED_EXECUTION"
        elif guardrail.status is GuardrailStatus.BLOCK:
            execution_status = "BLOCKED_NO_EXECUTION"
        else:
            execution_status = "OVERRIDDEN_NO_EXECUTION"

        fields = {
            "evaluation_date": str(evaluation_date),
            "promise_id": decision.promise_id,
            "invoice_id": int(context.get("invoice_id", 0)),
            "customer_id": decision.customer_id,
            "recommended_action": decision.recommended_action.value,
            "guardrail": guardrail.as_dict(),
            "expected_recovery": decision.expected_recovery,
            "break_probability": context.get("break_probability"),
            "promise_credibility": decision.promise_credibility,
            "priority_tier": decision.priority_tier,
        }
        canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"))
        audit_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        audit = AuditRecord(
            audit_id=audit_id,
            evaluation_date=str(evaluation_date),
            promise_id=decision.promise_id,
            invoice_id=int(context.get("invoice_id", 0)),
            customer_id=decision.customer_id,
            recommended_action=decision.recommended_action,
            guardrail_status=guardrail.status,
            final_action=guardrail.final_action,
            reason_code=guardrail.reason_code,
            reason=guardrail.reason,
            expected_recovery=decision.expected_recovery,
            break_probability=(float(context["break_probability"]) if "break_probability" in context else None),
            promise_credibility=decision.promise_credibility,
            priority_tier=decision.priority_tier,
            simulated=simulated,
            execution_status=execution_status,
        )
        return ExecutionResult(guardrail=guardrail, audit=audit)
