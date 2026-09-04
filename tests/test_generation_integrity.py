import tempfile
import unittest
from pathlib import Path
from promise_ledger.generation.run_all import generate_database
from promise_ledger.db.connection import connect


class GenerationIntegrityTests(unittest.TestCase):
    def test_expected_volume_and_payment_ceiling(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.db'
            counts = generate_database(path)
            self.assertEqual(counts['customers'], 200)
            self.assertEqual(counts['invoices'], 1000)
            self.assertGreaterEqual(counts['payments'], 2000)
            self.assertLessEqual(counts['payments'], 3000)
            self.assertGreaterEqual(counts['promises'], 1000)
            db = connect(path)
            violations = db.execute('''SELECT COUNT(*) FROM (SELECT i.invoice_id FROM invoices i LEFT JOIN payments p USING(invoice_id) GROUP BY i.invoice_id HAVING SUM(COALESCE(p.amount,0)) > i.amount + .005)''').fetchone()[0]
            self.assertEqual(violations, 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM promises WHERE promised_payment_date <= promise_created_date').fetchone()[0], 0)
            self.assertEqual(db.execute('''SELECT COUNT(*) FROM invoices i JOIN customers c USING(customer_id)
                WHERE c.created_date > i.invoice_date OR i.invoice_date > i.due_date''').fetchone()[0], 0)
            self.assertEqual(db.execute('''SELECT COUNT(*) FROM promises p JOIN invoices i USING(invoice_id)
                WHERE p.promised_amount > i.amount - COALESCE((SELECT SUM(amount) FROM payments x WHERE x.invoice_id=p.invoice_id AND x.payment_date < p.promise_created_date), 0) + .005''').fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM recovery_actions WHERE action_date > '2026-08-31'").fetchone()[0], 0)
            self.assertEqual(db.execute('''SELECT COUNT(*) FROM recovery_actions a JOIN promises p ON p.promise_id=a.promise_id
                WHERE a.action_date < p.promise_created_date OR a.action_date > '2026-08-31' ''').fetchone()[0], 0)
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM promises p WHERE p.outcome='KEPT' AND COALESCE((SELECT SUM(amount) FROM payments x WHERE x.invoice_id=p.invoice_id AND x.payment_date > p.promise_created_date AND x.payment_date <= p.promised_payment_date),0) + .005 < p.promised_amount""").fetchone()[0], 0)
            self.assertEqual(db.execute("""SELECT COUNT(*) FROM promises p WHERE p.outcome='BROKEN' AND COALESCE((SELECT SUM(amount) FROM payments x WHERE x.invoice_id=p.invoice_id AND x.payment_date > p.promise_created_date AND x.payment_date <= p.promised_payment_date),0) + .005 >= p.promised_amount""").fetchone()[0], 0)
            db.close()
