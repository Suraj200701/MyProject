"""Shared pagination, sorting, and filtering primitives for list endpoints."""

from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, Field
from sqlalchemy import Select, func
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def pagination_params(
    page: int = Query(default=1, ge=1, description="1-indexed page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)


class PageMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


class Page(BaseModel, Generic[T]):
    items: list[T]
    meta: PageMeta


async def paginate(
    session: AsyncSession,
    stmt: Select,
    params: PaginationParams,
) -> tuple[list, PageMeta]:
    """Runs a COUNT query + a windowed SELECT for the given statement."""
    count_stmt = stmt.with_only_columns(func.count()).order_by(None)
    total_items = (await session.execute(count_stmt)).scalar_one()

    windowed = stmt.offset(params.offset).limit(params.page_size)
    rows = (await session.execute(windowed)).scalars().all()

    total_pages = max(1, (total_items + params.page_size - 1) // params.page_size)
    meta = PageMeta(
        page=params.page,
        page_size=params.page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=params.page < total_pages,
        has_previous=params.page > 1,
    )
    return list(rows), meta
