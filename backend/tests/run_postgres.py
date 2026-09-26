"""Run the test suite against a real, throwaway PostgreSQL server - the
configuration the Vercel deployment uses (PostgreSQL + evidence in the DB).

    pip install pgserver "psycopg[binary]"
    python tests/run_postgres.py [pytest args]

Without pgserver, point PRAMANA_TEST_PG_URL at any PostgreSQL you can create
databases on and run pytest directly.
"""
import os
import sys
import tempfile

import pgserver
import pytest

if __name__ == "__main__":
    data = tempfile.mkdtemp(prefix="pramana-pg-")
    server = pgserver.get_server(data, cleanup_mode="delete")
    os.environ["PRAMANA_TEST_PG_URL"] = server.get_uri()
    sys.exit(pytest.main(sys.argv[1:] or ["-p", "no:warnings"]))
