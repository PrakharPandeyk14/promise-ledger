"""Deterministic promise outcome rules shared by generation and validation."""

EPSILON = 0.005


def evaluate_sequential_promises(promises, payments, simulation_date):
    """Return expected outcomes and reused eligible-payment attempts by promise id.

    Payments count only after creation and through the promised date. Within an
    invoice sequence, a timely payment is assigned to the first settled promise
    for which it is eligible; it cannot fulfil a later promise as well.
    """
    simulation_date = simulation_date.isoformat()
    payments_by_invoice, promises_by_invoice = {}, {}
    for payment in payments:
        payments_by_invoice.setdefault(payment['invoice_id'], []).append(payment)
    for promise in promises:
        promises_by_invoice.setdefault(promise['invoice_id'], []).append(promise)
    for invoice_payments in payments_by_invoice.values():
        invoice_payments.sort(key=lambda payment: (payment['payment_date'], payment['payment_id']))

    outcomes, reuse_attempts = {}, {}
    for invoice_id, invoice_promises in promises_by_invoice.items():
        invoice_promises.sort(key=lambda promise: (promise['promise_created_date'], promise['promise_id']))
        allocated = set()
        for promise in invoice_promises:
            raw_eligible = [
                payment for payment in payments_by_invoice.get(invoice_id, [])
                if promise['promise_created_date'] < payment['payment_date'] <= promise['promised_payment_date']
            ]
            reuse_attempts[promise['promise_id']] = sum(payment['payment_id'] in allocated for payment in raw_eligible)
            eligible = [payment for payment in raw_eligible if payment['payment_id'] not in allocated]
            if promise['promised_payment_date'] > simulation_date:
                outcomes[promise['promise_id']] = 'PENDING'
                continue
            outcomes[promise['promise_id']] = 'KEPT' if sum(payment['amount'] for payment in eligible) + EPSILON >= promise['promised_amount'] else 'BROKEN'
            allocated.update(payment['payment_id'] for payment in eligible)
    return outcomes, reuse_attempts
