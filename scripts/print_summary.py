from promise_ledger.stats.summary import build_summary

if __name__ == '__main__':
    for key, value in build_summary().items():
        print(f'{key}: {value}')

