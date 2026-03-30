"""
Admin service — user listing and stats stubs.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User
from ..schemas import AdminUserListItem


async def get_all_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


async def get_active_user_count(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).where(User.is_active.is_(True)))
    return result.scalar_one()


def format_admin_user(user: User) -> AdminUserListItem:
    return AdminUserListItem(
        user_id=str(user.id),
        email_address=user.email,
        role=user.role.value,
        account_status="Active" if user.is_active else "Inactive",
        joined_formatted=user.created_at.strftime("%b %Y"),
    )
