"""Comprehensive tests for dashboard presentation, frontend assets, and evaluation API."""

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from promise_ledger.api import create_app
from promise_ledger.config import DATABASE_PATH
from promise_ledger.evaluation.experiment import run_experiment


class DashboardAndFrontendValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.frontend_dir = cls.root / "frontend"
        cls.client = TestClient(create_app(DATABASE_PATH))

    def test_frontend_files_exist_and_not_empty(self):
        expected_files = [
            self.frontend_dir / "index.html",
            self.frontend_dir / "css" / "dashboard.css",
            self.frontend_dir / "js" / "utils.js",
            self.frontend_dir / "js" / "api-client.js",
            self.frontend_dir / "js" / "app.js",
        ]
        for file_path in expected_files:
            self.assertTrue(file_path.is_file(), f"Missing expected file: {file_path}")
            self.assertGreater(file_path.stat().st_size, 0, f"File is empty: {file_path}")

    def test_html_contains_all_core_and_experiment_elements(self):
        html = (self.frontend_dir / "index.html").read_text(encoding="utf-8")

        # Baseline required IDs and labels
        self.assertIn("portfolio-overview", html)
        self.assertIn("opportunities-table", html)
        self.assertIn("detail-panel", html)
        self.assertIn("healthIndicator", html)
        self.assertIn('id="totalOutstanding"', html)
        self.assertIn('id="expectedRecovery"', html)
        self.assertIn('id="atRiskCount"', html)
        self.assertIn('id="recoveryRate"', html)
        self.assertIn("Money at Risk (Outstanding)", html)
        self.assertIn("Expected Recovery Rate", html)
        self.assertIn("Break Probability", html)
        self.assertIn("Credibility Score / 100", html)

        # Control vs AI Treatment section
        self.assertIn("Control vs AI Treatment Evaluation", html)
        self.assertIn('id="controlRecoveredAmount"', html)
        self.assertIn('id="treatmentRecoveredAmount"', html)
        self.assertIn('id="incrementalRecoveryAmount"', html)
        self.assertIn('id="controlRecoveryRate"', html)
        self.assertIn('id="treatmentRecoveryRate"', html)
        self.assertIn('id="automationRate"', html)
        self.assertIn('id="humanReviewRate"', html)
        self.assertIn('id="stoppedRate"', html)

        # Simulated and synthetic indicators
        self.assertIn("SIMULATED", html.upper())
        self.assertIn("SYNTHETIC", html.upper())

    def test_css_contains_required_styling_classes_and_rupee_symbol(self):
        css = (self.frontend_dir / "css" / "dashboard.css").read_text(encoding="utf-8")

        self.assertIn(".metrics-grid", css)
        self.assertIn(".opportunities-table", css)
        self.assertIn(".detail-panel", css)
        self.assertIn(".risk-high", css)
        self.assertIn(".priority-badge", css)
        self.assertIn("₹", css)

    def test_app_js_contains_required_demo_strings(self):
        app_js = (self.frontend_dir / "js" / "app.js").read_text(encoding="utf-8")

        self.assertIn("Recommended Action", app_js)
        self.assertIn("Promise Credibility Score", app_js)
        self.assertIn("formatPercentage(evaluation.break_probability)", app_js)
        self.assertIn("formatPercentage(evaluation.recovery_probability)", app_js)
        self.assertIn("Guardrail Status", app_js)
        self.assertIn("Guardrail Reason", app_js)
        self.assertIn("Execution Status", app_js)
        self.assertIn("Audit ID", app_js)
        self.assertIn("formatCurrency(evaluation.expected_recovery)", app_js)
        self.assertIn("getEvaluationExperiment", app_js)

    def test_task3_primary_evaluation_cta_and_decision_chain(self):
        app_js = (self.frontend_dir / "js" / "app.js").read_text(encoding="utf-8")

        # 1. Clear primary action button
        self.assertIn("EVALUATE & GET RECOMMENDATION", app_js)

        # 2. Visible loading state "AI evaluating…"
        self.assertIn("AI evaluating…", app_js)

        # 3. Complete decision chain: AI Recommendation → Guardrail Outcome → Final Action → Simulated Execution → Audit ID
        self.assertIn(
            "AI Recommendation → Guardrail Outcome → Final Action → Simulated Execution → Audit ID",
            app_js,
        )

        # 4. Clicking Inspect only selects opportunity without auto-evaluating
        self.assertIn("async function selectOpportunity(promiseId)", app_js)
        self.assertIn("api.getOpportunityDetail(promiseId)", app_js)
        select_body = app_js.split("async function selectOpportunity(promiseId)")[1].split("function renderDetailPanel")[0]
        self.assertNotIn("evaluateOpportunity", select_body)

        # 5. evaluateOpportunity calls api.evaluateOpportunity(promiseId)
        self.assertIn("async function evaluateOpportunity(promiseId", app_js)
        self.assertIn("api.evaluateOpportunity(promiseId)", app_js)

    def test_task3_css_has_cta_and_decision_chain_styles(self):
        css = (self.frontend_dir / "css" / "dashboard.css").read_text(encoding="utf-8")
        self.assertIn(".evaluate-cta-card", css)
        self.assertIn(".evaluate-button.primary-cta", css)
        self.assertIn(".evaluate-button.loading", css)
        self.assertIn(".decision-chain-container", css)
        self.assertIn(".decision-chain", css)
        self.assertIn(".chain-node", css)

    def test_evaluation_experiment_endpoint(self):
        response = self.client.get("/evaluation/experiment")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        expected_experiment = run_experiment()
        self.assertEqual(data["evaluation_count"], expected_experiment.evaluation_count)
        self.assertEqual(data["total_outstanding_amount"], expected_experiment.total_outstanding_amount)
        self.assertEqual(data["control_recovered_amount"], expected_experiment.control_recovered_amount)
        self.assertEqual(data["treatment_recovered_amount"], expected_experiment.treatment_recovered_amount)
        self.assertEqual(data["incremental_recovery_amount"], expected_experiment.incremental_recovery_amount)
        self.assertEqual(data["control_recovery_rate"], expected_experiment.control_recovery_rate)
        self.assertEqual(data["treatment_recovery_rate"], expected_experiment.treatment_recovery_rate)
        self.assertEqual(data["automation_rate"], expected_experiment.automation_rate)
        self.assertEqual(data["human_review_rate"], expected_experiment.human_review_rate)
        self.assertEqual(data["stopped_rate"], expected_experiment.stopped_rate)
        self.assertEqual(data["evaluation_date"], expected_experiment.evaluation_date)

    def test_portfolio_summary_includes_experiment_metrics(self):
        response = self.client.get("/portfolio/summary")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("experiment", data)
        exp = data["experiment"]
        self.assertIsNotNone(exp)
        self.assertIn("control_recovered_amount", exp)
        self.assertIn("treatment_recovered_amount", exp)
        self.assertIn("incremental_recovery_amount", exp)
        self.assertIn("control_recovery_rate", exp)
        self.assertIn("treatment_recovery_rate", exp)
        self.assertIn("automation_rate", exp)
        self.assertIn("human_review_rate", exp)
        self.assertIn("stopped_rate", exp)

    def test_opportunities_contain_recommendation_and_guardrail_fields(self):
        response = self.client.get("/opportunities")
        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertGreater(len(items), 0)

        for opp in items:
            self.assertIn("recommended_action", opp)
            self.assertIn("final_action", opp)
            self.assertIn("guardrail_status", opp)
            self.assertIn(opp["guardrail_status"], {"ALLOW", "BLOCK", "OVERRIDE"})
            self.assertIn(
                opp["final_action"],
                {"SOFT_REMINDER", "FIRM_REMINDER", "PAYMENT_PLAN", "ESCALATE", "HUMAN_REVIEW", "STOP"},
            )

    def test_opportunity_detail_contains_recommendation_and_guardrails(self):
        response = self.client.get("/opportunities")
        promise_id = response.json()[0]["promise_id"]

        detail = self.client.get(f"/opportunities/{promise_id}").json()
        self.assertIn("recommended_action", detail)
        self.assertIn("final_action", detail)
        self.assertIn("guardrail_status", detail)
        self.assertIn(detail["guardrail_status"], {"ALLOW", "BLOCK", "OVERRIDE"})


if __name__ == "__main__":
    unittest.main()
