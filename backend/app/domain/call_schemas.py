"""The fixed stock-check question set, as data — not scattered string literals.

Sprint 04+ commodity-specific variants (cold-chain, expiry) extend this same
structure rather than duplicating it.
"""

from typing import Any

# CALL-E's Kenya (KE) region is English-only (see RULES.md) — no Swahili branch.
CALLE_RECIPIENT_REGION = "KE"
# BCP 47 locale hint. CALL-E's docs don't enumerate a Kenya-specific code; "en-KE"
# is the standard tag for English (Kenya) and the closest correct choice available.
CALLE_RECIPIENT_LOCALE = "en-KE"

_QUANTITY_BANDS = ["low", "medium", "high"]

# Every field is nullable and required per CALL-E's own convention for
# "ask for a value but allow an honest unknown" (see fetched OpenAPI spec) —
# an uncertain answer must be extractable as null/"unknown", never guessed.
STOCK_CHECK_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "in_stock",
        "quantity_band",
        "price_kes",
        "last_restock_date",
        "can_hold",
        "hold_duration_hours",
        "notes",
    ],
    "properties": {
        "in_stock": {
            "type": "string",
            "enum": ["yes", "no", "unknown"],
            "description": (
                "Whether the facility currently has the commodity in stock. Use "
                "'unknown' if the respondent is unsure or the call did not reach "
                "a clear answer — never guess."
            ),
        },
        "quantity_band": {
            "type": ["string", "null"],
            "enum": [*_QUANTITY_BANDS, None],
            "description": (
                "Rough quantity on hand, only when in_stock is 'yes'. Null otherwise "
                "or when the respondent could not estimate."
            ),
        },
        "price_kes": {
            "type": ["number", "null"],
            "description": "Current unit price in Kenyan shillings, only when in_stock is 'yes'.",
        },
        "last_restock_date": {
            "type": ["string", "null"],
            "format": "date",
            "description": (
                "ISO 8601 date of the last restock, if the respondent gave one — "
                "most relevant when in_stock is 'no'."
            ),
        },
        "can_hold": {
            "type": ["boolean", "null"],
            "description": (
                "Whether the facility offered to hold a unit for a patient, only "
                "when in_stock is 'yes'."
            ),
        },
        "hold_duration_hours": {
            "type": ["number", "null"],
            "description": "Hours the facility offered to hold a unit, if can_hold is true.",
        },
        "notes": {
            "type": ["string", "null"],
            "description": (
                "Any other relevant detail the respondent gave, e.g. a nearby facility "
                "that might have stock, or an expected restock date."
            ),
        },
    },
}


def build_stock_check_task(commodity_name: str) -> str:
    """The natural-language task instruction sent to CALL-E for one stock-check call.

    CALL-E's own agent handles live conversational branching from this prompt —
    we are instructing it what to ask and extract, not building a DTMF/decision
    tree engine ourselves.
    """
    return (
        f"You are calling on behalf of an independent medicine availability "
        f"monitoring service. You are NOT calling from the Ministry of Health, "
        f"KEMSA, or any government body — if asked, make that clear. "
        f"State in one sentence that you're checking current stock levels for "
        f"{commodity_name} as part of a routine availability survey, and that "
        f"you understand the pharmacy staff are busy. "
        f"Then ask, in order: "
        f"(1) Do you currently have {commodity_name} in stock? "
        f"(2) If yes, approximately how many units do you have? "
        f"(3) If yes, what is your current price? "
        f"(4) If no, when did you last restock this item, and do you know when "
        f"you expect to restock, or of a nearby facility that might have it? "
        f"(5) If yes, could you hold a unit for a patient, and for how long? "
        f"If the respondent is unsure or needs to check, offer to call back "
        f"later rather than guessing an answer. "
        f"Do not offer to place an order, arrange payment, or give any medical "
        f"advice — you are only gathering availability information. "
        f"Keep the call brief and polite."
    )
