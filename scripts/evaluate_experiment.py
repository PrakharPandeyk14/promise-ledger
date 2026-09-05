"""Run the control vs AI-treatment recovery experiment once.

Uses the existing unresolved opportunity batch and the existing
Promise → Decision → Guardrail → Executor pipeline. No real payments,
messages, or database writes.
"""

from promise_ledger.config import SIMULATION_DATE
from promise_ledger.evaluation.experiment import run_experiment


def main() -> None:
    metrics = run_experiment()
    print("=" * 80)
    print("CONTROL VS AI TREATMENT EVALUATION")
    print("=" * 80)
    print(f"Evaluation date: {metrics.evaluation_date}")
    print(f"Expected simulation date: {SIMULATION_DATE.isoformat()}")
    print()
    print("PORTFOLIO")
    print("-" * 80)
    print(f"evaluation_count:              {metrics.evaluation_count}")
    print(f"total_outstanding_amount:      {metrics.total_outstanding_amount:,.2f}")
    print()
    print("RECOVERY COMPARISON")
    print("-" * 80)
    print(f"control_recovered_amount:      {metrics.control_recovered_amount:,.2f}")
    print(f"treatment_recovered_amount:    {metrics.treatment_recovered_amount:,.2f}")
    print(f"incremental_recovery_amount:   {metrics.incremental_recovery_amount:,.2f}")
    print(f"control_recovery_rate:         {metrics.control_recovery_rate:.4f}")
    print(f"treatment_recovery_rate:       {metrics.treatment_recovery_rate:.4f}")
    print(f"treatment_improvement_percent: {metrics.treatment_improvement_percent:.2f}")
    print()
    print("OUTCOME MIX (mutually exclusive, sum to 100% when count > 0)")
    print("-" * 80)
    print(f"automation_rate:               {metrics.automation_rate:.2f}%")
    print(f"human_review_rate:             {metrics.human_review_rate:.2f}%")
    print(f"stopped_rate:                  {metrics.stopped_rate:.2f}%")
    mix_total = metrics.automation_rate + metrics.human_review_rate + metrics.stopped_rate
    print(f"outcome_rate_sum:              {mix_total:.2f}%")
    print()
    print("No real recovery actions were executed.")
    print("=" * 80)


if __name__ == "__main__":
    main()
