from uuid import uuid4

import pytest

from app.application.use_cases.get_sweep_status import GetSweepStatusUseCase
from app.core.exceptions import NotFoundError
from app.domain.entities.call import Call
from app.domain.entities.sweep import Sweep
from app.domain.enums import CallStatus, SweepStatus, SweepTrigger
from tests.application.fakes import InMemoryCallRepository, InMemorySweepRepository


async def test_unknown_sweep_raises() -> None:
    use_case = GetSweepStatusUseCase(InMemorySweepRepository(), InMemoryCallRepository())
    with pytest.raises(NotFoundError):
        await use_case.execute(uuid4())


async def test_counts_calls_by_status() -> None:
    sweeps = InMemorySweepRepository()
    calls = InMemoryCallRepository()
    sweep = await sweeps.add(
        Sweep(
            commodity_id=uuid4(),
            geography_scope={"kind": "county", "county": "Kirinyaga"},
            trigger_type=SweepTrigger.ON_DEMAND,
            status=SweepStatus.IN_PROGRESS,
        )
    )

    for status in (CallStatus.COMPLETED, CallStatus.COMPLETED, CallStatus.NO_ANSWER):
        await calls.add(Call(sweep_id=sweep.id, facility_id=uuid4(), status=status))

    use_case = GetSweepStatusUseCase(sweeps, calls)
    progress = await use_case.execute(sweep.id)

    assert progress.total_calls == 3
    assert progress.status == SweepStatus.IN_PROGRESS
    assert progress.counts_by_status[CallStatus.COMPLETED] == 2
    assert progress.counts_by_status[CallStatus.NO_ANSWER] == 1
