import argparse
import json
from pathlib import Path
from .storage import YearPlanStorage

DEFAULT_DB = Path.home() / '.yearplan.json'


def main(argv=None):
    parser = argparse.ArgumentParser(prog='yearplan')
    sub = parser.add_subparsers(dest='cmd')

    add = sub.add_parser('add')
    add.add_argument('text')

    listp = sub.add_parser('list')

    args = parser.parse_args(argv)
    storage = YearPlanStorage(DEFAULT_DB)
    if args.cmd == 'add':
        storage.add_goal(args.text)
        print('Added')
    elif args.cmd == 'list':
        for idx, g in enumerate(storage.list_goals(), 1):
            print(f"{idx}. {g['text']}")
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
