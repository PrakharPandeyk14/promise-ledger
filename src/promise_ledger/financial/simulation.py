"""Deterministic What-If Financial Scenario Simulation Engine."""

from __future__ import annotations

from typing import Any

from .models import (
    ForecastResponse,
    ScenarioCaseMetrics,
    ScenarioRequest,
    ScenarioResponse,
)


def simulate_financial_scenario(
    base_forecast: ForecastResponse,
    request: ScenarioRequest,
    base_risk_level: str = "MEDIUM",
    base_risk_score: float = 70.0,
) -> ScenarioResponse:
    """Simulate what-if financial scenario based on altered receivables and expense assumptions.
    
    Guarantees pure read-only simulation without modifying or mutating database records.
    """
    delay_days = request.receivable_delay_days
    expense_pct = request.expense_change_percent / 100.0
    extra_expense = request.additional_monthly_expense
    recovery_adj = request.recovery_rate_adjustment_percent / 100.0

    # Delay ratio: 30 days = 1 full monthly shift
    delay_ratio = min(1.0, delay_days / 30.0) if delay_days > 0 else 0.0

    base_months = base_forecast.months
    scenario_comparison: list[dict[str, Any]] = []

    # Temporary buckets to track shifted receivables cash flows
    shifted_inflows = [0.0] * (len(base_months) + 1)
    scenario_current_cash = base_forecast.starting_cash_balance

    # Step 1: Calculate adjusted receivables across months with delay
    for i, bm in enumerate(base_months):
        adjusted_rec = round(bm.receivables_contribution * (1.0 + recovery_adj), 2)
        on_time = round(adjusted_rec * (1.0 - delay_ratio), 2)
        delayed_amount = round(adjusted_rec * delay_ratio, 2)

        shifted_inflows[i] += on_time
        shifted_inflows[i + 1] += delayed_amount  # Pushed to next month

    # Step 2: Build monthly scenario forecast
    for i, bm in enumerate(base_months):
        # Base non-receivables income
        core_income = bm.projected_income - bm.receivables_contribution
        scen_income = round(core_income + shifted_inflows[i], 2)

        # Adjusted expenses: base * (1 + pct) + extra monthly expense
        scen_expenses = round(bm.projected_expenses * (1.0 + expense_pct) + extra_expense, 2)
        scen_net = round(scen_income - scen_expenses, 2)
        scenario_current_cash = round(scenario_current_cash + scen_net, 2)

        scenario_comparison.append({
            "month": bm.month,
            "month_name": bm.month_name,
            "base_income": bm.projected_income,
            "scenario_income": scen_income,
            "base_expenses": bm.projected_expenses,
            "scenario_expenses": scen_expenses,
            "base_net_flow": bm.projected_net_cash_flow,
            "scenario_net_flow": scen_net,
            "base_ending_cash": bm.projected_ending_cash,
            "scenario_ending_cash": scenario_current_cash,
        })

    # Base case metrics
    base_ending_cash = base_forecast.projected_final_cash
    base_total_net = base_forecast.total_projected_net_flow
    base_avg_net = round(base_total_net / len(base_months), 2)
    base_last_exp = base_months[-1].projected_expenses
    base_runway = round(base_ending_cash / base_last_exp, 1) if base_last_exp > 0 else 0.0

    base_metrics = ScenarioCaseMetrics(
        projected_ending_cash=base_ending_cash,
        total_net_cash_flow=base_total_net,
        average_monthly_net_flow=base_avg_net,
        cash_runway_months=base_runway,
        financial_risk_level=base_risk_level,
        risk_score=base_risk_score,
    )

    # Scenario case metrics
    scen_ending_cash = scenario_current_cash
    scen_total_net = round(sum(m["scenario_net_flow"] for m in scenario_comparison), 2)
    scen_avg_net = round(scen_total_net / len(base_months), 2)
    scen_last_exp = scenario_comparison[-1]["scenario_expenses"]
    scen_runway = round(scen_ending_cash / scen_last_exp, 1) if scen_last_exp > 0 else 0.0

    # Calculate scenario risk score and level
    scen_risk_score = base_risk_score
    if scen_avg_net < 0:
        scen_risk_score += 25.0
    elif scen_avg_net < base_avg_net * 0.5:
        scen_risk_score += 15.0

    if scen_runway < 2.5:
        scen_risk_score += 20.0
    elif scen_runway < 3.0:
        scen_risk_score += 10.0

    if delay_days >= 20:
        scen_risk_score += 10.0
    if request.expense_change_percent >= 15.0:
        scen_risk_score += 10.0

    scen_risk_score = min(100.0, max(0.0, scen_risk_score))

    if scen_risk_score >= 75.0:
        scen_risk_level = "HIGH"
    elif scen_risk_score >= 35.0:
        scen_risk_level = "MEDIUM"
    else:
        scen_risk_level = "LOW"

    scenario_metrics = ScenarioCaseMetrics(
        projected_ending_cash=scen_ending_cash,
        total_net_cash_flow=scen_total_net,
        average_monthly_net_flow=scen_avg_net,
        cash_runway_months=scen_runway,
        financial_risk_level=scen_risk_level,
        risk_score=scen_risk_score,
    )

    # Delta
    delta = {
        "ending_cash_difference": round(scen_ending_cash - base_ending_cash, 2),
        "projected_ending_cash": round(scen_ending_cash - base_ending_cash, 2),
        "total_net_flow_difference": round(scen_total_net - base_total_net, 2),
        "total_net_cash_flow": round(scen_total_net - base_total_net, 2),
        "monthly_net_flow_difference": round(scen_avg_net - base_avg_net, 2),
        "average_monthly_net_flow": round(scen_avg_net - base_avg_net, 2),
        "runway_difference_months": round(scen_runway - base_runway, 1),
        "cash_runway_months": round(scen_runway - base_runway, 1),
        "risk_score_difference": round(scen_risk_score - base_risk_score, 1),
        "risk_score": round(scen_risk_score - base_risk_score, 1),
    }

    # Narrative explanation
    explanations: list[str] = []
    cash_diff = delta["ending_cash_difference"]

    if cash_diff < 0:
        explanations.append(
            f"Scenario decreases projected 3-month ending cash by ₹{abs(cash_diff):,.2f} "
            f"(runway shifts from {base_runway} to {scen_runway} months)."
        )
    elif cash_diff > 0:
        explanations.append(
            f"Scenario improves ending cash reserves by ₹{cash_diff:,.2f} "
            f"(runway extends from {base_runway} to {scen_runway} months)."
        )
    else:
        explanations.append("Scenario produces neutral cash variance against base projections.")

    contributors: list[str] = []
    if delay_days > 0:
        contributors.append(f"receivables collections are delayed by {delay_days} days")
    if request.expense_change_percent != 0:
        sign = "+" if request.expense_change_percent > 0 else ""
        contributors.append(f"operating expenses alter by {sign}{request.expense_change_percent}%")
    if extra_expense > 0:
        contributors.append(f"unbudgeted monthly expense of ₹{extra_expense:,.2f} is incurred")
    if recovery_adj != 0:
        sign = "+" if recovery_adj > 0 else ""
        contributors.append(f"promise recovery rate adjusts by {sign}{request.recovery_rate_adjustment_percent}%")

    if contributors:
        drivers = ", ".join(contributors)
        explanations.append(f"Primary cash pressure drivers: {drivers}.")

    if scen_risk_level != base_risk_level:
        explanations.append(f"Financial risk tier changes from {base_risk_level} to {scen_risk_level}.")

    explanation_text = " ".join(explanations)

    return ScenarioResponse(
        parameters=request,
        base_case=base_metrics,
        scenario_case=scenario_metrics,
        delta=delta,
        risk_change={
            "base_risk": base_risk_level,
            "scenario_risk": scen_risk_level,
            "risk_level": f"{base_risk_level} -> {scen_risk_level}",
        },
        explanation=explanation_text,
        monthly_comparison=scenario_comparison,
    )
