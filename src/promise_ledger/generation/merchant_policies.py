def generate_merchant_policies(connection):
    row = (1, 'Promise Ledger Demo Merchant', 4, 3, 15000.0, 90, .70, '2026-01-01')
    connection.execute('INSERT INTO merchant_policies VALUES (?, ?, ?, ?, ?, ?, ?, ?)', row)
    return [row]

