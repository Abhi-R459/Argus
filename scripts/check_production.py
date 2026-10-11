"""Validate release configuration without printing secret values or touching data."""

import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from pydantic import ValidationError
from api.config import Settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    if args.env_file:
        if not args.env_file.is_file():
            print('Configuration file is missing.', file=sys.stderr)
            return 1
        load_dotenv(args.env_file, override=True)
    try:
        settings = Settings(_env_file=None)
        if settings.APP_ENV != 'production':
            print('APP_ENV must be production.', file=sys.stderr)
            return 1
        if os.environ.get('VITE_ENABLE_DIAGNOSTICS', 'false') == 'true':
            print('Frontend diagnostics must be disabled.', file=sys.stderr)
            return 1
    except ValidationError as exc:
        for error in exc.errors(include_input=False, include_context=False, include_url=False):
            print('Configuration rejected:', error['msg'], file=sys.stderr)
        return 1
    print('Production configuration and signing-key pair are valid. No data was changed.')
    print('Verify live sign-in, readiness, backups, and workflows before announcing launch.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
