from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    on_time_probability: float
    eventual_payment_probability: float
    partial_payment_probability: float
    payment_delay_range: tuple[int, int]
    promise_keep_tendency: float
    amount_range: tuple[int, int]


PERSONAS = {
    'RELIABLE_PAYER': Persona(.85, .98, .25, (-3, 5), .92, (500, 4000)),
    'SLOW_RELIABLE': Persona(.20, .94, .35, (3, 25), .82, (500, 4500)),
    'UNPREDICTABLE': Persona(.45, .78, .62, (-2, 60), .55, (400, 5500)),
    'CHRONIC_BROKEN_PROMISER': Persona(.08, .55, .70, (15, 100), .18, (300, 5000)),
    'HIGH_VALUE_STRATEGIC': Persona(.55, .84, .40, (-3, 45), .60, (6000, 25000)),
}

