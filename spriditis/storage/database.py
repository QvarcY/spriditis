from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from spriditis.core.entities import MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult


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
"""


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        self.conn.close()

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
