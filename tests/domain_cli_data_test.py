
import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from pathlib import Path
from tempfile import TemporaryDirectory

from spriditis.core.domains import DomainRecord
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult
from spriditis.storage.database import Database


def project():
    return ResearchProject.model_validate(
        {
            "id": "cli_domain_test",
            "name": "CLI domain test",
            "research_type": "product_market",
            "entity_type": "product",
            "keywords": ["chair"],
            "negative_keywords": [],
            "seed_urls": ["https://example.com"],
            "analysis": {
                "ai_enabled": False,
                "ai_provider": "none",
                "categories": ["product"],
            },
        }
    )


def main():
    with TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "spriditis.db")
        p = project()
        db.save_project(p)
        rid = db.start_run(p)

        result = ResearchRunResult(project_id=p.id)
        result.domains = {
            "example.com": DomainRecord(
                domain="example.com",
                status="active",
                relevance_score=1.0,
                sitemap_status="found",
                sitemap_urls_found=42,
                pages_seen=2,
                entities_found=1,
                reason="seed",
            ),
            "other.example": DomainRecord(
                domain="other.example",
                status="candidate",
                relevance_score=0.3,
                reason="below_threshold",
                discovered_from_url="https://example.com/page",
            ),
        }

        db.save_domain_registry(p, rid, result)

        all_rows = db.list_domains(p.id)
        candidate_rows = db.list_domains(p.id, status="candidate")
        counts = db.domain_status_counts(p.id)
        db.close()

        assert len(all_rows) == 2
        assert len(candidate_rows) == 1
        assert candidate_rows[0]["reason"] == "below_threshold"
        assert counts["active"] == 1
        assert counts["candidate"] == 1

    print("DOMAIN CLI DATA TEST OK")


if __name__ == "__main__":
    main()
