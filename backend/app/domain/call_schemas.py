from typing import Any

CALLE_RECIPIENT_REGION = "KE"
CALLE_RECIPIENT_LOCALE = "en-US"

_QUANTITY_BANDS = ["low", "medium", "high"]

STOCK_CHECK_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["in_stock"],
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
            "type": "string",
            "enum": [*_QUANTITY_BANDS, "unknown"],
            "description": (
                "Rough quantity on hand when in_stock is 'yes'. Use 'unknown' when "
                "in_stock is not 'yes' or the respondent could not estimate."
            ),
        },
        "price_kes": {
            "type": "number",
            "description": (
                "Current unit price in Kenyan shillings when in_stock is 'yes'. "
                "Omit this field entirely if the respondent did not give a price."
            ),
        },
        "last_restock_date": {
            "type": "string",
            "description": (
                "Date of the last restock as an ISO 8601 date (YYYY-MM-DD), most "
                "relevant when in_stock is 'no'. Omit this field entirely if the "
                "respondent did not give a date."
            ),
        },
        "can_hold": {
            "type": "boolean",
            "description": (
                "Whether the facility offered to hold a unit for a patient, only "
                "when in_stock is 'yes'. Omit this field entirely if it did not "
                "come up."
            ),
        },
        "hold_duration_hours": {
            "type": "number",
            "description": (
                "Hours the facility offered to hold a unit, when can_hold is true. "
                "Omit this field entirely otherwise."
            ),
        },
        "notes": {
            "type": "string",
            "description": (
                "Any other relevant detail the respondent gave, e.g. a nearby facility "
                "that might have stock, or an expected restock date. Omit if there is "
                "nothing to add."
            ),
        },
    },
}


def build_stock_check_task(commodity_name: str) -> str:
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
