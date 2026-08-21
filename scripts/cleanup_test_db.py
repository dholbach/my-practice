#!/usr/bin/env python3
"""Clean up test database by terminating connections and dropping it."""

import os
import sys
import time

import psycopg

try:
    conn = psycopg.connect(
        dbname="postgres",
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
    )
    conn.autocommit = True
    cur = conn.cursor()

    # Try multiple times
    for attempt in range(3):
        # Terminate all connections to test_payments
        cur.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid != pg_backend_pid()",
            ("test_payments",),
        )
        time.sleep(0.5)

        # Try to drop the database
        try:
            cur.execute("DROP DATABASE IF EXISTS test_payments")
            print("✓ Test database cleaned")
            break
        except Exception as e:
            if attempt < 2:
                time.sleep(1)
            else:
                print(f"ℹ Cleanup skipped: {e}")

    conn.close()
    sys.exit(0)
except Exception as e:
    print(f"ℹ No cleanup needed: {e}")
    sys.exit(0)
