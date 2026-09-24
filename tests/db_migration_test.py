
import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3

from spriditis.storage.database import (
    CURRENT_SCHEMA_VERSION,
    Database,
    sqlite_backup,
)


def main():
    with TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        old_db = tmp / "spriditis_v31.db"
        new_db = tmp / "spriditis.db"

        conn = sqlite3.connect(old_db)
        conn.executescript(
            """
            CREATE TABLE projects (
                project_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                research_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                config_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE domains (
                project_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                status TEXT NOT NULL,
                discovered_via TEXT,
                discovered_from_url TEXT,
                relevance_score REAL DEFAULT 0,
                robots_status TEXT DEFAULT 'unknown',
                sitemap_status TEXT DEFAULT 'unknown',
                pages_seen INTEGER DEFAULT 0,
                entities_found INTEGER DEFAULT 0,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                last_crawled TEXT,
                reason TEXT,
                PRIMARY KEY(project_id, domain)
            );

            INSERT INTO projects VALUES (
                'demo', 'Demo', 'product_market', 'product',
                '{}', '2026-01-01T00:00:00+00:00'
            );

            INSERT INTO domains(
                project_id, domain, status, relevance_score,
                first_seen, last_seen
            )
            VALUES (
                'demo', 'example.com', 'active', 1.0,
                '2026-01-01T00:00:00+00:00',
                '2026-01-01T00:00:00+00:00'
            );
            """
        )
        conn.commit()
        conn.close()

        sqlite_backup(old_db, new_db)

        conn = sqlite3.connect(new_db)
        conn.execute(
            """
            UPDATE domains
            SET status='blocked', reason='blocked_path'
            WHERE project_id='demo' AND domain='example.com'
            """
        )
        conn.commit()
        conn.close()

        db = Database(new_db)
        try:
            columns = db._table_columns("domains")
            assert "sitemap_urls_found" in columns
            assert db.schema_version() == CURRENT_SCHEMA_VERSION
            assert db.schema_version() == 6

            feed_table = db.conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='feeds'"
            ).fetchone()
            assert feed_table == ("feeds",)

            page_visit_table = db.conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='page_visits'"
            ).fetchone()
            assert page_visit_table == ("page_visits",)

            run_columns = db._table_columns("runs")
            assert "feed_entries_new" in run_columns
            assert "feed_not_modified" in run_columns

            row = db.conn.execute(
                """
                SELECT domain, status, reason
                FROM domains
                WHERE project_id='demo'
                """
            ).fetchone()
            assert row == ("example.com", "candidate", "")
        finally:
            db.close()

    print("DB MIGRATION TEST OK")


if __name__ == "__main__":
    main()
