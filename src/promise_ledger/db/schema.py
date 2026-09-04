SCHEMA_SQL = """
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    external_id TEXT NOT NULL UNIQUE,
    customer_name TEXT NOT NULL,
    persona TEXT NOT NULL CHECK (persona IN ('RELIABLE_PAYER','SLOW_RELIABLE','UNPREDICTABLE','CHRONIC_BROKEN_PROMISER','HIGH_VALUE_STRATEGIC')),
    created_date TEXT NOT NULL,
    credit_limit REAL NOT NULL CHECK (credit_limit >= 0)
);

CREATE TABLE invoices (
    invoice_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    invoice_number TEXT NOT NULL UNIQUE,
    invoice_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount >= 0),
    status TEXT NOT NULL CHECK (status IN ('OPEN','PARTIALLY_PAID','PAID','OVERDUE','WRITTEN_OFF')),
    written_off_date TEXT,
    CHECK (invoice_date <= due_date),
    CHECK (written_off_date IS NULL OR written_off_date >= invoice_date)
);

CREATE TABLE payments (
    payment_id INTEGER PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(invoice_id),
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    payment_date TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount > 0),
    payment_method TEXT NOT NULL CHECK (payment_method IN ('BANK_TRANSFER','CARD','UPI','CHEQUE'))
);

CREATE TABLE promises (
    promise_id INTEGER PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(invoice_id),
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    promise_created_date TEXT NOT NULL,
    promised_payment_date TEXT NOT NULL,
    promised_amount REAL NOT NULL CHECK (promised_amount > 0),
    outcome TEXT NOT NULL CHECK (outcome IN ('KEPT','BROKEN','PENDING')),
    CHECK (promise_created_date <= promised_payment_date)
);

CREATE TABLE recovery_actions (
    action_id INTEGER PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(invoice_id),
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    promise_id INTEGER REFERENCES promises(promise_id),
    action_date TEXT NOT NULL,
    action_type TEXT NOT NULL CHECK (action_type IN ('SOFT_REMINDER','FIRM_REMINDER','PAYMENT_PLAN','ESCALATE','HUMAN_REVIEW','STOP')),
    channel TEXT NOT NULL CHECK (channel IN ('EMAIL','SMS','PHONE','SYSTEM')),
    notes TEXT NOT NULL
);

CREATE TABLE merchant_policies (
    policy_id INTEGER PRIMARY KEY,
    merchant_name TEXT NOT NULL UNIQUE,
    maximum_automated_contacts INTEGER NOT NULL CHECK (maximum_automated_contacts >= 0),
    minimum_contact_cooldown_days INTEGER NOT NULL CHECK (minimum_contact_cooldown_days >= 0),
    maximum_invoice_value_autonomous REAL NOT NULL CHECK (maximum_invoice_value_autonomous >= 0),
    maximum_payment_plan_duration_days INTEGER NOT NULL CHECK (maximum_payment_plan_duration_days >= 0),
    human_review_threshold REAL NOT NULL CHECK (human_review_threshold >= 0 AND human_review_threshold <= 1),
    effective_date TEXT NOT NULL
);

CREATE INDEX idx_invoices_customer_due ON invoices(customer_id, due_date);
CREATE INDEX idx_invoices_status_due ON invoices(status, due_date);
CREATE INDEX idx_payments_invoice_date ON payments(invoice_id, payment_date);
CREATE INDEX idx_promises_invoice_date ON promises(invoice_id, promised_payment_date);
CREATE INDEX idx_recovery_actions_invoice_date ON recovery_actions(invoice_id, action_date);
"""

