from __future__ import annotations

import argparse
import json
from pathlib import Path

from spriditis.api.service import run_project
from spriditis.config import load_settings
from spriditis.core.projects import (
    PRESETS,
    TEMPLATE_CATALOG,
    load_project,
    project_from_preset,
    save_project,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sprīdītis 3.1 — universāls tirgus izpētes dzinējs"
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
    run.add_argument("--mode", choices=["domain", "discovery", "expedition"])
    run.add_argument("--no-ai", action="store_true")
    run.add_argument("--email", action="store_true")
    run.add_argument("--no-email", action="store_true")

    return parser


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

    if args.command == "run":
        settings = load_settings()
        project = load_project(Path(args.project))

        if args.max_pages is not None:
            data = project.model_dump()
            data["crawl"]["max_pages_total"] = args.max_pages
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

        print("🚀 Sprīdītis 3.1 sāk pētījumu")
        print(f"   Projekts: {project.name}")
        print(f"   ID: {project.id}")
        print(f"   Tips: {project.research_type}")
        print(f"   Režīms: {project.crawl.mode}")
        print(f"   Max lapas: {project.crawl.max_pages_total}")
        print(f"   Max domēni: {project.crawl.max_domains}")
        print(f"   AI: {ai_state}")
        print(f"   DB: {settings.db_path}")

        artifacts = run_project(
            settings,
            project,
            force_no_ai=args.no_ai,
            send_email=send_email,
        )

        print("")
        print("✅ Pētījums pabeigts.")
        print(f"   Run ID: {artifacts.run_id}")
        print(f"   Apmeklētas lapas: {artifacts.visited_pages}")
        print(f"   Atrasti objekti: {artifacts.entity_count}")
        print(f"   Domēni: {artifacts.domain_count}")
        print(f"   Atskaite: {artifacts.report_path.resolve()}")
        return 0

    return 2
