from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from database import get_async_session
from dependencies import get_current_admin
from models import User, Task


router = APIRouter(
    prefix="/admin",
    tags=["admin"]
)


@router.get("/users", response_model=list[dict])
async def list_users_with_tasks_count(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_async_session)
) -> list[dict]:
    result = await db.execute(
        select(
            User.id,
            User.nickname,
            User.email,
            User.role,
            func.count(Task.id).label("tasks_count")
        )
        .outerjoin(Task, Task.user_id == User.id)
        .group_by(User.id)
        .order_by(User.id)
    )
    rows = result.all()
    return [
        {
            "id": row.id,
            "nickname": row.nickname,
            "email": row.email,
            "role": row.role.value if hasattr(row.role, "value") else str(row.role),
            "tasks_count": row.tasks_count
        }
        for row in rows
    ]


