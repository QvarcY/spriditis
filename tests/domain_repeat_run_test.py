from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from pathlib import Path
from tempfile import TemporaryDirectory

from spriditis.core.projects import ResearchProject
from spriditis.crawler.discovery import DomainRegistry
from spriditis.storage.database import Database


def main():
    project = ResearchProject.model_validate(
        {
            "id": "domain_repeat_run",
            "name": "Domain repeat run",
            "research_type": "product_market",
            "entity_type": "product",
            "keywords": ["ergonomic", "chair"],
            "seed_urls": ["https://seed.example/catalog"],
            "crawl": {
                "mode": "discovery",
                "max_pages_total": 5,
                "max_pages_per_domain": 2,
                "max_domains": 2,
                "max_depth": 3,
                "delay_seconds": 0,
                "respect_robots": False,
                "external_link_threshold": 45,
                "discover_sitemaps": False,
                "discover_feeds": False
            },
            "analysis": {
                "ai_enabled": False,
                "ai_provider": "none"
            }
        }
    )

    with TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "spriditis.db")
        try:
            db.save_project(project)
            db.conn.executemany(
                """
                INSERT INTO domains(
                    project_id, domain, status, discovered_via,
                    discovered_from_url, relevance_score, robots_status,
                    sitemap_status, sitemap_urls_found, pages_seen,
                    entities_found, first_seen, last_seen, last_crawled,
                    reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        project.id, "blocked.example", "blocked",
                        "external_link", "https://seed.example/catalog",
                        0.9, "unknown", "unknown", 0, 7, 3,
                        "2026-09-20T00:00:00+00:00",
                        "2026-09-23T00:00:00+00:00",
                        None, "manual_block"
                    ),
                    (
                        project.id, "rejected.example", "rejected",
                        "external_link", "https://seed.example/catalog",
                        0.8, "unknown", "unknown", 0, 5, 1,
                        "2026-09-20T00:00:00+00:00",
                        "2026-09-23T00:00:00+00:00",
                        None, "manual_reject"
                    ),
                    (
                        project.id, "known.example", "active",
                        "external_link", "https://seed.example/catalog",
                        0.8, "allowed", "found", 12, 9, 4,
                        "2026-09-20T00:00:00+00:00",
                        "2026-09-23T00:00:00+00:00",
                        "2026-09-23T00:00:00+00:00", "relevance_threshold"
                    ),
                    (
                        project.id, "failed.example", "failed",
                        "external_link", "https://seed.example/catalog",
                        0.7, "unknown", "unknown", 0, 2, 0,
                        "2026-09-20T00:00:00+00:00",
                        "2026-09-23T00:00:00+00:00",
                        None, "http_status:503"
                    ),
                ],
            )
            db.conn.commit()

            states = db.load_domain_states(project.id)

            # Historical counters must not be replayed into the next run.
            assert states["known.example"].pages_seen == 0
            assert states["known.example"].entities_found == 0
            assert states["known.example"].sitemap_urls_found == 12

            registry = DomainRegistry(project, initial_records=states)
            registry.add_seed("https://seed.example/catalog")

            # A persisted safe blocked domain must not be reactivated merely
            # because it is later configured as a seed.
            blocked_seed_registry = DomainRegistry(
                project,
                initial_records=states,
            )
            blocked_seed = blocked_seed_registry.add_seed(
                "https://blocked.example/start"
            )
            assert blocked_seed.status == "blocked"
            assert blocked_seed_registry.active_count == 0

            blocked, blocked_event = registry.observe_link(
                source_url="https://seed.example/catalog",
                target_url="https://blocked.example/product/ergonomic-chair",
                anchor_text="ergonomic chair",
                raw_score=80,
            )
            assert blocked.status == "blocked"
            assert blocked_event.action == "blocked"
            assert blocked_event.reason == "manual_block"

            rejected, rejected_event = registry.observe_link(
                source_url="https://seed.example/catalog",
                target_url="https://rejected.example/product/ergonomic-chair",
                anchor_text="ergonomic chair",
                raw_score=80,
            )
            assert rejected.status == "rejected"
            assert rejected_event.action == "recorded"
            assert rejected_event.reason == "manual_reject"

            known, known_event = registry.observe_link(
                source_url="https://seed.example/catalog",
                target_url="https://known.example/product/ergonomic-chair",
                anchor_text="ergonomic chair",
                raw_score=80,
            )
            assert known.status == "active"
            assert known_event.action == "known"

            # Seed + known active already consume this run's domain budget.
            failed, failed_event = registry.observe_link(
                source_url="https://seed.example/catalog",
                target_url="https://failed.example/product/ergonomic-chair",
                anchor_text="ergonomic chair",
                raw_score=80,
            )
            assert failed.status == "candidate"
            assert failed_event.reason == "domain_budget_reached"

            current = registry.current_run_records()
            assert set(current) == {
                "seed.example",
                "blocked.example",
                "rejected.example",
                "known.example",
                "failed.example",
            }
        finally:
            db.close()

    print("DOMAIN REPEAT-RUN PERSISTENCE TEST OK")


if __name__ == "__main__":
    main()
