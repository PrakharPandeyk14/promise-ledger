import tempfile
import unittest
from pathlib import Path

from promise_ledger.config import SIMULATION_DATE
from promise_ledger.db.connection import connect, recreate_database
from promise_ledger.promise_ground_truth import evaluate_sequential_promises
from promise_ledger.validation.checks import validate_database


def promise(promise_id, created, promised, amount=100, outcome='BROKEN'):
    return {
        'promise_id': promise_id, 'invoice_id': 1, 'customer_id': 1,
        'promise_created_date': created, 'promised_payment_date': promised,
        'promised_amount': amount, 'outcome': outcome,
    }


def payment(payment_id, payment_date, amount=100):
    return {
        'payment_id': payment_id, 'invoice_id': 1, 'customer_id': 1,
        'payment_date': payment_date, 'amount': amount,
    }


class PromiseGroundTruthTests(unittest.TestCase):
    def test_payment_on_creation_date_is_not_eligible(self):
        outcomes, _ = evaluate_sequential_promises([promise(1, '2026-08-01', '2026-08-10')], [payment(1, '2026-08-01')], SIMULATION_DATE)
        self.assertEqual(outcomes[1], 'BROKEN')

    def test_payment_on_promised_date_is_eligible(self):
        outcomes, _ = evaluate_sequential_promises([promise(1, '2026-08-01', '2026-08-10')], [payment(1, '2026-08-10')], SIMULATION_DATE)
        self.assertEqual(outcomes[1], 'KEPT')

    def test_payment_after_promised_date_is_not_eligible_and_cannot_repair_broken_promise(self):
        outcomes, _ = evaluate_sequential_promises([promise(1, '2026-08-01', '2026-08-10')], [payment(1, '2026-08-11')], SIMULATION_DATE)
        self.assertEqual(outcomes[1], 'BROKEN')

    def test_future_promised_date_remains_pending(self):
        outcomes, _ = evaluate_sequential_promises([promise(1, '2026-08-01', '2026-09-01')], [payment(1, '2026-08-02')], SIMULATION_DATE)
        self.assertEqual(outcomes[1], 'PENDING')

    def test_payment_cannot_fulfil_two_sequential_promises(self):
        promises = [
            promise(1, '2026-08-01', '2026-08-10', outcome='KEPT'),
            promise(2, '2026-08-02', '2026-08-11', outcome='BROKEN'),
        ]
        outcomes, reuse_attempts = evaluate_sequential_promises(promises, [payment(1, '2026-08-05')], SIMULATION_DATE)
        self.assertEqual(outcomes, {1: 'KEPT', 2: 'BROKEN'})
        self.assertEqual(reuse_attempts[2], 1)


class PromiseConstraintValidationTests(unittest.TestCase):
    def _database_with_promise(self, promise_amount, payments=()):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'ledger.db'
        db = recreate_database(path)
        db.execute("INSERT INTO customers VALUES (1, 'C1', 'Customer', 'RELIABLE_PAYER', '2026-01-01', 1000)")
        db.execute("INSERT INTO invoices VALUES (1, 1, 'INV-1', '2026-08-01', '2026-08-15', 100, 'OPEN', NULL)")
        for row in payments:
            db.execute('INSERT INTO payments VALUES (?, 1, 1, ?, ?, \'UPI\')', row)
        db.execute('INSERT INTO promises VALUES (1, 1, 1, \'2026-08-10\', \'2026-08-20\', ?, \'BROKEN\')', (promise_amount,))
        db.commit()
        db.close()
        return path

    def test_promise_amount_may_equal_balance_at_creation(self):
        results = {row['name']: row for row in validate_database(self._database_with_promise(100))}
        self.assertTrue(results['promise_amount_within_outstanding_at_creation']['passed'])
        self.assertTrue(results['promise_created_only_with_positive_balance']['passed'])

    def test_promise_amount_cannot_exceed_balance_at_creation(self):
        results = {row['name']: row for row in validate_database(self._database_with_promise(100.01))}
        self.assertFalse(results['promise_amount_within_outstanding_at_creation']['passed'])

    def test_promise_requires_positive_balance_at_creation(self):
        results = {row['name']: row for row in validate_database(self._database_with_promise(1, [(1, '2026-08-09', 100)]))}
        self.assertFalse(results['promise_created_only_with_positive_balance']['passed'])
