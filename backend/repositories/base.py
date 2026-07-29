"""Generic async repository providing CRUD primitives over a single model."""

import uuid
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, id_: uuid.UUID) -> ModelT | None:
        return await self.session.get(self.model, id_)

    async def get_or_404(self, id_: uuid.UUID) -> ModelT:
        from utils.exceptions import NotFoundError

        obj = await self.get(id_)
        if obj is None:
            raise NotFoundError(f"{self.model.__name__} not found")
        return obj

    async def list_all(self) -> list[ModelT]:
        result = await self.session.execute(select(self.model))
        return list(result.scalars().all())

    async def create(self, **kwargs) -> ModelT:
        obj = self.model(**kwargs)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()
