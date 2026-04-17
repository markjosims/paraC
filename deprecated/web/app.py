from __future__ import annotations

import argparse
import os

from deprecated.web import create_app

DEFAULT_CONFIG_DIR = os.environ.get('CONFIG_DIR', 'config/')

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config_dir",
        help="Path to the config directory for the web app.",
        default=DEFAULT_CONFIG_DIR,
    )
    parser.add_argument("--debug", action="store_true", help="Run the Flask app in debug mode.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    app = create_app(args.config_dir)
    app.run(debug=args.debug)


if __name__ == "__main__":
    main()
