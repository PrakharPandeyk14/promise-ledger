from promise_ledger.validation.checks import validate_database

if __name__ == '__main__':
    results = validate_database()
    for result in results:
        print(f"{'PASS' if result['passed'] else 'FAIL'} {result['name']}: {result['detail']}")
    raise SystemExit(0 if all(result['passed'] for result in results) else 1)

