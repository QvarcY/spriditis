from __future__ import annotations

import json
import argparse
from pathlib import Path

from spriditis.api.service import run_project
from spriditis.config import load_settings
from spriditis.search.base import SearchProviderError
from spriditis.search.factory import build_search_provider
from spriditis.search.query import build_search_queries
from spriditis.storage.database import DEFAULT_STALE_AFTER_DAYS

from spriditis.core.projects import (
    PRESETS,
    TEMPLATE_CATALOG,
    load_project,
    project_from_preset,
    save_project,
)


DOMAIN_STATUSES = [
    "candidate",
    "active",
    "blocked",
    "rejected",
    "failed",
]


def _group_trace_discoveries(events: list[dict]) -> list[dict]:
    """Compact repeated discovery evidence without changing the raw audit."""
    groups: dict[tuple, dict] = {}

    for event in events:
        key = (
            event.get("action") or "",
            event.get("discovered_via") or "",
            event.get("target_domain") or "",
            event.get("reason") or "",
            event.get("provider") or "",
            event.get("query_text") or "",
        )
        group = groups.get(key)
        if group is None:
            group = dict(event)
            group["count"] = 0
            group["max_relevance_score"] = float(
                event.get("relevance_score") or 0.0
            )
            groups[key] = group

        group["count"] += 1
        group["max_relevance_score"] = max(
            group["max_relevance_score"],
            float(event.get("relevance_score") or 0.0),
        )

    return sorted(
        groups.values(),
        key=lambda row: (
            -int(row["count"]),
            row.get("target_domain") or "",
            row.get("action") or "",
            row.get("discovered_via") or "",
        ),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sprīdītis 3.3 — universāls tirgus izpētes dzinējs"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("templates", help="Parādīt pētījumu tipu katalogu")
    sub.add_parser("presets", help="Parādīt gatavos konfigurācijas presetus")

    create = sub.add_parser("create", help="Izveidot projekta JSON no preseta")
    create.add_argument("--preset", required=True, choices=sorted(PRESETS))
    create.add_argument("--output", required=True)

    validate = sub.add_parser("validate", help="Pārbaudīt projekta JSON")
    validate.add_argument("--project", required=True)

    run = sub.add_parser("run", help="Palaist tirgus pētījumu")
    run.add_argument("--project", required=True)
    run.add_argument("--max-pages", type=int)
    run.add_argument("--max-domains", type=int)
    run.add_argument("--max-pages-per-domain", type=int)
    run.add_argument("--search-provider", choices=["none", "searxng"])
    run.add_argument("--max-search-queries", type=int)
    run.add_argument("--mode", choices=["domain", "discovery", "expedition"])
    run.add_argument("--no-ai", action="store_true")
    run.add_argument("--email", action="store_true")
    run.add_argument("--no-email", action="store_true")

    queries = sub.add_parser("queries", help="Parādīt deterministisko Expedition search plānu")
    queries.add_argument("--project", required=True)

    search_check = sub.add_parser(
        "search-check",
        help="Pārbaudīt konfigurēto SearchProvider bez pilna crawl",
    )
    search_check.add_argument("--project", required=True)
    search_check.add_argument("--query")
    search_check.add_argument("--limit", type=int, default=5)

    domains = sub.add_parser("domains", help="Parādīt projekta Domain Registry")
    domains.add_argument("--project", required=True)
    domains.add_argument("--status", choices=DOMAIN_STATUSES)
    domains.add_argument(
        "--details",
        action="store_true",
        help="Parādīt arī pirmavotu un laika metadatus",
    )

    discoveries = sub.add_parser(
        "discoveries",
        help="Parādīt ārējo domēnu atklāšanas audita ierakstus",
    )
    discoveries.add_argument("--project", required=True)
    discoveries.add_argument(
        "--action",
        choices=["recorded", "activated", "blocked", "known"],
    )
    discoveries.add_argument("--limit", type=int, default=50)

    feeds = sub.add_parser(
        "feeds",
        help="Parādīt projekta RSS/Atom/JSON Feed stāvokli",
    )
    feeds.add_argument("--project", required=True)
    feeds.add_argument("--status")

    memory = sub.add_parser(
        "memory",
        help="Parādīt izskaidrojamu query un avotu Research Memory",
    )
    memory.add_argument("--project", required=True)
    memory.add_argument("--limit", type=int, default=10)
    memory.add_argument(
        "--stale-days",
        type=float,
        default=DEFAULT_STALE_AFTER_DAYS,
        help="Stale slieksnis dienās Research Memory freshness signālam",
    )

    explain = sub.add_parser(
        "explain",
        help="Izskaidrot, ko Sprīdītis zina par konkrētu domēnu",
    )
    explain.add_argument("--project", required=True)
    explain.add_argument("--domain", required=True)
    explain.add_argument("--limit", type=int, default=8)
    explain.add_argument(
        "--stale-days",
        type=float,
        default=DEFAULT_STALE_AFTER_DAYS,
        help="Stale slieksnis dienās Research Memory freshness signālam",
    )

    evidence_quality = sub.add_parser(
        "evidence-quality",
        help="Parādīt auditējamu extraction evidence kvalitātes kopsavilkumu",
    )
    evidence_quality.add_argument("--project", required=True)
    evidence_quality.add_argument(
        "--details",
        action="store_true",
        help="Parādīt arī katras entity evidence kopsavilkumu",
    )

    clusters = sub.add_parser(
        "clusters",
        help="Parādīt projekta canonical entity clusterus",
    )
    clusters.add_argument("--project", required=True)
    clusters.add_argument(
        "--details",
        action="store_true",
        help="Parādīt pilnus cluster/member identifikatorus",
    )

    explain_cluster = sub.add_parser(
        "explain-cluster",
        help="Izskaidrot vienu canonical entity clusteri",
    )
    explain_cluster.add_argument("--project", required=True)
    explain_cluster.add_argument("--cluster", required=True)

    merge_clusters = sub.add_parser(
        "merge-clusters",
        help="Explicit un auditējami sapludināt divus entity clusterus",
    )
    merge_clusters.add_argument("--project", required=True)
    merge_clusters.add_argument("--source", required=True)
    merge_clusters.add_argument("--target", required=True)

    cluster_merges = sub.add_parser(
        "cluster-merges",
        help="Parādīt explicit cluster merge audita ierakstus",
    )
    cluster_merges.add_argument("--project", required=True)
    cluster_merges.add_argument("--limit", type=int, default=50)

    review_queue = sub.add_parser(
        "review-queue",
        help="Parādīt neatrisinātos Entity Resolution gadījumus",
    )
    review_queue.add_argument("--project", required=True)
    review_queue.add_argument(
        "--kind",
        choices=["all", "ambiguous", "conflict"],
        default="all",
    )
    review_queue.add_argument("--limit", type=int, default=50)
    review_queue.add_argument(
        "--details",
        action="store_true",
        help="Parādīt pilnus cluster identifikatorus un signālus",
    )

    diff = sub.add_parser(
        "diff",
        help="Salīdzināt divus research run un parādīt jēgpilnas izmaiņas",
    )
    diff.add_argument("--project", required=True)
    diff.add_argument("--run-a", required=True, type=int)
    diff.add_argument("--run-b", required=True, type=int)
    diff.add_argument(
        "--details",
        action="store_true",
        help="Parādīt arī eventu before/after/evidence detaļas",
    )

    trace = sub.add_parser(
        "trace",
        help="Parādīt viena research run provenance pēdas",
    )
    trace.add_argument("--project", required=True)
    trace.add_argument("--run", required=True, type=int)
    trace.add_argument(
        "--full",
        action="store_true",
        help="Parādīt visus raw discovery eventus bez grupēšanas",
    )

    migrate = sub.add_parser(
        "migrate-db",
        help="Droši pārnest veco SQLite DB uz versiju-neitrālo DB",
    )
    migrate.add_argument("--from-db", required=True)
    migrate.add_argument("--to-db")
    migrate.add_argument("--force", action="store_true")

    return parser


def _print_domain_table(rows: list[dict], *, details: bool):
    print(
        f"{'DOMAIN':<30} {'STATUS':<10} {'SCORE':>6} "
        f"{'PAGES':>5} {'ENT':>4} {'ROBOTS':<8} "
        f"{'SITEMAP':<9} {'URLS':>4} {'REASON':<22}"
    )
    print("-" * 112)

    for row in rows:
        print(
            f"{row['domain'][:30]:<30} "
            f"{row['status']:<10} "
            f"{row['relevance_score']:>6.2f} "
            f"{row['pages_seen']:>5} "
            f"{row['entities_found']:>4} "
            f"{row['robots_status']:<8} "
            f"{row['sitemap_status']:<9} "
            f"{row['sitemap_urls_found']:>4} "
            f"{(row['reason'] or '-')[:22]:<22}"
        )

        if details:
            source = row["discovered_from_url"] or "-"
            print(f"    via={row['discovered_via']} source={source}")
            print(
                f"    first={row['first_seen']} "
                f"last={row['last_seen']} "
                f"crawled={row['last_crawled'] or '-'}"
            )


def main() -> int:
    args = _parser().parse_args()

    if args.command == "templates":
        for item in TEMPLATE_CATALOG:
            state = "GATAVS" if item["implemented"] else "PLĀNOTS"
            print(f"{item['id']:<22} [{state}] {item['name']}")
            print(f"  {item['description']}")
        return 0

    if args.command == "presets":
        for key, value in PRESETS.items():
            print(f"{key:<20} {value['name']}")
        return 0

    if args.command == "create":
        project = project_from_preset(args.preset)
        path = Path(args.output)
        save_project(project, path)
        print(f"✅ Projekts izveidots: {path.resolve()}")
        return 0

    if args.command == "validate":
        project = load_project(Path(args.project))
        print("✅ Projekts ir derīgs.")
        print(project.to_json())
        return 0


    if args.command == "queries":
        project = load_project(Path(args.project))
        queries = build_search_queries(project)
        if not queries:
            print("Projektam nav ģenerējamu search vaicājumu.")
            return 0
        print(f"Expedition query plāns ({len(queries)}):")
        for index, query in enumerate(queries, start=1):
            print(f"  {index:>2}. {query.query}  [{query.reason}]")
        return 0


    if args.command == "search-check":
        settings = load_settings()
        project = load_project(Path(args.project))
        try:
            provider = build_search_provider(settings, project)
        except ValueError as exc:
            print(f"❌ SearchProvider konfigurācijas kļūda: {exc}")
            return 2
        if provider is None:
            print("SearchProvider nav konfigurēts šim Expedition projektam.")
            return 2

        if args.query:
            query_text = args.query.strip()
        else:
            plan = build_search_queries(project)
            if not plan:
                print("Projektam nav neviena search vaicājuma provider pārbaudei.")
                return 2
            query_text = plan[0].query

        language = project.languages[0] if project.languages else "all"
        limit = max(1, min(args.limit, 20))
        print(f"🔎 SearchProvider pārbaude: {provider.name}")
        print(f"   Query: {query_text}")
        try:
            hits = provider.search(
                query_text,
                language=language,
                limit=limit,
                safesearch=project.search.safesearch,
            )
        except SearchProviderError as exc:
            print(f"❌ Provider pārbaude neizdevās: {exc}")
            print(f"   kind={exc.kind} retryable={exc.retryable} attempts={exc.attempts}")
            if exc.status_code is not None:
                print(f"   HTTP: {exc.status_code}")
            return 1

        print(f"✅ Provider atbildēja. Rezultāti: {len(hits)}")
        for index, hit in enumerate(hits, start=1):
            title = " ".join(hit.title.split())[:80] or "-"
            print(f"  {index:>2}. {title}")
            print(f"      {hit.url}")
        return 0

    if args.command == "discoveries":
        from spriditis.storage.database import Database

        settings = load_settings()
        project = load_project(Path(args.project))
        db = Database(
            settings.db_path,
            legacy_path=settings.legacy_db_path,
        )

        try:
            rows = db.list_domain_discoveries(
                project.id,
                action=args.action,
                limit=args.limit,
            )
            counts = db.discovery_action_counts(project.id)
        finally:
            db.close()

        if not rows:
            if args.action:
                print(
                    f"Nav discovery ierakstu ar darbību: "
                    f"{args.action}"
                )
            else:
                print("Discovery audit vēl nav ierakstu.")
            return 0

        print(
            f"{'RUN':>4} {'ACTION':<10} {'VIA':<15} {'SCORE':>6} "
            f"{'SOURCE':<22} {'TARGET':<25} {'REASON':<22}"
        )
        print("-" * 116)

        for row in rows:
            print(
                f"{row['run_id']:>4} "
                f"{row['action']:<10} "
                f"{row['discovered_via']:<15} "
                f"{row['relevance_score']:>6.2f} "
                f"{(row['source_domain'] or '-')[:22]:<22} "
                f"{row['target_domain'][:25]:<25} "
                f"{(row['reason'] or '-')[:22]:<22}"
            )
            print(f"     {row['target_url']}")
            if row.get("query_text"):
                print(f"     provider={row.get('provider') or '-'} query={row['query_text']}")

        print("")
        print(
            "Darbības: "
            + " · ".join(
                f"{action}={counts.get(action, 0)}"
                for action in ["activated", "recorded", "blocked", "known"]
            )
        )
        return 0


    if args.command == "feeds":
        from spriditis.storage.database import Database

        settings = load_settings()
        project = load_project(Path(args.project))
        db = Database(
            settings.db_path,
            legacy_path=settings.legacy_db_path,
        )

        try:
            rows = db.list_feeds(project.id, status=args.status)
        finally:
            db.close()

        if not rows:
            print("Šim projektam vēl nav saglabātu feed.")
            return 0

        print(
            f"{'TYPE':<9} {'STATUS':<13} {'DOMAIN':<28} "
            f"{'SEEN':>6} {'NEW':>6} {'LAST CHECK':<25}"
        )
        print("-" * 96)

        for row in rows:
            print(
                f"{row['feed_type']:<9} "
                f"{row['status']:<13} "
                f"{row['domain'][:28]:<28} "
                f"{row['entries_seen']:>6} "
                f"{row['new_entries']:>6} "
                f"{(row['last_checked'] or '-')[:25]:<25}"
            )
            print(f"    {row['feed_url']}")
            if row["last_error"]:
                print(f"    error={row['last_error']}")

        return 0


    if args.command == "memory":
        from spriditis.storage.database import Database

        settings = load_settings()
        project = load_project(Path(args.project))
        db = Database(
            settings.db_path,
            legacy_path=settings.legacy_db_path,
        )

        try:
            queries = db.query_memory(project.id, limit=args.limit)
            duplication = db.search_duplication_memory(
                project.id,
                limit=args.limit,
            )
            sources = db.source_profiles(
                project.id,
                limit=args.limit,
                stale_after_days=args.stale_days,
            )
        finally:
            db.close()

        print("🧠 Research Memory")
        print(f"   Projekts: {project.name} ({project.id})")
        print("")
        print("QUERY YIELD")
        if not queries:
            print("   Vēl nav query provenance datu.")
        else:
            print(
                f"{'YIELD%':>7} {'PROD':>4} {'NEW':>4} {'KNOWN':>5} "
                f"{'DOM':>4} {'EVT':>4} {'RUNS':>4} "
                f"{'PROVIDER':<10} QUERY"
            )
            print("-" * 122)
            for row in queries:
                print(
                    f"{row['productive_domain_rate'] * 100:>6.1f}% "
                    f"{row['productive_domains']:>4} "
                    f"{row['activated']:>4} "
                    f"{row['known']:>5} "
                    f"{row['unique_domains']:>4} "
                    f"{row['result_events']:>4} "
                    f"{row['runs']:>4} "
                    f"{(row['provider'] or '-')[:10]:<10} "
                    f"{row['query_text']}"
                )

        print("")
        print("SEARCH DUPLICATION")
        print(
            "   scope=normalized search URL across all queries in one run"
        )
        if duplication["runs"] == 0:
            print("   Vēl nav search run datu.")
        else:
            print(
                f"   TOTAL runs={duplication['runs']} "
                f"queries={duplication['queries']} "
                f"raw={duplication['raw_results']} "
                f"unique={duplication['unique_results']} "
                f"duplicates={duplication['duplicates']} "
                f"filtered={duplication['filtered_results']} "
                f"duplicate_rate={duplication['duplicate_rate']:.1%} "
                f"errors={duplication['provider_errors']}"
            )
            print(
                f"{'RUN':>5} {'RAW':>6} {'UNIQUE':>7} {'DUP':>5} "
                f"{'FILTER':>6} {'DUP%':>7} {'QUERY':>5} {'ERR':>4}"
            )
            print("-" * 57)
            for row in duplication["recent_runs"]:
                print(
                    f"{row['run_id']:>5} "
                    f"{row['raw_results']:>6} "
                    f"{row['unique_results']:>7} "
                    f"{row['duplicates']:>5} "
                    f"{row['filtered_results']:>6} "
                    f"{row['duplicate_rate'] * 100:>6.1f}% "
                    f"{row['queries']:>5} "
                    f"{row['provider_errors']:>4}"
                )

        print("")
        print("SOURCE PROFILES")
        print(
            f"   stale > {args.stale_days:g}d; "
            "basis=last_useful_at -> last_crawled -> last_seen"
        )
        if not sources:
            print("   Vēl nav avotu profilu.")
        else:
            print(
                f"{'DOMAIN':<30} {'STATE':<10} {'REL':>5} "
                f"{'RUNS':>4} {'PROD%':>6} {'PAGES':>5} "
                f"{'ENT':>4} {'YIELD':>7} {'OK%':>6} {'FEED':>4} "
                f"{'AGE':>7} {'FRESH':<6} {'BASIS':<6}"
            )
            print("-" * 130)
            for row in sources:
                age = row["stale_age_days"]
                age_text = "-" if age is None else f"{age:.1f}d"
                basis = {
                    "last_useful_at": "useful",
                    "last_crawled": "crawl",
                    "last_seen": "seen",
                }.get(row["stale_reference"], "-")
                print(
                    f"{row['domain'][:30]:<30} "
                    f"{row['status']:<10} "
                    f"{row['relevance_score']:>5.2f} "
                    f"{row['crawl_runs']:>4} "
                    f"{row['productive_run_rate'] * 100:>5.1f}% "
                    f"{row['pages_seen']:>5} "
                    f"{row['entities_found']:>4} "
                    f"{row['entity_yield']:>7.2f} "
                    f"{row['success_rate'] * 100:>5.1f}% "
                    f"{row['feed_count']:>4} "
                    f"{age_text:>7} "
                    f"{row['freshness']:<6} "
                    f"{basis:<6}"
                )
        return 0

    if args.command == "explain":
        from spriditis.crawler.policy import host_key
        from spriditis.storage.database import Database

        settings = load_settings()
        project = load_project(Path(args.project))
        domain = host_key(args.domain)
        db = Database(
            settings.db_path,
            legacy_path=settings.legacy_db_path,
        )

        try:
            explanation = db.explain_domain(
                project.id,
                domain,
                event_limit=args.limit,
                stale_after_days=args.stale_days,
            )
        finally:
            db.close()

        if explanation is None:
            print(f"Domēns nav Research Memory: {domain}")
            return 1

        row = explanation
        print(f"🧠 Explain domain: {row['domain']}")
        print(
            f"   status={row['status']} "
            f"relevance={row['relevance_score']:.2f} "
            f"via={row['discovered_via']} "
            f"reason={row['reason'] or '-'}"
        )
        print(
            f"   pages={row['pages_seen']} "
            f"entities={row['entities_found']} "
            f"entity_yield={row['entity_yield']:.2f}"
        )
        print(
            f"   visits={row['visit_count']} "
            f"ok={row['successful_visits']} "
            f"failed={row['failed_visits']} "
            f"success_rate={row['success_rate']:.1%}"
        )
        print(
            f"   crawl_runs={row['crawl_runs']} "
            f"productive_runs={row['productive_runs']} "
            f"productive_run_rate={row['productive_run_rate']:.1%} "
            f"observations={row['observation_count']}"
        )
        print(
            f"   robots={row['robots_status']} "
            f"sitemap={row['sitemap_status']} "
            f"feed_count={row['feed_count']}"
        )
        print(
            f"   first={row['first_seen']} "
            f"last={row['last_seen']} "
            f"crawled={row['last_crawled'] or '-'}"
        )
        stale_age = row["stale_age_days"]
        stale_age_text = "-" if stale_age is None else f"{stale_age:.1f}d"
        print(
            f"   freshness={row['freshness']} "
            f"age={stale_age_text} "
            f"threshold={row['stale_after_days']:g}d "
            f"basis={row['stale_reference']}"
        )
        print(
            f"   last_useful={row['last_useful_at'] or '-'} "
            f"last_feed_success={row['last_feed_success'] or '-'}"
        )

        if row["recent_discoveries"]:
            print("")
            print("DISCOVERY EVIDENCE")
            for event in row["recent_discoveries"]:
                print(
                    f"   run={event['run_id']} "
                    f"{event['action']} via={event['discovered_via']} "
                    f"score={event['relevance_score']:.2f} "
                    f"reason={event['reason'] or '-'}"
                )
                if event["query_text"]:
                    print(
                        f"      provider={event['provider'] or '-'} "
                        f"query={event['query_text']}"
                    )
                print(f"      {event['target_url']}")

        if row["recent_visits"]:
            print("")
            print("PAGE LINEAGE")
            for visit in row["recent_visits"]:
                status = (
                    str(visit["http_status"])
                    if visit["http_status"] is not None
                    else "-"
                )
                print(
                    f"   run={visit['run_id']} "
                    f"{visit['source_type']:<15} "
                    f"depth={visit['depth']} "
                    f"http={status} "
                    f"outcome={visit['outcome']}"
                )
                print(f"      {visit['final_url']}")

        if row["feeds"]:
            print("")
            print("FEEDS")
            for feed in row["feeds"]:
                print(
                    f"   {feed['feed_type']} {feed['status']} "
                    f"seen={feed['entries_seen']} new={feed['new_entries']}"
                )
                print(f"      {feed['feed_url']}")
        return 0

    if args.command == "evidence-quality":
        from spriditis.storage.database import Database

        settings = load_settings()
        project = load_project(Path(args.project))
        db = Database(
            settings.db_path,
            legacy_path=settings.legacy_db_path,
        )
        try:
            summary = db.project_evidence_quality(project.id)
        finally:
            db.close()

        if summary["entity_count"] == 0:
            print("Projektam vēl nav entity evidence datu.")
            return 0

        bands = summary["confidence_bands"]
        print(f"EVIDENCE QUALITY · {project.name}")
        print(
            f"   entities={summary['entity_count']} "
            f"with_evidence={summary['entities_with_evidence']} "
            f"without_evidence={summary['entities_without_evidence']}"
        )
        print(
            f"   facts={summary['evidence_fact_count']} "
            f"supported_current={summary['supported_field_count']}"
        )
        print(
            f"   confidence: high={bands['high']} "
            f"medium={bands['medium']} low={bands['low']}"
        )

        if summary["methods"]:
            print("")
            print("EXTRACTION METHODS")
            for method, count in summary["methods"].items():
                print(f"   {method}: {count}")

        def print_field_counts(title: str, rows: list[dict]):
            if not rows:
                return
            print("")
            print(title)
            for row in rows:
                print(f"   {row['field']}: {row['count']}")

        print_field_counts(
            "LOW CONFIDENCE FIELDS",
            summary["low_confidence_fields"],
        )
        print_field_counts(
            "MISSING EVIDENCE",
            summary["missing_evidence_fields"],
        )
        print_field_counts(
            "MISMATCHED / STALE EVIDENCE",
            summary["mismatched_evidence_fields"],
        )
        print_field_counts(
            "DEFAULT / INFERRED FIELDS",
            summary["default_fields"],
        )

        if args.details:
            print("")
            print("ENTITIES")
            for item in summary["entities"]:
                bands = item["confidence_bands"]
                print(
                    f"   {item['source_domain'] or '-'} "
                    f"{item['title']}"
                )
                print(
                    f"      supported={item['supported_field_count']}/"
                    f"{item['field_count']} "
                    f"high={bands['high']} "
                    f"medium={bands['medium']} "
                    f"low={bands['low']}"
                )
                if item["weakest_fields"]:
                    weak = ", ".join(
                        f"{field['field']}={field['confidence']:.2f}"
                        for field in item["weakest_fields"]
                    )
                    print(f"      weakest={weak}")
                if item["missing_evidence_fields"]:
                    print(
                        "      missing="
                        + ", ".join(item["missing_evidence_fields"])
                    )
                if item["mismatched_evidence_fields"]:
                    mismatch = ", ".join(
                        row["field"]
                        for row in item["mismatched_evidence_fields"]
                    )
                    print(f"      mismatched={mismatch}")
                print(f"      {item['source_url']}")
        return 0

    if args.command == "clusters":
        from spriditis.storage.database import Database

        settings = load_settings()
        project = load_project(Path(args.project))
        db = Database(
            settings.db_path,
            legacy_path=settings.legacy_db_path,
        )
        try:
            rows = db.entity_clusters(project.id)
        finally:
            db.close()

        if not rows:
            print("Projektam vēl nav canonical entity clusteru.")
            return 0

        print(
            f"{'CLUSTER':<20} {'TYPE':<10} {'MEM':>4} "
            f"{'SRC':>3} TITLE"
        )
        print("-" * 100)
        for row in rows:
            short_key = row["cluster_key"][:18] + "..."
            print(
                f"{short_key:<20} "
                f"{row['entity_type']:<10} "
                f"{row['member_count']:>4} "
                f"{row['source_count']:>3} "
                f"{row['canonical_title'][:55]}"
            )
            if args.details:
                print(f"   cluster_key={row['cluster_key']}")
                for member in row["members"]:
                    print(
                        f"      {member['source_domain'] or '-'} "
                        f"{member['title'][:55]}"
                    )
                    print(
                        f"         entity_key={member['entity_key']} "
                        f"reason={member['match_reason']}"
                    )
        return 0

    if args.command == "explain-cluster":
        from spriditis.storage.database import Database

        settings = load_settings()
        project = load_project(Path(args.project))
        db = Database(
            settings.db_path,
            legacy_path=settings.legacy_db_path,
        )
        try:
            info = db.explain_entity_cluster(
                project.id,
                args.cluster,
            )
        finally:
            db.close()

        if info is None:
            print(
                f"Canonical cluster nav atrasts projektā "
                f"{project.id}: {args.cluster}"
            )
            return 1

        print(
            f"CLUSTER {info['cluster_key']} "
            f"[{info['status']}]"
        )
        print(
            f"   type={info['entity_type']} "
            f"title={info['canonical_title']}"
        )
        print(
            f"   members={info['member_count']} "
            f"sources={info['source_count']} "
            f"observations={info['observation_count']}"
        )
        print(
            f"   first={info['first_seen']} "
            f"last={info['last_seen']}"
        )

        if info["merged_into_cluster_key"]:
            print(
                f"   merged_into="
                f"{info['merged_into_cluster_key']}"
            )
            print(f"   merged_at={info['merged_at']}")

        if info["identity_signals"]:
            print("")
            print("IDENTITY SIGNALS")
            for key, values in info["identity_signals"].items():
                print(f"   {key}: {', '.join(values)}")

        print("")
        print(f"MEMBERS ({len(info['members'])})")
        for member in info["members"]:
            price = (
                f"{member['last_price']} {member['currency']}"
                if member["last_price"] is not None
                else "-"
            )
            print(
                f"   {member['source_domain'] or '-'} "
                f"{member['title']} · {price}"
            )
            print(
                f"      entity={member['entity_key']} "
                f"reason={member['match_reason']}"
            )
            if member["attributes"]:
                identity = []
                for key in (
                    "gtin",
                    "brand",
                    "manufacturer",
                    "model",
                    "mpn",
                    "sku",
                ):
                    value = member["attributes"].get(key)
                    if value not in (None, ""):
                        identity.append(f"{key}={value}")
                if identity:
                    print("      identity=" + " · ".join(identity))

            if member["field_evidence"]:
                print("      FIELD EVIDENCE")
                for field, fact in sorted(
                    member["field_evidence"].items()
                ):
                    method = fact.get("extraction_method") or "-"
                    confidence = float(fact.get("confidence") or 0.0)
                    evidence = fact.get("evidence") or "-"
                    print(
                        f"         {field}: "
                        f"method={method} "
                        f"confidence={confidence:.2f} "
                        f"evidence={evidence}"
                    )

            quality = member["evidence_quality"]
            bands = quality["confidence_bands"]
            print(
                f"      EVIDENCE QUALITY "
                f"supported={quality['supported_field_count']}/"
                f"{quality['field_count']} "
                f"high={bands['high']} "
                f"medium={bands['medium']} "
                f"low={bands['low']}"
            )
            if quality["weakest_fields"]:
                weak = ", ".join(
                    f"{item['field']}={item['confidence']:.2f}"
                    for item in quality["weakest_fields"]
                )
                print(f"         weakest={weak}")
            if quality["missing_evidence_fields"]:
                print(
                    "         missing="
                    + ", ".join(quality["missing_evidence_fields"])
                )
            if quality["mismatched_evidence_fields"]:
                print(
                    "         mismatched="
                    + ", ".join(
                        item["field"]
                        for item in quality["mismatched_evidence_fields"]
                    )
                )

            print(
                f"      observations="
                f"{len(member['observations'])}"
            )
            for obs in member["observations"]:
                obs_price = (
                    f"{obs['price']} {obs['currency']}"
                    if obs["price"] is not None
                    else "-"
                )
                print(
                    f"         run={obs['run_id']} "
                    f"{obs['observed_at']} · {obs_price}"
                )
            print(f"      {member['source_url']}")

        print("")
        print(
            f"RESOLUTION EVENTS "
            f"({len(info['resolution_events'])})"
        )
        for event in info["resolution_events"]:
            print(
                f"   #{event['id']} "
                f"{event['decision']} "
                f"reason={event['reason']}"
            )
            signals = (
                event["matched_signals"]
                + event["supporting_signals"]
                + event["conflicting_signals"]
            )
            if signals:
                print("      signals=" + ", ".join(signals))

        print("")
        print(f"MERGE EVENTS ({len(info['merge_events'])})")
        for event in info["merge_events"]:
            print(
                f"   #{event['id']} "
                f"{event['decision']} "
                f"reason={event['reason']}"
            )
            print(
                f"      {event['source_cluster_key']} -> "
                f"{event['target_cluster_key']}"
            )
            signals = (
                event["matched_signals"]
                + event["conflicting_signals"]
            )
            if signals:
                print("      signals=" + ", ".join(signals))

        print("")
        print(
            f"REVIEW ITEMS ({len(info['review_items'])})"
        )
        for item in info["review_items"]:
            print(
                f"   #{item['event_id']} "
                f"{item['decision']} "
                f"reason={item['reason']}"
            )
            if item["candidate_cluster_keys"]:
                print(
                    "      candidates="
                    + ", ".join(item["candidate_cluster_keys"])
                )
            if item["conflict_cluster_keys"]:
                print(
                    "      conflicts="
                    + ", ".join(item["conflict_cluster_keys"])
                )

        return 0

    if args.command == "merge-clusters":
        from spriditis.storage.database import Database

        settings = load_settings()
        project = load_project(Path(args.project))
        db = Database(
            settings.db_path,
            legacy_path=settings.legacy_db_path,
        )
        try:
            event = db.merge_entity_clusters(
                project.id,
                args.source,
                args.target,
            )
        finally:
            db.close()

        print(
            f"Cluster merge: {event['decision']} "
            f"reason={event['reason']}"
        )
        print(f"   source={event['source_cluster_key']}")
        print(f"   target={event['target_cluster_key']}")
        if event["matched_signals"]:
            print(
                "   matched="
                + ", ".join(event["matched_signals"])
            )
        if event["conflicting_signals"]:
            print(
                "   conflicts="
                + ", ".join(event["conflicting_signals"])
            )
        print(
            f"   source_members={event['source_member_count']} "
            f"target_members={event['target_member_count']} "
            f"merged_members={event['merged_member_count']}"
        )
        return 0 if event["decision"] == "merged" else 2

    if args.command == "cluster-merges":
        from spriditis.storage.database import Database

        settings = load_settings()
        project = load_project(Path(args.project))
        db = Database(
            settings.db_path,
            legacy_path=settings.legacy_db_path,
        )
        try:
            rows = db.entity_cluster_merge_events(
                project.id,
                limit=args.limit,
            )
        finally:
            db.close()

        if not rows:
            print("Cluster merge audit vēl nav ierakstu.")
            return 0

        for row in rows:
            print(
                f"#{row['id']} {row['decision']:<8} "
                f"reason={row['reason']}"
            )
            print(
                f"   {row['source_cluster_key'][:20]}... -> "
                f"{row['target_cluster_key'][:20]}..."
            )
            if row["matched_signals"]:
                print(
                    "   matched="
                    + ", ".join(row["matched_signals"])
                )
            if row["conflicting_signals"]:
                print(
                    "   conflicts="
                    + ", ".join(row["conflicting_signals"])
                )
        return 0

    if args.command == "review-queue":
        from spriditis.storage.database import Database

        settings = load_settings()
        project = load_project(Path(args.project))
        db = Database(
            settings.db_path,
            legacy_path=settings.legacy_db_path,
        )
        try:
            rows = db.entity_resolution_review_queue(
                project.id,
                kind=args.kind,
                limit=args.limit,
            )
        finally:
            db.close()

        if not rows:
            print("Entity Resolution review queue ir tukša.")
            return 0

        print(
            f"{'ID':>4} {'KIND':<10} {'DOMAIN':<22} "
            f"{'TITLE':<42} {'CAND':>4} {'CONF':>4}"
        )
        print("-" * 96)

        for row in rows:
            kind = (
                "ambiguous"
                if row["decision"] == "deferred_ambiguous"
                else "conflict"
            )
            print(
                f"{row['event_id']:>4} "
                f"{kind:<10} "
                f"{row['source_domain'][:22]:<22} "
                f"{row['title'][:42]:<42} "
                f"{len(row['candidate_cluster_keys']):>4} "
                f"{len(row['conflict_cluster_keys']):>4}"
            )
            print(
                f"     source_cluster="
                f"{row['selected_cluster_key'][:24]}..."
            )

            if args.details:
                print(f"     entity_key={row['entity_key']}")
                print(
                    f"     source_cluster="
                    f"{row['selected_cluster_key']}"
                )
                if row["candidate_cluster_keys"]:
                    print("     candidates:")
                    for key in row["candidate_cluster_keys"]:
                        print(f"        {key}")
                if row["conflict_cluster_keys"]:
                    print("     conflicts:")
                    for key in row["conflict_cluster_keys"]:
                        print(f"        {key}")
                signals = (
                    row["matched_signals"]
                    + row["supporting_signals"]
                    + row["conflicting_signals"]
                )
                if signals:
                    print("     signals=" + ", ".join(signals))
                print(f"     source={row['source_url']}")

        print("")
        print(
            "Risināšanai izmanto: "
            "python -m spriditis.cli merge-clusters "
            "--project <fails> --source <source_cluster> "
            "--target <candidate_cluster>"
        )
        return 0

    if args.command == "diff":
        from spriditis.storage.database import Database

        settings = load_settings()
        project = load_project(Path(args.project))
        db = Database(
            settings.db_path,
            legacy_path=settings.legacy_db_path,
        )
        try:
            try:
                diff = db.compare_runs(
                    project.id,
                    args.run_a,
                    args.run_b,
                )
            except ValueError as exc:
                print(str(exc))
                return 1
        finally:
            db.close()

        before_run = diff["before_run"]
        after_run = diff["after_run"]
        counts = diff["counts"]

        print(
            f"CHANGE DIFF · {project.name} · "
            f"run #{before_run['id']} → #{after_run['id']}"
        )
        print(
            f"   entities={before_run['entity_count']}→"
            f"{after_run['entity_count']} · "
            f"clusters={before_run['cluster_count']}→"
            f"{after_run['cluster_count']} · "
            f"domains={before_run['domain_count']}→"
            f"{after_run['domain_count']}"
        )
        basis = diff["comparison_basis"]
        print(
            f"   basis=entities:{basis['entity_facts']} + "
            f"domains:{basis['domain_health']} + "
            f"identity:{basis['identity']}"
        )
        print(
            "   "
            + " · ".join(
                (
                    f"new={counts['NEW_ENTITY']}",
                    f"disappeared={counts['ENTITY_DISAPPEARED']}",
                    f"price_drop={counts['PRICE_DROP']}",
                    f"price_increase={counts['PRICE_INCREASE']}",
                    f"seller_changed={counts['SELLER_CHANGED']}",
                    f"description_changed={counts['DESCRIPTION_CHANGED']}",
                    f"image_changed={counts['IMAGE_CHANGED']}",
                    f"source_changed={counts['SOURCE_CHANGED']}",
                    f"domain_failed={counts['DOMAIN_FAILED']}",
                    f"domain_recovered={counts['DOMAIN_RECOVERED']}",
                )
            )
        )

        if not diff["events"]:
            print("")
            print("Nozīmīgas izmaiņas nav atrastas.")
            return 0

        print("")
        print(f"CHANGES ({len(diff['events'])})")
        for event in diff["events"]:
            print(
                f"   {event['change_type']:<20} "
                f"{event['title'] or '-'}"
            )
            if event["source_domain"]:
                print(
                    f"      source={event['source_domain']} "
                    f"{event['source_url']}"
                )
            if event["change_type"] in (
                "PRICE_DROP",
                "PRICE_INCREASE",
            ):
                old = event["before"]
                new = event["after"]
                print(
                    f"      {old['price']} {old['currency']} → "
                    f"{new['price']} {new['currency']}"
                )
            elif event["change_type"] in (
                "SELLER_CHANGED",
                "DESCRIPTION_CHANGED",
                "IMAGE_CHANGED",
            ):
                field = event["evidence"]["field"]
                old_value = event["before"].get(field)
                new_value = event["after"].get(field)
                print(
                    f"      {field}: "
                    f"{str(old_value)[:100]} → {str(new_value)[:100]}"
                )
            elif event["change_type"] in (
                "DOMAIN_FAILED",
                "DOMAIN_RECOVERED",
            ):
                print(
                    f"      domain={event['source_domain']} "
                    f"{event['before']['state']} → "
                    f"{event['after']['state']}"
                )
            if args.details:
                print(
                    "      before="
                    + json.dumps(
                        event["before"],
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
                print(
                    "      after="
                    + json.dumps(
                        event["after"],
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
                print(
                    "      evidence="
                    + json.dumps(
                        event["evidence"],
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                )
        return 0

    if args.command == "trace":
        from spriditis.storage.database import Database

        settings = load_settings()
        project = load_project(Path(args.project))
        db = Database(
            settings.db_path,
            legacy_path=settings.legacy_db_path,
        )

        try:
            trace = db.trace_run(project.id, args.run)
        finally:
            db.close()

        if trace is None:
            print(f"Run nav atrasts projektā {project.id}: {args.run}")
            return 1

        run = trace["run"]
        print(f"🧭 Trace run #{run['id']} · {project.name}")
        print(
            f"   started={run['started_at']} "
            f"finished={run['finished_at'] or '-'}"
        )
        print(
            f"   pages={run['visited_pages']} "
            f"failed={run['failed_pages']} "
            f"entities={run['entities_found']} "
            f"domains={run['domains_found']}"
        )
        print(
            f"   search={run['search_results_unique']} unique / "
            f"{run['search_domains_activated']} activated · "
            f"feed_new={run['feed_entries_new']} · "
            f"feed_304={run['feed_not_modified']}"
        )

        print("")
        print(
            f"ADAPTIVE DECISIONS "
            f"({len(trace['adaptive_decisions'])})"
        )
        for item in trace["adaptive_decisions"]:
            print(
                f"   #{item['sequence']:<3} "
                f"{item['stage']:<24} "
                f"{item['decision']:<18} "
                f"{item['target'][:72]}"
            )
            signals = item["signals"]
            if signals:
                signal_text = " · ".join(
                    f"{key}={value}"
                    for key, value in signals.items()
                )
                print(f"      {signal_text}")

        print("")
        print(f"PAGE VISITS ({len(trace['page_visits'])})")
        for visit in trace["page_visits"]:
            status = (
                str(visit["http_status"])
                if visit["http_status"] is not None
                else "-"
            )
            print(
                f"   {visit['source_type']:<15} "
                f"depth={visit['depth']} "
                f"http={status} "
                f"{visit['outcome']}"
            )
            print(f"      {visit['final_url']}")
            if visit["source_url"]:
                print(f"      from={visit['source_url']}")

        print("")
        if args.full:
            print(f"DISCOVERY EVENTS ({len(trace['discoveries'])} raw)")
            for event in trace["discoveries"]:
                print(
                    f"   {event['action']:<10} "
                    f"via={event['discovered_via']:<15} "
                    f"{event['target_domain']} "
                    f"score={event['relevance_score']:.2f}"
                )
                if event["query_text"]:
                    print(
                        f"      provider={event['provider'] or '-'} "
                        f"query={event['query_text']}"
                    )
        else:
            grouped = _group_trace_discoveries(trace["discoveries"])
            print(
                f"DISCOVERY EVENTS "
                f"({len(trace['discoveries'])} raw / "
                f"{len(grouped)} grouped)"
            )
            for event in grouped:
                print(
                    f"   x{event['count']:<4} "
                    f"{event['action']:<10} "
                    f"via={event['discovered_via']:<15} "
                    f"{event['target_domain']} "
                    f"max_score={event['max_relevance_score']:.2f}"
                )
                if event["query_text"]:
                    print(
                        f"      provider={event['provider'] or '-'} "
                        f"query={event['query_text']}"
                    )
                if event["reason"]:
                    print(f"      reason={event['reason']}")

        print("")
        print(
            f"ENTITY RESOLUTION "
            f"({len(trace['entity_resolution_events'])})"
        )
        for event in trace["entity_resolution_events"]:
            print(
                f"   {event['decision']:<20} "
                f"reason={event['reason']:<28} "
                f"compared={event['compared_entities']}"
            )
            print(
                f"      entity={event['entity_key'][:20]}... "
                f"cluster={event['selected_cluster_key'][:20]}..."
            )
            if event["candidate_cluster_keys"]:
                print(
                    "      candidates="
                    + ", ".join(
                        key[:16] + "..."
                        for key in event["candidate_cluster_keys"]
                    )
                )
            if event["conflict_cluster_keys"]:
                print(
                    "      conflicts="
                    + ", ".join(
                        key[:16] + "..."
                        for key in event["conflict_cluster_keys"]
                    )
                )
            signals = (
                event["matched_signals"]
                + event["supporting_signals"]
                + event["conflicting_signals"]
            )
            if signals:
                print("      signals=" + ", ".join(signals))

        print("")
        print(f"OBSERVATIONS ({len(trace['observations'])})")
        for obs in trace["observations"]:
            price = (
                f"{obs['price']} {obs['currency']}"
                if obs["price"] is not None
                else "-"
            )
            print(
                f"   {obs['entity_type'] or '-'} "
                f"{obs['title'][:70]} · {price}"
            )
            print(
                f"      method={obs['extraction_method'] or '-'} "
                f"relevance={obs['relevance_score']:.2f}"
            )
            if obs["cluster_key"]:
                print(
                    f"      cluster={obs['cluster_key'][:20]}... "
                    f"reason={obs['cluster_match_reason'] or '-'}"
                )
            print(f"      {obs['source_url']}")
        return 0

    if args.command == "migrate-db":
        from spriditis.storage.database import Database, sqlite_backup

        settings = load_settings()
        source = Path(args.from_db)
        target = Path(args.to_db) if args.to_db else settings.db_path

        sqlite_backup(
            source,
            target,
            overwrite=args.force,
        )

        # Opening the copied DB applies all current schema migrations.
        db = Database(target)
        try:
            version = db.schema_version()
        finally:
            db.close()

        print("✅ Datubāze pārnesta.")
        print(f"   Avots: {source.resolve()}")
        print(f"   Mērķis: {target.resolve()}")
        print(f"   Schema version: {version}")
        return 0

    if args.command == "domains":
        from spriditis.storage.database import Database

        settings = load_settings()
        project = load_project(Path(args.project))
        db = Database(
            settings.db_path,
            legacy_path=settings.legacy_db_path,
        )

        try:
            rows = db.list_domains(
                project.id,
                status=args.status,
            )
            counts = db.domain_status_counts(project.id)
        finally:
            db.close()

        if not rows:
            if args.status:
                print(f"Nav domēnu ar statusu: {args.status}")
            else:
                print("Domain Registry vēl nav ierakstu.")
            return 0

        _print_domain_table(rows, details=args.details)

        print("")
        observed = sum(counts.values())
        crawled = sum(1 for row in rows if row["pages_seen"] > 0) if not args.status else None

        if args.status:
            print(f"Parādīti: {len(rows)} ({args.status})")
        else:
            print(f"Novēroti domēni: {observed}")
            print(
                "Statusi: "
                + " · ".join(
                    f"{status}={counts.get(status, 0)}"
                    for status in DOMAIN_STATUSES
                )
            )

        return 0

    if args.command == "run":
        settings = load_settings()
        project = load_project(Path(args.project))

        if args.max_pages is not None:
            data = project.model_dump()
            data["crawl"]["max_pages_total"] = args.max_pages
            project = project.model_validate(data)

        if args.max_domains is not None:
            data = project.model_dump()
            data["crawl"]["max_domains"] = args.max_domains
            project = project.model_validate(data)

        if args.max_pages_per_domain is not None:
            data = project.model_dump()
            data["crawl"]["max_pages_per_domain"] = args.max_pages_per_domain
            project = project.model_validate(data)

        if args.search_provider is not None:
            data = project.model_dump()
            data["search"]["provider"] = args.search_provider
            project = project.model_validate(data)

        if args.max_search_queries is not None:
            data = project.model_dump()
            data["search"]["max_queries"] = args.max_search_queries
            project = project.model_validate(data)

        if args.mode is not None:
            data = project.model_dump()
            data["crawl"]["mode"] = args.mode
            if args.mode == "domain":
                data["crawl"]["max_domains"] = 1
            project = project.model_validate(data)

        send_email = settings.send_email
        if args.email:
            send_email = True
        if args.no_email:
            send_email = False

        ai_state = (
            "fallback"
            if args.no_ai
            or not project.analysis.ai_enabled
            or not settings.gemini_api_key
            else f"{project.analysis.ai_provider}/{settings.gemini_model}"
        )

        print("🚀 Sprīdītis 3.3.0-alpha.8 sāk pētījumu")
        print(f"   Projekts: {project.name}")
        print(f"   ID: {project.id}")
        print(f"   Tips: {project.research_type}")
        print(f"   Režīms: {project.crawl.mode}")
        print(f"   Max lapas: {project.crawl.max_pages_total}")
        print(f"   Max domēni: {project.crawl.max_domains}")
        print(f"   AI: {ai_state}")
        if project.crawl.mode == "expedition":
            print(f"   SearchProvider: {project.search.provider}")
            print(f"   Max search queries: {project.search.max_queries}")
        print(f"   DB: {settings.db_path}")

        artifacts = run_project(
            settings,
            project,
            force_no_ai=args.no_ai,
            send_email=send_email,
        )

        if artifacts.database_migrated_from:
            print(
                f"🗃️ Vecā DB droši pārnesta no: "
                f"{artifacts.database_migrated_from}"
            )

        print("")
        print("✅ Pētījums pabeigts.")
        print(f"   Run ID: {artifacts.run_id}")
        print(f"   Apmeklētas lapas: {artifacts.visited_pages}")
        print(f"   Atrasti objekti: {artifacts.entity_count}")
        print(
            f"   STOP_REASON: {artifacts.stop_reason or '-'} "
            f"(diminishing={artifacts.diminishing_returns_streak}, "
            f"saturation={artifacts.saturation_streak})"
        )
        print(
            f"   Diversity: {artifacts.diversity_penalties_applied} "
            f"priority penalties / "
            f"{artifacts.diversity_domain_count} domēni"
        )
        print(
            f"   Adaptive decisions: "
            f"{artifacts.adaptive_decision_count}"
        )
        print(
            f"   Domēni: {artifacts.observed_domain_count} novēroti / "
            f"{artifacts.activated_domain_count} aktivizēti / "
            f"{artifacts.crawled_domain_count} crawlēti"
        )
        for status in DOMAIN_STATUSES:
            print(
                f"      {status}: "
                f"{artifacts.domain_status_counts.get(status, 0)}"
            )
        if project.crawl.discover_feeds:
            print(
                f"   Feed: {artifacts.feed_candidates_seen} kandidāti / "
                f"{artifacts.feeds_found} atrasti / "
                f"{artifacts.feed_entries_seen} ieraksti / "
                f"{artifacts.feed_entries_new} jauni / "
                f"{artifacts.feed_not_modified} nemainīti / "
                f"{artifacts.feed_errors} kļūdas"
            )
        if project.crawl.mode == "expedition":
            print(
                f"   Search: {artifacts.search_queries_issued} vaicājumi / "
                f"{artifacts.search_results_seen} raw rezultāti / "
                f"{artifacts.search_results_unique} unikāli / "
                f"{artifacts.search_results_duplicates} dublikāti / "
                f"{artifacts.search_domains_activated} aktivizēti domēni / "
                f"{artifacts.search_provider_errors} kļūdas"
            )
        print(f"   Atskaite: {artifacts.report_path.resolve()}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
