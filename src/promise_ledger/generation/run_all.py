from ..config import DATABASE_PATH, SIMULATION_DATE, make_rng
from ..db.connection import recreate_database
from .customers import generate_customers
from .invoices import generate_invoices_and_payments
from .promises import generate_promises
from .recovery_actions import generate_recovery_actions
from .merchant_policies import generate_merchant_policies


def generate_database(path=DATABASE_PATH):
    rng = make_rng()
    connection = recreate_database(path)
    generate_customers(connection, rng, SIMULATION_DATE)
    generate_invoices_and_payments(connection, rng, SIMULATION_DATE)
    generate_promises(connection, rng, SIMULATION_DATE)
    generate_recovery_actions(connection, rng, SIMULATION_DATE)
    generate_merchant_policies(connection)
    connection.commit()
    counts = {table: connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('customers','invoices','payments','promises','recovery_actions','merchant_policies')}
    connection.close()
    return counts
