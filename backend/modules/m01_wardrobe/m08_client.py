"""Bridge to M8 (LLM layer, owner BO8) for receipt / label extraction.

M1 never calls an LLM itself (module rule: ask the owner, never re-implement). M8 does not support this
task yet: until it does, `extract()` raises ExtractionUnavailableError and the API answers 503, so the
user fills the form by hand. The contract requested from M8 is in README.md ("Needed from M8").
"""

import asyncio

from pydantic import ValidationError

from shared.config import settings

from .contract import DocumentKind, DocumentResponse, ExtractionUnavailableError

TASK = "extract_garment_document"

# JSON M8 must return in `result` (also documented in the README)
RESULT_SCHEMA = {
    "kind": "receipt | price_tag | care_label",
    "fields": {
        "price": "number|null", "currency": "ISO code|null", "purchase_date": "YYYY-MM-DD|null",
        "store": "str|null", "brand": "str|null", "size": "str|null",
        "size_system": "letter|eu|fr|us|uk|it|waist|shoe_eu|shoe_us|one_size|other|null",
        "reference": "str|null", "composition": [{"material": "str", "percent": "number"}], "care": ["str"],
    },
    "lines": [{"label": "str", "price": "number|null", "quantity": "int"}],
    "selected_line": "int|null",
    "confidence": {"<field>": "0..1"},
}


def _m08():
    """M8's own implementation (its mock or service), chosen with M8's rule (global USE_MOCKS)."""
    from modules.m08_llm_layer import mock, service

    return mock if getattr(settings, "use_mocks", True) else service


async def extract(user_id: str, image_data_url: str, kind: DocumentKind, hint: dict) -> DocumentResponse:
    request = {
        "user_id": user_id,
        "payload": {"task": TASK, "kind": kind.value, "image": image_data_url, "hint": hint,
                    "result_schema": RESULT_SCHEMA},
    }
    try:
        out = await asyncio.to_thread(_m08().parse, request)
    except NotImplementedError as e:
        raise ExtractionUnavailableError("M8 does not implement document extraction yet") from e
    except Exception as e:                       # provider down, timeout, bad key...
        raise ExtractionUnavailableError(f"M8 extraction failed: {e}") from e

    result = (out or {}).get("result") or {}
    if "fields" not in result:
        raise ExtractionUnavailableError(f"M8 does not support the '{TASK}' task yet")
    try:
        return DocumentResponse.model_validate(result)
    except ValidationError as e:
        msg = f"M8 returned an invalid extraction: {e.error_count()} errors"
        raise ExtractionUnavailableError(msg) from e
