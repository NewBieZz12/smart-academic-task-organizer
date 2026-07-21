#timetable.py


import os
import re
import shutil
import io
import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta, time as datetime_time


# Database and Opencv layout pipelines mapping
from database.timetable_db import TimetableDatabaseManager
# 🚀 IMPORTED: Updated Generic Scheduler Database Manager to sync intervals
from database.scheduler_db import get_db
from Opencv.grid_detector import parse_opencv_blocks_to_slots


router = APIRouter(tags=["Timetable"])


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "database", "timetable.db")


db_manager = TimetableDatabaseManager(db_name=DB_PATH)
scheduler_db = get_db()  # Instantiates the interval-clash capable database adapter
scheduler_db.initialize_warehouse()
print("✅ Scheduler warehouse initialized for timetable sync:", scheduler_db.db_path)


days_list = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ==============================================================================
# PROJECT / WORKSPACE CONTEXT
# ==============================================================================
def normalize_project_id(project_id: str = None) -> str:
   cleaned = str(project_id or "").strip()
   return cleaned if cleaned else "project-1"




def _supports_project_scoped_timetable_db() -> bool:
   """
   Optional compatibility check.
   If timetable_db.py has not yet been upgraded for project_id, this router
   will still work using the legacy global timetable table.
   """
   return all(
       hasattr(db_manager, method_name)
       for method_name in [
           "clear_timetable_records_by_project",
           "insert_batch_timetable_slots_by_project",
           "get_all_timetable_slots_by_project",
       ]
   )


def populate_scheduler_clash_matrix(new_slots: list, project_id: str):
   """
   Converts raw weekly timetable slots into 14-week absolute interval constraints
   for the scheduler optimizer.
   """
   active_project_id = normalize_project_id(project_id)


   try:
       scheduler_db.initialize_warehouse()
       scheduler_db.clear_timetable_events(active_project_id)


       base_start_date = datetime.now()


       for slot in new_slots:
           course_code = slot["course_code"]
           target_day_name = slot["class_day"]


           try:
               target_day_idx = days_list.index(target_day_name)
           except ValueError:
               continue


           start_str = slot["start_time"]
           end_str = slot["end_time"]


           start_h, start_m = map(int, start_str.split(":"))
           end_h, end_m = map(int, end_str.split(":"))


           for week_offset in range(14):
               current_week_start = base_start_date + timedelta(weeks=week_offset)
               days_ahead = target_day_idx - current_week_start.weekday()
               resolved_date = current_week_start + timedelta(days=days_ahead)


               absolute_start = datetime.combine(
                   resolved_date.date(),
                   datetime_time(start_h, start_m)
               )


               absolute_end = datetime.combine(
                   resolved_date.date(),
                   datetime_time(end_h, end_m)
               )


               scheduler_db.insert_timetable_event(
               project_id=active_project_id,
               course_code=course_code,
               course_name=slot.get("course_name", ""),
               course_venue=slot.get("course_venue", ""),
               start_iso=absolute_start.strftime("%Y-%m-%d %H:%M:%S"),
               end_iso=absolute_end.strftime("%Y-%m-%d %H:%M:%S")
               )


       print(f"✅ Synced scheduler clash matrix for project_id={active_project_id}")


   except Exception as e:
       print(f"❌ Critical failure syncing scheduler clash boundaries matrix: {str(e)}")
       raise e




def get_timetable_rows(project_id: str):
   active_project_id = normalize_project_id(project_id)
   if _supports_project_scoped_timetable_db():
       return db_manager.get_all_timetable_slots_by_project(active_project_id)
   return db_manager.get_all_timetable_slots()




def clear_timetable_rows(project_id: str):
   active_project_id = normalize_project_id(project_id)
   if _supports_project_scoped_timetable_db():
       return db_manager.clear_timetable_records_by_project(active_project_id)
   return db_manager.clear_timetable_records()




def insert_timetable_rows(project_id: str, db_ready_payload: list):
   active_project_id = normalize_project_id(project_id)
   if _supports_project_scoped_timetable_db():
       return db_manager.insert_batch_timetable_slots_by_project(active_project_id, db_ready_payload)
   return db_manager.insert_batch_timetable_slots(db_ready_payload)




# ==============================================================================
# 📋 REGEX ENGINE & LEXICON FILTER MATRIX CONFIGURATION
# ==============================================================================
CODE_PATTERN = re.compile(r'\b(MPU\d{4}\.\d|G\d{4}|[A-Z]{2,4}\s*\d{3,4}\*?)\b', re.IGNORECASE)
# Detects:
# - (Week 1-14)
# - (WEEK1-14)
# - Week 1-14
# - WEEK: 1-14
# - WK 1-14
# - W1-14
# - Week 1 14, in case OCR drops the dash
WEEK_PATTERN = re.compile(
   r'\(?\s*(?:WEEK|WK|W)\s*[:\-]?\s*(\d{1,2})\s*(?:[-–—~]|\bTO\b|\s+)\s*(\d{1,2})\s*\)?',
   re.IGNORECASE
)
VENUE_PATTERN = re.compile(r'(?:VENUE\s+)?([A-Z]\d{1,2}#(?:[A-Z]?\d+)|TBC)', re.IGNORECASE)


NAME_MARKERS = {
   "binti", "bin", "a/l", "a/p", "mohd", "mohamad", "muhamad", "muhammad",
   "dr", "prof", "assoc", "assistant", "kumar", "sevamalai", "ganapathy",
   "subashini", "yoong", "kooi", "kuan", "hassan", "ahmad", "nazmi", "safian",
   "nahar", "lutfun", "akma", "saravan", "nallappan", "clara", "teo", "bee", "guan"
}


COURSE_DICTIONARY = {
   "technology", "application", "internet", "of", "things", "project",
   "elective", "academic", "software", "engineering", "architecture", "design",
   "patterns", "information", "security", "cloud", "computing", "introduction",
   "mobile", "system", "fundamental", "research", "programming", "community", "service",
   "advanced", "data", "structures", "algorithms", "database", "network", "web", "devops"
}


# ==============================================================================
# 🛑 NOISE & ADMINISTRATIVE HEADER FILTER
# ==============================================================================
def should_ignore_text(text: str) -> bool:
   if not text:
       return True
   normalized = text.strip().lower()
   ignore_keywords = [
       "timetable", "export timetable", "export", "semester",
       "my weekly academic schedule", "7-day grid", "copyright",
       "xiamen university malaysia", "all rights reserved"
   ]
   if any(keyword in normalized for keyword in ignore_keywords):
       return True


   ignore_patterns = [
       r'\b\d{4}/\d{2}\b', r'\b\d{2}/\d{4}\b', r'\b\d{4}-\d{2}\b',
       r'\byear\s*/\s*month\b', r'\bsemester\s+\d+\b', r'©\s*\d{4}',
       r'^[\s\d\.\,\:\-\|_xX]+$',
   ]
   for pattern in ignore_patterns:
       if re.search(pattern, normalized):
           return True
   return False




def classify_line_hybrid(text_line: str) -> str:
   words = [w.lower() for w in re.findall(r'\b\w+\b', text_line)]
   if not words:
       return "EMPTY"


   title_score = 0
   lecturer_score = 0
   if "," in text_line:
       if any(suff in text_line.lower() for suff in {"phd", "msc", "ts", "ir", "dr", "prof"}):
           lecturer_score += 4


   for word in words:
       if word.isdigit() or len(word) <= 2:
           continue


       is_matched = False
       if word in NAME_MARKERS:
           lecturer_score += 5
           is_matched = True
       if word in COURSE_DICTIONARY:
           title_score += 4
           is_matched = True
       if not is_matched:
           title_score += 1
           lecturer_score += 1


   if title_score == lecturer_score:
       has_teacher_hints = any(w in NAME_MARKERS for w in words)
       return "LECTURER" if has_teacher_hints else "COURSE_TITLE"


   return "COURSE_TITLE" if title_score > lecturer_score else "LECTURER"




# ==============================================================================
# HELPER UTILITIES & SANITIZATION
# ==============================================================================
def draw_wrapped_text(draw, text, x, y, max_width, font, fill_color, line_spacing=4):
   words = text.split()
   lines = []
   current_line = []
   for word in words:
       test_line = ' '.join(current_line + [word])
       bbox = draw.textbbox((0, 0), test_line, font=font)
       if (bbox[2] - bbox[0]) <= max_width:
           current_line.append(word)
       else:
           if current_line:
               lines.append(' '.join(current_line))
           current_line = [word]
   if current_line:
       lines.append(' '.join(current_line))


   current_y = y
   for line in lines:
       draw.text((x, current_y), line, fill=fill_color, font=font)
       bbox = draw.textbbox((x, current_y), line, font=font)
       current_y += (bbox[3] - bbox[1]) + line_spacing
   return current_y




def sanitize_venue_string(venue_str: str) -> str:
   if not venue_str:
       return "ASSIGNED ROOM"
   return venue_str.strip().upper()




def extract_week_and_clean_text(text: str):
   """
   Detect academic week labels from an OCR token/line and remove the week segment
   so it will not be saved into course_name.


   Examples:
   Input : "Introduction Of Cloud Computing (Week 1-14)"
   Output: ("WEEK 1-14", "Introduction Of Cloud Computing")


   Input : "Introduction Of Cloud Computing WEEK1-14"
   Output: ("WEEK 1-14", "Introduction Of Cloud Computing")
   """
   if not text:
       return None, text


   week_match = WEEK_PATTERN.search(text)


   if not week_match:
       return None, text


   week_label = f"WEEK {week_match.group(1)}-{week_match.group(2)}"


   cleaned_text = WEEK_PATTERN.sub(" ", text, count=1)
   cleaned_text = re.sub(r"\s+", " ", cleaned_text)
   cleaned_text = cleaned_text.strip(" *-:()[]{}")


   return week_label, cleaned_text




def clean_week_from_course_name(course_name_text: str, current_academic_week: str = "ALL WEEKS"):
   """
   Final safety cleaning before saving course_name to database/frontend.
   This catches week text that survived token processing after name_parts are joined.
   """
   if not course_name_text:
       return "", current_academic_week


   detected_week, cleaned_name = extract_week_and_clean_text(course_name_text)


   if detected_week:
       current_academic_week = detected_week
       course_name_text = cleaned_name


   # Extra safety: remove any remaining week pattern occurrences.
   course_name_text = WEEK_PATTERN.sub(" ", course_name_text)
   course_name_text = re.sub(r"\s+", " ", course_name_text)
   course_name_text = course_name_text.strip(" *-:()[]{}")


   return course_name_text, current_academic_week




def run_tesseract_to_spatial_tokens(file_path: str) -> list:
   try:
       import pytesseract


       # Keep your existing deployment path, but allow local environment override.
       custom_cmd = os.environ.get("TESSERACT_CMD")
       if custom_cmd:
           pytesseract.pytesseract.tesseract_cmd = custom_cmd
       elif os.path.exists('/opt/homebrew/bin/tesseract'):
           pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'


       img = cv2.imread(file_path)
       if img is None:
           raise ValueError("CV2 failed to read image layout frame matrix reference.")


       gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
       data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)


       ocr_results = []
       for i in range(len(data['text'])):
           text = data['text'][i].strip()
           if text:
               x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
               box = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
               ocr_results.append((box, text))
       return ocr_results
   except Exception as e:
       raise HTTPException(status_code=500, detail=f"Spatial token extraction failed: {str(e)}")




# ==============================================================================
# 🔄 MATRIX TRANSFORMATION: TIMETABLE BLOCKS TO RECURRING ABSOLUTE INTERVALS
# ==============================================================================
def populate_scheduler_clash_matrix(new_slots: list, project_id: str = "project-1"):
   """
   Transforms structural raw slots into high-density absolute calendar ranges
   and pipes them straight into the optimizer engine constraint table.
   Generates a continuous 14-week block representation starting from the current date.
   """
   active_project_id = normalize_project_id(project_id)


   try:
       scheduler_db.clear_timetable_events(active_project_id)  # Avoid data drift duplication only for active profile
       base_start_date = datetime.now()


       for slot in new_slots:
           course_code = slot["course_code"]
           target_day_name = slot["class_day"]


           try:
               target_day_idx = days_list.index(target_day_name)
           except ValueError:
               continue


           start_str = slot["start_time"]
           end_str = slot["end_time"]


           start_h, start_m = map(int, start_str.split(":"))
           end_h, end_m = map(int, end_str.split(":"))


           # Loop over a standard academic trimester horizon (14 weeks)
           for week_offset in range(14):
               current_week_start = base_start_date + timedelta(weeks=week_offset)
               days_ahead = target_day_idx - current_week_start.weekday()


               # Align correct absolute weekday
               resolved_date = current_week_start + timedelta(days=days_ahead)


               absolute_start = datetime.combine(resolved_date.date(), datetime_time(start_h, start_m))
               absolute_end = datetime.combine(resolved_date.date(), datetime_time(end_h, end_m))


               # Write to Scheduler's inter-module link architecture
               scheduler_db.insert_timetable_event(
                   project_id=active_project_id,
                   course_code=course_code,
                   start_iso=absolute_start.strftime("%Y-%m-%d %H:%M:%S"),
                   end_iso=absolute_end.strftime("%Y-%m-%d %H:%M:%S")
               )
   except Exception as e:
       print(f"⚠️ Non-critical failure syncing scheduler clash boundaries matrix: {str(e)}")




# ==============================================================================
# ROUTER API ACTIONS
# ==============================================================================


# 🌟 NEW ENDPOINT: Strict status check decoupled from specific calendar dates
@router.get("/api/timetable-status")
async def get_timetable_status(project_id: str = Query(default="project-1")):
   """
   📡 SYSTEM PROFILE STATUS ENGINE
   Tells the frontend onboarding manager whether a valid file has been captured or not.
   """
   try:
       active_project_id = normalize_project_id(project_id)
       rows = get_timetable_rows(active_project_id)
       return {
           "success": True,
           "project_id": active_project_id,
           "has_timetable": len(rows) > 0,
           "count": len(rows)
       }
   except Exception as e:
       return {"success": False, "has_timetable": False, "error": str(e)}


@router.delete("/api/delete-workspace/{project_id}")
async def delete_workspace(project_id: str):
   """
   Deletes one complete timetable workspace/profile.


   It removes:
   1. Timetable OCR/extracted rows from timetable.db
   2. Scheduler timetable clash events from scheduler.db
   3. Saved assignment task milestones from scheduler.db
   """
   active_project_id = normalize_project_id(project_id)


   try:
       # 1. Clear timetable records from timetable.db
       clear_timetable_rows(active_project_id)


       # 2. Clear scheduler timetable clash events
       scheduler_db.clear_timetable_events(active_project_id)


       # 3. Clear scheduled tasks/milestones from scheduler.db
       with scheduler_db.get_connection() as conn:
           cursor = conn.cursor()


           cursor.execute(
               "DELETE FROM tasks WHERE project_id = ?",
               (active_project_id,)
           )


           cursor.execute(
               "DELETE FROM timetable_events WHERE project_id = ?",
               (active_project_id,)
           )


           conn.commit()


       return {
           "success": True,
           "project_id": active_project_id,
           "message": "Timetable workspace and all related records were deleted successfully."
       }


   except Exception as e:
       raise HTTPException(
           status_code=500,
           detail=f"Failed to delete timetable workspace: {str(e)}"
       )
  
@router.get("/api/timetable-data")
async def get_timetable_data(project_id: str = Query(default="project-1")):
   try:
       active_project_id = normalize_project_id(project_id)
       rows = get_timetable_rows(active_project_id)
       return {
           "success": True,
           "project_id": active_project_id,
           "has_timetable": len(rows) > 0,
           "data": [
               {
                   "course_code": r[0],
                   "course_name": r[1],
                   "course_venue": r[2],
                   "class_day": r[3],
                   "start_time": r[4],
                   "end_time": r[5]
               }
               for r in rows
           ]
       }
   except Exception as e:
       raise HTTPException(status_code=500, detail=str(e))




@router.post("/api/upload-timetable")
async def upload_timetable(
   file: UploadFile = File(...),
   project_id: str = Form(default="project-1")
):
   active_project_id = normalize_project_id(project_id)


   if not file.content_type.startswith("image/"):
       raise HTTPException(status_code=400, detail="Uploaded file must be a valid image format.")


   upload_dir = os.path.join(PROJECT_ROOT, "uploads")
   os.makedirs(upload_dir, exist_ok=True)
   safe_filename = os.path.basename(file.filename)
   file_path = os.path.join(upload_dir, f"{active_project_id}_{safe_filename}")


   try:
       # ── PHASE 1: DISK IO PROCESSING ──────────────────────────────────────
       file_bytes = await file.read()
       with open(file_path, "wb") as buffer:
           buffer.write(file_bytes)


       # ── PHASE 2: OCR TEXT AND SPATIAL LAYOUT EXTRACTION ──────────────────
       spatial_tokens = run_tesseract_to_spatial_tokens(file_path)


       # ── PHASE 3: OPENCV GEOMETRIC MATRIX SEGMENTATION ─────────────────────
       geometric_slots = parse_opencv_blocks_to_slots(spatial_tokens, file_path)


       new_timetable_payload = []


       # ── PHASE 4: RESTRUCTURE DATA WITH DETAILED REGEX & LEXICON FILTERS ───
       for slot in geometric_slots:
           raw_card_tokens = slot.get("raw_tokens", [])


           course_code = "UNKNOWN"
           academic_week = "ALL WEEKS"
           course_venue = "ASSIGNED ROOM"


           name_parts = []
           lecturer_parts = []


           # Pre-scan the full OCR card because OCR may split "(Week 1-14)"
           # across multiple tokens. This only stores the week value.
           full_card_text = " ".join(str(token).strip() for token in raw_card_tokens if str(token).strip())
           detected_card_week, _ = extract_week_and_clean_text(full_card_text)
           if detected_card_week:
               academic_week = detected_card_week


           for token_text in raw_card_tokens:
               txt = token_text.strip()


               if should_ignore_text(txt):
                   continue


               # 1. Detect course code but do not discard the whole line.
               #    This prevents losing course name if OCR merges code + title.
               code_match = CODE_PATTERN.search(txt)
               if code_match:
                   course_code = code_match.group(0).replace(" ", "").upper()
                   txt = CODE_PATTERN.sub(" ", txt, count=1)
                   txt = re.sub(r"\s+", " ", txt).strip(" *-:()[]{}")


                   if not txt:
                       continue


               # 2. Detect academic week and remove it from the remaining text.
               #    Example: "Introduction Of Cloud Computing (Week 1-14)"
               #    becomes: "Introduction Of Cloud Computing"
               detected_week, cleaned_txt = extract_week_and_clean_text(txt)
               if detected_week:
                   academic_week = detected_week
                   txt = cleaned_txt


                   if not txt:
                       continue


               # 3. Detect venue but do not discard useful remaining text.
               venue_match = VENUE_PATTERN.search(txt)
               if venue_match:
                   course_venue = venue_match.group(1).upper()
                   txt = VENUE_PATTERN.sub(" ", txt, count=1)
                   txt = re.sub(r"\s+", " ", txt).strip(" *-:()[]{}")


                   if not txt:
                       continue


               line_type = classify_line_hybrid(txt)
               if line_type == "LECTURER":
                   lecturer_parts.append(txt)
               elif line_type == "COURSE_TITLE":
                   name_parts.append(txt)


           final_course_name_raw = " ".join(name_parts).strip(" *-:")
           final_course_name_raw, academic_week = clean_week_from_course_name(
               final_course_name_raw,
               academic_week
           )


           final_course_name = final_course_name_raw.title()
           if not final_course_name:
               final_course_name = f"Module {course_code}"


           final_lecturer_raw = " ".join(lecturer_parts).strip()
           final_lecturer_raw, academic_week = clean_week_from_course_name(
               final_lecturer_raw,
               academic_week
           )


           final_lecturer = final_lecturer_raw.title()
           if not final_lecturer:
               final_lecturer = "NOT ASSIGNED"


           new_timetable_payload.append({
               "course_code": course_code,
               "course_name": final_course_name,
               "course_venue": course_venue if course_venue != "ASSIGNED ROOM" else slot.get("course_venue", "ASSIGNED ROOM"),
               "class_day": slot["class_day"],
               "start_time": slot["start_time"],
               "end_time": slot["end_time"],
               "lecturer_name": final_lecturer,
               "academic_week": academic_week
           })


       if not new_timetable_payload:
           raise HTTPException(status_code=422, detail="System extraction failed. Bounding boxes unaligned.")


       # ==============================================================================
       # 📊 BACKEND TERMINAL LOG EXTRACTION REPORT ENGINE
       # ==============================================================================
       print("\n" + "╔" + "═" * 98 + "╗")
       print(f"║ 📡 [CV + REGEX/LEXICON ENGINE REPORT] TARGET SOURCE FILE: {file.filename:<37} ║")
       print(f"║ 🧭 ACTIVE PROJECT PROFILE: {active_project_id:<70} ║")
       print("╠" + "═" * 98 + "╣")
       print(f"║ Total Identified Coordinate Blocks: {len(new_timetable_payload):<60} ║")
       print("╠" + "═" * 98 + "╣")


       for i, slot in enumerate(new_timetable_payload, start=1):
           formatted_time = f"{slot['start_time']} - {slot['end_time']}"
           print(f"║ Slot #{i:<2} ─────────────────────────────────────────────────────────────────────────────────────── ║")
           print(f"║   • COURSE CODE : {slot.get('course_code', 'N/A'):<81} ║")
           print(f"║   • COURSE NAME : {slot.get('course_name', 'N/A'):<81} ║")
           print(f"║   • LECTURER    : {slot.get('lecturer_name', 'NOT ASSIGNED'):<81} ║")
           print(f"║   • VENUE/ROOM  : {slot.get('course_venue', 'ASSIGNED ROOM'):<81} ║")
           print(f"║   • WEEK        : {slot.get('academic_week', 'ALL WEEKS'):<81} ║")
           print(f"║   • DAY OF WEEK : {slot.get('class_day', 'Monday'):<81} ║")
           print(f"║   • TIME FRAME  : {formatted_time:<81} ║")
           if i < len(new_timetable_payload):
               print("║                                                                                                  ║")


       print("╚" + "═" * 98 + "╝\n")


       # ── PHASE 5: RE-POPULATE DATABASE WITH FILTERED RECORDS ──────────────
       clear_timetable_rows(active_project_id)


       db_ready_payload = []
       for slot in new_timetable_payload:
           db_ready_payload.append({
               "course_code": slot["course_code"],
               "course_name": slot["course_name"],
               "course_venue": slot["course_venue"],
               "class_day": slot["class_day"],
               "start_time": slot["start_time"],
               "end_time": slot["end_time"]
           })


       insert_timetable_rows(active_project_id, db_ready_payload)


       # 🌟 LINK CRITICAL WINDOW: Convert structural slots to absolute scheduler timelines
       populate_scheduler_clash_matrix(db_ready_payload, active_project_id)


       return {
           "success": True,
           "project_id": active_project_id,
           "filename": file.filename,
           "extracted_count": len(new_timetable_payload)
       }
   except Exception as e:
       if isinstance(e, HTTPException):
           raise e
       raise HTTPException(status_code=500, detail=str(e))
   finally:
       if os.path.exists(file_path):
           os.remove(file_path)




@router.post("/api/clear-timetable")
async def clear_timetable(project_id: str = Form(default="project-1")):
   active_project_id = normalize_project_id(project_id)
   try:
       clear_timetable_rows(active_project_id)
       # Ensure the cross-module optimization ledger is synchronized upon erasure
       scheduler_db.clear_timetable_events(active_project_id)
       return {
           "success": True,
           "project_id": active_project_id,
           "message": "Selected timetable profile was cleared successfully."
       }
   except Exception as e:
       raise HTTPException(status_code=500, detail=f"Wipe operation failed: {str(e)}")




@router.get("/api/export-timetable-image")
async def export_timetable_image(project_id: str = Query(default="project-1")):
   active_project_id = normalize_project_id(project_id)
   try:
       rows = get_timetable_rows(active_project_id)
       if not rows:
           raise HTTPException(status_code=400, detail="No timetable data exists to export.")


       canvas_w, canvas_h = 1800, 1200
       image = Image.new("RGB", (canvas_w, canvas_h), "#F8FAFC")
       draw = ImageDraw.Draw(image)
       font_paths = [
           "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
           "/System/Library/Fonts/Helvetica.ttc",
           "C:\\Windows\\Fonts\\arial.ttf",
           "arial.ttf"
       ]
       font_title = font_header = font_code = font_body = None
       for path in font_paths:
           try:
               font_title = ImageFont.truetype(path, 28)
               font_header = ImageFont.truetype(path, 14)
               font_code = ImageFont.truetype(path, 14)
               font_body = ImageFont.truetype(path, 12)
               break
           except IOError:
               continue


       if not font_body:
           font_title = font_header = font_code = font_body = ImageFont.load_default()


       left_margin, top_margin = 140, 100
       col_width = (canvas_w - left_margin - 40) / 7
       row_height = (canvas_h - top_margin - 60) / 14
       hours_list = [f"{h}:00" for h in range(8, 23)]


       draw.rectangle([(0, 0), (canvas_w, top_margin - 15)], fill="#0F172A")
       draw.text((40, 28), f"MY WEEKLY ACADEMIC SCHEDULE - {active_project_id}", fill="#FFFFFF", font=font_title)


       for idx, day in enumerate(days_list):
           x_pos = left_margin + (idx * col_width)
           draw.rectangle([(x_pos, top_margin - 15), (x_pos + col_width - 6), (top_margin + 25)], fill="#E2E8F0")
           bbox = draw.textbbox((0, 0), day, font=font_header)
           text_w = bbox[2] - bbox[0]
           center_offset = (col_width - 6 - text_w) / 2
           draw.text((x_pos + center_offset, top_margin - 2), day, fill="#1E293B", font=font_header)


       for idx, hour in enumerate(hours_list):
           y_pos = top_margin + 35 + (idx * row_height)
           draw.text((35, y_pos), hour, fill="#64748B", font=font_header)
           if idx < 15:
               draw.line([(left_margin, y_pos), (canvas_w - 40, y_pos)], fill="#E2E8F0", width=1)


       for r in rows:
           code, name, room, day, start, end = r[0], r[1], r[2], r[3], r[4], r[5]
           if day not in days_list:
               continue


           try:
               start_h = int(start.split(":")[0])
               end_h = int(end.split(":")[0])
               day_idx = days_list.index(day)


               start_row_idx = start_h - 8
               duration_hours = end_h - start_h


               if start_row_idx < 0 or (start_row_idx + duration_hours) > 15:
                   continue


               box_x1 = left_margin + (day_idx * col_width) + 3
               box_y1 = top_margin + 35 + (start_row_idx * row_height) + 3
               box_x2 = box_x1 + col_width - 8
               box_y2 = box_y1 + (duration_hours * row_height) - 6


               draw.rectangle([(box_x1, box_y1), (box_x2, box_y2)], fill="#0284C7", outline="#0369A1", width=1)


               padding = 10
               usable_width = (box_x2 - box_x1) - (padding * 2)
               current_y = box_y1 + padding


               draw.text((box_x1 + padding, current_y), code, fill="#FFFFFF", font=font_code)
               current_y += 18
               draw.text((box_x1 + padding, current_y), sanitize_venue_string(room), fill="#E0F2FE", font=font_body)
               current_y += 16


               draw_wrapped_text(
                   draw=draw,
                   text=name,
                   x=box_x1 + padding,
                   y=current_y,
                   max_width=usable_width,
                   font=font_body,
                   fill_color="#FFFFFF"
               )
           except Exception as e:
               print(f"⚠️ Render block dropped safely due to layout crash: {e}")
               continue


       img_buffer = io.BytesIO()
       image.save(img_buffer, format="JPEG", quality=100)
       img_buffer.seek(0)
       return StreamingResponse(
           img_buffer,
           media_type="image/jpeg",
           headers={"Content-Disposition": f"attachment; filename=timetable_export_{active_project_id}.jpg"}
       )
   except Exception as e:
       raise HTTPException(status_code=500, detail=f"Image compilation generation crash: {str(e)}")



