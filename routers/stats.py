from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime, timezone
from models import Task, User, UserRole
from database import get_async_session
from dependencies import get_current_user

router = APIRouter(
    prefix="/stats",
    tags=["statistics"]
)

@router.get("/", response_model=dict)
async def get_tasks_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> dict:
    stmt = select(Task)
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(Task.user_id == current_user.id)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    total_tasks = len(tasks)
    by_quadrant = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    by_status = {"completed": 0, "pending": 0}
    for task in tasks:
        if task.quadrant in by_quadrant:
            by_quadrant[task.quadrant] += 1
        if task.completed:
            by_status["completed"] += 1
        else:
            by_status["pending"] += 1
    return {
        "total_tasks": total_tasks,
        "by_quadrant": by_quadrant,
        "by_status": by_status
    }

@router.get("/deadlines", response_model=List[dict])
async def get_deadlines_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> List[dict]:
    stmt = select(Task).where(Task.completed == False)
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(Task.user_id == current_user.id)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    
    now = datetime.now(timezone.utc)
    stats = []
    for task in tasks:
        deadline = task.deadline_at
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        
        days_left = (deadline - now).days
        
        stats.append({
            "title": task.title,
            "description": task.description,
            "created_at": task.created_at,
            "days_left": days_left
        })
    return stats
