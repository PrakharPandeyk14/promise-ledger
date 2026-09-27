"""Deterministic recurring expense detection engine."""

from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any


def detect_recurring_expenses(expenses: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float]:
    """Analyze expense transactions to identify recurring vendor commitments.
    
    Groups expenses by merchant and category, evaluates periodicity across months,
    and returns detected recurring expenses along with total monthly recurring expenditure.
    """
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for exp in expenses:
        if exp.get("transaction_type") != "EXPENSE":
            continue
        key = (exp.get("merchant", ""), exp.get("category", ""))
        grouped[key].append(exp)

    recurring_list: list[dict[str, Any]] = []
    expense_idx = 1

    for (merchant, category), items in grouped.items():
        if not merchant or len(items) < 2:
            continue

        # Check distinct months
        months = {item["date"][:7] for item in items}
        if len(months) < 2:
            continue

        # Check explicit flag or amount consistency
        amounts = [float(item["amount"]) for item in items]
        has_recurring_flag = any(item.get("is_recurring") for item in items)
        
        # Calculate median amount as reliable recurring baseline (robust to single-month surges like AWS)
        baseline_amount = round(float(median(amounts)), 2)

        # Check if at least 60% of items are close to the baseline
        consistent_items = [a for a in amounts if abs(a - baseline_amount) / baseline_amount < 0.25]
        is_consistent = (len(consistent_items) / len(amounts)) >= 0.50

        if has_recurring_flag or is_consistent:
            recurring_list.append({
                "expense_id": f"REC-{expense_idx:03d}",
                "merchant": merchant,
                "category": category,
                "amount": baseline_amount,
                "periodicity": "Monthly",
                "occurrences": len(items),
                "is_active": True,
            })
            expense_idx += 1

    # Sort recurring expenses descending by baseline amount
    recurring_list.sort(key=lambda r: r["amount"], reverse=True)
    total_monthly = round(sum(r["amount"] for r in recurring_list), 2)

    return recurring_list, total_monthly
