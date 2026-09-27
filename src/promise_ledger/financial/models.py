"""Data models for Financial Intelligence Layer."""

from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class FinancialTransaction(BaseModel):
    id: str
    date: str
    amount: float
    transaction_type: str  # "INCOME" | "EXPENSE"
    category: str
    description: str
    is_recurring: bool = False
    merchant: str = ""


class FinancialSummaryResponse(BaseModel):
    current_cash_balance: float
    monthly_income: float
    monthly_expenses: float
    net_cash_flow: float
    total_receivables: float
    financial_risk_level: str  # "LOW" | "MEDIUM" | "HIGH"
    financial_risk_score: float
    risk_contributors: list[str]
    receivables_risk_insight: str
    receivables_at_risk_amount: float
    high_break_risk_count: int
    total_portfolio_receivables: float
    simulation_date: str


class RecurringExpenseItem(BaseModel):
    expense_id: str
    merchant: str
    category: str
    amount: float
    periodicity: str  # e.g. "Monthly"
    occurrences: int
    is_active: bool = True


class RecurringExpensesResponse(BaseModel):
    recurring_expenses: list[RecurringExpenseItem]
    total_monthly_recurring: float
    recurring_expense_ratio: float


class FinancialAnomalyItem(BaseModel):
    anomaly_id: str
    transaction_id: str
    date: str
    description: str
    category: str
    amount: float
    historical_average: float
    deviation_percentage: float
    severity: str  # "LOW" | "MEDIUM" | "HIGH"
    reason: str


class AnomaliesResponse(BaseModel):
    anomalies: list[FinancialAnomalyItem]
    total_anomalies: int
    high_severity_count: int


class BudgetCategoryItem(BaseModel):
    category: str
    budget: float
    spent: float
    remaining: float
    utilization_pct: float
    status: str  # "ON_TRACK" | "WARNING" | "OVER_BUDGET"


class BudgetsResponse(BaseModel):
    period: str
    total_budget: float
    total_spent: float
    total_remaining: float
    overall_utilization_pct: float
    categories: list[BudgetCategoryItem]


class FinancialGoalItem(BaseModel):
    goal_id: str
    name: str
    target_amount: float
    current_amount: float
    target_date: str
    progress_pct: float
    status: str  # "ON_TRACK" | "NEEDS_ATTENTION"


class FinancialGoalsResponse(BaseModel):
    goals: list[FinancialGoalItem]
    total_target: float
    total_saved: float


# ==============================================================================
# Phase 2 Models: Forecasting, Scenario Simulation & AI Financial Decision Support
# ==============================================================================

class ForecastMonth(BaseModel):
    month: str  # e.g. "2026-09"
    month_name: str  # e.g. "September 2026"
    projected_income: float
    projected_expenses: float
    projected_net_cash_flow: float
    projected_ending_cash: float
    receivables_contribution: float
    recurring_expense_baseline: float


class ForecastResponse(BaseModel):
    forecast_period: str
    starting_cash_balance: float
    months: list[ForecastMonth]
    total_projected_income: float
    total_projected_expenses: float
    total_projected_net_flow: float
    projected_final_cash: float
    confidence: str  # "LOW" | "MEDIUM" | "HIGH"
    confidence_score: float
    methodology_summary: str
    receivables_integration_note: str


class ScenarioRequest(BaseModel):
    receivable_delay_days: int = Field(default=0, ge=0, le=120, description="Delay in days for receivables collection")
    expense_change_percent: float = Field(default=0.0, ge=-50.0, le=150.0, description="Percentage change in operating expenses")
    additional_monthly_expense: float = Field(default=0.0, ge=0.0, le=1_000_000.0, description="Extra fixed monthly expenditure")
    recovery_rate_adjustment_percent: float = Field(default=0.0, ge=-100.0, le=100.0, description="Adjustment to model expected recovery percentage")


class ScenarioCaseMetrics(BaseModel):
    projected_ending_cash: float
    total_net_cash_flow: float
    average_monthly_net_flow: float
    cash_runway_months: float
    financial_risk_level: str
    risk_score: float


class ScenarioResponse(BaseModel):
    parameters: ScenarioRequest
    base_case: ScenarioCaseMetrics
    scenario_case: ScenarioCaseMetrics
    delta: dict[str, float]
    risk_change: dict[str, str]
    explanation: str
    monthly_comparison: list[dict[str, Any]]


class RecommendationReviewRequest(BaseModel):
    action: str = Field(description="Review action: REVIEW, APPROVE, or REJECT")
    reviewer_notes: str | None = Field(default=None, description="Optional merchant review notes")


class FinancialRecommendationItem(BaseModel):
    id: str
    priority: str  # "HIGH" | "MEDIUM" | "LOW"
    recommendation: str
    category: str
    reason: str
    supporting_evidence: list[str]
    suggested_action: str
    action_type: str
    financial_impact_estimate: str
    human_approval_required: bool = True
    status: str = "NEW"  # "NEW" | "REVIEWED" | "APPROVED" | "REJECTED"
    created_at: str
    reviewed_at: str | None = None
    reviewer_notes: str | None = None


class RecommendationsResponse(BaseModel):
    recommendations: list[FinancialRecommendationItem]
    total_count: int
    high_priority_count: int
    pending_human_approval_count: int

