from spriditis.core.projects import ResearchProject
from spriditis.crawler.discovery import DomainRegistry


def project(mode="discovery", max_domains=3):
    return ResearchProject.model_validate(
        {
            "id": "domain_test",
            "name": "Domain test",
            "research_type": "product_market",
            "entity_type": "product",
            "keywords": ["office chair"],
            "negative_keywords": [],
            "seed_urls": ["https://seed.example/products"],
            "crawl": {
                "mode": mode,
                "max_pages_total": 20,
                "max_pages_per_domain": 10,
                "max_domains": max_domains,
                "max_depth": 3,
                "delay_seconds": 0,
                "respect_robots": True,
                "external_link_threshold": 45,
            },
            "analysis": {
                "ai_enabled": False,
                "ai_provider": "none",
                "min_relevance_score": 0.35,
                "categories": ["chair"],
                "desired_attributes": [],
            },
        }
    )


def main():
    registry = DomainRegistry(project())
    registry.add_seed("https://seed.example/products")

    high, discovery = registry.observe_link(
        source_url="https://seed.example/products",
        target_url="https://chairs.example/office-chair",
        anchor_text="ergonomic office chair",
        raw_score=70,
    )
    assert high.status == "active"
    assert discovery.action == "activated"

    low, discovery = registry.observe_link(
        source_url="https://seed.example/products",
        target_url="https://unrelated.example/about",
        anchor_text="about",
        raw_score=10,
    )
    assert low.status == "candidate"
    assert discovery.reason == "below_threshold"

    blocked, discovery = registry.observe_link(
        source_url="https://seed.example/products",
        target_url="https://facebook.com/somepage",
        anchor_text="social",
        raw_score=90,
    )
    assert blocked.status == "blocked"
    assert discovery.reason == "blocked_host"

    domain_only = DomainRegistry(project(mode="domain", max_domains=1))
    domain_only.add_seed("https://seed.example/products")
    record, discovery = domain_only.observe_link(
        source_url="https://seed.example/products",
        target_url="https://chairs.example/office-chair",
        anchor_text="office chair",
        raw_score=90,
    )
    assert record.status == "candidate"
    assert discovery.reason == "domain_mode"

    print("DOMAIN REGISTRY TEST OK")


if __name__ == "__main__":
    main()
