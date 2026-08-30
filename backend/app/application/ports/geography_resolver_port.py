from typing import Protocol

from app.domain.entities.facility import Facility
from app.domain.value_objects.geography_scope import GeographyScope


class GeographyResolverPort(Protocol):
    async def resolve(self, geography: GeographyScope) -> list[Facility]: ...
