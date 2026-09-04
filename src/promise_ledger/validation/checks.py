from dataclasses import asdict, dataclass
from pathlib import Path
from ..config import DATABASE_PATH, SIMULATION_DATE
from ..db.connection import connect
from ..promise_ground_truth import EPSILON, evaluate_sequential_promises

@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str

def _result(connection, name, sql, params=()):
    failures = connection.execute(sql, params).fetchone()[0]
    return CheckResult(name, failures == 0, f'{failures} violation(s)')

def _promise_allocation_checks(connection, simulation_date):
    amount_bad = non_positive_balance = outcome_bad = kept_bad = broken_bad = reused = 0
    for invoice in connection.execute('SELECT invoice_id, amount FROM invoices ORDER BY invoice_id'):
        payments = connection.execute('SELECT payment_id, invoice_id, customer_id, payment_date, amount FROM payments WHERE invoice_id=? ORDER BY payment_date, payment_id', (invoice['invoice_id'],)).fetchall()
        promises = connection.execute('SELECT * FROM promises WHERE invoice_id=? ORDER BY promise_created_date, promise_id', (invoice['invoice_id'],)).fetchall()
        expected_outcomes, reuse_attempts = evaluate_sequential_promises(promises, payments, simulation_date)
        for promise in promises:
            paid_before = sum(p['amount'] for p in payments if p['payment_date'] < promise['promise_created_date'])
            balance = invoice['amount'] - paid_before
            if balance <= EPSILON:
                non_positive_balance += 1
            if promise['promised_amount'] > balance + EPSILON:
                amount_bad += 1
            reused += reuse_attempts[promise['promise_id']]
            expected = expected_outcomes[promise['promise_id']]
            if promise['outcome'] == 'KEPT' and expected != 'KEPT':
                kept_bad += 1
            if promise['outcome'] == 'BROKEN' and expected != 'BROKEN':
                broken_bad += 1
            if promise['outcome'] != expected:
                outcome_bad += 1
                kept_bad += promise['outcome'] == 'KEPT'
                broken_bad += promise['outcome'] == 'BROKEN'
    return [
        CheckResult('promise_amount_within_outstanding_at_creation', amount_bad == 0, f'{amount_bad} violation(s)'),
        CheckResult('promise_created_only_with_positive_balance', non_positive_balance == 0, f'{non_positive_balance} violation(s)'),
        CheckResult('no_payment_reused_across_sequential_promises', reused == 0, f'{reused} violation(s)'),
        CheckResult('strict_post_creation_outcomes', outcome_bad == 0, f'{outcome_bad} violation(s)'),
        CheckResult('pre_creation_payments_excluded_from_promise_fulfillment', kept_bad == 0, f'{kept_bad} violation(s)'),
        CheckResult('kept_promises_have_strict_eligible_payments', kept_bad == 0, f'{kept_bad} violation(s)'),
        CheckResult('broken_promises_lack_strict_eligible_payments', broken_bad == 0, f'{broken_bad} violation(s)'),
    ]

def validate_database(path: Path = DATABASE_PATH, simulation_date=SIMULATION_DATE):
    connection = connect(path)
    foreign_keys = connection.execute('PRAGMA foreign_key_check').fetchall()
    results = [CheckResult('foreign_keys', not foreign_keys, f'{len(foreign_keys)} violation(s)')]
    results.extend([
        _result(connection, 'no_negative_amounts', "SELECT COUNT(*) FROM (SELECT amount FROM invoices WHERE amount < 0 UNION ALL SELECT amount FROM payments WHERE amount < 0 UNION ALL SELECT promised_amount FROM promises WHERE promised_amount < 0)"),
        _result(connection, 'invoice_dates', 'SELECT COUNT(*) FROM invoices WHERE invoice_date > due_date OR written_off_date IS NOT NULL AND written_off_date < invoice_date'),
        _result(connection, 'customer_invoice_due_chronology', 'SELECT COUNT(*) FROM invoices i JOIN customers c ON c.customer_id=i.customer_id WHERE c.created_date > i.invoice_date OR i.invoice_date > i.due_date'),
        _result(connection, 'payment_dates_and_customer', 'SELECT COUNT(*) FROM payments p JOIN invoices i ON p.invoice_id=i.invoice_id WHERE p.payment_date < i.invoice_date OR p.customer_id != i.customer_id'),
        _result(connection, 'payment_totals', 'SELECT COUNT(*) FROM (SELECT i.invoice_id FROM invoices i LEFT JOIN payments p USING(invoice_id) GROUP BY i.invoice_id HAVING COALESCE(SUM(p.amount),0) > i.amount + .005)'),
        _result(connection, 'promised_date_strictly_after_creation', 'SELECT COUNT(*) FROM promises WHERE promised_payment_date <= promise_created_date'),
        _result(connection, 'promise_references_and_dates', 'SELECT COUNT(*) FROM promises p JOIN invoices i ON p.invoice_id=i.invoice_id WHERE p.customer_id != i.customer_id OR p.promise_created_date < i.invoice_date'),
        _result(connection, 'recovery_action_references_and_dates', 'SELECT COUNT(*) FROM recovery_actions a JOIN invoices i ON a.invoice_id=i.invoice_id WHERE a.customer_id != i.customer_id OR a.action_date < i.invoice_date'),
        _result(connection, 'no_recovery_action_after_simulation_date', 'SELECT COUNT(*) FROM recovery_actions WHERE action_date > ?', (simulation_date.isoformat(),)),
        _result(connection, 'linked_recovery_action_promise_chronology', 'SELECT COUNT(*) FROM recovery_actions a JOIN promises p ON p.promise_id=a.promise_id WHERE a.action_date < p.promise_created_date OR a.action_date > ?', (simulation_date.isoformat(),)),
        _result(connection, 'required_fields', """SELECT COUNT(*) FROM (
            SELECT customer_id FROM customers WHERE external_id IS NULL OR customer_name IS NULL OR persona IS NULL OR created_date IS NULL
            UNION ALL SELECT invoice_id FROM invoices WHERE customer_id IS NULL OR invoice_number IS NULL OR invoice_date IS NULL OR due_date IS NULL OR amount IS NULL OR status IS NULL
            UNION ALL SELECT payment_id FROM payments WHERE invoice_id IS NULL OR customer_id IS NULL OR payment_date IS NULL OR amount IS NULL OR payment_method IS NULL
            UNION ALL SELECT promise_id FROM promises WHERE invoice_id IS NULL OR customer_id IS NULL OR promise_created_date IS NULL OR promised_payment_date IS NULL OR promised_amount IS NULL OR outcome IS NULL
            UNION ALL SELECT action_id FROM recovery_actions WHERE invoice_id IS NULL OR customer_id IS NULL OR action_date IS NULL OR action_type IS NULL OR channel IS NULL OR notes IS NULL
        )"""),
    ])
    results.extend(_promise_allocation_checks(connection, simulation_date))
    connection.close()
    return [asdict(result) for result in results]
