from decimal import Decimal

import pytest

from app.application.use_cases.handle_calle_webhook import HandleCalleWebhookUseCase
from app.core.config import Settings
from app.domain.entities.call import Call
from app.domain.entities.commodity import Commodity
from app.domain.entities.facility import Facility
from app.domain.entities.sweep import Sweep
from app.domain.enums import (
    CallStatus,
    CommodityCategory,
    FacilitySource,
    FacilityType,
    StockStatus,
    SweepStatus,
    SweepTrigger,
)
from tests.application.fakes import (
    FakeNotifier,
    InMemoryAvailabilityResultRepository,
    InMemoryCallRepository,
    InMemoryCommodityRepository,
    InMemoryFacilityRepository,
    InMemoryRealtimeEventBus,
    InMemoryStockoutAlertRepository,
    InMemorySubscriberRepository,
    InMemorySweepRepository,
    InMemoryWebhookEventRepository,
)


def _facility() -> Facility:
    return Facility(
        name="Test Dispensary",
        type=FacilityType.DISPENSARY,
        county="Kirinyaga",
        sub_county="Mwea",
        ward="Wamumu",
        gps_lat=-0.6849,
        gps_lng=37.3667,
        phone_number="+254700000001",
        source=FacilitySource.KMHFL,
    )


@pytest.fixture
def setup() -> dict:
    calls = InMemoryCallRepository()
    results = InMemoryAvailabilityResultRepository()
    events = InMemoryWebhookEventRepository()
    sweeps = InMemorySweepRepository()
    facilities = InMemoryFacilityRepository()
    commodities = InMemoryCommodityRepository()
    alerts = InMemoryStockoutAlertRepository()
    subscribers = InMemorySubscriberRepository()
    notifier = FakeNotifier()
    realtime_event_bus = InMemoryRealtimeEventBus()
    use_case = HandleCalleWebhookUseCase(
        call_repository=calls,
        availability_result_repository=results,
        webhook_event_repository=events,
        sweep_repository=sweeps,
        facility_repository=facilities,
        commodity_repository=commodities,
        stockout_alert_repository=alerts,
        subscriber_repository=subscribers,
        notifier_resolver=lambda channel: notifier,
        realtime_event_bus=realtime_event_bus,
        settings=Settings(),
    )
    return {
        "calls": calls,
        "results": results,
        "events": events,
        "sweeps": sweeps,
        "facilities": facilities,
        "commodities": commodities,
        "alerts": alerts,
        "subscribers": subscribers,
        "notifier": notifier,
        "bus": realtime_event_bus,
        "uc": use_case,
    }


async def _seed(setup: dict) -> Call:
    facility = await setup["facilities"].add(_facility())
    commodity = await setup["commodities"].add(
        Commodity(name="Carbetocin", category=CommodityCategory.ESSENTIAL_MEDICINE)
    )
    sweep = Sweep(
        commodity_id=commodity.id,
        geography_scope={"county": "Kirinyaga"},
        trigger_type=SweepTrigger.ON_DEMAND,
    )
    await setup["sweeps"].add(sweep)
    call = Call(
        sweep_id=sweep.id,
        facility_id=facility.id,
        status=CallStatus.QUEUED,
        provider_call_id="call_abc",
        provider_recipient_id="recip_1",
    )
    await setup["calls"].add(call)
    return call


async def test_handle_completed_event_creates_availability_result(setup: dict) -> None:
    call = await _seed(setup)
    call_data = {
        "id": "call_abc",
        "completion_confidence": {"score": 0.87, "label": "high"},
        "recipients": [
            {
                "id": "recip_1",
                "status": "completed",
                "summary": "In stock.",
                "structured_result": {
                    "in_stock": "yes",
                    "quantity_band": "medium",
                    "price_kes": 120.5,
                    "last_restock_date": None,
                    "can_hold": True,
                    "hold_duration_hours": 24,
                    "notes": "Ask for the pharmacist.",
                },
                "attempts": [{"failure_code": None}],
            }
        ],
    }

    await setup["uc"].handle(event_id="evt_1", event_type="call.completed", call_data=call_data)

    updated_call = await setup["calls"].get_by_id(call.id)
    assert updated_call is not None
    assert updated_call.status == CallStatus.COMPLETED

    result = await setup["results"].get_by_call_id(call.id)
    assert result is not None
    assert result.in_stock == StockStatus.YES
    assert result.quantity_band == "medium"
    assert result.price_kes == Decimal("120.5")
    assert result.can_hold is True
    assert result.hold_duration_hours == 24
    assert result.confidence == pytest.approx(0.87)


async def test_handle_failed_event_marks_unknown_with_no_answer_status(setup: dict) -> None:
    call = await _seed(setup)
    call_data = {
        "id": "call_abc",
        "completion_confidence": None,
        "failure_code": "no_recipients_reached",
        "recipients": [
            {
                "id": "recip_1",
                "status": "failed",
                "summary": None,
                "structured_result": None,
                "attempts": [{"failure_code": "no_answer"}],
            }
        ],
    }

    await setup["uc"].handle(event_id="evt_2", event_type="call.failed", call_data=call_data)

    updated_call = await setup["calls"].get_by_id(call.id)
    assert updated_call is not None
    assert updated_call.status == CallStatus.NO_ANSWER

    result = await setup["results"].get_by_call_id(call.id)
    assert result is not None
    assert result.in_stock == StockStatus.UNKNOWN
    assert result.confidence is None


async def test_handle_result_validation_failed_flags_for_review(setup: dict) -> None:
    call = await _seed(setup)
    call_data = {
        "id": "call_abc",
        "completion_confidence": {"score": 0.4, "label": "low"},
        "recipients": [
            {
                "id": "recip_1",
                "status": "completed",
                "summary": "Ambiguous.",
                "structured_result": {"in_stock": "yes"},
                "attempts": [{"failure_code": None}],
            }
        ],
    }

    await setup["uc"].handle(
        event_id="evt_3", event_type="call.result_validation_failed", call_data=call_data
    )

    result = await setup["results"].get_by_call_id(call.id)
    assert result is not None
    assert result.confidence == 0.0
    assert result.in_stock == StockStatus.UNKNOWN
    assert "human review" in (result.notes or "")


async def test_handle_unknown_call_id_is_acknowledged_without_changes(setup: dict) -> None:
    call_data = {"id": "call_never_dispatched", "completion_confidence": None, "recipients": []}

    await setup["uc"].handle(event_id="evt_4", event_type="call.completed", call_data=call_data)

    assert await setup["results"].list_all() == []
    assert await setup["events"].was_processed("evt_4") is False


async def test_handle_event_for_already_finalized_call_is_reapplied(setup: dict) -> None:
    call = await _seed(setup)
    call.status = CallStatus.FAILED
    await setup["calls"].update(call)

    call_data = {
        "id": "call_abc",
        "completion_confidence": {"score": 0.91, "label": "high"},
        "recipients": [
            {
                "id": "recip_1",
                "status": "completed",
                "summary": "Back in stock on a later event.",
                "structured_result": {"in_stock": "yes", "quantity_band": "high"},
                "attempts": [{"failure_code": None}],
            }
        ],
    }

    await setup["uc"].handle(event_id="evt_late", event_type="call.completed", call_data=call_data)

    updated_call = await setup["calls"].get_by_id(call.id)
    assert updated_call is not None
    assert updated_call.status == CallStatus.COMPLETED
    result = await setup["results"].get_by_call_id(call.id)
    assert result is not None
    assert result.in_stock == StockStatus.YES


async def test_handle_duplicate_event_is_a_noop(setup: dict) -> None:
    call = await _seed(setup)
    call_data = {
        "id": "call_abc",
        "completion_confidence": {"score": 0.9, "label": "high"},
        "recipients": [
            {
                "id": "recip_1",
                "status": "completed",
                "summary": None,
                "structured_result": {"in_stock": "no"},
                "attempts": [{"failure_code": None}],
            }
        ],
    }

    await setup["uc"].handle(event_id="evt_5", event_type="call.completed", call_data=call_data)
    first_result = await setup["results"].get_by_call_id(call.id)
    assert first_result is not None

    await setup["uc"].handle(event_id="evt_5", event_type="call.completed", call_data=call_data)

    all_results = await setup["results"].list_all()
    assert len(all_results) == 1


async def test_sweep_completes_once_its_only_call_goes_terminal(setup: dict) -> None:
    call = await _seed(setup)

    await setup["uc"].handle(
        event_id="evt_complete",
        event_type="call.completed",
        call_data={
            "id": "call_abc",
            "completion_confidence": {"score": 0.9, "label": "high"},
            "recipients": [
                {
                    "id": "recip_1",
                    "status": "completed",
                    "summary": None,
                    "structured_result": {"in_stock": "no"},
                    "attempts": [{"failure_code": None}],
                }
            ],
        },
    )

    sweep = await setup["sweeps"].get_by_id(call.sweep_id)
    assert sweep is not None
    assert sweep.status == SweepStatus.COMPLETED


async def test_sweep_stays_open_while_a_sibling_call_is_still_pending(setup: dict) -> None:
    call = await _seed(setup)
    facility = _facility()
    still_pending = Call(
        sweep_id=call.sweep_id,
        facility_id=facility.id,
        status=CallStatus.QUEUED,
        provider_call_id="call_other",
        provider_recipient_id="recip_other",
    )
    await setup["calls"].add(still_pending)

    await setup["uc"].handle(
        event_id="evt_partial",
        event_type="call.completed",
        call_data={
            "id": "call_abc",
            "completion_confidence": {"score": 0.9, "label": "high"},
            "recipients": [
                {
                    "id": "recip_1",
                    "status": "completed",
                    "summary": None,
                    "structured_result": {"in_stock": "no"},
                    "attempts": [{"failure_code": None}],
                }
            ],
        },
    )

    sweep = await setup["sweeps"].get_by_id(call.sweep_id)
    assert sweep is not None
    assert sweep.status == SweepStatus.QUEUED
