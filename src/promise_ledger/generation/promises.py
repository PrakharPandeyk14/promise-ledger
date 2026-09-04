from datetime import date, timedelta
from .personas import PERSONAS
from ..promise_ground_truth import evaluate_sequential_promises

PAYMENT_METHODS = ('BANK_TRANSFER', 'CARD', 'UPI', 'CHEQUE')


def _payment_date_for_persona(profile, rng, invoice_date, due_date, created, simulation_date):
    """Schedule a payment after a promise using the persona's timing parameters."""
    if rng.random() < profile.on_time_probability:
        # The on-time path is due-date-or-earlier; creation makes this a valid future event.
        target = due_date - timedelta(days=rng.randint(0, min(5, max(0, (due_date - invoice_date).days))))
    else:
        delay = rng.randint(*profile.payment_delay_range)
        target = due_date + timedelta(days=max(1, delay))
    return min(simulation_date, max(created + timedelta(days=1), target))


def _paid_before(connection, invoice_id, event_date, pending_rows=()):
    recorded = connection.execute('SELECT COALESCE(SUM(amount), 0) FROM payments WHERE invoice_id = ? AND payment_date < ?', (invoice_id, event_date.isoformat())).fetchone()[0]
    planned = sum(row[4] for row in pending_rows if row[1] == invoice_id and row[3] < event_date.isoformat())
    return recorded + planned


def _add_split_payments(rows, payment_id, invoice, rng, start_date, end_date, total, event_count=2):
    remaining, span = round(total, 2), max(1, (end_date - start_date).days)
    for number in range(event_count):
        amount = remaining if number == event_count - 1 else round(total * rng.uniform(.25, .45), 2)
        amount = min(amount, remaining)
        remaining = round(remaining - amount, 2)
        payment_date = start_date + timedelta(days=min(span, 1 + number * span // event_count))
        rows.append((payment_id, invoice['invoice_id'], invoice['customer_id'], payment_date.isoformat(), amount, rng.choice(PAYMENT_METHODS)))
        payment_id += 1
    return payment_id


def _finalize_invoice_statuses(connection, rng, simulation_date):
    for invoice in connection.execute('SELECT invoice_id, amount, due_date FROM invoices ORDER BY invoice_id').fetchall():
        paid = connection.execute('SELECT COALESCE(SUM(amount), 0) FROM payments WHERE invoice_id = ?', (invoice['invoice_id'],)).fetchone()[0]
        if paid + .005 >= invoice['amount']:
            status, written_off = 'PAID', None
        elif date.fromisoformat(invoice['due_date']) >= simulation_date:
            status, written_off = ('PARTIALLY_PAID' if paid else 'OPEN'), None
        else:
            status, written_off = 'OVERDUE', None
        if status == 'OVERDUE' and rng.random() < .04:
            status, written_off = 'WRITTEN_OFF', simulation_date.isoformat()
        connection.execute('UPDATE invoices SET status=?, written_off_date=? WHERE invoice_id=?', (status, written_off, invoice['invoice_id']))


def generate_promises(connection, rng, simulation_date):
    """Simulate promise creation, future cash behavior, and ground-truth outcomes in order."""
    invoices = connection.execute('SELECT i.*, c.persona FROM invoices i JOIN customers c USING(customer_id) ORDER BY i.invoice_id').fetchall()
    promise_rows, payment_rows = [], []
    promise_id = 1
    payment_id = connection.execute('SELECT COALESCE(MAX(payment_id), 0) + 1 FROM payments').fetchone()[0]
    for invoice in invoices:
        profile = PERSONAS[invoice['persona']]
        invoice_date, due_date = date.fromisoformat(invoice['invoice_date']), date.fromisoformat(invoice['due_date'])
        last_event_date = None
        for sequence in range(2 if rng.random() < .47 else 1):
            created = (max(invoice_date + timedelta(days=2), due_date + timedelta(days=rng.randint(-10, 20))) if sequence == 0 else last_event_date + timedelta(days=1))
            if created >= simulation_date:
                break
            outstanding = round(invoice['amount'] - _paid_before(connection, invoice['invoice_id'], created, payment_rows), 2)
            if outstanding <= .005:
                break
            promised_amount = round(min(outstanding, outstanding * rng.uniform(.30, .75)), 2)
            will_keep = rng.random() < profile.promise_keep_tendency
            planned_payment_date = _payment_date_for_persona(
                profile, rng, invoice_date, due_date, created, simulation_date
            )
            promised_date = max(
                created + timedelta(days=2),
                planned_payment_date if will_keep else created + timedelta(days=rng.randint(2, 30)),
            )
            promise_rows.append((promise_id, invoice['invoice_id'], invoice['customer_id'], created.isoformat(), promised_date.isoformat(), promised_amount, 'PENDING'))
            latest_payment = created
            if promised_date <= simulation_date and will_keep:
                payment_id = _add_split_payments(payment_rows, payment_id, invoice, rng, created, planned_payment_date, promised_amount)
                latest_payment = planned_payment_date
            elif promised_date <= simulation_date:
                if rng.random() < profile.partial_payment_probability:
                    payment_id = _add_split_payments(payment_rows, payment_id, invoice, rng, created, promised_date, round(promised_amount * rng.uniform(.08, .45), 2), event_count=1)
                    latest_payment = promised_date
                if rng.random() < profile.eventual_payment_probability:
                    late_date = max(
                        promised_date + timedelta(days=1),
                        _payment_date_for_persona(profile, rng, invoice_date, due_date, created, simulation_date),
                    )
                    late_date = min(simulation_date, late_date)
                    late_amount = round(min(invoice['amount'] - _paid_before(connection, invoice['invoice_id'], late_date, payment_rows), promised_amount * rng.uniform(.20, .70)), 2)
                    if late_date > promised_date and late_amount > .005:
                        payment_rows.append((payment_id, invoice['invoice_id'], invoice['customer_id'], late_date.isoformat(), late_amount, rng.choice(PAYMENT_METHODS)))
                        payment_id, latest_payment = payment_id + 1, late_date
            elif will_keep and created + timedelta(days=1) <= simulation_date and rng.random() < .35:
                observed = round(promised_amount * rng.uniform(.05, .25), 2)
                payment_rows.append((payment_id, invoice['invoice_id'], invoice['customer_id'], (created + timedelta(days=1)).isoformat(), observed, rng.choice(PAYMENT_METHODS)))
                payment_id, latest_payment = payment_id + 1, created + timedelta(days=1)
            last_event_date = max(promised_date, latest_payment)
            promise_id += 1
    connection.executemany('INSERT INTO promises VALUES (?, ?, ?, ?, ?, ?, ?)', promise_rows)
    connection.executemany('INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?)', payment_rows)
    promises = connection.execute('SELECT * FROM promises ORDER BY invoice_id, promise_created_date, promise_id').fetchall()
    payments = connection.execute('SELECT * FROM payments ORDER BY invoice_id, payment_date, payment_id').fetchall()
    outcomes, _ = evaluate_sequential_promises(promises, payments, simulation_date)
    connection.executemany('UPDATE promises SET outcome=? WHERE promise_id=?', [(outcome, promise_id) for promise_id, outcome in outcomes.items()])
    _finalize_invoice_statuses(connection, rng, simulation_date)
    return promise_rows
