# scheduler.py


import os
import time
from typing import List, Dict
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime, timedelta


from database.scheduler_db import get_db
from database.timetable_db import TimetableDatabaseManager


router = APIRouter(prefix="/api/schedule", tags=["Interactive Scheduling Workspace"])


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Use the actual timetable SQLite database file.
# If your project uses another path, change this to your real timetable.db path.
TIMETABLE_DB_PATH = os.path.join(PROJECT_ROOT, "database", "timetable.db")


db_manager = get_db()
timetable_db = TimetableDatabaseManager(db_name=TIMETABLE_DB_PATH)


days_list = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


DAILY_WORKLOAD_LIMIT_HOURS = 4.0
TASK_BLOCK_DURATION_HOURS = 2.0




# ==============================================================================
# WORKSPACE UTILITIES
# ==============================================================================
def normalize_project_id(project_id: str = None) -> str:
   """
   Normalizes the active sidebar workspace/profile ID.


   If project_id is missing, empty or whitespace-only, it falls back to project-1.
   """
   cleaned = str(project_id or "").strip()
   return cleaned if cleaned else "project-1"




def normalize_time_string(time_value: str) -> str:
   """
   Converts HH:MM into HH:MM:SS.
   Keeps HH:MM:SS unchanged.
   """
   cleaned = str(time_value or "12:00").strip()


   if len(cleaned) == 5:
       return f"{cleaned}:00"


   return cleaned




def get_existing_daily_task_hours(project_id: str) -> Dict[str, float]:
   """
   Counts existing saved task workload per day for the selected project.


   Each saved task phase is treated as TASK_BLOCK_DURATION_HOURS.
   This is used by /commit and /update-slot as backend safety validation.
   """
   active_project_id = normalize_project_id(project_id)
   daily_hours: Dict[str, float] = {}


   query = """
       SELECT planned_date
       FROM tasks
       WHERE project_id = ?
   """


   with db_manager.get_connection() as conn:
       cursor = conn.cursor()
       cursor.execute(query, (active_project_id,))


       for row in cursor.fetchall():
           planned_date = str(row[0] or "").strip()


           if not planned_date:
               continue


           daily_hours[planned_date] = daily_hours.get(planned_date, 0.0) + TASK_BLOCK_DURATION_HOURS


   return daily_hours




def validate_daily_workload_limit(project_id: str, milestones: List["MilestoneCommitItem"]):
   """
   Validates that existing tasks + new milestones do not exceed 4 hours per day.


   Rule:
   - Every day is limited to 4 task hours.
   - Each milestone is treated as 2 hours.
   - Therefore, maximum 2 task blocks can be saved on one date.
   """
   active_project_id = normalize_project_id(project_id)
   daily_hours = get_existing_daily_task_hours(active_project_id)


   for milestone in milestones:
       planned_date = str(milestone.planned_date or "").strip()


       if not planned_date:
           raise HTTPException(
               status_code=400,
               detail="Milestone planned_date is missing."
           )


       try:
           datetime.strptime(planned_date, "%Y-%m-%d")
       except ValueError:
           raise HTTPException(
               status_code=400,
               detail=f"Invalid planned_date format: {planned_date}. Expected YYYY-MM-DD."
           )


       daily_hours[planned_date] = daily_hours.get(planned_date, 0.0) + TASK_BLOCK_DURATION_HOURS


       if daily_hours[planned_date] > DAILY_WORKLOAD_LIMIT_HOURS:
           raise HTTPException(
               status_code=400,
               detail=(
                   f"Daily workload limit exceeded on {planned_date}. "
                   f"Maximum allowed is {DAILY_WORKLOAD_LIMIT_HOURS:.0f} hours per day. "
                   f"Each milestone is {TASK_BLOCK_DURATION_HOURS:.0f} hours, so only "
                   f"{int(DAILY_WORKLOAD_LIMIT_HOURS // TASK_BLOCK_DURATION_HOURS)} milestones "
                   f"can be scheduled on the same day."
               )
           )




def get_project_scoped_timetable_slots(project_id: str):
   """
   Gets timetable slots from timetable_db for the selected project.


   Supports both new project-scoped timetable DB methods and older methods.
   """
   active_project_id = normalize_project_id(project_id)


   try:
       return timetable_db.get_all_timetable_slots(active_project_id)
   except TypeError:
       return timetable_db.get_all_timetable_slots()
   except Exception:
       return []




# ==============================================================================
# DATA SCHEMAS
# ==============================================================================
class ScheduleProposalInput(BaseModel):
   project_id: str = Field(default="project-1", description="Active sidebar workspace/profile ID")
   title: str = Field(..., description="Assignment name header string")
   project: str = Field(..., description="Course code, for example SWE403")
   deadline_iso: str = Field(..., description="Assignment deadline")
   priority: str = Field(default="Normal")




class MilestoneCommitItem(BaseModel):
   title: str
   project: str
   planned_date: str
   planned_time: str
   deadline_iso: str
   priority: str = Field(default="Normal")
   sorting_score: int = Field(default=0)




class CommitScheduleInput(BaseModel):
   project_id: str = Field(default="project-1", description="Active sidebar workspace/profile ID")
   course_code: str
   assignment_name: str
   deadline_iso: str
   milestones: List[MilestoneCommitItem]




class DragDropAdjustmentInput(BaseModel):
   project_id: str = Field(default="project-1", description="Active sidebar workspace/profile ID")
   task_id: int
   new_planned_date: str
   new_planned_time: str




# ==============================================================================
# ROUTER WORKFLOWS
# ==============================================================================
@router.get("/tasks")
async def fetch_updated_dashboard_tasks(
   project_id: str = Query(default="project-1", description="Active sidebar workspace/profile ID")
):
   """
   PROJECT-SCOPED TASK DASHBOARD


   Returns all saved task phases for the selected project.
   """
   active_project_id = normalize_project_id(project_id)


   try:
       tasks_list = []


       with db_manager.get_connection() as conn:
           conn.row_factory = lambda cursor, row: {
               "id": row[0],
               "project_id": row[1],
               "title": row[2],
               "project": row[3],
               "planned_date": row[4],
               "planned_time": row[5],
               "deadline_iso": row[6],
               "priority": row[7],
               "sorting_score": row[8] if len(row) > 8 else 0
           }


           cursor = conn.cursor()


           query = """
               SELECT id,
                      project_id,
                      title,
                      project,
                      COALESCE(planned_date, deadline_iso) AS planned_date,
                      COALESCE(planned_time, '09:00') AS planned_time,
                      deadline_iso,
                      priority,
                      sorting_score
               FROM tasks
               WHERE project_id = ?
               ORDER BY planned_date ASC, planned_time ASC
           """


           cursor.execute(query, (active_project_id,))
           tasks_list = cursor.fetchall()


       return {
           "success": True,
           "project_id": active_project_id,
           "tasks": tasks_list
       }


   except Exception as err:
       print(f"❌ Core API task sync breakdown: {str(err)}")


       return {
           "success": False,
           "project_id": active_project_id,
           "tasks": [],
           "error": str(err)
       }




@router.get("/weekly-view")
async def get_interactive_weekly_view(
   target_date: str = Query(..., description="Selected date in YYYY-MM-DD format"),
   project_id: str = Query(default="project-1", description="Active sidebar workspace/profile ID")
):
   """
   PROJECT-SCOPED UNIFIED WEEKLY VIEW


   Returns:
   - saved task phases from scheduler_db
   - fixed class events from scheduler_db.timetable_events
   - recurring timetable slots from timetable_db
   """
   active_project_id = normalize_project_id(project_id)


   try:
       payload = db_manager.get_weekly_view_payload(target_date.strip(), active_project_id)


       parsed_date = datetime.strptime(target_date.strip(), "%Y-%m-%d")
       start_of_week = parsed_date - timedelta(days=parsed_date.weekday())


       week_date_map = {}


       for idx, day_name in enumerate(days_list):
           resolved_day_date = start_of_week + timedelta(days=idx)
           week_date_map[day_name] = resolved_day_date.strftime("%Y-%m-%d")


       raw_timetable_slots = get_project_scoped_timetable_slots(active_project_id)


       for slot in raw_timetable_slots:
           # Expected slot format:
           # course_code, course_name, course_venue, class_day, start_time, end_time
           try:
               course_code = slot[0]
               course_name = slot[1]
               course_venue = slot[2]
               day_name = slot[3]
               start_time = slot[4]
               end_time = slot[5]
           except Exception:
               continue


           if day_name in week_date_map:
               planned_date = week_date_map[day_name]


               payload["events"].append({
                   "id": f"fixed-class-{course_code}-{day_name}-{start_time}",
                   "type": "CLASS",
                   "is_fixed_class": True,
                   "title": course_name,
                   "course_code": course_code,
                   "project": course_code,
                   "planned_date": planned_date,
                   "planned_time": start_time,
                   "time_slot": start_time,
                   "end_time": end_time,
                   "venue": course_venue,
                   "start_iso": f"{planned_date} {normalize_time_string(start_time)}",
                   "end_iso": f"{planned_date} {normalize_time_string(end_time)}",
                   "deadline_iso": "",
                   "priority": "High"
               })


       payload["project_id"] = active_project_id
       payload["events"].sort(
           key=lambda event: f"{event.get('planned_date', '')} {event.get('planned_time') or event.get('time_slot', '')}"
       )


       return {
           "success": True,
           "project_id": active_project_id,
           "data": payload
       }


   except Exception as err:
       print(f"❌ Failed to resolve weekly calendar grid context: {str(err)}")
       raise HTTPException(
           status_code=500,
           detail=f"Calendar grid extraction error: {str(err)}"
       )




@router.post("/propose")
async def propose_assignment_schedule(payload: ScheduleProposalInput):
   """
   Generates a balanced schedule proposal.


   Important:
   This endpoint must call db_manager.propose_split_task().


   That function checks:
   - fixed timetable constraints
   - existing saved task time conflicts
   - existing saved daily workload


   Therefore, if a date already has 4 hours of tasks, the GA/Resource Leveling
   should automatically avoid that date and propose another available day.
   """
   active_project_id = normalize_project_id(payload.project_id)


   try:
       proposed_milestones = db_manager.propose_split_task(
           project_id=active_project_id,
           title=payload.title.strip(),
           project=payload.project.strip().upper(),
           deadline_iso=payload.deadline_iso.strip(),
           priority=payload.priority
       )


       return {
           "success": True,
           "project_id": active_project_id,
           "proposals": proposed_milestones
       }


   except Exception as err:
       import traceback
       traceback.print_exc()


       raise HTTPException(
           status_code=500,
           detail=f"Engine error: {str(err)}"
       )




@router.post("/commit")
async def commit_adjusted_schedule(payload: CommitScheduleInput):
   """
   Commits adjusted milestone blocks into the selected workspace only.


   Important validation:
   - Prevents more than 4 task hours per day.
   - Counts both existing saved tasks and new milestones.
   - Stops frontend fallback/manual edits from saving overloaded days.
   """
   active_project_id = normalize_project_id(payload.project_id)


   try:
       if not payload.milestones:
           raise HTTPException(
               status_code=400,
               detail="No milestones were provided for commit."
           )


       validate_daily_workload_limit(active_project_id, payload.milestones)


       with db_manager.get_connection() as conn:
           cursor = conn.cursor()


           cursor.execute("PRAGMA table_info(tasks)")
           columns = [col[1] for col in cursor.fetchall()]


           has_created_at = "created_at" in columns
           has_project_id = "project_id" in columns


           if not has_project_id:
               raise HTTPException(
                   status_code=500,
                   detail="Database schema missing tasks.project_id. Run scheduler_db.initialize_warehouse() migration first."
               )


           current_time_str = time.strftime("%Y-%m-%d %H:%M:%S")


           if has_created_at:
               query_calendar_task = """
                   INSERT INTO tasks (
                       project_id,
                       title,
                       project,
                       planned_date,
                       planned_time,
                       deadline_iso,
                       priority,
                       sorting_score,
                       created_at
                   )
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               """
           else:
               query_calendar_task = """
                   INSERT INTO tasks (
                       project_id,
                       title,
                       project,
                       planned_date,
                       planned_time,
                       deadline_iso,
                       priority,
                       sorting_score
                   )
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               """


           for milestone in payload.milestones:
               planned_time = normalize_time_string(milestone.planned_time)


               values = [
                   active_project_id,
                   milestone.title.strip(),
                   milestone.project.strip().upper(),
                   milestone.planned_date.strip(),
                   planned_time,
                   milestone.deadline_iso.strip(),
                   milestone.priority.strip(),
                   milestone.sorting_score
               ]


               if has_created_at:
                   values.append(current_time_str)


               cursor.execute(query_calendar_task, tuple(values))


           conn.commit()


       return {
           "success": True,
           "project_id": active_project_id,
           "message": "Adjusted milestone blocks committed successfully."
       }


   except HTTPException:
       raise


   except Exception as err:
       raise HTTPException(
           status_code=500,
           detail=f"Failed to commit blocks: {str(err)}"
       )




@router.put("/update-slot")
async def update_task_slot(payload: DragDropAdjustmentInput):
   """
   Project-scoped drag-and-drop override.


   This version also validates the 4-hour daily workload rule before moving a task.
   """
   active_project_id = normalize_project_id(payload.project_id)


   try:
       target_time = normalize_time_string(payload.new_planned_time)


       try:
           datetime.strptime(payload.new_planned_date.strip(), "%Y-%m-%d")
       except ValueError:
           raise HTTPException(
               status_code=400,
               detail="Invalid new_planned_date format. Expected YYYY-MM-DD."
           )


       existing_daily_hours = get_existing_daily_task_hours(active_project_id)


       # Remove current task's old date workload first.
       with db_manager.get_connection() as conn:
           cursor = conn.cursor()
           cursor.execute(
               """
               SELECT planned_date
               FROM tasks
               WHERE id = ? AND project_id = ?
               """,
               (payload.task_id, active_project_id)
           )


           row = cursor.fetchone()


           if not row:
               raise HTTPException(
                   status_code=404,
                   detail="Target task event block row not found in the active workspace."
               )


           old_date = str(row[0] or "").strip()


       if old_date in existing_daily_hours:
           existing_daily_hours[old_date] = max(
               0.0,
               existing_daily_hours[old_date] - TASK_BLOCK_DURATION_HOURS
           )


       new_date = payload.new_planned_date.strip()
       existing_daily_hours[new_date] = existing_daily_hours.get(new_date, 0.0) + TASK_BLOCK_DURATION_HOURS


       if existing_daily_hours[new_date] > DAILY_WORKLOAD_LIMIT_HOURS:
           raise HTTPException(
               status_code=400,
               detail=(
                   f"Cannot move task to {new_date}. "
                   f"Daily workload limit of {DAILY_WORKLOAD_LIMIT_HOURS:.0f} hours would be exceeded."
               )
           )


       query = """
           UPDATE tasks
           SET planned_date = ?, planned_time = ?
           WHERE id = ? AND project_id = ?
       """


       with db_manager.get_connection() as conn:
           cursor = conn.cursor()
           cursor.execute(
               query,
               (
                   new_date,
                   target_time,
                   payload.task_id,
                   active_project_id
               )
           )
           conn.commit()


           if cursor.rowcount == 0:
               raise HTTPException(
                   status_code=404,
                   detail="Target task event block row not found in the active workspace."
               )


       return {
           "success": True,
           "project_id": active_project_id,
           "message": "Workspace layout adjusted directly on disk."
       }


   except HTTPException:
       raise


   except Exception as err:
       raise HTTPException(
           status_code=500,
           detail=f"Failed to modify layout position: {str(err)}"
       )

