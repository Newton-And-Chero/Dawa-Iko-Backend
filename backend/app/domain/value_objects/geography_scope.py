"""GeographyScope — a tagged union of the geography-resolution variants from
PROJECT.md 2.2: county / sub_county / ward exact match, radius-from-point, and
nearest-N-facilities. Framework-free — `GeographyResolverPort` implementations
turn a scope into a facility list; `geography_scope_to_dict`/`_from_dict`
(de)serialize it for `Sweep.geography_scope`'s JSONB column.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CountyScope:
    county: str


@dataclass(frozen=True)
class SubCountyScope:
    sub_county: str


@dataclass(frozen=True)
class WardScope:
    ward: str


@dataclass(frozen=True)
class RadiusScope:
    lat: float
    lng: float
    radius_km: float


@dataclass(frozen=True)
class NearestNScope:
    lat: float
    lng: float
    n: int


GeographyScope = CountyScope | SubCountyScope | WardScope | RadiusScope | NearestNScope


def geography_scope_to_dict(scope: GeographyScope) -> dict[str, Any]:
    match scope:
        case CountyScope(county=county):
            return {"kind": "county", "county": county}
        case SubCountyScope(sub_county=sub_county):
            return {"kind": "sub_county", "sub_county": sub_county}
        case WardScope(ward=ward):
            return {"kind": "ward", "ward": ward}
        case RadiusScope(lat=lat, lng=lng, radius_km=radius_km):
            return {"kind": "radius", "lat": lat, "lng": lng, "radius_km": radius_km}
        case NearestNScope(lat=lat, lng=lng, n=n):
            return {"kind": "nearest_n", "lat": lat, "lng": lng, "n": n}
    raise TypeError(f"unsupported geography scope: {scope!r}")


def geography_scope_from_dict(data: dict[str, Any]) -> GeographyScope:
    kind = data["kind"]
    if kind == "county":
        return CountyScope(county=data["county"])
    if kind == "sub_county":
        return SubCountyScope(sub_county=data["sub_county"])
    if kind == "ward":
        return WardScope(ward=data["ward"])
    if kind == "radius":
        return RadiusScope(lat=data["lat"], lng=data["lng"], radius_km=data["radius_km"])
    if kind == "nearest_n":
        return NearestNScope(lat=data["lat"], lng=data["lng"], n=data["n"])
    raise ValueError(f"unknown geography scope kind: {kind!r}")
