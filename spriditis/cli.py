from __future__ import annotations

import argparse
from pathlib import Path

from spriditis.api.service import run_project
from spriditis.config import load_settings
from spriditis.search.base import SearchProviderError
from spriditis.search.factory import build_search_provider
from spriditis.search.query import build_search_queries

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

        print("🚀 Sprīdītis 3.3.0-alpha.2 sāk pētījumu")
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
            f"   Domēni: {artifacts.observed_domain_count} novēroti / "
            f"{artifacts.activated_domain_count} aktivizēti / "
            f"{artifacts.crawled_domain_count} crawlēti"
        )
        for status in DOMAIN_STATUSES:
            print(
                f"      {status}: "
                f"{artifacts.domain_status_counts.get(status, 0)}"
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
