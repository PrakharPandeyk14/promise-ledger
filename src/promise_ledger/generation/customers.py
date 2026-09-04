from datetime import timedelta
from .personas import PERSONAS


def generate_customers(connection, rng, simulation_date, count=200):
    persona_names = list(PERSONAS)
    weights = [30, 25, 22, 13, 10]
    rows = []
    for customer_id in range(1, count + 1):
        persona = rng.choices(persona_names, weights=weights, k=1)[0]
        created = simulation_date - timedelta(days=rng.randint(365, 1500))
        limit = rng.randint(8_000, 50_000) * (3 if persona == 'HIGH_VALUE_STRATEGIC' else 1)
        rows.append((customer_id, f'CUST-{customer_id:04d}', f'Synthetic Customer {customer_id:03d}', persona, created.isoformat(), limit))
    connection.executemany('INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)', rows)
    return rows

