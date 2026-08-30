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
