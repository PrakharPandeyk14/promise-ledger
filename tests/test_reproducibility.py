import tempfile
import unittest
from pathlib import Path

from promise_ledger.db.connection import connect
from promise_ledger.generation.run_all import generate_database


TABLES = ('customers', 'invoices', 'payments', 'promises', 'recovery_actions', 'merchant_policies')


def logical_contents(path):
    database = connect(path)
    contents = {}
    for table in TABLES:
        columns = [row['name'] for row in database.execute(f'PRAGMA table_info({table})')]
        order_by = columns[0]
        contents[table] = [tuple(row) for row in database.execute(f'SELECT * FROM {table} ORDER BY {order_by}')]
    database.close()
    return contents


class ReproducibilityTests(unittest.TestCase):
    def test_seed_42_generates_identical_logical_database_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / 'first.db'
            second = Path(directory) / 'second.db'
            generate_database(first)
            generate_database(second)
            self.assertEqual(logical_contents(first), logical_contents(second))
