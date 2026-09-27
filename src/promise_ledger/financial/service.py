"""Service orchestrator for Financial Intelligence Layer."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from promise_ledger.api.service import PromiseLedgerService
from promise_ledger.config import DATABASE_PATH, SIMULATION_DATE

from .anomalies import detect_financial_anomalies
from .forecasting import generate_cash_flow_forecast
from .health import calculate_financial_health
from .models import (
    AnomaliesResponse,
    BudgetCategoryItem,
    BudgetsResponse,
    FinancialAnomalyItem,
    FinancialGoalItem,
    FinancialGoalsResponse,
    FinancialRecommendationItem,
    FinancialSummaryResponse,
    FinancialTransaction,
    ForecastResponse,
    RecommendationsResponse,
    RecurringExpenseItem,
    RecurringExpensesResponse,
    ScenarioRequest,
    ScenarioResponse,
)
from .recommendations import (
    generate_financial_recommendations,
    review_financial_recommendation,
)
from .recurring import detect_recurring_expenses
from .simulation import simulate_financial_scenario
from .synthetic_data import (
    get_all_transactions,
    get_budget_configuration,
    get_synthetic_goals,
)


class FinancialService:
    """Provides financial intelligence data, recurring expenses, anomalies, budgets, and goals."""

    def __init__(
        self,
        database_path: Path = DATABASE_PATH,
        simulation_date: date = SIMULATION_DATE,
        promise_service: PromiseLedgerService | None = None,
    ):
        self.database_path = Path(database_path)
        self.simulation_date = simulation_date
        self.promise_service = promise_service or PromiseLedgerService(database_path)
        self._cached_transactions: list[dict[str, Any]] | None = None
        self._cached_recurring: tuple[list[dict[str, Any]], float] | None = None
        self._cached_anomalies: list[dict[str, Any]] | None = None

    def get_transactions(
        self,
        transaction_type: str | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> list[FinancialTransaction]:
        """Fetch transaction histories with optional type and category filters."""
        if self._cached_transactions is None:
            self._cached_transactions = get_all_transactions(
                database_path=self.database_path,
                simulation_date=self.simulation_date,
            )

        items = self._cached_transactions
        if transaction_type:
            items = [t for t in items if t["transaction_type"].upper() == transaction_type.upper()]
        if category:
            items = [t for t in items if t["category"].lower() == category.lower()]

        return [FinancialTransaction(**t) for t in items[:limit]]

    def get_recurring_expenses(self) -> RecurringExpensesResponse:
        """Detect and return recurring financial expense intelligence."""
        if self._cached_recurring is None:
            if self._cached_transactions is None:
                self._cached_transactions = get_all_transactions(
                    database_path=self.database_path,
                    simulation_date=self.simulation_date,
                )
            self._cached_recurring = detect_recurring_expenses(self._cached_transactions)

        rec_items, total_monthly = self._cached_recurring
        
        # Calculate ratio of recurring to total monthly expenses
        curr_month = f"{self.simulation_date.year:04d}-{self.simulation_date.month:02d}"
        month_expenses = sum(
            float(t["amount"])
            for t in self._cached_transactions
            if t["transaction_type"] == "EXPENSE" and t["date"].startswith(curr_month)
        )
        ratio = round((total_monthly / month_expenses) * 100, 1) if month_expenses > 0 else 0.0

        return RecurringExpensesResponse(
            recurring_expenses=[RecurringExpenseItem(**item) for item in rec_items],
            total_monthly_recurring=total_monthly,
            recurring_expense_ratio=ratio,
        )

    def get_anomalies(self) -> AnomaliesResponse:
        """Detect and return unusual financial transactions with severity and explainability."""
        if self._cached_anomalies is None:
            if self._cached_transactions is None:
                self._cached_transactions = get_all_transactions(
                    database_path=self.database_path,
                    simulation_date=self.simulation_date,
                )
            self._cached_anomalies = detect_financial_anomalies(self._cached_transactions)

        items = [FinancialAnomalyItem(**a) for a in self._cached_anomalies]
        high_count = sum(1 for a in items if a.severity == "HIGH")
        return AnomaliesResponse(
            anomalies=items,
            total_anomalies=len(items),
            high_severity_count=high_count,
        )

    def get_budgets(self) -> BudgetsResponse:
        """Calculate budget tracking against actual monthly spending."""
        if self._cached_transactions is None:
            self._cached_transactions = get_all_transactions(
                database_path=self.database_path,
                simulation_date=self.simulation_date,
            )

        curr_month = f"{self.simulation_date.year:04d}-{self.simulation_date.month:02d}"
        spent_by_category: dict[str, float] = defaultdict(float)
        for t in self._cached_transactions:
            if t["transaction_type"] == "EXPENSE" and t["date"].startswith(curr_month):
                spent_by_category[t["category"]] += float(t["amount"])

        config = get_budget_configuration()
        categories: list[BudgetCategoryItem] = []
        total_budget = 0.0
        total_spent = 0.0

        for cat, budget_val in config.items():
            spent_val = round(spent_by_category.get(cat, 0.0), 2)
            rem_val = round(budget_val - spent_val, 2)
            util_pct = round((spent_val / budget_val) * 100, 1) if budget_val > 0 else 0.0

            if util_pct > 100.0:
                status = "OVER_BUDGET"
            elif util_pct >= 85.0:
                status = "WARNING"
            else:
                status = "ON_TRACK"

            categories.append(
                BudgetCategoryItem(
                    category=cat,
                    budget=budget_val,
                    spent=spent_val,
                    remaining=rem_val,
                    utilization_pct=util_pct,
                    status=status,
                )
            )
            total_budget += budget_val
            total_spent += spent_val

        overall_util = round((total_spent / total_budget) * 100, 1) if total_budget > 0 else 0.0

        # Sort categories by spent descending
        categories.sort(key=lambda c: c.spent, reverse=True)

        return BudgetsResponse(
            period=curr_month,
            total_budget=round(total_budget, 2),
            total_spent=round(total_spent, 2),
            total_remaining=round(total_budget - total_spent, 2),
            overall_utilization_pct=overall_util,
            categories=categories,
        )

    def get_goals(self) -> FinancialGoalsResponse:
        """Fetch financial goals and progress."""
        raw_goals = get_synthetic_goals()
        goals = [FinancialGoalItem(**g) for g in raw_goals]
        total_target = sum(g.target_amount for g in goals)
        total_saved = sum(g.current_amount for g in goals)
        return FinancialGoalsResponse(
            goals=goals,
            total_target=round(total_target, 2),
            total_saved=round(total_saved, 2),
        )

    def get_summary(self) -> FinancialSummaryResponse:
        """Compute holistic financial health summary connected with Promise Ledger risk."""
        if self._cached_transactions is None:
            self._cached_transactions = get_all_transactions(
                database_path=self.database_path,
                simulation_date=self.simulation_date,
            )

        recurring_resp = self.get_recurring_expenses()
        anomalies_resp = self.get_anomalies()

        # Fetch actual Promise Ledger snapshot and metrics
        snapshot = self.promise_service.snapshot()
        portfolio_metrics = self.promise_service.evaluate_portfolio(snapshot)

        health_data = calculate_financial_health(
            transactions=self._cached_transactions,
            anomalies=[a.model_dump() for a in anomalies_resp.anomalies],
            recurring_expenses=[r.model_dump() for r in recurring_resp.recurring_expenses],
            total_recurring=recurring_resp.total_monthly_recurring,
            portfolio_metrics=portfolio_metrics,
            opportunities=snapshot.opportunities,
            simulation_date=self.simulation_date,
        )

        return FinancialSummaryResponse(**health_data)

    def get_forecast(self) -> ForecastResponse:
        """Generate rolling 3-month cash flow forecast integrating Promise Ledger expected recovery."""
        summary = self.get_summary()
        recurring_resp = self.get_recurring_expenses()
        snapshot = self.promise_service.snapshot()
        portfolio_metrics = self.promise_service.evaluate_portfolio(snapshot)

        return generate_cash_flow_forecast(
            starting_cash=summary.current_cash_balance,
            total_recurring_expenses=recurring_resp.total_monthly_recurring,
            total_expected_recovery=float(getattr(portfolio_metrics, "total_expected_recovery", 0.0)),
            total_outstanding_receivables=float(getattr(portfolio_metrics, "total_outstanding_amount", 0.0)),
            historical_transactions=self._cached_transactions or [],
            simulation_date=self.simulation_date,
            months_ahead=3,
        )

    def simulate_scenario(self, request: ScenarioRequest) -> ScenarioResponse:
        """Simulate financial position under what-if scenario assumptions (pure simulation, no DB mutations)."""
        base_forecast = self.get_forecast()
        summary = self.get_summary()

        return simulate_financial_scenario(
            base_forecast=base_forecast,
            request=request,
            base_risk_level=summary.financial_risk_level,
            base_risk_score=summary.financial_risk_score,
        )

    def get_recommendations(self) -> RecommendationsResponse:
        """Generate explainable AI decision-support financial recommendations."""
        summary = self.get_summary()
        anomalies_resp = self.get_anomalies()
        recurring_resp = self.get_recurring_expenses()
        budgets_resp = self.get_budgets()
        goals_resp = self.get_goals()
        forecast = self.get_forecast()

        return generate_financial_recommendations(
            financial_summary=summary.model_dump(),
            anomalies=[a.model_dump() for a in anomalies_resp.anomalies],
            recurring_expenses=[r.model_dump() for r in recurring_resp.recurring_expenses],
            budgets=budgets_resp.model_dump(),
            goals=[g.model_dump() for g in goals_resp.goals],
            forecast=forecast,
        )

    def review_recommendation(
        self,
        recommendation_id: str,
        action: str,
        reviewer_notes: str | None = None,
    ) -> FinancialRecommendationItem | None:
        """Acknowledge or update review status for a financial recommendation with merchant human-in-the-loop."""
        return review_financial_recommendation(
            recommendation_id=recommendation_id,
            action=action,
            reviewer_notes=reviewer_notes,
        )

