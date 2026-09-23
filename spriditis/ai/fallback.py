from __future__ import annotations

from spriditis.core.entities import EntityEnrichment, MarketEntity
from spriditis.core.projects import ResearchProject

from .base import AIProvider


class FallbackProvider(AIProvider):
    def enrich(
        self,
        entity: MarketEntity,
        project: ResearchProject,
    ) -> EntityEnrichment:
        text = " ".join(
            [
                entity.title,
                entity.description,
                entity.evidence,
                entity.seller,
            ]
        ).lower()

        positive_hits = 0
        tags = []
        for keyword in project.keywords:
            key = keyword.strip().lower()
            if key and key in text:
                positive_hits += 1
                tags.append(keyword)

        negative_hits = 0
        for keyword in project.negative_keywords:
            key = keyword.strip().lower()
            if key and key in text:
                negative_hits += 1

        score = min(
            1.0,
            max(
                0.0,
                0.18 + positive_hits * 0.10 - negative_hits * 0.22,
            ),
        )
        relevant = score >= project.analysis.min_relevance_score

        category = "uncategorized"
        categories = project.analysis.categories

        # CraftIN presetam saglabājam saprotamu offline fallbacku.
        if "karbinas_dekori" in categories:
            if any(
                word in text
                for word in (
                    "kārbi",
                    "kastīt",
                    "dekor",
                    "rotājum",
                    "karte",
                    "balva",
                    "medaļ",
                    "uzrakst",
                    "plāksn",
                )
            ):
                category = "karbinas_dekori"
            elif any(
                word in text
                for word in (
                    "piekari",
                    "atslēgu",
                    "suvenīr",
                    "dāvana",
                    "dāvan",
                )
            ):
                category = "piekarini_davanas"
            else:
                category = "cits"
        elif categories:
            category = categories[0]

        attributes = {}
        desired = set(project.analysis.desired_attributes)

        if "personalization" in desired:
            attributes["personalization"] = any(
                word in text for word in ("personaliz", "grav", "vārdu", "vārds")
            )

        if "engraving_likelihood" in desired:
            attributes["engraving_likelihood"] = (
                0.9 if "grav" in text else min(0.2 + positive_hits * 0.08, 0.75)
            )

        if "materials" in desired:
            materials = []
            for material in ("koks", "bērzs", "ozols", "saplāksnis", "akrils"):
                if material in text:
                    materials.append(material)
            attributes["materials"] = materials

        if "audience" in desired:
            attributes["audience"] = ""

        return EntityEnrichment(
            is_relevant=relevant,
            category=category,
            confidence=min(0.35 + positive_hits * 0.08, 0.85),
            relevance_score=score,
            summary=entity.description[:500],
            tags=list(dict.fromkeys(tags))[:12],
            attributes=attributes,
            opportunity_notes="",
        )
