import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Establish System Path Environment Context Anchor
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Mount Routers from Sub-package layouts
# 🌟 REACTIVATED: Bringing your dual-verification parser back online
from routers.assignment_parser import router as assignment_parser_router

from routers.assignment_summarizer import router as assignment_summarizer_router

from routers.timetable import router as timetable_router
from routers.scheduler import router as interactive_scheduler_router

# LAZY IMPORT BUFFER: Instantiating database layer safely via functional wrappers
from database.scheduler_db import get_db

app = FastAPI(
    title="FYP Smart Scheduler AI Core API",
    description="Decoupled Modular Architecture Routing Engine for Assignments, Summaries, and Timetables."
)

# Explicitly declare local development origins to satisfy browser security boundaries
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate database manager through functional wrapper hook safely
db_manager = get_db()

# =========================================================================
# CENTRALIZED ROUTE ROUTING ARCHITECTURE
# =========================================================================

# 🚀 Active: Route engine for your side-by-side comparison endpoint (/api/assignment/upload)
app.include_router(assignment_parser_router)

# Automated timetable grid scheduling route
app.include_router(timetable_router)

# Interactive scheduling override panel logic router
app.include_router(interactive_scheduler_router)

app.include_router(assignment_summarizer_router)

# LIVE CALENDAR BROADCAST ENDPOINT (UPDATED FOR DUAL-DATE MATRIX)
@app.get("/api/tasks/all")
def get_calendar_events():
    """
    Exposes all scheduled tasks and assignments directly to the Next.js calendar UI grid.
    Correctly unpacks updated dual-date sequence schema to eliminate 500 processing errors.
    """
    try:
        raw_records = db_manager.get_all_tasks()
    
        # Format database tuples neatly into standard JSON object dictionaries for the frontend
        formatted_tasks = []
        for row in raw_records:
            formatted_tasks.append({
                "id": row[0],
                "title": row[1],
                "project": row[2],
                "planned_date": row[3],  # 📅 Scheduled/adjusted workspace day
                "planned_time": row[4],  # ⏰ Scheduled working time execution window
                "deadline_iso": row[5],  # 🔒 Immovable final submission anchor
                "priority": row[6]       # Ranking category weight label
            })
        
        return formatted_tasks
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch operational calendar tasks layer: {str(e)}"
        )


@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "FYP Core Gateway Orchestrator Online. Pure BERT vs Hybrid Comparison Parser active."
    }

@app.post("/api/assignment/save-manual")
async def save_manual_assignment(payload: dict):
    db = get_db()
 
    db.insert_assignment_direct(
        title=payload.get("title"),
        project=payload.get("project"),
        deadline_iso=payload.get("deadline_iso"),
        priority=payload.get("priority", "Normal"),
        planned_date=payload.get("deadline_iso"),
        planned_time=payload.get("time_slot")    
    )
    return {"status": "success", "detail": "Task committed safely to sqlite system structures."}

@app.post("/api/assignment/save-bulk-milestones")
async def save_bulk_milestones(payload: dict):
    db = get_db()
    milestones = payload.get("milestones", [])
 
    if not milestones:
        return {"status": "error", "detail": "Empty block payload array received."}
      
    db.insert_bulk_milestones(milestones)
    return {"status": "success", "detail": "All timeline block adjustments updated inside scheduler.db database tables."}

if __name__ == "__main__":
    import uvicorn
    file_name = os.path.basename(__file__).replace(".py", "")
    uvicorn.run(f"{file_name}:app", host="127.0.0.1", port=8000, reload=True, log_level="info")
