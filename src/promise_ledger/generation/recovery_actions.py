from datetime import date, timedelta


def generate_recovery_actions(connection, rng, simulation_date):
    invoices = connection.execute("SELECT * FROM invoices WHERE status IN ('OVERDUE','PARTIALLY_PAID','WRITTEN_OFF')").fetchall()
    rows, action_id = [], 1
    action_types = ('SOFT_REMINDER','FIRM_REMINDER','PAYMENT_PLAN','ESCALATE','HUMAN_REVIEW','STOP')
    for invoice in invoices:
        due = date.fromisoformat(invoice['due_date'])
        for position in range(rng.randint(1, 3)):
            promises = connection.execute('SELECT promise_id, promise_created_date FROM promises WHERE invoice_id = ? ORDER BY promise_id', (invoice['invoice_id'],)).fetchall()
            promise = rng.choice(promises) if promises and rng.random() < .65 else None
            promise_id = promise['promise_id'] if promise else None
            candidate_date = due + timedelta(days=5 + position * rng.randint(4, 16))
            promise_created = date.fromisoformat(promise['promise_created_date']) if promise else due
            action_date = min(simulation_date, max(candidate_date, promise_created))
            rows.append((action_id, invoice['invoice_id'], invoice['customer_id'], promise_id, action_date.isoformat(), rng.choice(action_types), rng.choice(('EMAIL','SMS','PHONE','SYSTEM')), 'Synthetic historical recovery action'))
            action_id += 1
    connection.executemany('INSERT INTO recovery_actions VALUES (?, ?, ?, ?, ?, ?, ?, ?)', rows)
    return rows
