from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.api.v1.dependencies import AUTHENTICATED_ROLES, get_call_gate, require_role
from app.api.v1.schemas.call_engine import CallEngineEnableIn, CallEngineStateOut
from app.application.ports.call_gate_port import CallEngineState, CallGatePort
from app.domain.enums import UserRole

router = APIRouter(
    prefix="/call-engine",
    tags=["call-engine"],
    dependencies=[Depends(require_role(*AUTHENTICATED_ROLES))],
)

_write_roles = [Depends(require_role(UserRole.ADMIN, UserRole.ANALYST))]


def _out(state: CallEngineState) -> CallEngineStateOut:
    return CallEngineStateOut(**asdict(state))


@router.get("", response_model=CallEngineStateOut)
async def get_call_engine(
    call_gate: CallGatePort = Depends(get_call_gate),
) -> CallEngineStateOut:
    return _out(await call_gate.status())


@router.post("/enable", response_model=CallEngineStateOut, dependencies=_write_roles)
async def enable_call_engine(
    body: CallEngineEnableIn = CallEngineEnableIn(),
    call_gate: CallGatePort = Depends(get_call_gate),
) -> CallEngineStateOut:
    return _out(await call_gate.enable(ttl_seconds=body.ttl_seconds))


@router.post("/disable", response_model=CallEngineStateOut, dependencies=_write_roles)
async def disable_call_engine(
    call_gate: CallGatePort = Depends(get_call_gate),
) -> CallEngineStateOut:
    return _out(await call_gate.disable())
