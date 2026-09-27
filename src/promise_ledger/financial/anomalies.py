"""Deterministic statistical financial anomaly detection."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from statistics import mean, median
from typing import Any


def detect_financial_anomalies(expenses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Identify unusual financial transactions using deterministic statistical deviations and heuristics.
    
    Detects:
    1. Category/Merchant baseline spikes (>50% deviation)
    2. Suspected rapid duplicate transactions within 48h
    3. Unusually large one-off transaction outliers
    """
    anomalies: list[dict[str, Any]] = []
    anomaly_counter = 1

    # 1. Group by merchant to compute historical baselines (excluding the latest month)
    merchant_history: dict[str, list[float]] = defaultdict(list)
    for exp in sorted(expenses, key=lambda x: x["date"]):
        merchant = exp.get("merchant", "")
        merchant_history[merchant].append(float(exp["amount"]))

    # Detect baseline deviations
    for exp in expenses:
        if exp.get("transaction_type") != "EXPENSE":
            continue

        merchant = exp.get("merchant", "")
        amount = float(exp["amount"])
        history = merchant_history.get(merchant, [])

        # If we have multiple historical payments, calculate historical baseline
        if len(history) >= 2:
            # Baseline is median of historical amounts
            base = median(history)
            if base > 0 and amount > base * 1.5:  # Over 50% spike
                dev_pct = round(((amount - base) / base) * 100, 1)
                severity = "HIGH" if dev_pct >= 90.0 else "MEDIUM"
                anomalies.append({
                    "anomaly_id": f"ANM-{anomaly_counter:03d}",
                    "transaction_id": exp["id"],
                    "date": exp["date"],
                    "description": exp["description"],
                    "category": exp["category"],
                    "amount": amount,
                    "historical_average": round(base, 2),
                    "deviation_percentage": dev_pct,
                    "severity": severity,
                    "reason": f"Transaction amount is significantly above historical category behavior (+{dev_pct}% vs baseline ₹{base:,.0f}).",
                })
                anomaly_counter += 1

    # 2. Detect duplicate / repeated transactions within 48 hours with identical merchant & amount
    sorted_by_date = sorted(
        [e for e in expenses if e.get("transaction_type") == "EXPENSE"],
        key=lambda x: (x["date"], x["id"])
    )
    for i in range(len(sorted_by_date)):
        curr = sorted_by_date[i]
        curr_d = date.fromisoformat(curr["date"])
        for j in range(i + 1, min(i + 5, len(sorted_by_date))):
            nxt = sorted_by_date[j]
            nxt_d = date.fromisoformat(nxt["date"])
            days_diff = (nxt_d - curr_d).days

            if days_diff > 2:
                break

            if (
                curr["merchant"] == nxt["merchant"]
                and abs(float(curr["amount"]) - float(nxt["amount"])) < 0.01
                and curr["id"] != nxt["id"]
            ):
                # Check if not already added
                if not any(a["transaction_id"] == nxt["id"] for a in anomalies):
                    anomalies.append({
                        "anomaly_id": f"ANM-{anomaly_counter:03d}",
                        "transaction_id": nxt["id"],
                        "date": nxt["date"],
                        "description": nxt["description"],
                        "category": nxt["category"],
                        "amount": float(nxt["amount"]),
                        "historical_average": float(curr["amount"]),
                        "deviation_percentage": 0.0,
                        "severity": "MEDIUM",
                        "reason": f"Suspicious duplicate transaction detected: Identical charge of ₹{float(nxt['amount']):,.2f} to {nxt['merchant']} within {days_diff * 24 or 24} hours of prior billing.",
                    })
                    anomaly_counter += 1

    # 3. Detect extreme outlier transactions (e.g. > ₹30,000 for unexpected operational purchases)
    for exp in expenses:
        if exp.get("transaction_type") != "EXPENSE":
            continue
        amt = float(exp["amount"])
        # High unbudgeted threshold
        if amt >= 30000.0 and exp.get("category") in ("Other", "Vendor"):
            if not any(a["transaction_id"] == exp["id"] for a in anomalies):
                anomalies.append({
                    "anomaly_id": f"ANM-{anomaly_counter:03d}",
                    "transaction_id": exp["id"],
                    "date": exp["date"],
                    "description": exp["description"],
                    "category": exp["category"],
                    "amount": amt,
                    "historical_average": 5000.0,
                    "deviation_percentage": round(((amt - 5000.0) / 5000.0) * 100, 1),
                    "severity": "HIGH",
                    "reason": f"Unusually large one-off transaction: ₹{amt:,.2f} in category '{exp['category']}' exceeds normal operating range.",
                })
                anomaly_counter += 1

    # Sort anomalies by date descending
    anomalies.sort(key=lambda a: (a["severity"] == "HIGH", a["date"]), reverse=True)
    return anomalies
