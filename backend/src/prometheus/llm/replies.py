"""Reading JSON out of model replies (shared by every one-shot task that asks for JSON)."""

import json


def first_json_object(text: str, accept=lambda value: isinstance(value, dict)):
    """The first complete JSON object in ``text`` that ``accept`` likes, else None.
    Models wrap JSON in prose and code fences; raw_decode walks past them."""
    decoder = json.JSONDecoder()
    text = text or ""
    start = text.find("{")
    while start != -1:
        try:
            value, _ = decoder.raw_decode(text, start)
        except ValueError:
            start = text.find("{", start + 1)
            continue
        if accept(value):
            return value
        start = text.find("{", start + 1)
    return None
