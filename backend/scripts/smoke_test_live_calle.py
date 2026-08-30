import argparse
import asyncio
import sys
from datetime import datetime

from app.core.config import get_settings
from app.core.exceptions import CallProviderError
from app.core.webhook_security import build_webhook_url
from app.domain.call_schemas import (
    CALLE_RECIPIENT_LOCALE,
    CALLE_RECIPIENT_REGION,
    STOCK_CHECK_RESULT_SCHEMA,
    build_stock_check_task,
)
from app.domain.value_objects.call_task_ref import CallRecipient
from app.infrastructure.call_e.calle_adapter import CallEAdapter

_CONFIRM_FLAG = "--i-understand-this-costs-money-and-calls-a-real-phone"
_PLACEHOLDER_API_KEYS = {"", "changeme", "change-me"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Place ONE real CALL-E phone call. Costs real money, rings a real phone."
    )
    parser.add_argument(
        "--to",
        required=True,
        help="Real E.164 phone number to call, e.g. +2547XXXXXXXX. "
        "Use a number you control — this is a live call.",
    )
    parser.add_argument(
        "--commodity-name",
        default="Carbetocin",
        help="Commodity name to ask about (default: Carbetocin).",
    )
    parser.add_argument(
        _CONFIRM_FLAG,
        action="store_true",
        help="Required. Confirms you understand this places a real, billed phone call.",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()

    if not args.i_understand_this_costs_money_and_calls_a_real_phone:
        print(f"Refusing to run without {_CONFIRM_FLAG} — this places a real, billed call.")
        sys.exit(1)

    settings = get_settings()
    if settings.CALLE_API_KEY.strip().lower() in _PLACEHOLDER_API_KEYS:
        print(
            "CALLE_API_KEY is empty or still a placeholder — set a real key in .env "
            "before running this script."
        )
        sys.exit(1)

    print(f"About to place a REAL call to {args.to} via {settings.CALLE_BASE_URL}")
    print(f"Webhook URL registered on this call: {build_webhook_url()}")
    if "localhost" in settings.PUBLIC_BASE_URL or "127.0.0.1" in settings.PUBLIC_BASE_URL:
        print(
            "Warning: PUBLIC_BASE_URL is not publicly reachable — CALL-E will not be able "
            "to deliver the result webhook. This run only proves the call was placed."
        )

    adapter = CallEAdapter(base_url=settings.CALLE_BASE_URL, api_key=settings.CALLE_API_KEY)
    idempotency_key = f"smoke-test-{datetime.now().strftime('%Y%m%dT%H%M%S')}"

    try:
        call_task = await adapter.place_call(
            task=build_stock_check_task(args.commodity_name),
            recipients=[
                CallRecipient(
                    phones=[args.to],
                    region=CALLE_RECIPIENT_REGION,
                    locale=CALLE_RECIPIENT_LOCALE,
                )
            ],
            result_schema=None,
            recipient_result_schema=STOCK_CHECK_RESULT_SCHEMA,
            webhook_url=build_webhook_url(),
            idempotency_key=idempotency_key,
            metadata={"smoke_test": "true"},
        )
    except CallProviderError as exc:
        print(f"CALL-E rejected the call: {exc}")
        sys.exit(1)

    print(f"Call placed: id={call_task.id} status={call_task.status}")
    print("Nothing was written to the database — this script only calls the live API.")


if __name__ == "__main__":
    asyncio.run(main())
