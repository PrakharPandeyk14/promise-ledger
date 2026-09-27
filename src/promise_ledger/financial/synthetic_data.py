"""Deterministic synthetic financial transaction generator.

Builds on existing database payments/invoices as income and generates
realistic deterministic B2B expense transactions, budgets, and financial goals.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from random import Random
import sqlite3
from typing import Any

from promise_ledger.config import DATABASE_PATH, SEED, SIMULATION_DATE


def generate_synthetic_expenses(rng_seed: int = SEED, simulation_date: date = SIMULATION_DATE) -> list[dict[str, Any]]:
    """Generate deterministic B2B expense transactions over a 6-month simulation window."""
    rng = Random(rng_seed)
    expenses: list[dict[str, Any]] = []
    txn_counter = 1

    # Months: March 2026 to August 2026
    start_year = simulation_date.year
    start_month = 3  # March

    for month_offset in range(6):
        month = start_month + month_offset
        year = start_year
        if month > 12:
            month -= 12
            year += 1

        is_current_month = (year == simulation_date.year and month == simulation_date.month)

        # 1. Office Rent (Recurring, Monthly on 1st)
        rent_date = date(year, month, 1)
        if rent_date <= simulation_date:
            expenses.append({
                "id": f"TXN-EX-{txn_counter:06d}",
                "date": rent_date.isoformat(),
                "amount": 25000.0,
                "transaction_type": "EXPENSE",
                "category": "Rent",
                "description": "Office Rent - Brigade Tech Park",
                "is_recurring": True,
                "merchant": "Brigade Tech Park Commercial",
            })
            txn_counter += 1

        # 2. Cloud Infrastructure - AWS (Recurring, Monthly on 18th)
        aws_date = date(year, month, 18)
        if aws_date <= simulation_date:
            # Anomaly injection in August 2026!
            if is_current_month:
                aws_amount = 18400.0  # Anomaly: +124% over ~8200 baseline
            else:
                aws_amount = round(8200.0 + rng.uniform(-150, 150), 2)

            expenses.append({
                "id": f"TXN-EX-{txn_counter:06d}",
                "date": aws_date.isoformat(),
                "amount": aws_amount,
                "transaction_type": "EXPENSE",
                "category": "Software",
                "description": "AWS Cloud Hosting - Compute & S3",
                "is_recurring": True,
                "merchant": "Amazon Web Services",
            })
            txn_counter += 1

        # 3. Software SaaS - GitHub & Developer Tooling (Recurring, Monthly on 5th)
        dev_date = date(year, month, 5)
        if dev_date <= simulation_date:
            expenses.append({
                "id": f"TXN-EX-{txn_counter:06d}",
                "date": dev_date.isoformat(),
                "amount": 4800.0,
                "transaction_type": "EXPENSE",
                "category": "Software",
                "description": "GitHub Enterprise & CI/CD Subscription",
                "is_recurring": True,
                "merchant": "GitHub Inc.",
            })
            txn_counter += 1

        # 4. Telecom & Fiber Internet (Recurring, Monthly on 10th)
        fiber_date = date(year, month, 10)
        if fiber_date <= simulation_date:
            expenses.append({
                "id": f"TXN-EX-{txn_counter:06d}",
                "date": fiber_date.isoformat(),
                "amount": 1200.0,
                "transaction_type": "EXPENSE",
                "category": "Utilities",
                "description": "High-Speed Commercial Fiber Internet",
                "is_recurring": True,
                "merchant": "Airtel Commercial Broadband",
            })
            txn_counter += 1

        # 5. Core Payroll (Recurring, Monthly on 28th)
        payroll_date = date(year, month, 28)
        if payroll_date <= simulation_date:
            expenses.append({
                "id": f"TXN-EX-{txn_counter:06d}",
                "date": payroll_date.isoformat(),
                "amount": 48000.0,
                "transaction_type": "EXPENSE",
                "category": "Payroll",
                "description": "Core Staff & Contractor Monthly Payroll",
                "is_recurring": True,
                "merchant": "RazorpayX Payroll",
            })
            txn_counter += 1

        # 6. Operations & Facilities (Monthly on 12th)
        ops_date = date(year, month, 12)
        if ops_date <= simulation_date:
            ops_amt = round(14000.0 + rng.uniform(-400, 400), 2)
            expenses.append({
                "id": f"TXN-EX-{txn_counter:06d}",
                "date": ops_date.isoformat(),
                "amount": ops_amt,
                "transaction_type": "EXPENSE",
                "category": "Operations",
                "description": "Office Operations & Facility Upkeep",
                "is_recurring": True,
                "merchant": "Apex Facility Management",
            })
            txn_counter += 1

        # 7. Marketing (Monthly on 15th)
        mkt_date = date(year, month, 15)
        if mkt_date <= simulation_date:
            mkt_amt = round(11500.0 + rng.uniform(-800, 800), 2)
            expenses.append({
                "id": f"TXN-EX-{txn_counter:06d}",
                "date": mkt_date.isoformat(),
                "amount": mkt_amt,
                "transaction_type": "EXPENSE",
                "category": "Marketing",
                "description": "Search & Inbound Marketing Ads",
                "is_recurring": False,
                "merchant": "Google Ads India",
            })
            txn_counter += 1

        # 8. Vendor Logistics & Supplies (Variable)
        vendor_date = date(year, month, 22)
        if vendor_date <= simulation_date:
            expenses.append({
                "id": f"TXN-EX-{txn_counter:06d}",
                "date": vendor_date.isoformat(),
                "amount": 6450.0,
                "transaction_type": "EXPENSE",
                "category": "Vendor",
                "description": "Logistics & Dispatch Courier Services",
                "is_recurring": False,
                "merchant": "BlueDart Express Logistics",
            })
            txn_counter += 1

        # Anomaly in August: Duplicate Vendor Transaction 24h later!
        if is_current_month:
            dup_date = date(year, month, 23)
            if dup_date <= simulation_date:
                expenses.append({
                    "id": f"TXN-EX-{txn_counter:06d}",
                    "date": dup_date.isoformat(),
                    "amount": 6450.0,
                    "transaction_type": "EXPENSE",
                    "category": "Vendor",
                    "description": "Logistics & Dispatch Courier Services",
                    "is_recurring": False,
                    "merchant": "BlueDart Express Logistics",
                })
                txn_counter += 1

            # Anomaly in August: Unusually large one-off server replacement
            srv_date = date(year, month, 11)
            if srv_date <= simulation_date:
                expenses.append({
                    "id": f"TXN-EX-{txn_counter:06d}",
                    "date": srv_date.isoformat(),
                    "amount": 34500.0,
                    "transaction_type": "EXPENSE",
                    "category": "Other",
                    "description": "Emergency Server Hardware Replacement",
                    "is_recurring": False,
                    "merchant": "Dell Enterprise Direct",
                })
                txn_counter += 1

        # Quarterly Tax in June
        if month == 6:
            tax_date = date(year, month, 20)
            expenses.append({
                "id": f"TXN-EX-{txn_counter:06d}",
                "date": tax_date.isoformat(),
                "amount": 22000.0,
                "transaction_type": "EXPENSE",
                "category": "Tax",
                "description": "Quarterly GST & Advance Corporate Tax",
                "is_recurring": False,
                "merchant": "GSTN Government Portal",
            })
            txn_counter += 1

    return sorted(expenses, key=lambda x: x["date"], reverse=True)


def load_income_from_database(database_path: Path = DATABASE_PATH, start_date: str = "2026-03-01", end_date: str = "2026-08-31", simulation_date: date = SIMULATION_DATE) -> list[dict[str, Any]]:
    """Query real database payments to serve as Income transactions."""
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        query = """
            SELECT p.payment_id, p.payment_date, p.amount, p.payment_method,
                   c.customer_name, i.invoice_number
            FROM payments p
            JOIN customers c ON p.customer_id = c.customer_id
            JOIN invoices i ON p.invoice_id = i.invoice_id
            WHERE p.payment_date >= ? AND p.payment_date <= ?
            ORDER BY p.payment_date DESC
        """
        cursor.execute(query, (start_date, end_date))
        rows = cursor.fetchall()
        incomes: list[dict[str, Any]] = []
        for row in rows:
            incomes.append({
                "id": f"TXN-IN-{row['payment_id']:06d}",
                "date": row["payment_date"],
                "amount": float(row["amount"]),
                "transaction_type": "INCOME",
                "category": "Customer Payment",
                "description": f"Invoice Payment from {row['customer_name']} ({row['payment_method']})",
                "is_recurring": False,
                "merchant": row["customer_name"],
            })

        # Add deterministic B2B Direct Sales & Recurring Retainers (category 'Sales')
        sales_counter = 1
        for m in range(3, simulation_date.month + 1):
            retainer_d = date(2026, m, 2)
            sub_d = date(2026, m, 16)
            if retainer_d <= simulation_date:
                incomes.append({
                    "id": f"TXN-SA-{sales_counter:04d}",
                    "date": retainer_d.isoformat(),
                    "amount": 85000.0,
                    "transaction_type": "INCOME",
                    "category": "Sales",
                    "description": "Enterprise Managed Services & Software Retainer",
                    "is_recurring": True,
                    "merchant": "Apex Global Solutions Ltd",
                })
                sales_counter += 1
            if sub_d <= simulation_date:
                incomes.append({
                    "id": f"TXN-SA-{sales_counter:04d}",
                    "date": sub_d.isoformat(),
                    "amount": 46620.0,
                    "transaction_type": "INCOME",
                    "category": "Sales",
                    "description": "Direct SaaS Subscription & Platform Licensing",
                    "is_recurring": True,
                    "merchant": "CloudScale Enterprises",
                })
                sales_counter += 1

        return incomes
    finally:
        conn.close()


def get_all_transactions(database_path: Path = DATABASE_PATH, simulation_date: date = SIMULATION_DATE) -> list[dict[str, Any]]:
    """Combine database payments as income and synthetic deterministic expenses."""
    expenses = generate_synthetic_expenses(simulation_date=simulation_date)
    incomes = load_income_from_database(database_path=database_path, start_date="2026-03-01", end_date=simulation_date.isoformat(), simulation_date=simulation_date)
    all_txns = expenses + incomes
    all_txns.sort(key=lambda t: (t["date"], t["id"]), reverse=True)
    return all_txns


def get_budget_configuration() -> dict[str, float]:
    """Default monthly budget amounts by category."""
    return {
        "Operations": 20000.0,
        "Payroll": 50000.0,
        "Software": 15000.0,
        "Marketing": 15000.0,
        "Rent": 26000.0,
        "Utilities": 5000.0,
        "Vendor": 12000.0,
        "Other": 10000.0,
    }


def get_synthetic_goals() -> list[dict[str, Any]]:
    """Synthetic financial goals with target progress."""
    return [
        {
            "goal_id": "GOAL-01",
            "name": "Emergency Reserve Fund",
            "target_amount": 500000.0,
            "current_amount": 320000.0,
            "target_date": "2026-12-31",
            "progress_pct": 64.0,
            "status": "ON_TRACK",
        },
        {
            "goal_id": "GOAL-02",
            "name": "Equipment & Hardware Upgrade",
            "target_amount": 150000.0,
            "current_amount": 95000.0,
            "target_date": "2026-11-30",
            "progress_pct": 63.3,
            "status": "ON_TRACK",
        },
        {
            "goal_id": "GOAL-03",
            "name": "Tax Provision Reserve",
            "target_amount": 80000.0,
            "current_amount": 65000.0,
            "target_date": "2026-09-30",
            "progress_pct": 81.3,
            "status": "ON_TRACK",
        },
    ]
