import pytest

from app.domain.value_objects.geography_scope import (
    CountyScope,
    NearestNScope,
    RadiusScope,
    SubCountyScope,
    WardScope,
    geography_scope_from_dict,
    geography_scope_to_dict,
)

SCOPES = [
    CountyScope(county="Kirinyaga"),
    SubCountyScope(sub_county="Mwea"),
    WardScope(ward="Wamumu"),
    RadiusScope(lat=-0.6849, lng=37.3667, radius_km=5.0),
    NearestNScope(lat=-0.6849, lng=37.3667, n=10),
]


@pytest.mark.parametrize("scope", SCOPES)
def test_round_trip(scope: object) -> None:
    assert geography_scope_from_dict(geography_scope_to_dict(scope)) == scope  # type: ignore[arg-type]


def test_to_dict_tags_kind() -> None:
    assert geography_scope_to_dict(CountyScope(county="Nairobi"))["kind"] == "county"


def test_from_dict_unknown_kind_raises() -> None:
    with pytest.raises(ValueError, match="unknown geography scope kind"):
        geography_scope_from_dict({"kind": "planet"})
