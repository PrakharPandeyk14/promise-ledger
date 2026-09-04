import random
import unittest
from datetime import date

from promise_ledger.generation.personas import PERSONAS, Persona
from promise_ledger.generation.promises import _payment_date_for_persona


class PersonaTests(unittest.TestCase):
    def test_five_personas_and_independent_high_value_reliability_are_preserved(self):
        self.assertEqual(set(PERSONAS), {'RELIABLE_PAYER', 'SLOW_RELIABLE', 'UNPREDICTABLE', 'CHRONIC_BROKEN_PROMISER', 'HIGH_VALUE_STRATEGIC'})
        strategic = PERSONAS['HIGH_VALUE_STRATEGIC']
        self.assertGreater(strategic.amount_range[0], PERSONAS['RELIABLE_PAYER'].amount_range[1])
        self.assertGreater(strategic.promise_keep_tendency, PERSONAS['CHRONIC_BROKEN_PROMISER'].promise_keep_tendency)
        self.assertLess(strategic.promise_keep_tendency, PERSONAS['RELIABLE_PAYER'].promise_keep_tendency)

    def test_on_time_probability_and_delay_range_drive_payment_timing(self):
        invoice_date = date(2026, 1, 1)
        due_date = date(2026, 1, 31)
        created = date(2026, 1, 10)
        simulation_date = date(2026, 8, 31)
        always_on_time = Persona(1, .9, .2, (20, 20), .8, (1, 2))
        always_delayed = Persona(0, .9, .2, (20, 20), .8, (1, 2))
        on_time_date = _payment_date_for_persona(always_on_time, random.Random(42), invoice_date, due_date, created, simulation_date)
        delayed_date = _payment_date_for_persona(always_delayed, random.Random(42), invoice_date, due_date, created, simulation_date)
        self.assertLessEqual(on_time_date, due_date)
        self.assertEqual(delayed_date, date(2026, 2, 20))
