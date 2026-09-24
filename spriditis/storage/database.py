from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from spriditis.core.domains import DomainRecord
from spriditis.core.entities import MarketEntity
from spriditis.core.feeds import FeedState
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult


CURRENT_SCHEMA_VERSION = 6


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
    search_queries_issued INTEGER DEFAULT 0,
    search_results_seen INTEGER DEFAULT 0,
    search_results_unique INTEGER DEFAULT 0,
    search_results_duplicates INTEGER DEFAULT 0,
    search_domains_activated INTEGER DEFAULT 0,
    search_provider_errors INTEGER DEFAULT 0,
    feed_candidates_seen INTEGER DEFAULT 0,
    feeds_found INTEGER DEFAULT 0,
    feed_entries_seen INTEGER DEFAULT 0,
    feed_entries_new INTEGER DEFAULT 0,
    feed_not_modified INTEGER DEFAULT 0,
    feed_errors INTEGER DEFAULT 0,
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
    discovered_via TEXT NOT NULL DEFAULT 'external_link',
    provider TEXT DEFAULT '',
    query_text TEXT DEFAULT '',
    discovered_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE INDEX IF NOT EXISTS idx_domain_discoveries_target
ON domain_discoveries(project_id, target_domain, discovered_at);



CREATE TABLE IF NOT EXISTS page_visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    run_id INTEGER NOT NULL,
    url TEXT NOT NULL,
    final_url TEXT NOT NULL,
    domain TEXT NOT NULL,
    source_url TEXT DEFAULT '',
    source_type TEXT NOT NULL DEFAULT 'unknown',
    depth INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 0,
    outcome TEXT NOT NULL DEFAULT 'unknown',
    http_status INTEGER,
    content_type TEXT DEFAULT '',
    visited_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE INDEX IF NOT EXISTS idx_page_visits_project_run
ON page_visits(project_id, run_id, id);

CREATE INDEX IF NOT EXISTS idx_page_visits_project_domain
ON page_visits(project_id, domain, visited_at);

CREATE TABLE IF NOT EXISTS feeds (
    project_id TEXT NOT NULL,
    feed_url TEXT NOT NULL,
    domain TEXT NOT NULL,
    feed_type TEXT NOT NULL DEFAULT 'unknown',
    status TEXT NOT NULL DEFAULT 'unknown',
    etag TEXT DEFAULT '',
    last_modified TEXT DEFAULT '',
    last_entry_id TEXT DEFAULT '',
    last_published TEXT DEFAULT '',
    last_checked TEXT DEFAULT '',
    last_success TEXT DEFAULT '',
    entries_seen INTEGER NOT NULL DEFAULT 0,
    new_entries INTEGER NOT NULL DEFAULT 0,
    last_error TEXT DEFAULT '',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    PRIMARY KEY(project_id, feed_url),
    FOREIGN KEY(project_id) REFERENCES projects(project_id)
);

CREATE INDEX IF NOT EXISTS idx_feeds_project_domain
ON feeds(project_id, domain, status);

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

        self._ensure_column(
            "runs",
            "search_queries_issued",
            "INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            "runs",
            "search_results_seen",
            "INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            "runs",
            "search_results_unique",
            "INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            "runs",
            "search_results_duplicates",
            "INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            "runs",
            "search_domains_activated",
            "INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            "runs",
            "search_provider_errors",
            "INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            "runs",
            "feed_candidates_seen",
            "INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            "runs",
            "feeds_found",
            "INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            "runs",
            "feed_entries_seen",
            "INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            "runs",
            "feed_entries_new",
            "INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            "runs",
            "feed_not_modified",
            "INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            "runs",
            "feed_errors",
            "INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            "domain_discoveries",
            "discovered_via",
            "TEXT NOT NULL DEFAULT 'external_link'",
        )
        self._ensure_column(
            "domain_discoveries",
            "provider",
            "TEXT DEFAULT ''",
        )
        self._ensure_column(
            "domain_discoveries",
            "query_text",
            "TEXT DEFAULT ''",
        )

        # Alpha4 development builds briefly persisted URL-scoped safety
        # failures as sticky domain blocks. Heal those rows idempotently:
        # blocked_path/static-file failures apply to a URL, not its host.
        self.conn.execute(
            """
            UPDATE domains
            SET status='candidate',
                reason=''
            WHERE status='blocked'
              AND reason IN ('blocked_path', 'binary_or_static_file')
            """
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
                       sitemap_urls_found, status, reason
                FROM domains
                WHERE project_id=? AND domain=?
                """,
                (project.id, record.domain),
            ).fetchone()

            first_seen = existing[0] if existing else record.first_seen
            previous_pages = int(existing[1]) if existing else 0
            previous_entities = int(existing[2]) if existing else 0
            previous_sitemap_urls = int(existing[3]) if existing else 0

            persisted_status = record.status
            persisted_reason = record.reason
            if existing and len(existing) >= 6:
                old_status = existing[4]
                old_reason = existing[5] or ""
                if old_status == "blocked":
                    persisted_status = "blocked"
                    persisted_reason = old_reason or record.reason
                elif old_status == "rejected" and record.status != "active":
                    persisted_status = "rejected"
                    persisted_reason = old_reason or record.reason
                elif old_status == "active" and record.status == "candidate":
                    persisted_status = "active"
                    persisted_reason = old_reason or record.reason

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
                    persisted_status,
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
                    persisted_reason,
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
                    action, reason, discovered_via, provider, query_text,
                    discovered_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    discovery.discovered_via,
                    discovery.provider,
                    discovery.query_text,
                    discovery.discovered_at,
                ),
            )

        self.conn.commit()




    def save_page_visits(
        self,
        project: ResearchProject,
        run_id: int,
        result: ResearchRunResult,
    ):
        if not result.page_visits:
            return

        self.conn.executemany(
            """
            INSERT INTO page_visits(
                project_id, run_id, url, final_url, domain,
                source_url, source_type, depth, priority, outcome,
                http_status, content_type, visited_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    project.id,
                    run_id,
                    visit.url,
                    visit.final_url,
                    visit.domain,
                    visit.source_url,
                    visit.source_type,
                    visit.depth,
                    visit.priority,
                    visit.outcome,
                    visit.http_status,
                    visit.content_type,
                    visit.visited_at,
                )
                for visit in result.page_visits
            ],
        )
        self.conn.commit()

    def query_memory(
        self,
        project_id: str,
        *,
        limit: int = 20,
    ) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT
                provider,
                query_text,
                COUNT(*) AS result_events,
                COUNT(DISTINCT target_domain) AS unique_domains,
                SUM(CASE WHEN action='activated' THEN 1 ELSE 0 END) AS activated,
                SUM(CASE WHEN action='known' THEN 1 ELSE 0 END) AS known,
                SUM(CASE WHEN action='blocked' THEN 1 ELSE 0 END) AS blocked,
                SUM(CASE WHEN action='recorded' THEN 1 ELSE 0 END) AS recorded,
                COUNT(DISTINCT run_id) AS runs,
                MAX(discovered_at) AS last_used
            FROM domain_discoveries
            WHERE project_id=?
              AND query_text IS NOT NULL
              AND query_text<>''
            GROUP BY provider, query_text
            ORDER BY activated DESC, unique_domains DESC, result_events DESC,
                     query_text ASC
            LIMIT ?
            """,
            (project_id, max(1, min(int(limit), 1000))),
        ).fetchall()

        result = []
        for row in rows:
            total = int(row[2] or 0)
            activated = int(row[4] or 0)
            result.append(
                {
                    "provider": row[0] or "",
                    "query_text": row[1] or "",
                    "result_events": total,
                    "unique_domains": int(row[3] or 0),
                    "activated": activated,
                    "known": int(row[5] or 0),
                    "blocked": int(row[6] or 0),
                    "recorded": int(row[7] or 0),
                    "runs": int(row[8] or 0),
                    "last_used": row[9] or "",
                    "activation_rate": (
                        activated / total if total else 0.0
                    ),
                }
            )
        return result

    def source_profiles(
        self,
        project_id: str,
        *,
        limit: int = 50,
    ) -> list[dict]:
        rows = self.conn.execute(
            """
            WITH visit_stats AS (
                SELECT
                    domain,
                    COUNT(*) AS visits,
                    SUM(CASE WHEN outcome='html_ok' THEN 1 ELSE 0 END) AS html_ok,
                    SUM(CASE
                        WHEN outcome LIKE 'http_error:%'
                          OR outcome='unsafe_redirect'
                          OR outcome='http_status'
                        THEN 1 ELSE 0
                    END) AS failures,
                    MAX(visited_at) AS last_visit
                FROM page_visits
                WHERE project_id=?
                GROUP BY domain
            ),
            feed_stats AS (
                SELECT
                    domain,
                    COUNT(*) AS feed_count,
                    MAX(last_success) AS last_feed_success
                FROM feeds
                WHERE project_id=?
                GROUP BY domain
            ),
            discovery_stats AS (
                SELECT
                    target_domain AS domain,
                    COUNT(*) AS discovery_events,
                    SUM(CASE WHEN action='activated' THEN 1 ELSE 0 END) AS activated_events,
                    SUM(CASE WHEN action='blocked' THEN 1 ELSE 0 END) AS blocked_events,
                    MAX(discovered_at) AS last_discovered
                FROM domain_discoveries
                WHERE project_id=?
                GROUP BY target_domain
            )
            SELECT
                d.domain,
                d.status,
                d.relevance_score,
                d.pages_seen,
                d.entities_found,
                d.robots_status,
                d.sitemap_status,
                d.sitemap_urls_found,
                d.discovered_via,
                d.reason,
                d.first_seen,
                d.last_seen,
                d.last_crawled,
                COALESCE(v.visits, 0),
                COALESCE(v.html_ok, 0),
                COALESCE(v.failures, 0),
                COALESCE(v.last_visit, ''),
                COALESCE(f.feed_count, 0),
                COALESCE(f.last_feed_success, ''),
                COALESCE(x.discovery_events, 0),
                COALESCE(x.activated_events, 0),
                COALESCE(x.blocked_events, 0),
                COALESCE(x.last_discovered, '')
            FROM domains d
            LEFT JOIN visit_stats v ON v.domain=d.domain
            LEFT JOIN feed_stats f ON f.domain=d.domain
            LEFT JOIN discovery_stats x ON x.domain=d.domain
            WHERE d.project_id=?
            ORDER BY d.entities_found DESC, d.pages_seen DESC,
                     d.relevance_score DESC, d.domain ASC
            LIMIT ?
            """,
            (
                project_id,
                project_id,
                project_id,
                project_id,
                max(1, min(int(limit), 1000)),
            ),
        ).fetchall()

        profiles = []
        for row in rows:
            pages_seen = int(row[3] or 0)
            entities_found = int(row[4] or 0)
            visits = int(row[13] or 0)
            html_ok = int(row[14] or 0)
            profiles.append(
                {
                    "domain": row[0],
                    "status": row[1],
                    "relevance_score": float(row[2] or 0.0),
                    "pages_seen": pages_seen,
                    "entities_found": entities_found,
                    "entity_yield": (
                        entities_found / pages_seen
                        if pages_seen else 0.0
                    ),
                    "robots_status": row[5] or "unknown",
                    "sitemap_status": row[6] or "unknown",
                    "sitemap_urls_found": int(row[7] or 0),
                    "discovered_via": row[8] or "",
                    "reason": row[9] or "",
                    "first_seen": row[10] or "",
                    "last_seen": row[11] or "",
                    "last_crawled": row[12] or "",
                    "visit_count": visits,
                    "successful_visits": html_ok,
                    "failed_visits": int(row[15] or 0),
                    "success_rate": (
                        html_ok / visits if visits else 0.0
                    ),
                    "last_visit": row[16] or "",
                    "feed_count": int(row[17] or 0),
                    "last_feed_success": row[18] or "",
                    "discovery_events": int(row[19] or 0),
                    "activated_events": int(row[20] or 0),
                    "blocked_events": int(row[21] or 0),
                    "last_discovered": row[22] or "",
                }
            )
        return profiles

    def explain_domain(
        self,
        project_id: str,
        domain: str,
        *,
        event_limit: int = 10,
    ) -> dict | None:
        profile = next(
            (
                item
                for item in self.source_profiles(project_id, limit=1000)
                if item["domain"] == domain
            ),
            None,
        )
        if profile is None:
            return None

        discoveries = self.conn.execute(
            """
            SELECT run_id, source_domain, source_url, target_url,
                   relevance_score, action, reason, discovered_via,
                   provider, query_text, discovered_at
            FROM domain_discoveries
            WHERE project_id=? AND target_domain=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                project_id,
                domain,
                max(1, min(int(event_limit), 100)),
            ),
        ).fetchall()

        visits = self.conn.execute(
            """
            SELECT run_id, url, final_url, source_url, source_type,
                   depth, priority, outcome, http_status, content_type,
                   visited_at
            FROM page_visits
            WHERE project_id=? AND domain=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                project_id,
                domain,
                max(1, min(int(event_limit), 100)),
            ),
        ).fetchall()

        feeds = self.conn.execute(
            """
            SELECT feed_url, feed_type, status, last_checked,
                   last_success, entries_seen, new_entries, last_error
            FROM feeds
            WHERE project_id=? AND domain=?
            ORDER BY feed_url
            """,
            (project_id, domain),
        ).fetchall()

        profile["recent_discoveries"] = [
            {
                "run_id": row[0],
                "source_domain": row[1] or "",
                "source_url": row[2] or "",
                "target_url": row[3] or "",
                "relevance_score": float(row[4] or 0.0),
                "action": row[5] or "",
                "reason": row[6] or "",
                "discovered_via": row[7] or "",
                "provider": row[8] or "",
                "query_text": row[9] or "",
                "discovered_at": row[10] or "",
            }
            for row in discoveries
        ]
        profile["recent_visits"] = [
            {
                "run_id": row[0],
                "url": row[1],
                "final_url": row[2],
                "source_url": row[3] or "",
                "source_type": row[4] or "",
                "depth": int(row[5] or 0),
                "priority": int(row[6] or 0),
                "outcome": row[7] or "",
                "http_status": row[8],
                "content_type": row[9] or "",
                "visited_at": row[10] or "",
            }
            for row in visits
        ]
        profile["feeds"] = [
            {
                "feed_url": row[0],
                "feed_type": row[1],
                "status": row[2],
                "last_checked": row[3] or "",
                "last_success": row[4] or "",
                "entries_seen": int(row[5] or 0),
                "new_entries": int(row[6] or 0),
                "last_error": row[7] or "",
            }
            for row in feeds
        ]
        return profile

    def trace_run(
        self,
        project_id: str,
        run_id: int,
    ) -> dict | None:
        run = self.conn.execute(
            """
            SELECT id, project_id, started_at, finished_at,
                   visited_pages, failed_pages, skipped_by_robots,
                   entities_found, domains_found,
                   search_queries_issued, search_results_seen,
                   search_results_unique, search_results_duplicates,
                   search_domains_activated, search_provider_errors,
                   feed_candidates_seen, feeds_found, feed_entries_seen,
                   feed_entries_new, feed_not_modified, feed_errors
            FROM runs
            WHERE id=? AND project_id=?
            """,
            (run_id, project_id),
        ).fetchone()

        if run is None:
            return None

        page_rows = self.conn.execute(
            """
            SELECT url, final_url, domain, source_url, source_type,
                   depth, priority, outcome, http_status, content_type,
                   visited_at
            FROM page_visits
            WHERE project_id=? AND run_id=?
            ORDER BY id
            """,
            (project_id, run_id),
        ).fetchall()

        discovery_rows = self.conn.execute(
            """
            SELECT source_domain, target_domain, source_url, target_url,
                   relevance_score, action, reason, discovered_via,
                   provider, query_text, discovered_at
            FROM domain_discoveries
            WHERE project_id=? AND run_id=?
            ORDER BY id
            """,
            (project_id, run_id),
        ).fetchall()

        observation_rows = self.conn.execute(
            """
            SELECT o.entity_key, e.title, e.entity_type, e.source_url,
                   e.source_domain, o.observed_at, o.price, o.currency,
                   e.extraction_method, e.relevance_score
            FROM observations o
            LEFT JOIN entities e
              ON e.project_id=o.project_id
             AND e.entity_key=o.entity_key
            WHERE o.project_id=? AND o.run_id=?
            ORDER BY o.id
            """,
            (project_id, run_id),
        ).fetchall()

        return {
            "run": {
                "id": run[0],
                "project_id": run[1],
                "started_at": run[2],
                "finished_at": run[3] or "",
                "visited_pages": int(run[4] or 0),
                "failed_pages": int(run[5] or 0),
                "skipped_by_robots": int(run[6] or 0),
                "entities_found": int(run[7] or 0),
                "domains_found": int(run[8] or 0),
                "search_queries_issued": int(run[9] or 0),
                "search_results_seen": int(run[10] or 0),
                "search_results_unique": int(run[11] or 0),
                "search_results_duplicates": int(run[12] or 0),
                "search_domains_activated": int(run[13] or 0),
                "search_provider_errors": int(run[14] or 0),
                "feed_candidates_seen": int(run[15] or 0),
                "feeds_found": int(run[16] or 0),
                "feed_entries_seen": int(run[17] or 0),
                "feed_entries_new": int(run[18] or 0),
                "feed_not_modified": int(run[19] or 0),
                "feed_errors": int(run[20] or 0),
            },
            "page_visits": [
                {
                    "url": row[0],
                    "final_url": row[1],
                    "domain": row[2],
                    "source_url": row[3] or "",
                    "source_type": row[4] or "",
                    "depth": int(row[5] or 0),
                    "priority": int(row[6] or 0),
                    "outcome": row[7] or "",
                    "http_status": row[8],
                    "content_type": row[9] or "",
                    "visited_at": row[10] or "",
                }
                for row in page_rows
            ],
            "discoveries": [
                {
                    "source_domain": row[0] or "",
                    "target_domain": row[1],
                    "source_url": row[2] or "",
                    "target_url": row[3],
                    "relevance_score": float(row[4] or 0.0),
                    "action": row[5] or "",
                    "reason": row[6] or "",
                    "discovered_via": row[7] or "",
                    "provider": row[8] or "",
                    "query_text": row[9] or "",
                    "discovered_at": row[10] or "",
                }
                for row in discovery_rows
            ],
            "observations": [
                {
                    "entity_key": row[0],
                    "title": row[1] or "",
                    "entity_type": row[2] or "",
                    "source_url": row[3] or "",
                    "source_domain": row[4] or "",
                    "observed_at": row[5] or "",
                    "price": row[6],
                    "currency": row[7] or "",
                    "extraction_method": row[8] or "",
                    "relevance_score": float(row[9] or 0.0),
                }
                for row in observation_rows
            ],
        }

    def load_domain_states(
        self,
        project_id: str,
    ) -> dict[str, DomainRecord]:
        rows = self.conn.execute(
            """
            SELECT domain, status, discovered_via, discovered_from_url,
                   relevance_score, robots_status, sitemap_status,
                   sitemap_urls_found, first_seen, last_seen,
                   last_crawled, reason
            FROM domains
            WHERE project_id=?
            """,
            (project_id,),
        ).fetchall()

        states: dict[str, DomainRecord] = {}
        for row in rows:
            record = DomainRecord(
                domain=row[0],
                status=row[1],
                discovered_via=row[2] or "link",
                discovered_from_url=row[3] or "",
                relevance_score=float(row[4] or 0.0),
                robots_status=row[5] or "unknown",
                sitemap_status=row[6] or "unknown",
                sitemap_urls_found=int(row[7] or 0),
                # Run-local counters intentionally start at zero. Historical
                # totals remain in SQLite and are merged by save_domain_registry().
                pages_seen=0,
                entities_found=0,
                first_seen=row[8],
                last_seen=row[9],
                last_crawled=row[10],
                reason=row[11] or "",
            )
            states[record.domain] = record

        return states

    def load_feed_states(self, project_id: str) -> dict[str, FeedState]:
        rows = self.conn.execute(
            """
            SELECT feed_url, domain, feed_type, status, etag,
                   last_modified, last_entry_id, last_published,
                   last_checked, last_success, entries_seen,
                   new_entries, last_error, first_seen, last_seen
            FROM feeds
            WHERE project_id=?
            """,
            (project_id,),
        ).fetchall()

        states: dict[str, FeedState] = {}
        for row in rows:
            state = FeedState(
                feed_url=row[0],
                domain=row[1],
                feed_type=row[2],
                status=row[3],
                etag=row[4] or "",
                last_modified=row[5] or "",
                last_entry_id=row[6] or "",
                last_published=row[7] or "",
                last_checked=row[8] or "",
                last_success=row[9] or "",
                entries_seen=int(row[10] or 0),
                new_entries=int(row[11] or 0),
                last_error=row[12] or "",
                first_seen=row[13] or "",
                last_seen=row[14] or "",
            )
            states[state.feed_url] = state
        return states

    def save_feed_states(
        self,
        project: ResearchProject,
        result: ResearchRunResult,
    ):
        for state in result.feed_states.values():
            now = datetime.now(timezone.utc).isoformat()
            first_seen = state.first_seen or now
            last_seen = state.last_seen or now

            self.conn.execute(
                """
                INSERT INTO feeds(
                    project_id, feed_url, domain, feed_type, status,
                    etag, last_modified, last_entry_id, last_published,
                    last_checked, last_success, entries_seen, new_entries,
                    last_error, first_seen, last_seen
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, feed_url) DO UPDATE SET
                    domain=excluded.domain,
                    feed_type=excluded.feed_type,
                    status=excluded.status,
                    etag=excluded.etag,
                    last_modified=excluded.last_modified,
                    last_entry_id=excluded.last_entry_id,
                    last_published=excluded.last_published,
                    last_checked=excluded.last_checked,
                    last_success=excluded.last_success,
                    entries_seen=excluded.entries_seen,
                    new_entries=excluded.new_entries,
                    last_error=excluded.last_error,
                    last_seen=excluded.last_seen
                """,
                (
                    project.id,
                    state.feed_url,
                    state.domain,
                    state.feed_type,
                    state.status,
                    state.etag,
                    state.last_modified,
                    state.last_entry_id,
                    state.last_published,
                    state.last_checked,
                    state.last_success,
                    state.entries_seen,
                    state.new_entries,
                    state.last_error,
                    first_seen,
                    last_seen,
                ),
            )

        self.conn.commit()

    def list_feeds(
        self,
        project_id: str,
        *,
        status: str | None = None,
    ) -> list[dict]:
        sql = """
        SELECT feed_url, domain, feed_type, status, etag,
               last_modified, last_entry_id, last_published,
               last_checked, last_success, entries_seen,
               new_entries, last_error, first_seen, last_seen
        FROM feeds
        WHERE project_id=?
        """
        params: list[object] = [project_id]

        if status:
            sql += " AND status=?"
            params.append(status)

        sql += " ORDER BY domain ASC, feed_url ASC"
        rows = self.conn.execute(sql, params).fetchall()

        keys = [
            "feed_url",
            "domain",
            "feed_type",
            "status",
            "etag",
            "last_modified",
            "last_entry_id",
            "last_published",
            "last_checked",
            "last_success",
            "entries_seen",
            "new_entries",
            "last_error",
            "first_seen",
            "last_seen",
        ]
        return [dict(zip(keys, row)) for row in rows]

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
               relevance_score, action, reason, discovered_via,
               provider, query_text, discovered_at
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
            "discovered_via",
            "provider",
            "query_text",
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
                domains_found=?,
                search_queries_issued=?,
                search_results_seen=?,
                search_results_unique=?,
                search_results_duplicates=?,
                search_domains_activated=?,
                search_provider_errors=?,
                feed_candidates_seen=?,
                feeds_found=?,
                feed_entries_seen=?,
                feed_entries_new=?,
                feed_not_modified=?,
                feed_errors=?
            WHERE id=?
            """,
            (
                result.finished_at,
                result.visited_pages,
                result.failed_pages,
                result.skipped_by_robots,
                len(result.entities),
                len(result.discovered_domains),
                result.search_queries_issued,
                result.search_results_seen,
                result.search_results_unique,
                result.search_results_duplicates,
                result.search_domains_activated,
                result.search_provider_errors,
                result.feed_candidates_seen,
                result.feeds_found,
                result.feed_entries_seen,
                result.feed_entries_new,
                result.feed_not_modified,
                result.feed_errors,
                run_id,
            ),
        )
        self.conn.commit()
