from promise_ledger.generation.run_all import generate_database

if __name__ == '__main__':
    for table, count in generate_database().items():
        print(f'{table}: {count}')

