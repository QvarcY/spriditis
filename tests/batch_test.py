from spriditis.ai.gemini import (
    GeminiAttribute,
    GeminiBatchResponse,
    GeminiEntityResult,
    _to_internal,
)


def main():
    response = GeminiBatchResponse(
        results=[
            GeminiEntityResult(
                entity_id=0,
                is_relevant=True,
                category="karbinas_dekori",
                confidence=0.91,
                relevance_score=0.88,
                summary="Koka dekors.",
                tags=["koks", "gravējums"],
                attributes=[
                    GeminiAttribute(
                        name="materials",
                        value='["koks", "akrils"]',
                    ),
                    GeminiAttribute(
                        name="personalization",
                        value="true",
                    ),
                    GeminiAttribute(
                        name="engraving_likelihood",
                        value="0.85",
                    ),
                ],
                opportunity_notes="Testa ideja",
            )
        ]
    )

    internal = _to_internal(response.results[0])

    assert internal.attributes["materials"] == [
        "koks",
        "akrils",
    ]
    assert internal.attributes["personalization"] is True
    assert (
        internal.attributes["engraving_likelihood"]
        == 0.85
    )

    print("BATCH TEST OK")


if __name__ == "__main__":
    main()
