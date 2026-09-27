"""Unit tests for Phase 2 Forecasting, Scenario Simulation, and AI Recommendations."""

import unittest
from fastapi.testclient import TestClient

from promise_ledger.api import create_app
from promise_ledger.config import DATABASE_PATH
from promise_ledger.db.connection import connect


class Phase2FinancialEndpointsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app(DATABASE_PATH))

    def test_cash_flow_forecast_endpoint(self):
        response = self.client.get("/financial/forecast")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("forecast_period", data)
        self.assertIn("months", data)
        self.assertEqual(len(data["months"]), 3)
        self.assertIn("confidence", data)
        self.assertIn("confidence_score", data)
        self.assertIn("methodology_summary", data)
        self.assertIn("receivables_integration_note", data)

        # Check month structure
        m1 = data["months"][0]
        self.assertIn("month", m1)
        self.assertIn("month_name", m1)
        self.assertGreater(m1["projected_income"], 0)
        self.assertGreater(m1["projected_expenses"], 0)
        self.assertGreater(m1["projected_ending_cash"], 0)
        self.assertGreater(m1["receivables_contribution"], 0)
        self.assertGreater(m1["recurring_expense_baseline"], 0)

        # Check total calculations consistency
        total_income = sum(m["projected_income"] for m in data["months"])
        self.assertAlmostEqual(data["total_projected_income"], total_income, places=1)

    def test_forecast_determinism(self):
        first = self.client.get("/financial/forecast").json()
        second = self.client.get("/financial/forecast").json()
        self.assertEqual(first, second)

    def test_scenario_simulation_endpoint(self):
        payload = {
            "receivable_delay_days": 15,
            "expense_change_percent": 10.0,
            "additional_monthly_expense": 20000.0,
            "recovery_rate_adjustment_percent": -10.0
        }
        response = self.client.post("/financial/scenario", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("base_case", data)
        self.assertIn("scenario_case", data)
        self.assertIn("delta", data)
        self.assertIn("risk_change", data)
        self.assertIn("explanation", data)
        self.assertIn("monthly_comparison", data)

        base = data["base_case"]
        scen = data["scenario_case"]

        # Adverse scenario should reduce ending cash
        self.assertLess(scen["projected_ending_cash"], base["projected_ending_cash"])
        self.assertLess(scen["cash_runway_months"], base["cash_runway_months"])
        self.assertIn("delay", data["explanation"].lower())

    def test_scenario_validation_rejects_invalid_inputs(self):
        # Negative delay
        resp1 = self.client.post("/financial/scenario", json={"receivable_delay_days": -10})
        self.assertEqual(resp1.status_code, 422)

        # Extreme expense change
        resp2 = self.client.post("/financial/scenario", json={"expense_change_percent": 500.0})
        self.assertEqual(resp2.status_code, 422)

    def test_scenario_does_not_mutate_database(self):
        conn = connect(DATABASE_PATH)
        before_counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("payments", "invoices", "customers", "promises", "recovery_actions")
        }
        conn.close()

        # Run several heavy scenarios
        for _ in range(3):
            self.client.post("/financial/scenario", json={
                "receivable_delay_days": 30,
                "expense_change_percent": 25.0,
                "additional_monthly_expense": 50000.0
            })

        conn = connect(DATABASE_PATH)
        after_counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("payments", "invoices", "customers", "promises", "recovery_actions")
        }
        conn.close()

        self.assertEqual(before_counts, after_counts)

    def test_ai_recommendations_generation(self):
        response = self.client.get("/financial/recommendations")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("recommendations", data)
        self.assertGreaterEqual(data["total_count"], 4)
        self.assertGreaterEqual(data["high_priority_count"], 1)

        recs = data["recommendations"]
        # Check rule 1: Receivables risk
        rec1 = next((r for r in recs if r["id"] == "REC-FIN-001"), None)
        self.assertIsNotNone(rec1)
        self.assertEqual(rec1["priority"], "HIGH")
        self.assertTrue(rec1["human_approval_required"])
        self.assertIn("break", rec1["reason"].lower())

        # Check human approval indicator is present
        self.assertTrue(any(r["human_approval_required"] for r in recs))

    def test_recommendation_human_review_workflow(self):
        response = self.client.get("/financial/recommendations")
        recs = response.json()["recommendations"]
        rec_id = recs[0]["id"]

        # Review action
        review_resp = self.client.post(
            f"/financial/recommendations/{rec_id}/review",
            json={"action": "APPROVE", "reviewer_notes": "Approved by CFO in simulated demo"}
        )
        self.assertEqual(review_resp.status_code, 200)
        updated = review_resp.json()
        self.assertEqual(updated["status"], "APPROVED")
        self.assertEqual(updated["reviewer_notes"], "Approved by CFO in simulated demo")
        self.assertIsNotNone(updated["reviewed_at"])


if __name__ == "__main__":
    unittest.main()
