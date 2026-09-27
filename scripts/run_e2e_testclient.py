"""Run end-to-end API and HTML tests against FastAPI app in-process."""

from starlette.testclient import TestClient
from promise_ledger.api import create_app
from promise_ledger.config import DATABASE_PATH

app = create_app(DATABASE_PATH)
client = TestClient(app)

print("1. Health check:")
r = client.get("/health")
print(f"   Status: {r.status_code}, Body: {r.json()}")
assert r.status_code == 200

print("\n2. Financial Summary:")
r = client.get("/financial/summary")
print(f"   Status: {r.status_code}")
summary = r.json()
print(f"   Cash Balance: ₹{summary['current_cash_balance']:,.2f}")
print(f"   Monthly Income: ₹{summary['monthly_income']:,.2f}")
print(f"   Monthly Expenses: ₹{summary['monthly_expenses']:,.2f}")
print(f"   Net Cash Flow: ₹{summary['net_cash_flow']:,.2f}")
print(f"   Receivables: ₹{summary['total_receivables']:,.2f}")
print(f"   Financial Risk: {summary['financial_risk_level']} (Score: {summary['financial_risk_score']})")
print(f"   Contributors: {summary['risk_contributors']}")
print(f"   Insight: {summary['receivables_risk_insight']}")
assert r.status_code == 200

print("\n3. Financial Recurring Expenses:")
r = client.get("/financial/recurring-expenses")
print(f"   Status: {r.status_code}")
rec = r.json()
print(f"   Total Monthly Recurring: ₹{rec['total_monthly_recurring']:,.2f}")
print(f"   Recurring count: {len(rec['recurring_expenses'])}")
for item in rec['recurring_expenses'][:3]:
    print(f"   - {item['merchant']}: ₹{item['amount']:,.2f} / {item['periodicity']}")
assert r.status_code == 200

print("\n4. Financial Anomalies:")
r = client.get("/financial/anomalies")
print(f"   Status: {r.status_code}")
anm = r.json()
print(f"   Total anomalies: {anm['total_anomalies']} ({anm['high_severity_count']} high)")
for a in anm['anomalies']:
    print(f"   - [{a['severity']}] {a['description']}: ₹{a['amount']:,.2f} (Dev: {a['deviation_percentage']}%) - {a['reason']}")
assert r.status_code == 200

print("\n5. Financial Budgets:")
r = client.get("/financial/budgets")
print(f"   Status: {r.status_code}")
b = r.json()
print(f"   Overall: ₹{b['total_spent']:,.2f} / ₹{b['total_budget']:,.2f} ({b['overall_utilization_pct']}%)")
for c in b['categories'][:4]:
    print(f"   - {c['category']}: ₹{c['spent']:,.2f} / ₹{c['budget']:,.2f} ({c['status']})")
assert r.status_code == 200

print("\n6. Financial Goals:")
r = client.get("/financial/goals")
print(f"   Status: {r.status_code}")
g = r.json()
print(f"   Total saved: ₹{g['total_saved']:,.2f} / ₹{g['total_target']:,.2f}")
for goal in g['goals']:
    print(f"   - {goal['name']}: {goal['progress_pct']}% funded")
assert r.status_code == 200

print("\n7. Financial Transactions (All, Income, Expense):")
r_all = client.get("/financial/transactions?limit=10")
r_inc = client.get("/financial/transactions?type=INCOME&limit=5")
r_exp = client.get("/financial/transactions?type=EXPENSE&limit=5")
print(f"   All count: {len(r_all.json())}, Income count: {len(r_inc.json())}, Expense count: {len(r_exp.json())}")
assert r_all.status_code == 200 and r_inc.status_code == 200 and r_exp.status_code == 200

print("\n8. Existing Opportunities & Decision Engine:")
r_opp = client.get("/opportunities")
assert r_opp.status_code == 200
opps = r_opp.json()
first_id = opps[0]["promise_id"]
r_eval = client.post(f"/opportunities/{first_id}/evaluate")
assert r_eval.status_code == 200
eval_data = r_eval.json()
print(f"   Evaluated promise {first_id}: {eval_data['recommended_action']} -> {eval_data['final_action']} ({eval_data['guardrail_status']})")

print("\n9. Phase 2 Cash Flow Forecast:")
r_fc = client.get("/financial/forecast")
assert r_fc.status_code == 200
fc = r_fc.json()
print(f"   Period: {fc['forecast_period']}, Confidence: {fc['confidence']}")
print(f"   Starting Cash: ₹{fc['starting_cash_balance']:,.2f} -> Ending Cash: ₹{fc['projected_final_cash']:,.2f}")
print(f"   Months projected: {len(fc['months'])}")
for m in fc['months']:
    print(f"   - {m['month_name']}: Inflow +₹{m['projected_income']:,.2f}, Outflow -₹{m['projected_expenses']:,.2f}, Net {m['projected_net_cash_flow']:+,.2f}")

print("\n10. Phase 2 What-If Scenario Simulator:")
r_scen = client.post("/financial/scenario", json={
    "receivable_delay_days": 15,
    "expense_change_percent": 10.0,
    "additional_monthly_expense": 20000.0
})
assert r_scen.status_code == 200
scen = r_scen.json()
base_cash = scen['base_case']['projected_ending_cash']
sim_cash = scen['scenario_case']['projected_ending_cash']
delta_cash = scen['delta']['projected_ending_cash']
print(f"   Base Ending Cash: ₹{base_cash:,.2f} vs Simulated: ₹{sim_cash:,.2f} (Delta: ₹{delta_cash:,.2f})")
print(f"   Runway: {scen['base_case']['cash_runway_months']} mo -> {scen['scenario_case']['cash_runway_months']} mo")
print(f"   Risk Shift: {scen['risk_change']['risk_level']}")
print(f"   Explanation: {scen['explanation']}")

print("\n11. Phase 2 AI Decision Support Recommendations & Human Approval:")
r_recs = client.get("/financial/recommendations")
assert r_recs.status_code == 200
recs = r_recs.json()
print(f"   Total recommendations: {recs['total_count']}, High priority: {recs['high_priority_count']}, Pending: {recs['pending_human_approval_count']}")
for r_item in recs['recommendations'][:3]:
    print(f"   - [{r_item['priority']}] {r_item['recommendation']} (Human Approval: {r_item['human_approval_required']}, Status: {r_item['status']})")

first_rec_id = recs['recommendations'][0]['id']
r_rev = client.post(f"/financial/recommendations/{first_rec_id}/review", json={
    "action": "APPROVE",
    "reviewer_notes": "Live E2E merchant approval test"
})
assert r_rev.status_code == 200
rev_res = r_rev.json()
print(f"   Reviewed {first_rec_id}: Status {rev_res['status']} by merchant")

print("\n12. Frontend Phase 1 & Phase 2 UI Elements:")
r_html = client.get("/")
assert r_html.status_code == 200
assert 'id="financial"' in r_html.text
assert 'id="forecast"' in r_html.text
assert 'id="scenarios"' in r_html.text
assert 'id="recommendations"' in r_html.text
assert 'id="fcEndingCash"' in r_html.text
assert 'id="btnRunScenario"' in r_html.text
assert 'id="recPendingBadge"' in r_html.text
assert "HUMAN-IN-THE-LOOP" in r_html.text
print("   ✓ All Phase 1 and Phase 2 UI elements confirmed present in rendered HTML")

print("\n" + "=" * 60)
print("ALL LIVE PHASE 1 & PHASE 2 E2E VALIDATION CHECKS PASSED!")
print("=" * 60)
