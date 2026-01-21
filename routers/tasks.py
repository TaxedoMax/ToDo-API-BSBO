from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime, timezone, timedelta

from schemas import TaskCreate, TaskResponse, TaskUpdate
from models import Task, UserRole
from database import get_async_session
from dependencies import get_current_user
from models import User

router = APIRouter(prefix="/tasks", tags=["tasks"])

def calculate_quadrant(is_important: bool, deadline_at: datetime) -> str:
    now = datetime.now(timezone.utc)
    if deadline_at.tzinfo is None:
        deadline_at = deadline_at.replace(tzinfo=timezone.utc)
    
    # Срочно, если до дедлайна <= 3 дней
    is_urgent = (deadline_at - now) <= timedelta(days=3)
    
    if is_important and is_urgent:
        return "Q1"
    elif is_important and not is_urgent:
        return "Q2"
    elif not is_important and is_urgent:
        return "Q3"
    else:
        return "Q4"

# GET ALL TASKS - Получить все задачи
@router.get("", response_model=List[TaskResponse])
async def get_all_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> List[TaskResponse]:
    stmt = select(Task)
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(Task.user_id == current_user.id)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return tasks

# SEARCH TASKS - Поиск задач
@router.get("/search", response_model=List[TaskResponse])
async def search_tasks(
    q: str = Query(..., min_length=2),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> List[TaskResponse]:
    keyword = f"%{q.lower()}%"
    stmt = select(Task).where(
        (Task.title.ilike(keyword)) |
        (Task.description.ilike(keyword))
    )
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(Task.user_id == current_user.id)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    if not tasks:
        raise HTTPException(status_code=404, detail="По данному запросу ничего не найдено")
    return tasks

# GET TASKS BY STATUS - Получить задачи по статусу
@router.get("/status/{status}", response_model=List[TaskResponse])
async def get_tasks_by_status(
    status: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> List[TaskResponse]:
    if status not in ["completed", "pending"]:
        raise HTTPException(
            status_code=404,
            detail="Недопустимый статус. Используйте: completed или pending"
        )
    is_completed = (status == "completed")
    stmt = select(Task).where(Task.completed == is_completed)
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(Task.user_id == current_user.id)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return tasks

# GET TASKS BY QUADRANT - Получить задачи по квадранту
@router.get("/quadrant/{quadrant}", response_model=List[TaskResponse])
async def get_tasks_by_quadrant(
    quadrant: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> List[TaskResponse]:
    if quadrant not in ["Q1", "Q2", "Q3", "Q4"]:
        raise HTTPException(
            status_code=400,
            detail="Неверный квадрант. Используйте: Q1, Q2, Q3, Q4"
        )
    stmt = select(Task).where(Task.quadrant == quadrant)
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(Task.user_id == current_user.id)
    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return tasks

# GET TASKS DUE TODAY - Получить задачи, срок которых истекает сегодня
@router.get("/today", response_model=List[TaskResponse])
async def get_tasks_due_today(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> List[TaskResponse]:
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    stmt = select(Task).where(
        Task.deadline_at >= start_of_day,
        Task.deadline_at < end_of_day
    )
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(Task.user_id == current_user.id)

    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return tasks

# GET TASK BY ID - Получить задачу по ID
@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_by_id(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> TaskResponse:
    stmt = select(Task).where(Task.id == task_id)
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(Task.user_id == current_user.id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task

# POST - СОЗДАНИЕ НОВОЙ ЗАДАЧИ
@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task: TaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> TaskResponse:
    quadrant = calculate_quadrant(task.is_important, task.deadline_at)

    new_task = Task(
        title=task.title,
        description=task.description,
        is_important=task.is_important,
        deadline_at=task.deadline_at,
        user_id=current_user.id,
        quadrant=quadrant,
        completed=False
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    return new_task

# PUT - ОБНОВЛЕНИЕ ЗАДАЧИ
@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> TaskResponse:
    stmt = select(Task).where(Task.id == task_id)
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(Task.user_id == current_user.id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    update_data = task_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(task, field, value)

    # Пересчитываем квадрант при изменении важности или дедлайна
    if "is_important" in update_data or "deadline_at" in update_data:
        task.quadrant = calculate_quadrant(task.is_important, task.deadline_at)

    await db.commit()
    await db.refresh(task)
    return task

# PATCH - ОТМЕТИТЬ ЗАДАЧУ ВЫПОЛНЕННОЙ
@router.patch("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> TaskResponse:
    stmt = select(Task).where(Task.id == task_id)
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(Task.user_id == current_user.id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    task.completed = True
    task.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(task)
    return task

# DELETE - УДАЛЕНИЕ ЗАДАЧИ
@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
async def delete_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
) -> dict:
    stmt = select(Task).where(Task.id == task_id)
    if current_user.role != UserRole.ADMIN:
        stmt = stmt.where(Task.user_id == current_user.id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    deleted_task_info = {
        "id": task.id,
        "title": task.title
    }
    await db.delete(task)
    await db.commit()
    return {
        "message": "Задача успешно удалена",
        "id": deleted_task_info["id"],
        "title": deleted_task_info["title"]
    }
