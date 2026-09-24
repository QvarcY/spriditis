from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator


ResearchType = Literal[
    "product_market",
    "price_monitoring",
    "competitor_research",
    "service_market",
    "trend_research",
]

CrawlMode = Literal["domain", "discovery", "expedition"]


class CrawlConfig(BaseModel):
    mode: CrawlMode = "domain"
    max_pages_total: int = Field(default=60, ge=1, le=100000)
    max_pages_per_domain: int = Field(default=50, ge=1, le=10000)
    max_domains: int = Field(default=1, ge=1, le=10000)
    max_depth: int = Field(default=4, ge=0, le=20)
    delay_seconds: float = Field(default=2.0, ge=0.0, le=60.0)
    respect_robots: bool = True
    external_link_threshold: int = Field(default=45, ge=0, le=100)
    discover_sitemaps: bool = True
    max_sitemap_urls_per_domain: int = Field(default=100, ge=0, le=5000)
    discover_feeds: bool = True
    probe_common_feed_paths: bool = False
    max_feeds_per_domain: int = Field(default=3, ge=0, le=20)
    max_feed_entries_per_feed: int = Field(default=50, ge=0, le=1000)
    diminishing_returns_window: int = Field(default=0, ge=0, le=10000)
    saturation_window: int = Field(default=0, ge=0, le=10000)


class SearchConfig(BaseModel):
    provider: Literal["none", "searxng"] = "none"
    max_queries: int = Field(default=4, ge=0, le=50)
    results_per_query: int = Field(default=8, ge=1, le=100)
    result_threshold: int = Field(default=35, ge=0, le=100)
    safesearch: Literal[0, 1, 2] = 1
    queries: list[str] = Field(default_factory=list)


class AnalysisConfig(BaseModel):
    ai_enabled: bool = True
    ai_provider: Literal["gemini", "none"] = "gemini"
    min_relevance_score: float = Field(default=0.35, ge=0.0, le=1.0)
    categories: list[str] = Field(default_factory=list)
    desired_attributes: list[str] = Field(default_factory=list)


class ResearchProject(BaseModel):
    id: str
    name: str
    description: str = ""

    research_type: ResearchType = "product_market"
    entity_type: str = "product"

    languages: list[str] = Field(default_factory=lambda: ["lv"])
    countries: list[str] = Field(default_factory=lambda: ["LV"])

    keywords: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)
    seed_urls: list[str] = Field(default_factory=list)

    crawl: CrawlConfig = Field(default_factory=CrawlConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,63}", value):
            raise ValueError(
                "Project id drīkst saturēt tikai a-z, 0-9, _ un -, 2-64 zīmes."
            )
        return value

    @field_validator("seed_urls")
    @classmethod
    def validate_seed_urls(cls, value: list[str]) -> list[str]:
        for url in value:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Nederīgs seed URL: {url}")
        return value

    def to_json(self) -> str:
        return json.dumps(self.model_dump(), ensure_ascii=False, indent=2)


IMPLEMENTED_RESEARCH_TYPES = {
    "product_market",
    "price_monitoring",
}


PRESETS: dict[str, dict] = {
    "craftin_gifts": {
        "id": "craftin_gifts",
        "name": "Latvijas personalizēto dāvanu tirgus",
        "description": (
            "CraftIN testa profils: personalizēti koka izstrādājumi, gravējumi, "
            "dekori, kārbiņas, piekariņi un dāvanas."
        ),
        "research_type": "product_market",
        "entity_type": "product",
        "languages": ["lv"],
        "countries": ["LV"],
        "keywords": [
            "personalizēts",
            "personalizēta",
            "gravējums",
            "gravēšana",
            "koka",
            "koks",
            "saplāksnis",
            "dekors",
            "dekorācija",
            "kārbiņa",
            "kastīte",
            "piekariņš",
            "dāvana",
            "balva",
            "medaļa",
            "uzraksts",
            "plāksne",
        ],
        "negative_keywords": [
            "ziņas",
            "vakance",
            "bezdarbs",
        ],
        "seed_urls": [
            "https://www.meistardarbs.lv/katalogs/koka-izstradajumi"
        ],
        "crawl": {
            "mode": "domain",
            "max_pages_total": 60,
            "max_pages_per_domain": 60,
            "max_domains": 1,
            "max_depth": 5,
            "delay_seconds": 2.0,
            "respect_robots": True,
            "external_link_threshold": 45,
        },
        "analysis": {
            "ai_enabled": True,
            "ai_provider": "gemini",
            "min_relevance_score": 0.35,
            "categories": [
                "karbinas_dekori",
                "piekarini_davanas",
                "cits",
            ],
            "desired_attributes": [
                "materials",
                "personalization",
                "engraving_likelihood",
                "audience",
            ],
        },
    },
    "generic_products": {
        "id": "generic_products",
        "name": "Universāls produktu tirgus pētījums",
        "description": (
            "Sagatave jebkuram produktu tirgum. Nomaini seed_urls, keywords, "
            "negative_keywords un kategorijas."
        ),
        "research_type": "product_market",
        "entity_type": "product",
        "languages": ["lv"],
        "countries": ["LV"],
        "keywords": ["produkts", "cena", "veikals"],
        "negative_keywords": [],
        "seed_urls": ["https://example.com"],
        "crawl": {
            "mode": "domain",
            "max_pages_total": 40,
            "max_pages_per_domain": 40,
            "max_domains": 1,
            "max_depth": 4,
            "delay_seconds": 2.0,
            "respect_robots": True,
            "external_link_threshold": 50,
        },
        "analysis": {
            "ai_enabled": True,
            "ai_provider": "gemini",
            "min_relevance_score": 0.35,
            "categories": ["uncategorized"],
            "desired_attributes": [],
        },
    },
}


TEMPLATE_CATALOG = [
    {
        "id": "product_market",
        "name": "Produktu tirgus izpēte",
        "implemented": True,
        "description": "Produkti, cenas, pārdevēji, kategorijas un tirgus pazīmes.",
    },
    {
        "id": "price_monitoring",
        "name": "Cenu monitorings",
        "implemented": True,
        "description": "Atkārtoti novērojumi un cenu vēsture tiem pašiem avotiem.",
    },
    {
        "id": "competitor_research",
        "name": "Konkurentu izpēte",
        "implemented": False,
        "description": "Plānots: uzņēmumi, piedāvājums, pozicionējums un kanāli.",
    },
    {
        "id": "service_market",
        "name": "Pakalpojumu tirgus izpēte",
        "implemented": False,
        "description": "Plānots: pakalpojumi, cenas, reģions un nosacījumi.",
    },
    {
        "id": "trend_research",
        "name": "Tendenču izpēte",
        "implemented": False,
        "description": "Plānots: izmaiņas laikā un jaunu tēmu pieaugums.",
    },
]


def project_from_preset(name: str) -> ResearchProject:
    if name not in PRESETS:
        raise KeyError(f"Nezināms presets: {name}")
    return ResearchProject.model_validate(PRESETS[name])


def load_project(path: Path) -> ResearchProject:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    project = ResearchProject.model_validate(data)
    if project.research_type not in IMPLEMENTED_RESEARCH_TYPES:
        raise NotImplementedError(
            f"Research type '{project.research_type}' ir definēts, "
            "bet šajā alpha vēl nav izpildāms."
        )
    return project


def save_project(project: ResearchProject, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(project.to_json() + "\n", encoding="utf-8")
