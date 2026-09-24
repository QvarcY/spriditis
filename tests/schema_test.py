
import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.ai.gemini import GeminiBatchResponse


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def main():
    schema = GeminiBatchResponse.model_json_schema()

    bad = [
        node
        for node in walk(schema)
        if isinstance(node, dict)
        and "additionalProperties" in node
    ]

    assert not bad, (
        "Gemini response schema satur additionalProperties: "
        f"{bad}"
    )

    print("SCHEMA TEST OK")
    print(
        "Gemini batch structured-output schema "
        "nesatur additionalProperties."
    )


if __name__ == "__main__":
    main()


def _bom_project_load_test():
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from spriditis.core.projects import load_project

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "bom_project.json"
        payload = """{
  "id": "bom_project",
  "name": "BOM project",
  "research_type": "product_market",
  "entity_type": "product",
  "seed_urls": ["https://example.com"]
}"""
        path.write_text(payload, encoding="utf-8-sig")
        project = load_project(path)
        assert project.id == "bom_project"


_bom_project_load_test()
