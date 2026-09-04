import unittest

from fastapi.testclient import TestClient

from promise_ledger.api import create_app
from promise_ledger.api.service import PromiseLedgerService
from promise_ledger.config import DATABASE_PATH
from promise_ledger.db.connection import connect


class PromiseLedgerApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(create_app(DATABASE_PATH))
        response = cls.client.get("/opportunities")
        cls.opportunities = response.json()
        cls.promise_id = cls.opportunities[0]["promise_id"]

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_service_reuses_snapshot_until_invalidated(self):
        service = PromiseLedgerService(DATABASE_PATH)
        first = service.snapshot()
        second = service.snapshot()

        self.assertIs(first, second)
        self.assertEqual(first.opportunities, second.opportunities)

        service.invalidate_snapshot()
        refreshed = service.snapshot()
        self.assertIsNot(first, refreshed)
        self.assertEqual(first.opportunities, refreshed.opportunities)

    def test_frontend_is_served_by_api(self):
        index = self.client.get("/")
        script = self.client.get("/js/api-client.js")
        self.assertEqual(index.status_code, 200)
        self.assertIn("Promise Ledger", index.text)
        self.assertEqual(script.status_code, 200)
        self.assertIn("class PromiseLedgerAPI", script.text)

    def test_portfolio_summary_uses_evaluated_opportunities(self):
        response = self.client.get("/portfolio/summary")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["evaluation_count"], len(self.opportunities))
        self.assertGreater(body["total_outstanding_amount"], 0)
        self.assertGreaterEqual(body["total_expected_recovery"], 0)
        self.assertEqual(sum(body["priority_tiers"].values()), len(self.opportunities))
        self.assertEqual(sum(body["final_actions"].values()), len(self.opportunities))

    def test_opportunities_are_ranked_and_explainable(self):
        response = self.client.get("/opportunities")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([item["priority_rank"] for item in body], list(range(1, len(body) + 1)))
        self.assertTrue(all(item["explanation"] for item in body))
        self.assertEqual(
            body,
            sorted(body, key=lambda item: (-item["expected_recovery"], -item["outstanding_amount"], -item["break_probability"], item["promise_id"])),
        )

    def test_opportunity_detail(self):
        response = self.client.get(f"/opportunities/{self.promise_id}")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["promise_id"], self.promise_id)
        self.assertEqual(body["outcome"], "PENDING")
        self.assertIn("current_outstanding_amount", body)

    def test_missing_opportunity_returns_404(self):
        response = self.client.get("/opportunities/999999999")
        self.assertEqual(response.status_code, 404)

    def test_evaluate_is_deterministic_and_simulated(self):
        before = self._ledger_counts()
        first = self.client.post(f"/opportunities/{self.promise_id}/evaluate")
        second = self.client.post(f"/opportunities/{self.promise_id}/evaluate")
        after = self._ledger_counts()

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertEqual(before, after)
        body = first.json()
        self.assertIn(body["guardrail_status"], {"ALLOW", "BLOCK", "OVERRIDE"})
        self.assertIn(body["final_action"], {"SOFT_REMINDER", "FIRM_REMINDER", "PAYMENT_PLAN", "ESCALATE", "HUMAN_REVIEW", "STOP"})
        self.assertEqual(body["audit"]["execution_status"] in {"SIMULATED_EXECUTION", "BLOCKED_NO_EXECUTION", "OVERRIDDEN_NO_EXECUTION"}, True)

    def test_evaluate_missing_opportunity_returns_404(self):
        response = self.client.post("/opportunities/999999999/evaluate")
        self.assertEqual(response.status_code, 404)

    @staticmethod
    def _ledger_counts():
        connection = connect(DATABASE_PATH)
        try:
            return tuple(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("payments", "recovery_actions")
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()