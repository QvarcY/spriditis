from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from spriditis.core.domains import DomainDiscovery, DomainRecord
from spriditis.core.entities import MarketEntity
from spriditis.core.memory import PageVisit
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult
from spriditis.storage.database import Database
from spriditis.cli import _group_trace_discoveries


def main():
    project = ResearchProject.model_validate(
        {
            "id": "memory_test",
            "name": "Research Memory test",
            "research_type": "product_market",
            "entity_type": "product",
            "keywords": ["ergonomic", "chair"],
            "seed_urls": ["https://seed.example/catalog"],
            "analysis": {
                "ai_enabled": False,
                "ai_provider": "none",
            },
        }
    )

    with TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "memory.db")
        try:
            db.save_project(project)
            run_id = db.start_run(project)

            result = ResearchRunResult(project_id=project.id)
            result.finished_at = datetime.now(timezone.utc).isoformat()
            result.visited_pages = 1
            result.search_queries_issued = 1
            result.search_results_seen = 2
            result.search_results_unique = 2
            result.search_domains_activated = 1

            result.domains = {
                "market.example": DomainRecord(
                    domain="market.example",
                    status="active",
                    discovered_via="search_provider",
                    relevance_score=0.8,
                    pages_seen=1,
                    entities_found=1,
                    robots_status="allowed",
                    sitemap_status="found",
                    sitemap_urls_found=5,
                    reason="search_relevance_threshold",
                ),
                "blocked.example": DomainRecord(
                    domain="blocked.example",
                    status="blocked",
                    discovered_via="search_provider",
                    relevance_score=0.6,
                    reason="blocked_host",
                ),
            }

            query = "ergonomic office chair"
            result.domain_discoveries = [
                DomainDiscovery(
                    target_domain="market.example",
                    target_url="https://market.example/product/chair",
                    relevance_score=0.8,
                    action="activated",
                    reason="search_relevance_threshold",
                    discovered_via="search_provider",
                    provider="fake",
                    query_text=query,
                ),
                DomainDiscovery(
                    target_domain="blocked.example",
                    target_url="https://blocked.example/chair",
                    relevance_score=0.6,
                    action="blocked",
                    reason="blocked_host",
                    discovered_via="search_provider",
                    provider="fake",
                    query_text=query,
                ),
            ]

            result.page_visits = [
                PageVisit(
                    url="https://market.example/product/chair",
                    final_url="https://market.example/product/chair",
                    domain="market.example",
                    source_type="search_provider",
                    depth=0,
                    priority=88,
                    outcome="html_ok",
                    http_status=200,
                    content_type="text/html",
                )
            ]

            entity = MarketEntity(
                title="Ergonomic office chair",
                source_url="https://market.example/product/chair",
                source_domain="market.example",
                price=199.0,
                currency="EUR",
                extraction_method="json-ld",
                relevance_score=0.9,
            )

            db.upsert_entity(project, run_id, entity)
            db.save_domain_registry(project, run_id, result)
            db.save_page_visits(project, run_id, result)
            db.finish_run(run_id, result)

            queries = db.query_memory(project.id)
            assert len(queries) == 1
            assert queries[0]["query_text"] == query
            assert queries[0]["result_events"] == 2
            assert queries[0]["activated"] == 1
            assert queries[0]["blocked"] == 1
            assert queries[0]["productive_domains"] == 1
            assert queries[0]["blocked_domains"] == 1
            assert queries[0]["activation_rate"] == 0.5
            assert queries[0]["productive_domain_rate"] == 0.5

            profiles = db.source_profiles(project.id)
            market = next(
                row for row in profiles
                if row["domain"] == "market.example"
            )
            assert market["pages_seen"] == 1
            assert market["entities_found"] == 1
            assert market["entity_yield"] == 1.0
            assert market["visit_count"] == 1
            assert market["crawl_runs"] == 1
            assert market["success_rate"] == 1.0
            assert market["observation_count"] == 1
            assert market["productive_runs"] == 1
            assert market["productive_run_rate"] == 1.0
            assert market["last_useful_at"]

            explanation = db.explain_domain(
                project.id,
                "market.example",
            )
            assert explanation is not None
            assert explanation["status"] == "active"
            assert explanation["recent_discoveries"][0]["provider"] == "fake"
            assert explanation["recent_visits"][0]["source_type"] == "search_provider"

            trace = db.trace_run(project.id, run_id)
            assert trace is not None
            assert trace["run"]["id"] == run_id
            assert len(trace["page_visits"]) == 1
            assert len(trace["discoveries"]) == 2
            assert len(trace["observations"]) == 1
            assert trace["observations"][0]["title"] == "Ergonomic office chair"

            grouped = _group_trace_discoveries(
                trace["discoveries"] + trace["discoveries"]
            )
            assert len(grouped) == 2
            assert sum(row["count"] for row in grouped) == 4
            assert max(row["count"] for row in grouped) == 2
        finally:
            db.close()

    print("RESEARCH MEMORY TEST OK")
    print("query_activation_rate=0.50")
    print("source_entity_yield=1.00")
    print("trace_pages=1 discoveries=2 observations=1")


if __name__ == "__main__":
    main()
