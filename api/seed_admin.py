"""Helper script to seed the default admin account."""

from __future__ import annotations

import asyncio
import sys

from api.bootstrap import _seed_user


async def main() -> None:
    try:
        await _seed_user({
            "name": "Demo Admin",
            "email": "admin@example.com",
            "password": "adminpass",
            "role": "admin",
            "metadata": {"seeded": True},
        })
        print("SUCCESS: Default admin seeded successfully.")
    except Exception as e:
        print(f"ERROR: Seeding failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
