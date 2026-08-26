"""Shared pagination envelope. Offset/limit (not cursor) pagination —
simple, sufficient for this project's list sizes, and easy to express
identically on every list endpoint. The `page_params` FastAPI dependency
that produces a `PageParams` lives in `api/v1/dependencies.py`."""

from dataclasses import dataclass

from pydantic import BaseModel


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


@dataclass
class PageParams:
    limit: int
    offset: int


def paginate[T](items: list[T], params: PageParams) -> Page[T]:
    window = items[params.offset : params.offset + params.limit]
    return Page[T](items=window, total=len(items), limit=params.limit, offset=params.offset)
