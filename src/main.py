import argparse
import logging
import sys

from application import Application

logger = logging.getLogger(__name__)

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate tweets against predetermined criteria",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "command",
        nargs="?",
        choices=["extract-tweets", "analyze-tweets"],
        help="Command to execute",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    app = Application()
    if args.command == "extract-tweets":
        result = app.extract_tweets()

        if not result.success:
            sys.exit(1)
    elif args.command == "analyze-tweets":
        result = app.analyze_tweets()

        if not result.success:
            sys.exit(1)

if __name__ == "__main__":
    main()