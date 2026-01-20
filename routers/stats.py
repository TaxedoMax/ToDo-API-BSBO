from fastapi import APIRouter
from .tasks import tasks_db

router = APIRouter(prefix="/tasks/stats", tags=["statistics"])

@router.get("/")
async def get_tasks_stats() -> dict:
    by_quadrant = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    for task in tasks_db:
        if task["quadrant"] in by_quadrant:
            by_quadrant[task["quadrant"]] += 1

    completed_count = sum(1 for task in tasks_db if task["completed"])
    pending_count = len(tasks_db) - completed_count

    return {
        "total_tasks": len(tasks_db),
        "by_quadrant": by_quadrant,
        "by_status": {
            "completed": completed_count,
            "pending": pending_count
        }
    }

