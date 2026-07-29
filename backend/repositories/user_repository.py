"""User lookups used by the auth flow."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.user import User
from repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .where(User.email == email.lower())
            .options(selectinload(User.role), selectinload(User.profile))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        stmt = select(User.id).where(User.email == email.lower())
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None


def get_user_repository(session: AsyncSession) -> UserRepository:
    return UserRepository(session)
