import os
import glob
from pathlib import Path
import asyncpg

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


async def run_migrations(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        # Create tracking table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                name       TEXT        PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # Get already-applied migrations
        rows = await conn.fetch("SELECT name FROM _migrations")
        applied = {row["name"] for row in rows}

        # Run pending migrations in order
        migration_files = sorted(glob.glob(str(MIGRATIONS_DIR / "*.sql")))

        for filepath in migration_files:
            name = os.path.basename(filepath)
            if name in applied:
                print(f"⏭️  Skipped (already applied): {name}")
                continue

            sql = Path(filepath).read_text()

            # Run inside a savepoint so a failure doesn't kill the outer txn
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO _migrations (name) VALUES ($1)", name
                )

            print(f"✅ Applied migration: {name}")