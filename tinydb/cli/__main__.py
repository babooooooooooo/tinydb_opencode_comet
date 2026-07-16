# tinydb/cli/__main__.py
"""Entry point for python3 -m tinydb.cli"""
import sys

from tinydb import Database
from tinydb.cli import REPL


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    path = argv[0] if argv else "tinydb.db"
    db = Database(path)
    try:
        REPL(db).run()
    finally:
        db.close()


if __name__ == "__main__":
    main()
