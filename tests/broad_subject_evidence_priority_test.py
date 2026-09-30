from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)

from spriditis.ai.fallback import FallbackProvider
from spriditis.config import AppSettings
from spriditis.core.entities import MarketEntity
from spriditis.core.projects import ResearchProject
from spriditis.crawler.coverage import ResearchCoverage
from spriditis.crawler.engine import ResearchCrawler
from spriditis.crawler.policy import text_relevance_score
from spriditis.search.fake import FakeSearchProvider
from spriditis.search.query import subject_focus_terms


project = ResearchProject.model_validate(
    {
        "id": "broad-subject-evidence-priority",
        "name": (
            "Opel Zafira 2005 cenas automa??n?m "
            "ar tehnisko apskati"
        ),
        "keywords": [
            "Opel",
            "Zafira",
            "2005",
            "cenas",
            "automa??n?m",
            "tehnisko",
            "apskati",
        ],
        "crawl": {
            "mode": "expedition",
            "max_domains": 4,
        },
        "search": {
            "provider": "none",
            "result_threshold": 35,
        },
        "analysis": {
            "ai_enabled": False,
            "ai_provider": "none",
            "required_evidence_terms": [
                "2005",
                "tehnisk",
                "apskat",
            ],
        },
    }
)

assert subject_focus_terms(project) == [
    "Opel",
    "Zafira",
]

wrong_url = (
    "https://example.test/msg/lv/transport/"
    "cars/opel/astra/example.html"
)
wrong_context = (
    "Opel Astra 2014 lab? tehnisk? st?vokl?"
)

right_url = (
    "https://example.test/msg/lv/transport/"
    "cars/opel/zafira/example.html"
)
right_context = (
    "Opel Zafira 2012 2.0D"
)

wrong_score = text_relevance_score(
    project,
    wrong_url,
    wrong_context,
)
right_score = text_relevance_score(
    project,
    right_url,
    right_context,
)

assert right_score > wrong_score, (
    wrong_score,
    right_score,
)

settings = AppSettings(
    gemini_api_key="",
    gemini_model="none",
    gemini_batch_size=10,
    gemini_requests_per_minute=5,
    gemini_max_retries=0,
    gemini_retry_base_seconds=1.0,
    db_path=Path("data/test.db"),
    legacy_db_path=None,
    report_dir=Path("reports"),
    smtp_host="",
    smtp_port=465,
    smtp_user="",
    smtp_app_password="",
    report_to="",
    send_email=False,
    user_agent="SpriditisTest/3.3",
    request_timeout_seconds=1,
)

crawler = ResearchCrawler(
    settings,
    project,
    FallbackProvider(),
    search_provider=FakeSearchProvider({}),
)

assert not crawler._promising_probe_link(
    wrong_url,
    wrong_context,
    wrong_score,
)

assert crawler._promising_probe_link(
    right_url,
    right_context,
    right_score,
)

coverage = ResearchCoverage.for_project(project)

wrong_entity = MarketEntity(
    title="Opel Astra, 2014",
    source_url=wrong_url,
    source_domain="example.test",
    description="Lab? tehnisk? st?vokl?",
    evidence=(
        "Opel Astra 2014. "
        "Lab? tehnisk? st?vokl?."
    ),
)

coverage.observe_entities(
    "example.test",
    [wrong_entity],
)

assert "example.test" not in coverage.productive_domains
assert "example.test" not in coverage.retained_domains

subject_only = MarketEntity(
    title="Opel Zafira, 2005",
    source_url=right_url,
    source_domain="example.test",
    description="P?rdod Opel Zafira",
    evidence="Opel Zafira 2005",
)

coverage.observe_entities(
    "example.test",
    [subject_only],
)

assert "example.test" not in coverage.productive_domains
assert "example.test" not in coverage.retained_domains

qualified = MarketEntity(
    title="Opel Zafira, 2005",
    source_url=right_url,
    source_domain="example.test",
    description="P?rdod Opel Zafira",
    evidence=(
        "Opel Zafira 2005. "
        "Tehnisk? apskate l?dz 2027."
    ),
    attributes={
        "inspection_until": "2027",
    },
)

coverage.observe_entities(
    "example.test",
    [qualified],
)

assert "example.test" in coverage.productive_domains
assert "example.test" in coverage.retained_domains

print("BROAD SUBJECT EVIDENCE PRIORITY TEST OK")
print(
    f"wrong_model_score={wrong_score} "
    f"subject_model_score={right_score}"
)
print("wrong_model_productive=False")
print("subject_without_constraints_productive=False")
print("qualified_subject_productive=True")
