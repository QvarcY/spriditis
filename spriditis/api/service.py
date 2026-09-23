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
        crawler = ResearchCrawler(settings, project, ai)
        result = crawler.crawl()

        for entity in result.entities:
            db.upsert_entity(project, run_id, entity)

        db.save_domain_registry(project, run_id, result)
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
            database_migrated_from=migrated_from,
        )
    finally:
        db.close()
