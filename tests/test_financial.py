"""Tests for Phase 1 Financial Intelligence Layer APIs and engines."""

from __future__ import annotations

import unittest
from fastapi.testclient import TestClient

from promise_ledger.api import create_app
from promise_ledger.config import DATABASE_PATH


class FinancialIntelligenceApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app(DATABASE_PATH))

    def test_financial_summary_endpoint(self):
        response = self.client.get("/financial/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Required fields from SIH Phase 1 specification
        required_fields = [
            "current_cash_balance",
            "monthly_income",
            "monthly_expenses",
            "net_cash_flow",
            "total_receivables",
            "financial_risk_level",
            "financial_risk_score",
            "risk_contributors",
            "receivables_risk_insight",
            "receivables_at_risk_amount",
            "high_break_risk_count",
            "total_portfolio_receivables",
            "simulation_date",
        ]
        for field in required_fields:
            self.assertIn(field, data, f"Missing field in financial summary: {field}")

        self.assertGreater(data["current_cash_balance"], 0)
        self.assertGreater(data["monthly_income"], 0)
        self.assertGreater(data["monthly_expenses"], 0)
        self.assertIn(data["financial_risk_level"], {"LOW", "MEDIUM", "HIGH"})
        self.assertTrue(len(data["risk_contributors"]) > 0)
        self.assertIn("break risk", data["receivables_risk_insight"])
        self.assertEqual(data["simulation_date"], "2026-08-31")

    def test_financial_transactions_endpoint_and_filtering(self):
        # All transactions
        response = self.client.get("/financial/transactions?limit=50")
        self.assertEqual(response.status_code, 200)
        txns = response.json()
        self.assertIsInstance(txns, list)
        self.assertTrue(len(txns) > 0)

        sample = txns[0]
        for field in ("id", "date", "amount", "transaction_type", "category", "description", "is_recurring"):
            self.assertIn(field, sample)

        # Filter by type=EXPENSE
        exp_resp = self.client.get("/financial/transactions?type=EXPENSE&limit=30")
        self.assertEqual(exp_resp.status_code, 200)
        exp_txns = exp_resp.json()
        self.assertTrue(all(t["transaction_type"] == "EXPENSE" for t in exp_txns))

        # Filter by type=INCOME
        inc_resp = self.client.get("/financial/transactions?type=INCOME&limit=30")
        self.assertEqual(inc_resp.status_code, 200)
        inc_txns = inc_resp.json()
        self.assertTrue(all(t["transaction_type"] == "INCOME" for t in inc_txns))

    def test_recurring_expenses_endpoint(self):
        response = self.client.get("/financial/recurring-expenses")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("recurring_expenses", data)
        self.assertIn("total_monthly_recurring", data)
        self.assertGreater(data["total_monthly_recurring"], 0)

        rec_items = data["recurring_expenses"]
        self.assertTrue(len(rec_items) >= 4)

        categories = {item["category"] for item in rec_items}
        self.assertIn("Rent", categories)
        self.assertIn("Payroll", categories)
        self.assertIn("Software", categories)
        self.assertIn("Utilities", categories)

    def test_anomalies_detection_endpoint(self):
        response = self.client.get("/financial/anomalies")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("anomalies", data)
        self.assertIn("total_anomalies", data)
        self.assertGreater(data["total_anomalies"], 0)

        anomalies = data["anomalies"]
        # Verify AWS cloud hosting surge anomaly is detected
        aws_anomaly = next((a for a in anomalies if "AWS" in a["description"] or "Amazon" in a.get("merchant", "")), None)
        self.assertIsNotNone(aws_anomaly, "Expected AWS anomaly to be detected")
        self.assertEqual(aws_anomaly["severity"], "HIGH")
        self.assertGreater(aws_anomaly["deviation_percentage"], 50.0)
        self.assertIn("historical", aws_anomaly["reason"].lower())

        # Verify duplicate charge anomaly is detected
        dup_anomaly = next((a for a in anomalies if "duplicate" in a["reason"].lower()), None)
        self.assertIsNotNone(dup_anomaly, "Expected duplicate charge anomaly to be detected")

    def test_budgets_endpoint(self):
        response = self.client.get("/financial/budgets")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("categories", data)
        self.assertIn("total_budget", data)
        self.assertIn("total_spent", data)
        self.assertIn("overall_utilization_pct", data)

        cats = {c["category"]: c for c in data["categories"]}
        for required_cat in ("Operations", "Payroll", "Software", "Marketing"):
            self.assertIn(required_cat, cats)
            self.assertGreater(cats[required_cat]["budget"], 0)
            self.assertIn(cats[required_cat]["status"], {"ON_TRACK", "WARNING", "OVER_BUDGET"})

    def test_goals_endpoint(self):
        response = self.client.get("/financial/goals")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("goals", data)
        self.assertIn("total_target", data)
        self.assertIn("total_saved", data)

        goals = data["goals"]
        self.assertTrue(len(goals) >= 2)
        names = [g["name"] for g in goals]
        self.assertTrue(any("Emergency" in n for n in names))
        self.assertTrue(any("Equipment" in n or "Hardware" in n for n in names))


if __name__ == "__main__":
    unittest.main()
