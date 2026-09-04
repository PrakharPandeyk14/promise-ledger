import tempfile
import unittest
from pathlib import Path
from promise_ledger.generation.run_all import generate_database
from promise_ledger.validation.checks import validate_database


class ValidationTests(unittest.TestCase):
    def test_generated_database_passes_all_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.db'
            generate_database(path)
            results = validate_database(path)
            self.assertTrue(all(result['passed'] for result in results))
            names = {result['name'] for result in results}
            self.assertTrue({'promise_amount_within_outstanding_at_creation', 'pre_creation_payments_excluded_from_promise_fulfillment', 'no_payment_reused_across_sequential_promises', 'kept_promises_have_strict_eligible_payments', 'broken_promises_lack_strict_eligible_payments', 'no_recovery_action_after_simulation_date', 'promised_date_strictly_after_creation', 'customer_invoice_due_chronology', 'linked_recovery_action_promise_chronology'}.issubset(names))

    def test_validation_detects_recovery_action_after_simulation_date(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.db'
            generate_database(path)
            from promise_ledger.db.connection import connect
            db = connect(path)
            db.execute("UPDATE recovery_actions SET action_date='2026-09-01' WHERE action_id=1")
            db.commit()
            db.close()
            result_by_name = {result['name']: result for result in validate_database(path)}
            self.assertFalse(result_by_name['no_recovery_action_after_simulation_date']['passed'])

    def test_validation_detects_customer_invoice_chronology_violation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.db'
            generate_database(path)
            from promise_ledger.db.connection import connect
            db = connect(path)
            db.execute("UPDATE invoices SET invoice_date='2020-01-01' WHERE invoice_id=1")
            db.commit()
            db.close()
            result_by_name = {result['name']: result for result in validate_database(path)}
            self.assertFalse(result_by_name['customer_invoice_due_chronology']['passed'])

    def test_validation_detects_linked_action_before_promise_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.db'
            generate_database(path)
            from promise_ledger.db.connection import connect
            db = connect(path)
            db.execute('''UPDATE recovery_actions SET action_date='2020-01-01'
                WHERE action_id=(SELECT MIN(action_id) FROM recovery_actions WHERE promise_id IS NOT NULL)''')
            db.commit()
            db.close()
            result_by_name = {result['name']: result for result in validate_database(path)}
            self.assertFalse(result_by_name['linked_recovery_action_promise_chronology']['passed'])
