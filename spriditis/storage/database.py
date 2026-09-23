from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from spriditis.core.entities import MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult


CURRENT_SCHEMA_VERSION = 2


SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    research_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    config_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    visited_pages INTEGER DEFAULT 0,
    failed_pages INTEGER DEFAULT 0,
    skipped_by_robots INTEGER DEFAULT 0,
    entities_found INTEGER DEFAULT 0,
    domains_found INTEGER DEFAULT 0,
    FOREIGN KEY(project_id) REFERENCES projects(project_id)
);

CREATE TABLE IF NOT EXISTS entities (
    entity_key TEXT NOT NULL,
    project_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_domain TEXT,
    title TEXT NOT NULL,
    seller TEXT,
    last_price REAL,
    currency TEXT,
    category TEXT,
    is_relevant INTEGER NOT NULL DEFAULT 1,
    confidence REAL,
    relevance_score REAL,
    image_url TEXT,
    description TEXT,
    tags_json TEXT,
    attributes_json TEXT,
    opportunity_notes TEXT,
    extraction_method TEXT,
    evidence TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    PRIMARY KEY(project_id, entity_key)
);

CREATE INDEX IF NOT EXISTS idx_entities_project_url
ON entities(project_id, source_url);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    run_id INTEGER NOT NULL,
    entity_key TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    price REAL,
    currency TEXT,
    snapshot_json TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE INDEX IF NOT EXISTS idx_observations_entity
ON observations(project_id, entity_key, observed_at);

CREATE TABLE IF NOT EXISTS domains (
    project_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    status TEXT NOT NULL,
    discovered_via TEXT,
    discovered_from_url TEXT,
    relevance_score REAL DEFAULT 0,
    robots_status TEXT DEFAULT 'unknown',
    sitemap_status TEXT DEFAULT 'unknown',
    sitemap_urls_found INTEGER NOT NULL DEFAULT 0,
    pages_seen INTEGER DEFAULT 0,
    entities_found INTEGER DEFAULT 0,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    last_crawled TEXT,
    reason TEXT,
    PRIMARY KEY(project_id, domain),
    FOREIGN KEY(project_id) REFERENCES projects(project_id)
);

CREATE INDEX IF NOT EXISTS idx_domains_project_status
ON domains(project_id, status, relevance_score DESC);

CREATE TABLE IF NOT EXISTS domain_discoveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    run_id INTEGER NOT NULL,
    source_domain TEXT,
    target_domain TEXT NOT NULL,
    source_url TEXT,
    target_url TEXT NOT NULL,
    anchor_text TEXT,
    relevance_score REAL DEFAULT 0,
    action TEXT,
    reason TEXT,
    discovered_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE INDEX IF NOT EXISTS idx_domain_discoveries_target
ON domain_discoveries(project_id, target_domain, discovered_at);

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def sqlite_backup(
    source: Path,
    target: Path,
    *,
    overwrite: bool = False,
) -> Path:
    """
    Copy a SQLite database using SQLite's backup API.

    This is safer than a plain file copy when the source database uses WAL.
    The target is replaced atomically only after the backup succeeds.
    """
    source = Path(source)
    target = Path(target)

    if not source.exists():
        raise FileNotFoundError(f"Avota DB neeksistē: {source}")

    if source.resolve() == target.resolve():
        raise ValueError("Avota un mērķa DB nevar būt viens un tas pats fails.")

    if target.exists() and not overwrite:
        raise FileExistsError(
            f"Mērķa DB jau eksistē: {target}. "
            "Izmanto --force tikai tad, ja tiešām vēlies to aizstāt."
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    temp_target = target.with_suffix(target.suffix + ".migration-tmp")

    if temp_target.exists():
        temp_target.unlink()

    src_conn = sqlite3.connect(f"file:{source.resolve()}?mode=ro", uri=True)
    dst_conn = sqlite3.connect(temp_target)

    try:
        src_conn.backup(dst_conn)
        dst_conn.commit()
    finally:
        dst_conn.close()
        src_conn.close()

    if target.exists():
        target.unlink()

    os.replace(temp_target, target)
    return target


class Database:
    def __init__(
        self,
        path: Path,
        *,
        legacy_path: Path | None = None,
    ):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        self.path = path
        self.migrated_from: Path | None = None

        if (
            not path.exists()
            and legacy_path is not None
            and Path(legacy_path).exists()
            and Path(legacy_path).resolve() != path.resolve()
        ):
            sqlite_backup(Path(legacy_path), path)
            self.migrated_from = Path(legacy_path)

        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self._apply_migrations()
        self.conn.commit()

    def close(self):
        self.conn.close()

    def _table_columns(self, table: str) -> set[str]:
        rows = self.conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {row[1] for row in rows}

    def _ensure_column(
        self,
        table: str,
        column: str,
        declaration: str,
    ):
        if column not in self._table_columns(table):
            self.conn.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {declaration}"
            )

    def _apply_migrations(self):
        # Alpha1 Domain Registry DBs do not have this field.
        self._ensure_column(
            "domains",
            "sitemap_urls_found",
            "INTEGER NOT NULL DEFAULT 0",
        )

        self.conn.execute(
            """
            INSERT INTO schema_meta(key, value)
            VALUES ('schema_version', ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (str(CURRENT_SCHEMA_VERSION),),
        )
        self.conn.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION}")

    def schema_version(self) -> int:
        row = self.conn.execute("PRAGMA user_version").fetchone()
        return int(row[0]) if row else 0

    def save_project(self, project: ResearchProject):
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """
            INSERT INTO projects(
                project_id, name, research_type, entity_type, config_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                name=excluded.name,
                research_type=excluded.research_type,
                entity_type=excluded.entity_type,
                config_json=excluded.config_json,
                updated_at=excluded.updated_at
            """,
            (
                project.id,
                project.name,
                project.research_type,
                project.entity_type,
                project.to_json(),
                now,
            ),
        )
        self.conn.commit()

    def start_run(self, project: ResearchProject) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.execute(
            """
            INSERT INTO runs(project_id, started_at)
            VALUES (?, ?)
            """,
            (project.id, now),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def upsert_entity(
        self,
        project: ResearchProject,
        run_id: int,
        entity: MarketEntity,
    ):
        now = datetime.now(timezone.utc).isoformat()

        row = self.conn.execute(
            """
            SELECT entity_key, first_seen
            FROM entities
            WHERE project_id=? AND source_url=? AND title=?
            LIMIT 1
            """,
            (project.id, entity.source_url, entity.title),
        ).fetchone()

        key = row[0] if row else entity.stable_key
        first_seen = row[1] if row else now

        self.conn.execute(
            """
            INSERT INTO entities(
                entity_key, project_id, entity_type, source_url, source_domain,
                title, seller, last_price, currency, category, is_relevant,
                confidence, relevance_score, image_url, description, tags_json,
                attributes_json, opportunity_notes, extraction_method, evidence,
                first_seen, last_seen
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, entity_key) DO UPDATE SET
                entity_type=excluded.entity_type,
                source_url=excluded.source_url,
                source_domain=excluded.source_domain,
                title=excluded.title,
                seller=excluded.seller,
                last_price=excluded.last_price,
                currency=excluded.currency,
                category=excluded.category,
                is_relevant=excluded.is_relevant,
                confidence=excluded.confidence,
                relevance_score=excluded.relevance_score,
                image_url=excluded.image_url,
                description=excluded.description,
                tags_json=excluded.tags_json,
                attributes_json=excluded.attributes_json,
                opportunity_notes=excluded.opportunity_notes,
                extraction_method=excluded.extraction_method,
                evidence=excluded.evidence,
                last_seen=excluded.last_seen
            """,
            (
                key,
                project.id,
                entity.entity_type,
                entity.source_url,
                entity.source_domain,
                entity.title,
                entity.seller,
                entity.price,
                entity.currency,
                entity.category,
                int(entity.is_relevant),
                entity.confidence,
                entity.relevance_score,
                entity.image_url,
                entity.description,
                json.dumps(entity.tags, ensure_ascii=False),
                json.dumps(entity.attributes, ensure_ascii=False),
                entity.opportunity_notes,
                entity.extraction_method,
                entity.evidence,
                first_seen,
                now,
            ),
        )

        self.conn.execute(
            """
            INSERT INTO observations(
                project_id, run_id, entity_key, observed_at,
                price, currency, snapshot_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project.id,
                run_id,
                key,
                now,
                entity.price,
                entity.currency,
                entity.as_json(),
            ),
        )
        self.conn.commit()

    def save_domain_registry(
        self,
        project: ResearchProject,
        run_id: int,
        result: ResearchRunResult,
    ):
        for record in result.domains.values():
            existing = self.conn.execute(
                """
                SELECT first_seen, pages_seen, entities_found,
                       sitemap_urls_found
                FROM domains
                WHERE project_id=? AND domain=?
                """,
                (project.id, record.domain),
            ).fetchone()

            first_seen = existing[0] if existing else record.first_seen
            previous_pages = int(existing[1]) if existing else 0
            previous_entities = int(existing[2]) if existing else 0
            previous_sitemap_urls = int(existing[3]) if existing else 0

            self.conn.execute(
                """
                INSERT INTO domains(
                    project_id, domain, status, discovered_via,
                    discovered_from_url, relevance_score, robots_status,
                    sitemap_status, sitemap_urls_found,
                    pages_seen, entities_found,
                    first_seen, last_seen, last_crawled, reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, domain) DO UPDATE SET
                    status=excluded.status,
                    discovered_via=CASE
                        WHEN domains.discovered_via='seed'
                        THEN domains.discovered_via
                        ELSE excluded.discovered_via
                    END,
                    discovered_from_url=CASE
                        WHEN domains.discovered_from_url IS NULL
                          OR domains.discovered_from_url=''
                        THEN excluded.discovered_from_url
                        ELSE domains.discovered_from_url
                    END,
                    relevance_score=MAX(
                        domains.relevance_score,
                        excluded.relevance_score
                    ),
                    robots_status=CASE
                        WHEN excluded.robots_status='unknown'
                        THEN domains.robots_status
                        ELSE excluded.robots_status
                    END,
                    sitemap_status=CASE
                        WHEN excluded.sitemap_status='unknown'
                        THEN domains.sitemap_status
                        ELSE excluded.sitemap_status
                    END,
                    sitemap_urls_found=MAX(
                        domains.sitemap_urls_found,
                        excluded.sitemap_urls_found
                    ),
                    pages_seen=?,
                    entities_found=?,
                    last_seen=excluded.last_seen,
                    last_crawled=COALESCE(
                        excluded.last_crawled,
                        domains.last_crawled
                    ),
                    reason=excluded.reason
                """,
                (
                    project.id,
                    record.domain,
                    record.status,
                    record.discovered_via,
                    record.discovered_from_url,
                    record.relevance_score,
                    record.robots_status,
                    record.sitemap_status,
                    max(previous_sitemap_urls, record.sitemap_urls_found),
                    record.pages_seen,
                    record.entities_found,
                    first_seen,
                    record.last_seen,
                    record.last_crawled,
                    record.reason,
                    previous_pages + record.pages_seen,
                    previous_entities + record.entities_found,
                ),
            )

        for discovery in result.domain_discoveries:
            self.conn.execute(
                """
                INSERT INTO domain_discoveries(
                    project_id, run_id, source_domain, target_domain,
                    source_url, target_url, anchor_text, relevance_score,
                    action, reason, discovered_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project.id,
                    run_id,
                    discovery.source_domain,
                    discovery.target_domain,
                    discovery.source_url,
                    discovery.target_url,
                    discovery.anchor_text,
                    discovery.relevance_score,
                    discovery.action,
                    discovery.reason,
                    discovery.discovered_at,
                ),
            )

        self.conn.commit()

    def list_domains(
        self,
        project_id: str,
        *,
        status: str | None = None,
    ) -> list[dict]:
        sql = """
        SELECT domain, status, relevance_score, pages_seen,
               entities_found, robots_status, sitemap_status,
               sitemap_urls_found, discovered_via, reason,
               discovered_from_url, first_seen, last_seen, last_crawled
        FROM domains
        WHERE project_id=?
        """
        params: list[object] = [project_id]

        if status:
            sql += " AND status=?"
            params.append(status)

        sql += " ORDER BY relevance_score DESC, domain ASC"

        rows = self.conn.execute(sql, params).fetchall()

        keys = [
            "domain",
            "status",
            "relevance_score",
            "pages_seen",
            "entities_found",
            "robots_status",
            "sitemap_status",
            "sitemap_urls_found",
            "discovered_via",
            "reason",
            "discovered_from_url",
            "first_seen",
            "last_seen",
            "last_crawled",
        ]

        return [dict(zip(keys, row)) for row in rows]

    def domain_status_counts(self, project_id: str) -> dict[str, int]:
        rows = self.conn.execute(
            """
            SELECT status, COUNT(*)
            FROM domains
            WHERE project_id=?
            GROUP BY status
            """,
            (project_id,),
        ).fetchall()

        return {status: int(count) for status, count in rows}


    def list_domain_discoveries(
        self,
        project_id: str,
        *,
        action: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        sql = """
        SELECT id, run_id, source_domain, target_domain,
               source_url, target_url, anchor_text,
               relevance_score, action, reason, discovered_at
        FROM domain_discoveries
        WHERE project_id=?
        """
        params: list[object] = [project_id]

        if action:
            sql += " AND action=?"
            params.append(action)

        sql += " ORDER BY id DESC LIMIT ?"
        params.append(max(1, min(int(limit), 1000)))

        rows = self.conn.execute(sql, params).fetchall()
        keys = [
            "id",
            "run_id",
            "source_domain",
            "target_domain",
            "source_url",
            "target_url",
            "anchor_text",
            "relevance_score",
            "action",
            "reason",
            "discovered_at",
        ]
        return [dict(zip(keys, row)) for row in rows]

    def discovery_action_counts(
        self,
        project_id: str,
        *,
        run_id: int | None = None,
    ) -> dict[str, int]:
        sql = """
        SELECT action, COUNT(*)
        FROM domain_discoveries
        WHERE project_id=?
        """
        params: list[object] = [project_id]

        if run_id is not None:
            sql += " AND run_id=?"
            params.append(run_id)

        sql += " GROUP BY action"
        rows = self.conn.execute(sql, params).fetchall()
        return {action: int(count) for action, count in rows}

    def finish_run(
        self,
        run_id: int,
        result: ResearchRunResult,
    ):
        self.conn.execute(
            """
            UPDATE runs
            SET finished_at=?,
                visited_pages=?,
                failed_pages=?,
                skipped_by_robots=?,
                entities_found=?,
                domains_found=?
            WHERE id=?
            """,
            (
                result.finished_at,
                result.visited_pages,
                result.failed_pages,
                result.skipped_by_robots,
                len(result.entities),
                len(result.discovered_domains),
                run_id,
            ),
        )
        self.conn.commit()
