# Promise Ledger — Data Foundation

Promise Ledger is a fintech hackathon project for B2B receivables recovery. This repository contains only its reproducible SQLite synthetic-data foundation; it does not contain the API, frontend, recovery agent, ML, or risk engine.

## Promise-break intelligence foundation

`scripts/build_features.py` builds a leakage-safe in-memory feature dataset for
each promise. Every historical event has a date strictly before the promise
creation date. Earlier promise outcomes are used only when their promised date
has also passed, so a still-unresolved earlier promise cannot leak its eventual
result. PENDING promises receive no target and are excluded from supervised
training and evaluation.

The deterministic baseline uses a customer's observed broken / resolved prior
promises after at least three resolved promises. Customers with less history
receive a fixed 0.50 probability. The evaluation split sorts usable promises by
creation date and assigns whole creation dates to the earlier training or later
test partition (80/20 target), never mixing a date across both.
`historical_recovery_rate` means paid historical invoice value divided by the
value of invoices issued before the prediction point.

## Promise risk scoring

`src/promise_ledger/risk/scoring.py` converts a promise-break probability into two distinct business signals. `promise_credibility_score` is the complement of break probability on a 0–100 scale. `recovery_probability` is intentionally different: it is a transparent heuristic blending historical invoice recovery rate (55%), historical on-time payment rate (20%), and promise credibility (25%). It is not a calibrated ML probability; it represents recovery propensity and recognizes that a broken promise can still be followed by eventual payment.

`scripts/score_promises.py` trains the deterministic Random Forest candidate on all resolved historical promises and scores unresolved promises only. Unresolved promises never contribute their unknown outcomes to model training. Each score includes deterministic explanation text based on observable historical behavior.

## Synthetic-data disclaimer

All records are fabricated for development and testing. They are not sourced from Razorpay or any other private, production, or customer dataset.

## Schema

The SQLite database has exactly six main tables: `customers`, `invoices`, `payments`, `promises`, `recovery_actions`, and `merchant_policies`. Foreign keys, amount checks, status checks, and lookup indexes are built into the schema.

## Personas

Five centrally configured behaviours drive the simulation: reliable payer, slow but reliable, unpredictable payer, chronic broken-promiser, and high-value strategic customer. Strategic customers have larger invoices, while their payment reliability remains independently generated rather than intrinsically high or low risk.

Promise simulation is chronological. A promise is capped at the invoice balance at creation; only payments strictly after creation and on or before its due date can fulfill it. Persona promise-keeping tendency influences those future payment events, while the stored outcome is derived from the final payment ledger.

## Commands

Run from the repository root on Python 3. The project uses only the standard library.

```powershell
$env:PYTHONPATH = "src"
python scripts/generate_data.py
python scripts/validate_data.py
python scripts/print_summary.py
python scripts/build_features.py
python -m unittest discover -s tests -v
```

The generated database is `data/promise_ledger.db`. Generation uses `SEED = 42`, so rerunning it recreates the same data.

## Expected recovery and portfolio prioritization

`src/promise_ledger/risk/prioritization.py` turns the recovery-propensity signal into a financial opportunity value:
`expected_recovery = outstanding_amount_at_promise_creation × recovery_probability`.
Unresolved promises are ranked by expected recovery, with deterministic tie-breakers on outstanding amount, break probability, and promise ID.
The ranked portfolio is split into deterministic HIGH/MEDIUM/LOW priority tiers and receives a relative priority score for presentation.
This layer only prioritizes opportunities; it does not execute actions or bypass merchant policies. Day 4 will consume the ranking in the decision and guardrail layers.

Run:

```powershell
$env:PYTHONPATH = "src"
python scripts/prioritize_recovery.py
```

## Day 4 Step 1: Recovery Decision Engine

`src/promise_ledger/recovery/` converts each Day 3 `RecoveryOpportunity` into
one deterministic recommendation. It consumes the existing break probability,
promise credibility, recovery probability, expected recovery, and priority
tier. Optional historical feature context can identify contradictory or
structured-repayment situations. The current promise's outcome is never read.

Available recommendations are:

- `STOP`: no actionable balance or negligible recovery opportunity.
- `HUMAN_REVIEW`: exposure or contradictory evidence requires judgment.
- `ESCALATE`: high-priority, high-break-risk opportunity needing stronger attention.
- `PAYMENT_PLAN`: immediate full payment appears unlikely but structured recovery is meaningful.
- `FIRM_REMINDER`: elevated break risk remains suitable for automated intervention.
- `SOFT_REMINDER`: lower break risk with an actionable balance.

The hierarchy is evaluated in that order. All numerical policy thresholds are
centralized in the immutable `DecisionConfig` in
`src/promise_ledger/recovery/config.py`; these defaults are documented policy
values and can later be replaced by merchant policies. They are not simulator
parameters or persona labels.

Run the recommendation report with:

```powershell
$env:PYTHONPATH = "src"
python scripts/decide_recovery.py
```

For example, a high-break-risk, high-priority promise with meaningful expected
recovery is recommended for `ESCALATE`; a lower-risk actionable promise is
recommended for `SOFT_REMINDER`.

These are recommendations only. The engine does not send messages, modify
payments, call payment APIs, or execute recovery. Future execution must apply
merchant guardrails before any action is considered. Guardrails and execution
are intentionally outside Day 4 Step 1.

## Day 4 Step 2: Guardrail Engine

`src/promise_ledger/recovery/guardrails.py` independently evaluates a Step 1
recommendation against the existing `merchant_policies` row and current
observable state. It returns `ALLOW`, `BLOCK`, or `OVERRIDE`, with a final
action, explicit reason code, explanation, policy value, and observed value.
It has no execution path: it cannot send contact, modify payments, create
transactions, or call an external API.

The safety hierarchy is:

`STOP -> HUMAN_REVIEW -> ESCALATE -> PAYMENT_PLAN -> FIRM_REMINDER -> SOFT_REMINDER`

Checks run in that order. A negligible balance, negligible expected recovery,
resolved promise, paid invoice, or written-off invoice becomes `STOP`. Risk at
or above the merchant `human_review_threshold`, or an invoice above
`maximum_invoice_value_autonomous`, becomes `HUMAN_REVIEW`. Automated contact
is blocked when `maximum_automated_contacts` has been reached or when the
`minimum_contact_cooldown_days` has not elapsed. A payment plan exceeding
`maximum_payment_plan_duration_days` is routed to `HUMAN_REVIEW`.

The generated merchant policy currently configures:

- maximum automated contacts: `4`
- minimum contact cooldown: `3` days
- maximum autonomous invoice value: `15000.0`
- maximum payment-plan duration: `90` days
- human-review risk threshold: `0.70`

For example, an overdue `SOFT_REMINDER` with a meaningful balance and no
recent contacts is allowed. The same recommendation after four automated
contacts is blocked and routed to `HUMAN_REVIEW` with
`MAX_CONTACTS_EXCEEDED`. An invoice above `15000.0` is overridden to
`HUMAN_REVIEW` with `AUTONOMOUS_VALUE_LIMIT_EXCEEDED`.

Run the deterministic portfolio evaluation with:

```powershell
$env:PYTHONPATH = "src"
python scripts/evaluate_guardrails.py
```

The schema has no policy-window column, so contact counts use all observable
historical automated recovery actions for the invoice up to the evaluation
date. The schema also has no payment-plan minimum-recovery field, so Step 2
enforces the available duration limit and relies on Step 1 for recovery
appropriateness. These assumptions can be replaced when merchant policy
fields are expanded; no schema change is made in this step.

## Day 4 Step 3: Safe Action Execution and Audit

`src/promise_ledger/recovery/executor.py` provides the final prototype layer:
`Promise -> Decision Engine -> Guardrail Engine -> Action Executor -> AuditRecord`.
The `ActionExecutor` accepts a Step 1 `RecoveryDecision`, always invokes the
existing `GuardrailEngine`, and does not accept a caller-supplied final action.
This keeps execution from bypassing policy checks.

The executor records three outcomes without real-world side effects:

- `ALLOW`: records `SIMULATED_EXECUTION` for the recommended action.
- `BLOCK`: records `BLOCKED_NO_EXECUTION` and the guardrail reason.
- `OVERRIDE`: records the original recommendation, replacement final action,
  and `OVERRIDDEN_NO_EXECUTION`.

Each immutable `AuditRecord` includes a deterministic SHA-256 `audit_id`,
evaluation date, promise/invoice/customer identifiers, recommended action,
guardrail status, final action, reason code and explanation, expected recovery,
break probability, promise credibility, priority tier, simulated flag, and
execution status. Records are currently returned in memory rather than written
to the database, so the database schema remains unchanged.

Run the demonstration against existing unresolved promises with:

```powershell
$env:PYTHONPATH = "src"
python scripts/simulate_recovery.py
```

The demonstration only records what would happen. It does not send email,
SMS, WhatsApp, or other messages; process payments; modify payment records;
create recovery transactions; or call external services. A production version
would need an append-only durable audit store, authentication, idempotency,
merchant guardrails, and explicit execution adapters before any real action.

## Day 4 Step 4: Portfolio-Level Orchestration and Evaluation

`src/promise_ledger/recovery/orchestration.py` chains the existing components
into a deterministic end-to-end recovery workflow that accepts a collection of
unresolved promises and produces audit records and portfolio metrics:

```
Portfolio → Risk/Decision Engine → Guardrail Engine → Action Executor → Audit Records
                                                                       ↓
                                                              Portfolio Evaluation
```

The `RecoveryOrchestrator` does not invent a second decision system. Instead,
it orchestrates the three existing layers:

1. **Step 1 (Decision Engine)**: Recommends a single recovery action based on
   promise risk, expected recovery, and priority. The recommendation is
   advisory; it does not constrain guardrails.

2. **Step 2 (Guardrail Engine)**: Evaluates the recommendation against
   merchant policy and observable state. Returns `ALLOW`, `BLOCK`, or
   `OVERRIDE`, with a final action. The final action is binding; the executor
   never accepts a caller-supplied override.

3. **Step 3 (Action Executor)**: Records the outcome as an immutable audit
   record. Only ALLOW outcomes are marked `SIMULATED_EXECUTION`; BLOCK and
   OVERRIDE outcomes are marked `BLOCKED_NO_EXECUTION` and
   `OVERRIDDEN_NO_EXECUTION` respectively.

**Key Design Properties:**

- **No Bypass**: The orchestrator cannot accept or force a caller-supplied
  final action. Guardrails are always invoked.
- **Deterministic**: Identical input data produces identical audit IDs and
  decisions across multiple runs.
- **Side-Effect Free**: No database writes, no payment changes, no real
  communication, no external API calls.
- **Audit Trail**: Every evaluated opportunity generates an immutable audit
  record with the full decision chain.

### Portfolio Evaluation Metrics

`src/promise_ledger/recovery/portfolio.py` provides the `PortfolioEvaluator`
and `PortfolioMetrics` classes. The evaluator aggregates orchestration results
into comprehensive portfolio statistics:

**Financial Metrics:**

- Total outstanding amount across the portfolio
- Total expected recovery
- Average expected recovery per opportunity
- Expected recovery and outstanding amount by final action

**Decision Metrics:**

- Recommended action distribution (SOFT_REMINDER, FIRM_REMINDER, PAYMENT_PLAN,
  ESCALATE, HUMAN_REVIEW, STOP)
- Final action distribution (after guardrails)

**Guardrail Metrics:**

- Count of ALLOW decisions (simulated execution)
- Count of BLOCK decisions (guardrail rejected recommendation)
- Count of OVERRIDE decisions (recommendation replaced with HUMAN_REVIEW)

**Execution Metrics:**

- Count of simulated executions
- Count of blocked (no execution)
- Count of overridden (no execution)
- Count of STOP outcomes
- Count of HUMAN_REVIEW outcomes

**Portfolio Classification:**

- Percentage of opportunities automated (ALLOW)
- Percentage requiring human review (HUMAN_REVIEW + BLOCK + OVERRIDE)
- Percentage stopped (no recovery action)

### Demonstration Script

`scripts/orchestrate_recovery.py` demonstrates the complete end-to-end pipeline
using the existing database:

1. Fetches the top 10 unresolved opportunities by expected recovery
2. Runs each through the decision engine → guardrails → executor chain
3. Evaluates the portfolio with PortfolioEvaluator
4. Prints a comprehensive summary including:
   - Portfolio overview (total amount, expected recovery, counts)
   - Recommended action distribution
   - Final action distribution (after guardrails)
   - Guardrail decision counts
   - Execution outcome counts
   - Opportunity classification (automated, human review, stopped)
   - Expected recovery by final action
   - Outstanding amount by final action

5. Prints representative audit records demonstrating:
   - An ALLOW outcome (simulated execution)
   - A BLOCK outcome (guardrail rejected)
   - An OVERRIDE outcome (overridden to HUMAN_REVIEW)
   - A STOP outcome (no actionable recovery)
   - A HUMAN_REVIEW outcome (if available)

Run with:

```powershell
$env:PYTHONPATH = "src"
python scripts/orchestrate_recovery.py
```

### Architecture Summary

The complete Day 4 recovery pipeline follows this architecture:

```
Unresolved Promise (from database)
  ↓
RecoveryOpportunity (Day 3 risk/prioritization)
  ↓
RecoveryDecisionEngine (Step 1: Recommendation)
  → RecoveryDecision (what action is recommended)
  ↓
GuardrailEngine (Step 2: Policy validation)
  → GuardrailResult (ALLOW/BLOCK/OVERRIDE + final action)
  ↓
ActionExecutor (Step 3: Audit recording)
  → ExecutionResult
    - GuardrailResult (decision chain)
    - AuditRecord (immutable, deterministic SHA-256 audit_id)
  ↓
PortfolioEvaluator (portfolio-level analysis)
  → PortfolioMetrics (comprehensive summary statistics)
```

**Critical Distinctions:**

- **Recommendation**: The decision engine's suggested action. Purely advisory.
- **Guardrail Decision**: The policy check result (ALLOW/BLOCK/OVERRIDE).
  Binding. The final action follows this decision.
- **Final Action**: The action that results from the guardrail decision.
  Binding. Never set by the caller. Always determined by guardrails.
- **Execution Status**: How the final action was recorded (SIMULATED if ALLOW,
  BLOCKED if BLOCK, OVERRIDDEN if OVERRIDE).
- **Audit Record**: Immutable evidence of the complete evaluation chain,
  including all four elements above, plus promise/invoice/customer identifiers,
  expected recovery, risk scores, and a deterministic audit ID.

### No Schema Changes

The orchestration and portfolio evaluation layers use only the existing
`promises`, `invoices`, `customers`, `recovery_actions`, and
`merchant_policies` tables. No new tables, columns, or indexes are added. Audit
records are currently in-memory; a production system would add an append-only
audit log table and durable persistence.

### Testing

Comprehensive test suite in `tests/test_orchestration.py` validates:

- Complete pipeline execution (decision → guardrails → executor → audit)
- Guardrail enforcement is preserved across orchestration
- Executor is always used (no bypass path exists)
- No final-action bypass is possible (caller cannot override guardrails)
- Deterministic results (identical input → identical audit_id)
- Portfolio metrics are correctly aggregated
- Audit records are complete and immutable
- Blocked actions are not simulated
- Overridden actions are not simulated
- Allowed actions are simulated
- No database mutations occur
- Empty portfolio handling
- Mixed portfolio handling (various outcomes in one run)
