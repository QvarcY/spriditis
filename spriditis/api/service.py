from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from spriditis.ai.factory import build_ai_provider
from spriditis.config import AppSettings
from spriditis.core.projects import ResearchProject
from spriditis.crawler.engine import ResearchCrawler
from spriditis.mailer import send_html_report
from spriditis.reports.html import generate_html_report, save_html_report
from spriditis.search.factory import build_search_provider
from spriditis.storage.database import Database


@dataclass
class RunArtifacts:
    report_path: Path
    run_id: int
    entity_count: int
    visited_pages: int
    observed_domain_count: int
    crawled_domain_count: int
    domain_status_counts: dict[str, int]
    activated_domain_count: int = 0
    search_queries_issued: int = 0
    search_results_seen: int = 0
    search_results_unique: int = 0
    search_results_duplicates: int = 0
    search_domains_activated: int = 0
    search_provider_errors: int = 0
    feed_candidates_seen: int = 0
    feeds_found: int = 0
    feed_entries_seen: int = 0
    feed_entries_new: int = 0
    feed_not_modified: int = 0
    feed_errors: int = 0
    database_migrated_from: Path | None = None

    @property
    def domain_count(self) -> int:
        # Compatibility with alpha1 callers.
        return self.observed_domain_count


def run_project(
    settings: AppSettings,
    project: ResearchProject,
    *,
    force_no_ai: bool = False,
    send_email: bool = False,
) -> RunArtifacts:
    db = Database(
        settings.db_path,
        legacy_path=settings.legacy_db_path,
    )
    try:
        migrated_from = db.migrated_from

        db.save_project(project)
        run_id = db.start_run(project)

        ai = build_ai_provider(
            settings,
            project,
            force_no_ai=force_no_ai,
        )
        search_provider = build_search_provider(settings, project)
        feed_states = db.load_feed_states(project.id)
        domain_states = db.load_domain_states(project.id)
        query_memory = db.query_memory(project.id, limit=1000)
        crawler = ResearchCrawler(
            settings,
            project,
            ai,
            search_provider=search_provider,
            feed_states=feed_states,
            domain_states=domain_states,
            query_memory=query_memory,
        )
        result = crawler.crawl()

        for entity in result.entities:
            db.upsert_entity(project, run_id, entity)

        db.save_domain_registry(project, run_id, result)
        db.save_feed_states(project, result)
        db.save_page_visits(project, run_id, result)
        db.finish_run(run_id, result)

        html = generate_html_report(project, result)
        report_path = save_html_report(
            html,
            settings.report_dir,
            project.id,
        )

        send_html_report(
            settings,
            html,
            subject=f"Sprīdītis — {project.name}",
            enabled=send_email,
        )

        counts = Counter(record.status for record in result.domains.values())

        return RunArtifacts(
            report_path=report_path,
            run_id=run_id,
            entity_count=len(result.entities),
            visited_pages=result.visited_pages,
            observed_domain_count=len(result.domains),
            crawled_domain_count=sum(
                1 for record in result.domains.values()
                if record.pages_seen > 0
            ),
            domain_status_counts=dict(counts),
            activated_domain_count=sum(
                1 for item in result.domain_discoveries
                if item.action == "activated"
            ),
            search_queries_issued=result.search_queries_issued,
            search_results_seen=result.search_results_seen,
            search_results_unique=result.search_results_unique,
            search_results_duplicates=result.search_results_duplicates,
            search_domains_activated=result.search_domains_activated,
            search_provider_errors=result.search_provider_errors,
            feed_candidates_seen=result.feed_candidates_seen,
            feeds_found=result.feeds_found,
            feed_entries_seen=result.feed_entries_seen,
            feed_entries_new=result.feed_entries_new,
            feed_not_modified=result.feed_not_modified,
            feed_errors=result.feed_errors,
            database_migrated_from=migrated_from,
        )
    finally:
        db.close()
