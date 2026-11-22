import argparse
import json
from pathlib import Path


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', action='version', version='ledger 1.0')
    parser.add_argument('--store', type=Path, required=True)
    parser.add_argument('command', choices=['add', 'list'])
    parser.add_argument('label', nargs='?')
    args = parser.parse_args()
    rows = json.loads(args.store.read_text()) if args.store.exists() else []
    if args.command == 'add':
        label = (args.label or '').strip()
        if not label:
            parser.error('label must not be blank')
        rows.append({'id': len(rows) + 1, 'label': label})
        args.store.parent.mkdir(parents=True, exist_ok=True)
        args.store.write_text(json.dumps(rows) + '\n')
    print(json.dumps(rows))


if __name__ == '__main__':
    run()
