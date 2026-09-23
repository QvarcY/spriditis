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
