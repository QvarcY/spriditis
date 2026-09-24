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
from spriditis.resolution.identity import resolve_entities


CURRENT_SCHEMA_VERSION = 10
DEFAULT_STALE_AFTER_DAYS = 30.0


def _parse_iso_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_days(value: str, now: datetime) -> float | None:
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds() / 86400.0)



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

CREATE TABLE IF NOT EXISTS adaptive_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    run_id INTEGER NOT NULL,
    sequence INTEGER NOT NULL,
    stage TEXT NOT NULL,
    decision TEXT NOT NULL,
    target TEXT NOT NULL,
    signals_json TEXT NOT NULL DEFAULT '{}',
    decided_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE INDEX IF NOT EXISTS idx_adaptive_decisions_run
ON adaptive_decisions(project_id, run_id, sequence);

CREATE TABLE IF NOT EXISTS entity_clusters (
    project_id TEXT NOT NULL,
    cluster_key TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    canonical_title TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    merged_into_cluster_key TEXT NOT NULL DEFAULT '',
    merged_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(project_id, cluster_key),
    FOREIGN KEY(project_id) REFERENCES projects(project_id)
);

CREATE TABLE IF NOT EXISTS entity_cluster_members (
    project_id TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    cluster_key TEXT NOT NULL,
    match_reason TEXT NOT NULL,
    matched_signals_json TEXT NOT NULL DEFAULT '[]',
    supporting_signals_json TEXT NOT NULL DEFAULT '[]',
    linked_at TEXT NOT NULL,
    PRIMARY KEY(project_id, entity_key),
    FOREIGN KEY(project_id, cluster_key)
        REFERENCES entity_clusters(project_id, cluster_key),
    FOREIGN KEY(project_id, entity_key)
        REFERENCES entities(project_id, entity_key)
);

CREATE INDEX IF NOT EXISTS idx_entity_cluster_members_cluster
ON entity_cluster_members(project_id, cluster_key, linked_at);

CREATE TABLE IF NOT EXISTS entity_resolution_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    run_id INTEGER NOT NULL,
    entity_key TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    selected_cluster_key TEXT NOT NULL,
    candidate_cluster_keys_json TEXT NOT NULL DEFAULT '[]',
    conflict_cluster_keys_json TEXT NOT NULL DEFAULT '[]',
    matched_signals_json TEXT NOT NULL DEFAULT '[]',
    supporting_signals_json TEXT NOT NULL DEFAULT '[]',
    conflicting_signals_json TEXT NOT NULL DEFAULT '[]',
    compared_entities INTEGER NOT NULL DEFAULT 0,
    resolved_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(id),
    FOREIGN KEY(project_id, entity_key)
        REFERENCES entities(project_id, entity_key)
);

CREATE INDEX IF NOT EXISTS idx_entity_resolution_events_run
ON entity_resolution_events(project_id, run_id, id);

CREATE INDEX IF NOT EXISTS idx_entity_resolution_events_entity
ON entity_resolution_events(project_id, entity_key, id);

CREATE TABLE IF NOT EXISTS entity_cluster_merge_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    source_cluster_key TEXT NOT NULL,
    target_cluster_key TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    matched_signals_json TEXT NOT NULL DEFAULT '[]',
    conflicting_signals_json TEXT NOT NULL DEFAULT '[]',
    source_member_count INTEGER NOT NULL DEFAULT 0,
    target_member_count INTEGER NOT NULL DEFAULT 0,
    merged_member_count INTEGER NOT NULL DEFAULT 0,
    requested_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entity_cluster_merge_events_project
ON entity_cluster_merge_events(project_id, id);

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
            SET status=CASE
                    WHEN status='blocked' THEN 'candidate'
                    ELSE status
                END,
                reason=''
            WHERE reason IN ('blocked_path', 'binary_or_static_file')
            """
        )

        self._ensure_column(
            "entity_clusters",
            "merged_into_cluster_key",
            "TEXT NOT NULL DEFAULT ''",
        )
        self._ensure_column(
            "entity_clusters",
            "merged_at",
            "TEXT NOT NULL DEFAULT ''",
        )

        # Alpha6 canonical clustering is layered on top of the existing
        # source-specific entities/observations model. Existing entities are
        # bootstrapped into one-member clusters so migration never merges
        # historical evidence implicitly.
        self.conn.execute(
            """
            INSERT OR IGNORE INTO entity_clusters(
                project_id, cluster_key, entity_type, canonical_title,
                first_seen, last_seen
            )
            SELECT project_id, entity_key, entity_type, title,
                   first_seen, last_seen
            FROM entities
            """
        )
        self.conn.execute(
            """
            INSERT OR IGNORE INTO entity_cluster_members(
                project_id, entity_key, cluster_key, match_reason,
                matched_signals_json, supporting_signals_json, linked_at
            )
            SELECT project_id, entity_key, entity_key, 'legacy_seed',
                   '[]', '[]', first_seen
            FROM entities
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

        self._resolve_entity_cluster(
            project.id,
            run_id,
            key,
            entity,
            now,
        )
        self.conn.commit()

    def _entity_from_storage_row(self, row) -> MarketEntity:
        return MarketEntity(
            title=row[2],
            entity_type=row[1],
            source_url=row[3],
            source_domain=row[4] or "",
            description=row[5] or "",
            price=row[6],
            currency=row[7] or "EUR",
            seller=row[8] or "",
            image_url=row[9] or "",
            category=row[10] or "uncategorized",
            is_relevant=bool(row[11]),
            confidence=float(row[12] or 0.0),
            relevance_score=float(row[13] or 0.0),
            tags=json.loads(row[14] or "[]"),
            attributes=json.loads(row[15] or "{}"),
            opportunity_notes=row[16] or "",
            extraction_method=row[17] or "",
            evidence=row[18] or "",
        )

    def _resolve_entity_cluster(
        self,
        project_id: str,
        run_id: int,
        entity_key: str,
        entity: MarketEntity,
        linked_at: str,
    ) -> str:
        existing = self.conn.execute(
            """
            SELECT cluster_key
            FROM entity_cluster_members
            WHERE project_id=? AND entity_key=?
            """,
            (project_id, entity_key),
        ).fetchone()

        if existing:
            cluster_key = existing[0]
            self.conn.execute(
                """
                UPDATE entity_clusters
                SET last_seen=?
                WHERE project_id=? AND cluster_key=?
                """,
                (linked_at, project_id, cluster_key),
            )
            return cluster_key

        rows = self.conn.execute(
            """
            SELECT e.entity_key, e.entity_type, e.title, e.source_url,
                   e.source_domain, e.description, e.last_price,
                   e.currency, e.seller, e.image_url, e.category,
                   e.is_relevant, e.confidence, e.relevance_score,
                   e.tags_json, e.attributes_json, e.opportunity_notes,
                   e.extraction_method, e.evidence, m.cluster_key
            FROM entities e
            JOIN entity_cluster_members m
              ON m.project_id=e.project_id
             AND m.entity_key=e.entity_key
            WHERE e.project_id=?
              AND e.entity_key<>?
              AND e.entity_type=?
            ORDER BY e.first_seen, e.entity_key
            """,
            (project_id, entity_key, entity.entity_type),
        ).fetchall()

        matches_by_cluster: dict[str, list] = {}
        conflicts_by_cluster: dict[str, list] = {}
        supporting_signal_set: set[str] = set()

        for row in rows:
            candidate = self._entity_from_storage_row(row)
            decision = resolve_entities(entity, candidate)
            if decision.outcome == "match":
                matches_by_cluster.setdefault(row[19], []).append(decision)
            elif decision.outcome == "conflict":
                conflicts_by_cluster.setdefault(row[19], []).append(decision)
            else:
                supporting_signal_set.update(decision.supporting_signals)

        cluster_key = entity_key
        match_reason = "new_cluster"
        resolution_decision = "new_cluster"
        resolution_reason = (
            "no_candidates" if not rows else "no_strong_match"
        )
        matched_signals: tuple[str, ...] = ()
        supporting_signals: tuple[str, ...] = tuple(
            sorted(supporting_signal_set)
        )

        if len(matches_by_cluster) == 1:
            cluster_key, decisions = next(iter(matches_by_cluster.items()))
            selected = decisions[0]
            match_reason = selected.reason
            resolution_decision = "linked"
            resolution_reason = selected.reason
            matched_signals = selected.matched_signals
            supporting_signals = selected.supporting_signals
        elif len(matches_by_cluster) > 1:
            match_reason = "ambiguous_multiple_clusters"
            resolution_decision = "deferred_ambiguous"
            resolution_reason = "ambiguous_multiple_clusters"
            matched_signals = tuple(
                sorted(
                    {
                        signal
                        for decisions in matches_by_cluster.values()
                        for decision in decisions
                        for signal in decision.matched_signals
                    }
                )
            )
            supporting_signals = tuple(
                sorted(
                    {
                        *supporting_signal_set,
                        *(
                            signal
                            for decisions in matches_by_cluster.values()
                            for decision in decisions
                            for signal in decision.supporting_signals
                        ),
                    }
                )
            )
        elif conflicts_by_cluster:
            match_reason = "identity_conflict"
            resolution_decision = "created_separate"
            resolution_reason = "identity_conflict"

        self.conn.execute(
            """
            INSERT OR IGNORE INTO entity_clusters(
                project_id, cluster_key, entity_type, canonical_title,
                first_seen, last_seen
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                cluster_key,
                entity.entity_type,
                entity.title,
                linked_at,
                linked_at,
            ),
        )
        self.conn.execute(
            """
            INSERT INTO entity_cluster_members(
                project_id, entity_key, cluster_key, match_reason,
                matched_signals_json, supporting_signals_json, linked_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                entity_key,
                cluster_key,
                match_reason,
                json.dumps(matched_signals, ensure_ascii=False),
                json.dumps(supporting_signals, ensure_ascii=False),
                linked_at,
            ),
        )
        self.conn.execute(
            """
            UPDATE entity_clusters
            SET last_seen=MAX(last_seen, ?)
            WHERE project_id=? AND cluster_key=?
            """,
            (linked_at, project_id, cluster_key),
        )

        conflicting_signals = tuple(
            sorted(
                {
                    signal
                    for decisions in conflicts_by_cluster.values()
                    for decision in decisions
                    for signal in decision.conflicting_signals
                }
            )
        )
        self.conn.execute(
            """
            INSERT INTO entity_resolution_events(
                project_id, run_id, entity_key, decision, reason,
                selected_cluster_key, candidate_cluster_keys_json,
                conflict_cluster_keys_json, matched_signals_json,
                supporting_signals_json, conflicting_signals_json,
                compared_entities, resolved_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                run_id,
                entity_key,
                resolution_decision,
                resolution_reason,
                cluster_key,
                json.dumps(
                    sorted(matches_by_cluster),
                    ensure_ascii=False,
                ),
                json.dumps(
                    sorted(conflicts_by_cluster),
                    ensure_ascii=False,
                ),
                json.dumps(matched_signals, ensure_ascii=False),
                json.dumps(supporting_signals, ensure_ascii=False),
                json.dumps(conflicting_signals, ensure_ascii=False),
                len(rows),
                linked_at,
            ),
        )
        return cluster_key

    def entity_resolution_events(
        self,
        project_id: str,
        *,
        run_id: int | None = None,
        limit: int = 100,
    ) -> list[dict]:
        clauses = ["project_id=?"]
        params: list[object] = [project_id]

        if run_id is not None:
            clauses.append("run_id=?")
            params.append(run_id)

        params.append(max(1, min(int(limit), 1000)))
        rows = self.conn.execute(
            f"""
            SELECT id, run_id, entity_key, decision, reason,
                   selected_cluster_key, candidate_cluster_keys_json,
                   conflict_cluster_keys_json, matched_signals_json,
                   supporting_signals_json, conflicting_signals_json,
                   compared_entities, resolved_at
            FROM entity_resolution_events
            WHERE {' AND '.join(clauses)}
            ORDER BY id
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()

        return [
            {
                "id": int(row[0]),
                "run_id": int(row[1]),
                "entity_key": row[2],
                "decision": row[3],
                "reason": row[4],
                "selected_cluster_key": row[5],
                "candidate_cluster_keys": json.loads(row[6] or "[]"),
                "conflict_cluster_keys": json.loads(row[7] or "[]"),
                "matched_signals": json.loads(row[8] or "[]"),
                "supporting_signals": json.loads(row[9] or "[]"),
                "conflicting_signals": json.loads(row[10] or "[]"),
                "compared_entities": int(row[11] or 0),
                "resolved_at": row[12] or "",
            }
            for row in rows
        ]

    def entity_resolution_review_queue(
        self,
        project_id: str,
        *,
        kind: str = "all",
        limit: int = 100,
    ) -> list[dict]:
        kind = kind.strip().casefold()
        if kind not in {"all", "ambiguous", "conflict"}:
            raise ValueError(
                "Review queue kind jābūt: all, ambiguous vai conflict."
            )

        filters = [
            "r.project_id=?",
            "("
            "r.decision='deferred_ambiguous' "
            "OR (r.decision='created_separate' "
            "AND r.reason='identity_conflict')"
            ")",
            "c.merged_into_cluster_key=''",
        ]
        params: list[object] = [project_id]

        if kind == "ambiguous":
            filters.append("r.decision='deferred_ambiguous'")
        elif kind == "conflict":
            filters.append(
                "r.decision='created_separate' "
                "AND r.reason='identity_conflict'"
            )

        params.append(max(1, min(int(limit), 1000)))
        rows = self.conn.execute(
            f"""
            SELECT r.id, r.run_id, r.entity_key, r.decision, r.reason,
                   r.selected_cluster_key,
                   r.candidate_cluster_keys_json,
                   r.conflict_cluster_keys_json,
                   r.matched_signals_json,
                   r.supporting_signals_json,
                   r.conflicting_signals_json,
                   r.compared_entities, r.resolved_at,
                   e.title, e.source_url, e.source_domain,
                   c.canonical_title
            FROM entity_resolution_events r
            JOIN entities e
              ON e.project_id=r.project_id
             AND e.entity_key=r.entity_key
            JOIN entity_clusters c
              ON c.project_id=r.project_id
             AND c.cluster_key=r.selected_cluster_key
            WHERE {' AND '.join(filters)}
            ORDER BY r.id
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()

        return [
            {
                "event_id": int(row[0]),
                "run_id": int(row[1]),
                "entity_key": row[2],
                "decision": row[3],
                "reason": row[4],
                "selected_cluster_key": row[5],
                "candidate_cluster_keys": json.loads(row[6] or "[]"),
                "conflict_cluster_keys": json.loads(row[7] or "[]"),
                "matched_signals": json.loads(row[8] or "[]"),
                "supporting_signals": json.loads(row[9] or "[]"),
                "conflicting_signals": json.loads(row[10] or "[]"),
                "compared_entities": int(row[11] or 0),
                "resolved_at": row[12] or "",
                "title": row[13] or "",
                "source_url": row[14] or "",
                "source_domain": row[15] or "",
                "canonical_title": row[16] or "",
            }
            for row in rows
        ]

    def _cluster_member_rows(
        self,
        project_id: str,
        cluster_key: str,
    ) -> list:
        return self.conn.execute(
            """
            SELECT e.entity_key, e.entity_type, e.title, e.source_url,
                   e.source_domain, e.description, e.last_price,
                   e.currency, e.seller, e.image_url, e.category,
                   e.is_relevant, e.confidence, e.relevance_score,
                   e.tags_json, e.attributes_json, e.opportunity_notes,
                   e.extraction_method, e.evidence
            FROM entity_cluster_members m
            JOIN entities e
              ON e.project_id=m.project_id
             AND e.entity_key=m.entity_key
            WHERE m.project_id=? AND m.cluster_key=?
            ORDER BY m.linked_at, m.entity_key
            """,
            (project_id, cluster_key),
        ).fetchall()

    def _record_cluster_merge_event(
        self,
        *,
        project_id: str,
        source_cluster_key: str,
        target_cluster_key: str,
        decision: str,
        reason: str,
        matched_signals: tuple[str, ...] = (),
        conflicting_signals: tuple[str, ...] = (),
        source_member_count: int = 0,
        target_member_count: int = 0,
        merged_member_count: int = 0,
        requested_at: str,
    ) -> dict:
        cur = self.conn.execute(
            """
            INSERT INTO entity_cluster_merge_events(
                project_id, source_cluster_key, target_cluster_key,
                decision, reason, matched_signals_json,
                conflicting_signals_json, source_member_count,
                target_member_count, merged_member_count, requested_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                source_cluster_key,
                target_cluster_key,
                decision,
                reason,
                json.dumps(matched_signals, ensure_ascii=False),
                json.dumps(conflicting_signals, ensure_ascii=False),
                source_member_count,
                target_member_count,
                merged_member_count,
                requested_at,
            ),
        )
        return {
            "id": int(cur.lastrowid),
            "project_id": project_id,
            "source_cluster_key": source_cluster_key,
            "target_cluster_key": target_cluster_key,
            "decision": decision,
            "reason": reason,
            "matched_signals": list(matched_signals),
            "conflicting_signals": list(conflicting_signals),
            "source_member_count": source_member_count,
            "target_member_count": target_member_count,
            "merged_member_count": merged_member_count,
            "requested_at": requested_at,
        }

    def merge_entity_clusters(
        self,
        project_id: str,
        source_cluster_key: str,
        target_cluster_key: str,
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()

        if source_cluster_key == target_cluster_key:
            event = self._record_cluster_merge_event(
                project_id=project_id,
                source_cluster_key=source_cluster_key,
                target_cluster_key=target_cluster_key,
                decision="rejected",
                reason="same_cluster",
                requested_at=now,
            )
            self.conn.commit()
            return event

        source_cluster = self.conn.execute(
            """
            SELECT entity_type, merged_into_cluster_key
            FROM entity_clusters
            WHERE project_id=? AND cluster_key=?
            """,
            (project_id, source_cluster_key),
        ).fetchone()
        target_cluster = self.conn.execute(
            """
            SELECT entity_type, merged_into_cluster_key
            FROM entity_clusters
            WHERE project_id=? AND cluster_key=?
            """,
            (project_id, target_cluster_key),
        ).fetchone()

        if source_cluster is None or target_cluster is None:
            event = self._record_cluster_merge_event(
                project_id=project_id,
                source_cluster_key=source_cluster_key,
                target_cluster_key=target_cluster_key,
                decision="rejected",
                reason="cluster_not_found",
                requested_at=now,
            )
            self.conn.commit()
            return event

        if source_cluster[1]:
            event = self._record_cluster_merge_event(
                project_id=project_id,
                source_cluster_key=source_cluster_key,
                target_cluster_key=target_cluster_key,
                decision="rejected",
                reason="source_cluster_already_merged",
                requested_at=now,
            )
            self.conn.commit()
            return event

        if target_cluster[1]:
            event = self._record_cluster_merge_event(
                project_id=project_id,
                source_cluster_key=source_cluster_key,
                target_cluster_key=target_cluster_key,
                decision="rejected",
                reason="target_cluster_already_merged",
                requested_at=now,
            )
            self.conn.commit()
            return event

        source_rows = self._cluster_member_rows(
            project_id,
            source_cluster_key,
        )
        target_rows = self._cluster_member_rows(
            project_id,
            target_cluster_key,
        )
        source_count = len(source_rows)
        target_count = len(target_rows)

        if source_cluster[0] != target_cluster[0]:
            event = self._record_cluster_merge_event(
                project_id=project_id,
                source_cluster_key=source_cluster_key,
                target_cluster_key=target_cluster_key,
                decision="rejected",
                reason="entity_type_mismatch",
                source_member_count=source_count,
                target_member_count=target_count,
                requested_at=now,
            )
            self.conn.commit()
            return event

        matched_signals: set[str] = set()
        conflicting_signals: set[str] = set()

        for source_row in source_rows:
            source_entity = self._entity_from_storage_row(source_row)
            for target_row in target_rows:
                target_entity = self._entity_from_storage_row(target_row)
                decision = resolve_entities(source_entity, target_entity)
                if decision.outcome == "match":
                    matched_signals.update(decision.matched_signals)
                elif decision.outcome == "conflict":
                    conflicting_signals.update(
                        decision.conflicting_signals
                    )

        matched = tuple(sorted(matched_signals))
        conflicts = tuple(sorted(conflicting_signals))

        if conflicts:
            event = self._record_cluster_merge_event(
                project_id=project_id,
                source_cluster_key=source_cluster_key,
                target_cluster_key=target_cluster_key,
                decision="rejected",
                reason="identity_conflict",
                matched_signals=matched,
                conflicting_signals=conflicts,
                source_member_count=source_count,
                target_member_count=target_count,
                requested_at=now,
            )
            self.conn.commit()
            return event

        if not matched:
            event = self._record_cluster_merge_event(
                project_id=project_id,
                source_cluster_key=source_cluster_key,
                target_cluster_key=target_cluster_key,
                decision="rejected",
                reason="no_strong_identity_match",
                source_member_count=source_count,
                target_member_count=target_count,
                requested_at=now,
            )
            self.conn.commit()
            return event

        self.conn.execute(
            """
            UPDATE entity_cluster_members
            SET cluster_key=?
            WHERE project_id=? AND cluster_key=?
            """,
            (
                target_cluster_key,
                project_id,
                source_cluster_key,
            ),
        )
        self.conn.execute(
            """
            UPDATE entity_clusters
            SET last_seen=MAX(
                    last_seen,
                    (
                        SELECT last_seen
                        FROM entity_clusters
                        WHERE project_id=? AND cluster_key=?
                    )
                )
            WHERE project_id=? AND cluster_key=?
            """,
            (
                project_id,
                source_cluster_key,
                project_id,
                target_cluster_key,
            ),
        )
        self.conn.execute(
            """
            UPDATE entity_clusters
            SET merged_into_cluster_key=?, merged_at=?
            WHERE project_id=? AND cluster_key=?
            """,
            (
                target_cluster_key,
                now,
                project_id,
                source_cluster_key,
            ),
        )

        event = self._record_cluster_merge_event(
            project_id=project_id,
            source_cluster_key=source_cluster_key,
            target_cluster_key=target_cluster_key,
            decision="merged",
            reason="explicit_strong_identity_match",
            matched_signals=matched,
            source_member_count=source_count,
            target_member_count=target_count,
            merged_member_count=source_count,
            requested_at=now,
        )
        self.conn.commit()
        return event

    def entity_cluster_merge_events(
        self,
        project_id: str,
        *,
        limit: int = 100,
    ) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT id, source_cluster_key, target_cluster_key,
                   decision, reason, matched_signals_json,
                   conflicting_signals_json, source_member_count,
                   target_member_count, merged_member_count, requested_at
            FROM entity_cluster_merge_events
            WHERE project_id=?
            ORDER BY id
            LIMIT ?
            """,
            (project_id, max(1, min(int(limit), 1000))),
        ).fetchall()

        return [
            {
                "id": int(row[0]),
                "source_cluster_key": row[1],
                "target_cluster_key": row[2],
                "decision": row[3],
                "reason": row[4],
                "matched_signals": json.loads(row[5] or "[]"),
                "conflicting_signals": json.loads(row[6] or "[]"),
                "source_member_count": int(row[7] or 0),
                "target_member_count": int(row[8] or 0),
                "merged_member_count": int(row[9] or 0),
                "requested_at": row[10] or "",
            }
            for row in rows
        ]

    def entity_clusters(
        self,
        project_id: str,
    ) -> list[dict]:
        clusters = self.conn.execute(
            """
            SELECT c.cluster_key, c.entity_type, c.canonical_title,
                   c.first_seen, c.last_seen,
                   COUNT(m.entity_key) AS member_count,
                   COUNT(DISTINCT e.source_domain) AS source_count
            FROM entity_clusters c
            LEFT JOIN entity_cluster_members m
              ON m.project_id=c.project_id
             AND m.cluster_key=c.cluster_key
            LEFT JOIN entities e
              ON e.project_id=m.project_id
             AND e.entity_key=m.entity_key
            WHERE c.project_id=?
              AND c.merged_into_cluster_key=''
            GROUP BY c.cluster_key, c.entity_type, c.canonical_title,
                     c.first_seen, c.last_seen
            ORDER BY c.first_seen, c.cluster_key
            """,
            (project_id,),
        ).fetchall()

        result: list[dict] = []
        for row in clusters:
            members = self.conn.execute(
                """
                SELECT m.entity_key, e.title, e.source_url, e.source_domain,
                       e.last_price, e.currency, m.match_reason,
                       m.matched_signals_json,
                       m.supporting_signals_json, m.linked_at
                FROM entity_cluster_members m
                JOIN entities e
                  ON e.project_id=m.project_id
                 AND e.entity_key=m.entity_key
                WHERE m.project_id=? AND m.cluster_key=?
                ORDER BY m.linked_at, m.entity_key
                """,
                (project_id, row[0]),
            ).fetchall()
            result.append(
                {
                    "cluster_key": row[0],
                    "entity_type": row[1],
                    "canonical_title": row[2],
                    "first_seen": row[3],
                    "last_seen": row[4],
                    "member_count": int(row[5] or 0),
                    "source_count": int(row[6] or 0),
                    "members": [
                        {
                            "entity_key": member[0],
                            "title": member[1],
                            "source_url": member[2],
                            "source_domain": member[3] or "",
                            "price": member[4],
                            "currency": member[5] or "",
                            "match_reason": member[6],
                            "matched_signals": json.loads(
                                member[7] or "[]"
                            ),
                            "supporting_signals": json.loads(
                                member[8] or "[]"
                            ),
                            "linked_at": member[9],
                        }
                        for member in members
                    ],
                }
            )
        return result

    def explain_entity_cluster(
        self,
        project_id: str,
        cluster_key: str,
    ) -> dict | None:
        cluster = self.conn.execute(
            """
            SELECT cluster_key, entity_type, canonical_title,
                   first_seen, last_seen,
                   merged_into_cluster_key, merged_at
            FROM entity_clusters
            WHERE project_id=? AND cluster_key=?
            """,
            (project_id, cluster_key),
        ).fetchone()

        if cluster is None:
            return None

        status = "merged" if cluster[5] else "active"

        member_rows = self.conn.execute(
            """
            SELECT m.entity_key, e.title, e.source_url, e.source_domain,
                   e.last_price, e.currency, e.seller, e.attributes_json,
                   e.first_seen, e.last_seen, m.match_reason,
                   m.matched_signals_json, m.supporting_signals_json,
                   m.linked_at
            FROM entity_cluster_members m
            JOIN entities e
              ON e.project_id=m.project_id
             AND e.entity_key=m.entity_key
            WHERE m.project_id=? AND m.cluster_key=?
            ORDER BY m.linked_at, m.entity_key
            """,
            (project_id, cluster_key),
        ).fetchall()

        members: list[dict] = []
        entity_keys: list[str] = []

        for row in member_rows:
            entity_key = row[0]
            entity_keys.append(entity_key)
            observations = self.conn.execute(
                """
                SELECT run_id, observed_at, price, currency
                FROM observations
                WHERE project_id=? AND entity_key=?
                ORDER BY observed_at, id
                """,
                (project_id, entity_key),
            ).fetchall()

            members.append(
                {
                    "entity_key": entity_key,
                    "title": row[1],
                    "source_url": row[2],
                    "source_domain": row[3] or "",
                    "last_price": row[4],
                    "currency": row[5] or "",
                    "seller": row[6] or "",
                    "attributes": json.loads(row[7] or "{}"),
                    "first_seen": row[8] or "",
                    "last_seen": row[9] or "",
                    "match_reason": row[10] or "",
                    "matched_signals": json.loads(row[11] or "[]"),
                    "supporting_signals": json.loads(row[12] or "[]"),
                    "linked_at": row[13] or "",
                    "observations": [
                        {
                            "run_id": int(obs[0]),
                            "observed_at": obs[1] or "",
                            "price": obs[2],
                            "currency": obs[3] or "",
                        }
                        for obs in observations
                    ],
                }
            )

        resolution_events: list[dict] = []
        if entity_keys:
            placeholders = ",".join("?" for _ in entity_keys)
            rows = self.conn.execute(
                f"""
                SELECT id, run_id, entity_key, decision, reason,
                       selected_cluster_key,
                       candidate_cluster_keys_json,
                       conflict_cluster_keys_json,
                       matched_signals_json,
                       supporting_signals_json,
                       conflicting_signals_json,
                       compared_entities, resolved_at
                FROM entity_resolution_events
                WHERE project_id=?
                  AND (
                      entity_key IN ({placeholders})
                      OR selected_cluster_key=?
                  )
                ORDER BY id
                """,
                (project_id, *entity_keys, cluster_key),
            ).fetchall()

            resolution_events = [
                {
                    "id": int(row[0]),
                    "run_id": int(row[1]),
                    "entity_key": row[2],
                    "decision": row[3],
                    "reason": row[4],
                    "selected_cluster_key": row[5],
                    "candidate_cluster_keys": json.loads(row[6] or "[]"),
                    "conflict_cluster_keys": json.loads(row[7] or "[]"),
                    "matched_signals": json.loads(row[8] or "[]"),
                    "supporting_signals": json.loads(row[9] or "[]"),
                    "conflicting_signals": json.loads(row[10] or "[]"),
                    "compared_entities": int(row[11] or 0),
                    "resolved_at": row[12] or "",
                }
                for row in rows
            ]
        else:
            rows = self.conn.execute(
                """
                SELECT id, run_id, entity_key, decision, reason,
                       selected_cluster_key,
                       candidate_cluster_keys_json,
                       conflict_cluster_keys_json,
                       matched_signals_json,
                       supporting_signals_json,
                       conflicting_signals_json,
                       compared_entities, resolved_at
                FROM entity_resolution_events
                WHERE project_id=? AND selected_cluster_key=?
                ORDER BY id
                """,
                (project_id, cluster_key),
            ).fetchall()
            resolution_events = [
                {
                    "id": int(row[0]),
                    "run_id": int(row[1]),
                    "entity_key": row[2],
                    "decision": row[3],
                    "reason": row[4],
                    "selected_cluster_key": row[5],
                    "candidate_cluster_keys": json.loads(row[6] or "[]"),
                    "conflict_cluster_keys": json.loads(row[7] or "[]"),
                    "matched_signals": json.loads(row[8] or "[]"),
                    "supporting_signals": json.loads(row[9] or "[]"),
                    "conflicting_signals": json.loads(row[10] or "[]"),
                    "compared_entities": int(row[11] or 0),
                    "resolved_at": row[12] or "",
                }
                for row in rows
            ]

        merge_rows = self.conn.execute(
            """
            SELECT id, source_cluster_key, target_cluster_key,
                   decision, reason, matched_signals_json,
                   conflicting_signals_json, source_member_count,
                   target_member_count, merged_member_count, requested_at
            FROM entity_cluster_merge_events
            WHERE project_id=?
              AND (
                  source_cluster_key=?
                  OR target_cluster_key=?
              )
            ORDER BY id
            """,
            (project_id, cluster_key, cluster_key),
        ).fetchall()

        merge_events = [
            {
                "id": int(row[0]),
                "source_cluster_key": row[1],
                "target_cluster_key": row[2],
                "decision": row[3],
                "reason": row[4],
                "matched_signals": json.loads(row[5] or "[]"),
                "conflicting_signals": json.loads(row[6] or "[]"),
                "source_member_count": int(row[7] or 0),
                "target_member_count": int(row[8] or 0),
                "merged_member_count": int(row[9] or 0),
                "requested_at": row[10] or "",
            }
            for row in merge_rows
        ]

        review_rows = self.entity_resolution_review_queue(
            project_id,
            kind="all",
            limit=1000,
        )
        review_items = [
            item
            for item in review_rows
            if item["selected_cluster_key"] == cluster_key
        ]

        source_domains = {
            member["source_domain"]
            for member in members
            if member["source_domain"]
        }
        observation_count = sum(
            len(member["observations"])
            for member in members
        )

        identity_signals: dict[str, list[str]] = {}
        for member in members:
            attributes = member["attributes"]
            for key in (
                "gtin",
                "brand",
                "manufacturer",
                "model",
                "mpn",
                "sku",
            ):
                value = attributes.get(key)
                if value in (None, ""):
                    continue
                text_value = str(value)
                bucket = identity_signals.setdefault(key, [])
                if text_value not in bucket:
                    bucket.append(text_value)

        return {
            "cluster_key": cluster[0],
            "entity_type": cluster[1],
            "canonical_title": cluster[2],
            "first_seen": cluster[3],
            "last_seen": cluster[4],
            "status": status,
            "merged_into_cluster_key": cluster[5] or "",
            "merged_at": cluster[6] or "",
            "member_count": len(members),
            "source_count": len(source_domains),
            "observation_count": observation_count,
            "identity_signals": identity_signals,
            "members": members,
            "resolution_events": resolution_events,
            "merge_events": merge_events,
            "review_items": review_items,
        }

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

    def save_adaptive_decisions(
        self,
        project: ResearchProject,
        run_id: int,
        result: ResearchRunResult,
    ):
        if not result.adaptive_decisions:
            return

        self.conn.executemany(
            """
            INSERT INTO adaptive_decisions(
                project_id, run_id, sequence, stage, decision,
                target, signals_json, decided_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    project.id,
                    run_id,
                    sequence,
                    item.stage,
                    item.decision,
                    item.target,
                    json.dumps(item.signals, ensure_ascii=False, sort_keys=True),
                    item.decided_at,
                )
                for sequence, item in enumerate(
                    result.adaptive_decisions,
                    start=1,
                )
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
                MAX(discovered_at) AS last_used,
                COUNT(DISTINCT CASE
                    WHEN action IN ('activated', 'known')
                    THEN target_domain
                END) AS productive_domains,
                COUNT(DISTINCT CASE
                    WHEN action='blocked'
                    THEN target_domain
                END) AS blocked_domains
            FROM domain_discoveries
            WHERE project_id=?
              AND query_text IS NOT NULL
              AND query_text<>''
            GROUP BY provider, query_text
            ORDER BY productive_domains DESC,
                     activated DESC,
                     unique_domains DESC,
                     result_events DESC,
                     query_text ASC
            LIMIT ?
            """,
            (project_id, max(1, min(int(limit), 1000))),
        ).fetchall()

        result = []
        for row in rows:
            total = int(row[2] or 0)
            unique_domains = int(row[3] or 0)
            activated = int(row[4] or 0)
            productive_domains = int(row[10] or 0)
            result.append(
                {
                    "provider": row[0] or "",
                    "query_text": row[1] or "",
                    "result_events": total,
                    "unique_domains": unique_domains,
                    "activated": activated,
                    "known": int(row[5] or 0),
                    "blocked": int(row[6] or 0),
                    "recorded": int(row[7] or 0),
                    "runs": int(row[8] or 0),
                    "last_used": row[9] or "",
                    "productive_domains": productive_domains,
                    "blocked_domains": int(row[11] or 0),
                    # Historical first-activation ratio is kept for
                    # compatibility and audit. It naturally falls on repeat
                    # runs as useful domains become "known".
                    "activation_rate": (
                        activated / total if total else 0.0
                    ),
                    # Stable query yield: share of unique domains that have
                    # ever been activated or subsequently recognized as known.
                    "productive_domain_rate": (
                        productive_domains / unique_domains
                        if unique_domains else 0.0
                    ),
                }
            )
        return result

    def search_duplication_memory(
        self,
        project_id: str,
        *,
        limit: int = 20,
    ) -> dict:
        aggregate_row = self.conn.execute(
            """
            SELECT
                COUNT(*) AS runs,
                COALESCE(SUM(search_queries_issued), 0) AS queries,
                COALESCE(SUM(search_results_seen), 0) AS raw_results,
                COALESCE(SUM(search_results_unique), 0) AS unique_results,
                COALESCE(SUM(search_results_duplicates), 0) AS duplicates,
                COALESCE(SUM(search_provider_errors), 0) AS provider_errors
            FROM runs
            WHERE project_id=?
              AND (
                    search_queries_issued > 0
                 OR search_results_seen > 0
                 OR search_provider_errors > 0
              )
            """,
            (project_id,),
        ).fetchone()

        rows = self.conn.execute(
            """
            SELECT
                id,
                started_at,
                finished_at,
                search_queries_issued,
                search_results_seen,
                search_results_unique,
                search_results_duplicates,
                search_provider_errors
            FROM runs
            WHERE project_id=?
              AND (
                    search_queries_issued > 0
                 OR search_results_seen > 0
                 OR search_provider_errors > 0
              )
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                project_id,
                max(1, min(int(limit), 1000)),
            ),
        ).fetchall()

        raw_results = int(aggregate_row[2] or 0)
        unique_results = int(aggregate_row[3] or 0)
        duplicates = int(aggregate_row[4] or 0)
        filtered_results = max(
            0,
            raw_results - unique_results - duplicates,
        )

        recent_runs = []
        for row in rows:
            raw = int(row[4] or 0)
            unique = int(row[5] or 0)
            duplicate = int(row[6] or 0)
            filtered = max(0, raw - unique - duplicate)
            recent_runs.append(
                {
                    "run_id": int(row[0]),
                    "started_at": row[1] or "",
                    "finished_at": row[2] or "",
                    "queries": int(row[3] or 0),
                    "raw_results": raw,
                    "unique_results": unique,
                    "duplicates": duplicate,
                    "filtered_results": filtered,
                    "duplicate_rate": (
                        duplicate / raw if raw else 0.0
                    ),
                    "provider_errors": int(row[7] or 0),
                }
            )

        return {
            "scope": "normalized_search_url_across_run",
            "runs": int(aggregate_row[0] or 0),
            "queries": int(aggregate_row[1] or 0),
            "raw_results": raw_results,
            "unique_results": unique_results,
            "duplicates": duplicates,
            "filtered_results": filtered_results,
            "duplicate_rate": (
                duplicates / raw_results if raw_results else 0.0
            ),
            "provider_errors": int(aggregate_row[5] or 0),
            "recent_runs": recent_runs,
        }


    def source_profiles(
        self,
        project_id: str,
        *,
        limit: int = 50,
        stale_after_days: float = DEFAULT_STALE_AFTER_DAYS,
        as_of: datetime | None = None,
    ) -> list[dict]:
        stale_after_days = max(0.0, float(stale_after_days))
        now = as_of or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)
        rows = self.conn.execute(
            """
            WITH visit_stats AS (
                SELECT
                    domain,
                    COUNT(*) AS visits,
                    COUNT(DISTINCT run_id) AS crawl_runs,
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
            ),
            observation_stats AS (
                SELECT
                    e.source_domain AS domain,
                    COUNT(*) AS observations,
                    COUNT(DISTINCT o.run_id) AS productive_runs,
                    MAX(o.observed_at) AS last_useful_at
                FROM observations o
                JOIN entities e
                  ON e.project_id=o.project_id
                 AND e.entity_key=o.entity_key
                WHERE o.project_id=?
                  AND e.source_domain IS NOT NULL
                  AND e.source_domain<>''
                GROUP BY e.source_domain
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
                COALESCE(v.crawl_runs, 0),
                COALESCE(v.html_ok, 0),
                COALESCE(v.failures, 0),
                COALESCE(v.last_visit, ''),
                COALESCE(f.feed_count, 0),
                COALESCE(f.last_feed_success, ''),
                COALESCE(x.discovery_events, 0),
                COALESCE(x.activated_events, 0),
                COALESCE(x.blocked_events, 0),
                COALESCE(x.last_discovered, ''),
                COALESCE(o.observations, 0),
                COALESCE(o.productive_runs, 0),
                COALESCE(o.last_useful_at, '')
            FROM domains d
            LEFT JOIN visit_stats v ON v.domain=d.domain
            LEFT JOIN feed_stats f ON f.domain=d.domain
            LEFT JOIN discovery_stats x ON x.domain=d.domain
            LEFT JOIN observation_stats o ON o.domain=d.domain
            WHERE d.project_id=?
            ORDER BY COALESCE(o.productive_runs, 0) DESC,
                     d.entities_found DESC,
                     d.pages_seen DESC,
                     d.relevance_score DESC,
                     d.domain ASC
            LIMIT ?
            """,
            (
                project_id,
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
            crawl_runs = int(row[14] or 0)
            html_ok = int(row[15] or 0)
            productive_runs = int(row[25] or 0)
            last_seen = row[11] or ""
            last_crawled = row[12] or ""
            last_visit = row[17] or ""
            last_feed_success = row[19] or ""
            last_useful_at = row[26] or ""

            age_since_last_useful = _age_days(last_useful_at, now)
            age_since_last_crawl = _age_days(last_crawled, now)
            age_since_last_feed_success = _age_days(last_feed_success, now)

            if last_useful_at:
                stale_reference = "last_useful_at"
                stale_reference_at = last_useful_at
                stale_age_days = age_since_last_useful
            elif last_crawled:
                stale_reference = "last_crawled"
                stale_reference_at = last_crawled
                stale_age_days = age_since_last_crawl
            else:
                stale_reference = "last_seen"
                stale_reference_at = last_seen
                stale_age_days = _age_days(last_seen, now)

            is_stale = bool(
                stale_age_days is not None
                and stale_age_days > stale_after_days
            )

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
                    "last_seen": last_seen,
                    "last_crawled": last_crawled,
                    "visit_count": visits,
                    "crawl_runs": crawl_runs,
                    "successful_visits": html_ok,
                    "failed_visits": int(row[16] or 0),
                    "success_rate": (
                        html_ok / visits if visits else 0.0
                    ),
                    "last_visit": last_visit,
                    "feed_count": int(row[18] or 0),
                    "last_feed_success": last_feed_success,
                    "discovery_events": int(row[20] or 0),
                    "activated_events": int(row[21] or 0),
                    "blocked_events": int(row[22] or 0),
                    "last_discovered": row[23] or "",
                    "observation_count": int(row[24] or 0),
                    "productive_runs": productive_runs,
                    "productive_run_rate": (
                        productive_runs / crawl_runs
                        if crawl_runs else 0.0
                    ),
                    "last_useful_at": last_useful_at,
                    "age_since_last_useful_days": age_since_last_useful,
                    "age_since_last_crawl_days": age_since_last_crawl,
                    "age_since_last_feed_success_days": (
                        age_since_last_feed_success
                    ),
                    "stale_after_days": stale_after_days,
                    "stale_reference": stale_reference,
                    "stale_reference_at": stale_reference_at,
                    "stale_age_days": stale_age_days,
                    "is_stale": is_stale,
                    "freshness": "stale" if is_stale else "fresh",
                }
            )
        return profiles

    def explain_domain(
        self,
        project_id: str,
        domain: str,
        *,
        event_limit: int = 10,
        stale_after_days: float = DEFAULT_STALE_AFTER_DAYS,
        as_of: datetime | None = None,
    ) -> dict | None:
        profile = next(
            (
                item
                for item in self.source_profiles(
                    project_id,
                    limit=1000,
                    stale_after_days=stale_after_days,
                    as_of=as_of,
                )
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

        adaptive_rows = self.conn.execute(
            """
            SELECT sequence, stage, decision, target,
                   signals_json, decided_at
            FROM adaptive_decisions
            WHERE project_id=? AND run_id=?
            ORDER BY sequence
            """,
            (project_id, run_id),
        ).fetchall()

        resolution_rows = self.conn.execute(
            """
            SELECT id, entity_key, decision, reason,
                   selected_cluster_key, candidate_cluster_keys_json,
                   conflict_cluster_keys_json, matched_signals_json,
                   supporting_signals_json, conflicting_signals_json,
                   compared_entities, resolved_at
            FROM entity_resolution_events
            WHERE project_id=? AND run_id=?
            ORDER BY id
            """,
            (project_id, run_id),
        ).fetchall()

        observation_rows = self.conn.execute(
            """
            SELECT o.entity_key, e.title, e.entity_type, e.source_url,
                   e.source_domain, o.observed_at, o.price, o.currency,
                   e.extraction_method, e.relevance_score,
                   m.cluster_key, m.match_reason
            FROM observations o
            LEFT JOIN entities e
              ON e.project_id=o.project_id
             AND e.entity_key=o.entity_key
            LEFT JOIN entity_cluster_members m
              ON m.project_id=o.project_id
             AND m.entity_key=o.entity_key
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
            "adaptive_decisions": [
                {
                    "sequence": int(row[0]),
                    "stage": row[1] or "",
                    "decision": row[2] or "",
                    "target": row[3] or "",
                    "signals": json.loads(row[4] or "{}"),
                    "decided_at": row[5] or "",
                }
                for row in adaptive_rows
            ],
            "entity_resolution_events": [
                {
                    "id": int(row[0]),
                    "entity_key": row[1],
                    "decision": row[2],
                    "reason": row[3],
                    "selected_cluster_key": row[4],
                    "candidate_cluster_keys": json.loads(row[5] or "[]"),
                    "conflict_cluster_keys": json.loads(row[6] or "[]"),
                    "matched_signals": json.loads(row[7] or "[]"),
                    "supporting_signals": json.loads(row[8] or "[]"),
                    "conflicting_signals": json.loads(row[9] or "[]"),
                    "compared_entities": int(row[10] or 0),
                    "resolved_at": row[11] or "",
                }
                for row in resolution_rows
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
                    "cluster_key": row[10] or "",
                    "cluster_match_reason": row[11] or "",
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
