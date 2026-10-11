"""Retired Clerk demo setup; never create stale credentials or seed launch data."""
import sys


def main() -> int:
    print("The Clerk demo setup is retired. See docs/LOCAL_DEMO_SETUP.md for isolated Supabase-era development checks.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
