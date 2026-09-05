"""Pydantic response models for the Promise Ledger API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ExperimentMetricsResponse(BaseModel):
    evaluation_date: str
    evaluation_count: int
    total_outstanding_amount: float
    control_recovered_amount: float
    treatment_recovered_amount: float
    incremental_recovery_amount: float
    control_recovery_rate: float
    treatment_recovery_rate: float
    treatment_improvement_percent: float
    automation_rate: float
    human_review_rate: float
    stopped_rate: float


class OpportunityResponse(BaseModel):
    promise_id: int
    invoice_id: int
    customer_id: int
    outstanding_amount: float
    break_probability: float
    promise_credibility_score: float
    recovery_probability: float
    expected_recovery: float
    priority_rank: int
    priority_tier: str
    priority_score: float
    explanation: list[str]
    recommended_action: str | None = None
    final_action: str | None = None
    guardrail_status: str | None = None


class OpportunityDetailResponse(OpportunityResponse):
    promise_created_date: str
    promised_payment_date: str
    promised_amount: float
    outcome: str
    invoice_amount: float
    invoice_status: str
    invoice_due_date: str
    paid_amount: float
    current_outstanding_amount: float


class PortfolioSummaryResponse(BaseModel):
    evaluation_count: int
    total_outstanding_amount: float
    total_expected_recovery: float
    average_expected_recovery_per_opportunity: float
    priority_tiers: dict[str, int]
    recommended_actions: dict[str, int]
    final_actions: dict[str, int]
    guardrail_outcomes: dict[str, int]
    simulated_execution_count: int
    blocked_no_execution_count: int
    overridden_no_execution_count: int
    stopped_opportunity_count: int
    human_review_opportunity_count: int
    percentage_automated: float
    percentage_human_review: float
    percentage_stopped: float
    expected_recovery_by_final_action: dict[str, float]
    amount_by_final_action: dict[str, float]
    experiment: ExperimentMetricsResponse | None = None


class EvaluationResponse(BaseModel):
    promise_id: int
    invoice_id: int
    customer_id: int
    recommended_action: str
    guardrail_status: str
    final_action: str
    reason_code: str
    explanation: str
    expected_recovery: float | None
    break_probability: float | None
    promise_credibility: float | None
    recovery_probability: float
    priority_tier: str
    audit: dict[str, Any]