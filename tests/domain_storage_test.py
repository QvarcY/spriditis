
import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from pathlib import Path
from tempfile import TemporaryDirectory

from spriditis.core.domains import DomainDiscovery, DomainRecord
from spriditis.core.projects import ResearchProject
from spriditis.core.run import ResearchRunResult
from spriditis.storage.database import Database


def project():
    return ResearchProject.model_validate(
        {
            "id": "storage_test",
            "name": "Storage test",
            "research_type": "product_market",
            "entity_type": "product",
            "keywords": ["product"],
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
        db = Database(Path(tmp) / "test.db")
        p = project()
        db.save_project(p)
        run_id = db.start_run(p)

        result = ResearchRunResult(project_id=p.id)
        result.domains = {
            "example.com": DomainRecord(
                domain="example.com",
                status="active",
                discovered_via="seed",
                relevance_score=1.0,
                pages_seen=3,
                entities_found=2,
            )
        }
        result.domain_discoveries = [
            DomainDiscovery(
                source_domain="example.com",
                target_domain="other.example",
                source_url="https://example.com",
                target_url="https://other.example/product",
                relevance_score=0.7,
                action="recorded",
            )
        ]

        db.save_domain_registry(p, run_id, result)
        rows = db.list_domains(p.id)
        db.close()

        assert len(rows) == 1
        assert rows[0]["domain"] == "example.com"
        assert rows[0]["pages_seen"] == 3

    print("DOMAIN STORAGE TEST OK")


if __name__ == "__main__":
    main()
