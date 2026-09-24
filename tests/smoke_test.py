
import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from pathlib import Path

from spriditis.ai.fallback import FallbackProvider
from spriditis.core.projects import load_project
from spriditis.extraction.engine import extract_entities


def main():
    project = load_project(Path("projects/craftin_gifts.json"))

    html = """
    <html>
      <head><meta property="og:image" content="/img/test.jpg"></head>
      <body>
        <h1>Personalizēta koka dāvanu kastīte ar gravējumu</h1>
        <div>18.27 €</div>
        <div>Preces apraksts:</div>
        <p>Bērza saplākšņa kastīte ar gravējumu un personalizāciju.</p>
        <div>Piegādes nosacījumi:</div><p>Omniva</p>
        <div><h3>Informācija par pārdevēju</h3><h5>Testa veikals</h5></div>
      </body>
    </html>
    """

    entities = extract_entities(
        html,
        "https://www.meistardarbs.lv/katalogs/koka-izstradajumi/testa-prece",
        project,
    )
    assert entities, "Netika atrasts testa produkts."
    assert entities[0].price == 18.27
    assert entities[0].field_evidence["title"].extraction_method == "meistardarbs-html"
    assert entities[0].field_evidence["price"].value == 18.27
    assert entities[0].field_evidence["price"].confidence == 0.84
    assert entities[0].field_evidence["currency"].value == "EUR"
    assert entities[0].field_evidence["seller"].value == "Testa veikals"

    enriched = entities[0].apply_enrichment(
        FallbackProvider().enrich(entities[0], project)
    )
    assert enriched.is_relevant
    assert enriched.category == "karbinas_dekori"
    assert enriched.attributes.get("personalization") is True

    print("SMOKE TEST OK")
    print(enriched.model_dump())


if __name__ == "__main__":
    main()
