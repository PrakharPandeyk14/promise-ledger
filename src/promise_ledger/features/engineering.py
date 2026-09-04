"""Construct promise features using only facts known before creation time.

Every historical ledger event used here has a date strictly earlier than the
promise's ``promise_created_date``.  In particular, outcomes from earlier
promises are used only after their promised date has passed, because before
then their eventual outcome is not knowable.
"""

from __future__ import annotations

from datetime import date
from statistics import median
from typing import Any


FEATURE_COLUMNS = (
    "previous_promise_count",
    "previous_promises_kept",
    "previous_promises_broken",
    "historical_promise_keep_rate",
    "recent_promise_break_rate",
    "average_days_late",
    "median_days_late",
    "payment_on_time_rate",
    "partial_payment_rate",
    "historical_payment_completion_ratio",
    "invoice_amount",
    "outstanding_amount_at_promise_creation",
    "days_overdue_at_promise_creation",
    "invoice_age_at_promise_creation",
    "customer_tenure_at_promise",
    "historical_invoice_count",
    "historical_average_invoice_amount",
    "historical_recovery_rate",
)

TARGET_COLUMN = "target_broken"
RECENT_PROMISE_WINDOW = 3


def _as_date(value: str) -> date:
    return date.fromisoformat(value)


def _rate(numerator: int | float, denominator: int | float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def _load_ledger(connection) -> tuple[list[Any], list[Any], list[Any], list[Any]]:
    customers = connection.execute("SELECT * FROM customers ORDER BY customer_id").fetchall()
    invoices = connection.execute("SELECT * FROM invoices ORDER BY invoice_id").fetchall()
    payments = connection.execute("SELECT * FROM payments ORDER BY payment_date, payment_id").fetchall()
    promises = connection.execute(
        "SELECT * FROM promises ORDER BY promise_created_date, promise_id"
    ).fetchall()
    return customers, invoices, payments, promises


def build_feature_dataset(connection) -> list[dict[str, Any]]:
    """Return one leakage-safe feature row per promise, in chronological order.

    Rows include only the derived ``target_broken`` label for downstream
    filtering; it is not in :data:`FEATURE_COLUMNS`. PENDING rows deliberately have a
    ``None`` target and must be excluded from supervised work with
    :func:`supervised_rows`.
    """
    customers, invoices, payments, promises = _load_ledger(connection)
    customer_by_id = {row["customer_id"]: row for row in customers}
    invoice_by_id = {row["invoice_id"]: row for row in invoices}

    invoices_by_customer: dict[int, list[Any]] = {}
    payments_by_customer: dict[int, list[Any]] = {}
    promises_by_customer: dict[int, list[Any]] = {}
    payments_by_invoice: dict[int, list[Any]] = {}
    for invoice in invoices:
        invoices_by_customer.setdefault(invoice["customer_id"], []).append(invoice)
    for payment in payments:
        payments_by_customer.setdefault(payment["customer_id"], []).append(payment)
        payments_by_invoice.setdefault(payment["invoice_id"], []).append(payment)
    for promise in promises:
        promises_by_customer.setdefault(promise["customer_id"], []).append(promise)

    rows: list[dict[str, Any]] = []
    for promise in promises:
        prediction_time = _as_date(promise["promise_created_date"])
        customer_id, invoice_id = promise["customer_id"], promise["invoice_id"]
        invoice, customer = invoice_by_id[invoice_id], customer_by_id[customer_id]

        # Promise creation is observable immediately. Outcome is observable only
        # once its promised date has passed, and never for the current promise.
        earlier_promises = [
            item for item in promises_by_customer.get(customer_id, [])
            if _as_date(item["promise_created_date"]) < prediction_time
        ]
        resolved_promises = [
            item for item in earlier_promises
            if _as_date(item["promised_payment_date"]) < prediction_time
            and item["outcome"] in ("KEPT", "BROKEN")
        ]
        kept = sum(item["outcome"] == "KEPT" for item in resolved_promises)
        broken = sum(item["outcome"] == "BROKEN" for item in resolved_promises)
        recent = sorted(
            resolved_promises,
            key=lambda item: (item["promise_created_date"], item["promise_id"]),
        )[-RECENT_PROMISE_WINDOW:]

        # Payments on the prediction date are excluded deliberately. Invoice
        # issuance is also strict for historical customer aggregates.
        earlier_payments = [
            item for item in payments_by_customer.get(customer_id, [])
            if _as_date(item["payment_date"]) < prediction_time
        ]
        payment_lateness = [
            (_as_date(item["payment_date"]) - _as_date(invoice_by_id[item["invoice_id"]]["due_date"])).days
            for item in earlier_payments
        ]
        historical_invoices = [
            item for item in invoices_by_customer.get(customer_id, [])
            if _as_date(item["invoice_date"]) < prediction_time
        ]
        partial_invoices = 0
        # Recovery rate is the proportion of issued historical invoice value
        # recovered through payments observable before prediction time.
        total_historical_amount = sum(item["amount"] for item in historical_invoices)
        paid_on_historical_invoices = 0.0
        for historical_invoice in historical_invoices:
            paid = sum(
                payment["amount"] for payment in payments_by_invoice.get(historical_invoice["invoice_id"], [])
                if _as_date(payment["payment_date"]) < prediction_time
            )
            paid_on_historical_invoices += paid
            if 0 < paid + 0.005 < historical_invoice["amount"]:
                partial_invoices += 1

        paid_current_invoice = sum(
            payment["amount"] for payment in payments_by_invoice.get(invoice_id, [])
            if _as_date(payment["payment_date"]) < prediction_time
        )
        outstanding = max(0.0, round(invoice["amount"] - paid_current_invoice, 2))
        row: dict[str, Any] = {
            "promise_id": promise["promise_id"],
            "customer_id": customer_id,
            "invoice_id": invoice_id,
            "promise_created_date": promise["promise_created_date"],
            TARGET_COLUMN: {"KEPT": 0, "BROKEN": 1}.get(promise["outcome"]),
            "previous_promise_count": len(earlier_promises),
            "previous_promises_kept": kept,
            "previous_promises_broken": broken,
            "historical_promise_keep_rate": _rate(kept, len(resolved_promises)),
            "recent_promise_break_rate": _rate(sum(item["outcome"] == "BROKEN" for item in recent), len(recent)),
            "average_days_late": _rate(sum(payment_lateness), len(payment_lateness)),
            "median_days_late": float(median(payment_lateness)) if payment_lateness else 0.0,
            "payment_on_time_rate": _rate(sum(days <= 0 for days in payment_lateness), len(payment_lateness)),
            "partial_payment_rate": _rate(partial_invoices, len(historical_invoices)),
            "historical_payment_completion_ratio": _rate(paid_on_historical_invoices, total_historical_amount),
            "invoice_amount": float(invoice["amount"]),
            "outstanding_amount_at_promise_creation": outstanding,
            "days_overdue_at_promise_creation": max(0, (prediction_time - _as_date(invoice["due_date"])).days),
            "invoice_age_at_promise_creation": (prediction_time - _as_date(invoice["invoice_date"])).days,
            "customer_tenure_at_promise": (prediction_time - _as_date(customer["created_date"])).days,
            "historical_invoice_count": len(historical_invoices),
            "historical_average_invoice_amount": _rate(total_historical_amount, len(historical_invoices)),
            "historical_recovery_rate": _rate(paid_on_historical_invoices, total_historical_amount),
        }
        rows.append(row)
    return rows


def supervised_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only promises with a known binary historical outcome."""
    return [row for row in rows if row[TARGET_COLUMN] in (0, 1)]
