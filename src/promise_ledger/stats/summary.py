from pathlib import Path
from ..config import DATABASE_PATH, SIMULATION_DATE
from ..db.connection import connect


def build_summary(path: Path = DATABASE_PATH, simulation_date=SIMULATION_DATE):
    connection = connect(path)
    scalar = lambda query, params=(): connection.execute(query, params).fetchone()[0]
    promise_count = scalar('SELECT COUNT(*) FROM promises')
    summary = {
        'customer_count': scalar('SELECT COUNT(*) FROM customers'),
        'invoice_count': scalar('SELECT COUNT(*) FROM invoices'),
        'total_invoiced_amount': round(scalar('SELECT COALESCE(SUM(amount),0) FROM invoices'), 2),
        'total_paid': round(scalar('SELECT COALESCE(SUM(amount),0) FROM payments'), 2),
        'total_outstanding': round(scalar('SELECT COALESCE(SUM(i.amount)-SUM(COALESCE(p.paid,0)),0) FROM invoices i LEFT JOIN (SELECT invoice_id, SUM(amount) paid FROM payments GROUP BY invoice_id) p USING(invoice_id)'), 2),
        'overdue_amount': round(scalar("SELECT COALESCE(SUM(i.amount-COALESCE(p.paid,0)),0) FROM invoices i LEFT JOIN (SELECT invoice_id, SUM(amount) paid FROM payments GROUP BY invoice_id) p USING(invoice_id) WHERE i.due_date < ? AND i.amount > COALESCE(p.paid,0)", (simulation_date.isoformat(),)), 2),
        'promise_count': promise_count,
        'promises_kept_pct': round(100 * scalar("SELECT COUNT(*) FROM promises WHERE outcome='KEPT'") / promise_count, 2) if promise_count else 0,
        'promises_broken_pct': round(100 * scalar("SELECT COUNT(*) FROM promises WHERE outcome='BROKEN'") / promise_count, 2) if promise_count else 0,
        'promises_pending_pct': round(100 * scalar("SELECT COUNT(*) FROM promises WHERE outcome='PENDING'") / promise_count, 2) if promise_count else 0,
        'partial_payment_count': scalar("SELECT COUNT(*) FROM invoices i WHERE EXISTS (SELECT 1 FROM payments p WHERE p.invoice_id=i.invoice_id) AND (SELECT SUM(amount) FROM payments p WHERE p.invoice_id=i.invoice_id) < i.amount - .005"),
        'recovery_action_count': scalar('SELECT COUNT(*) FROM recovery_actions'),
        'customers_by_persona': {row['persona']: row['count'] for row in connection.execute('SELECT persona, COUNT(*) count FROM customers GROUP BY persona ORDER BY persona')},
    }
    connection.close()
    return summary

