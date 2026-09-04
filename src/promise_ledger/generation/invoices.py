from datetime import date, timedelta
from .personas import PERSONAS


def generate_invoices_and_payments(connection, rng, simulation_date, count=1000):
    """Create invoices and initial payments only; promise-driven payments follow later."""
    customers = connection.execute('SELECT customer_id, persona, created_date FROM customers ORDER BY customer_id').fetchall()
    invoice_rows, payment_rows = [], []
    payment_id = 1
    for invoice_id in range(1, count + 1):
        customer = rng.choice(customers)
        profile = PERSONAS[customer['persona']]
        proposed_invoice_date = simulation_date - timedelta(days=rng.randint(20, 540))
        invoice_date = max(proposed_invoice_date, date.fromisoformat(customer['created_date']))
        due_date = invoice_date + timedelta(days=rng.choice((15, 30, 45)))
        amount = round(rng.uniform(*profile.amount_range), 2)
        invoice_rows.append((invoice_id, customer['customer_id'], f'INV-{invoice_id:05d}', invoice_date.isoformat(), due_date.isoformat(), amount, 'OPEN', None))
        if rng.random() < .32:
            initial_amount = round(amount * rng.uniform(.08, .35), 2)
            payment_rows.append((payment_id, invoice_id, customer['customer_id'], (invoice_date + timedelta(days=1)).isoformat(), initial_amount, rng.choice(('BANK_TRANSFER', 'CARD', 'UPI', 'CHEQUE'))))
            payment_id += 1
    connection.executemany('INSERT INTO invoices VALUES (?, ?, ?, ?, ?, ?, ?, ?)', invoice_rows)
    connection.executemany('INSERT INTO payments VALUES (?, ?, ?, ?, ?, ?)', payment_rows)
    return invoice_rows, payment_rows
