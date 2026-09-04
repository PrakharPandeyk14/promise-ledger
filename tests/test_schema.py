import sqlite3
import unittest
from promise_ledger.db.schema import SCHEMA_SQL


class SchemaTests(unittest.TestCase):
    def test_exactly_six_main_tables_and_indexes(self):
        db = sqlite3.connect(':memory:')
        db.executescript(SCHEMA_SQL)
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(tables, {'customers','invoices','payments','promises','recovery_actions','merchant_policies'})
        with self.assertRaises(sqlite3.IntegrityError):
            db.execute("INSERT INTO customers VALUES (1,'C','Name','INVALID','2026-01-01',0)")
        db.close()
