#assignment_parser.py
import os
import shutil
import re
import time
import json
import traceback
import pdfplumber
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel, Field

# 🌟 TRANSFORMERS: Token Classification Infrastructure
from transformers import BertTokenizerFast, BertForTokenClassification, pipeline

# 🌟 CONNECTED: Persistence layer
from database.scheduler_db import get_db, TasksDatabaseManager
db_manager = TasksDatabaseManager()

router = APIRouter(prefix="/api/assignment", tags=["Assignment Hybrid Extractor"])

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploaded_assignments")
MODEL_DIR = os.path.join(PROJECT_ROOT, "saved_assignment_bert_model")

os.makedirs(UPLOAD_DIR, exist_ok=True)

from database.file_processor import FileTextExtractor


def normalize_project_id(project_id: str = None) -> str:
    """Return a safe workspace identifier for database isolation."""
    cleaned = str(project_id or "").strip()
    return cleaned if cleaned else "project-1"

# ==============================================================================
# ASSIGNMENT TEMPLATE VALIDATION & UTILITIES
# ==============================================================================
TEMPLATE_OFFICIAL_HEADERS = [
    "OFFICE OF ACADEMIC AFFAIRS",
    "REFERENCE NO",
    "EFFECTIVE DATE",
    "DESCRIPTION OF COURSEWORK",
]

def validate_assignment_template(extracted_text: str) -> bool:
    raw_clean = (
        extracted_text.upper()
        .replace('"', '')
        .replace(',', ' ')
        .replace(':', ' ')
        .replace('-', ' ')
    )

    text_upper = " ".join(raw_clean.split())

    matched_headers = [
        h for h in TEMPLATE_OFFICIAL_HEADERS
        if h in text_upper
    ]

    has_clo_marker = bool(re.search(r'\bCLO\s*\d+\b', text_upper))

    return len(matched_headers) >= 1 and has_clo_marker


def remove_template_headers(extracted_text: str) -> str:
    """
    Remove fixed template header information after validation.
    """

    patterns = [
        r'OFFICE\s+OF\s+ACADEMIC\s+AFFAIRS\s*',
        r'REFERENCE\s+NO\.?\s*:.*?(?:\n|$)',
        r'EFFECTIVE\s+DATE\s*:.*?(?:\n|$)',
    ]

    cleaned = extracted_text

    for pattern in patterns:
        cleaned = re.sub(
            pattern,
            "",
            cleaned,
            flags=re.IGNORECASE
        )

    return cleaned.strip()

# Target validation labels mapping directly to your fine-tuned BERT entity heads
TARGET_LABELS = ["PROJECT_NAME", "COURSE_NAME", "TASK_TYPE", "DEADLINE"]

bert_nlp_pipeline = None

def load_local_bert_model():
    global bert_nlp_pipeline
    if bert_nlp_pipeline is None:
        if not os.path.exists(MODEL_DIR):
            raise HTTPException(
                status_code=500,
                detail=f"BERT weights directory missing at {MODEL_DIR}."
            )
        tokenizer = BertTokenizerFast.from_pretrained(MODEL_DIR)
        model = BertForTokenClassification.from_pretrained(MODEL_DIR)
        bert_nlp_pipeline = pipeline(
            "ner",
            model=model,
            tokenizer=tokenizer,
            aggregation_strategy="simple"
        )
    return bert_nlp_pipeline

def normalize_extracted_date(text_input) -> str:
    if not text_input: return "NOT_FOUND"
    clean_text = " ".join(text_input).strip() if isinstance(text_input, list) else " ".join(text_input.split())
    if "EFFECTIVE" in clean_text.upper(): return "NOT_FOUND"

    month_mapping = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
        'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
        'january': '01', 'february': '02', 'march': '03', 'april': '04', 'june': '06',
        'july': '07', 'august': '08', 'september': '09', 'october': '10', 'november': '11', 'december': '12'
    }
    clean_text_normalized = clean_text.replace('.', '')

    # Pattern 1: Month DD, YYYY
    pattern_month_first = r'\b([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?[\s,]+\s*(\d{4})\b'
    match_mf = re.search(pattern_month_first, clean_text_normalized, re.IGNORECASE)
    if match_mf:
        try:
            m_str = match_mf.group(1).lower()[:3]
            d_str = match_mf.group(2).zfill(2)
            y_str = match_mf.group(3)
            if m_str in month_mapping: return f"{d_str}/{month_mapping[m_str]}/{y_str}"
        except Exception: pass

    # Pattern 2: DD Month YYYY
    pattern_day_first = r'\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\s+(\d{4})\b'
    match_df = re.search(pattern_day_first, clean_text_normalized, re.IGNORECASE)
    if match_df:
        try:
            d_str = match_df.group(1).zfill(2)
            m_str = match_df.group(2).lower()[:3]
            y_str = match_df.group(3)
            if m_str in month_mapping: return f"{d_str}/{month_mapping[m_str]}/{y_str}"
        except Exception: pass

    # Pattern 3: Numerical Standard
    pattern_numeric = r'\b(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})\b'
    match_num = re.search(pattern_numeric, clean_text_normalized)
    if match_num:
        try: return f"{match_num.group(1).zfill(2)}/{match_num.group(2).zfill(2)}/{match_num.group(3)}"
        except Exception: pass
        
    return "NOT_FOUND"

def convert_to_calendar_iso(dd_mm_yyyy_date: str) -> str:
    if not dd_mm_yyyy_date or dd_mm_yyyy_date in ("Unable to detect", "NO_DATE_EXTRACTED", "NOT_FOUND"):
        return ""
    try:
        parts = dd_mm_yyyy_date.split('/')
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    except Exception: pass
    return ""

def remove_template_headers(text: str) -> str:
    patterns = [
        r'OFFICE\s+OF\s+ACADEMIC\s+AFFAIRS',
        r'REFERENCE\s+NO\.?\s*:.*',
        r'EFFECTIVE\s+DATE\s*:.*',
    ]

    cleaned = text

    for pattern in patterns:
        cleaned = re.sub(
            pattern,
            "",
            cleaned,
            flags=re.IGNORECASE
        )

    return cleaned


# ==============================================================================
# DATA SCHEMAS
# ==============================================================================
class ExtractedAssignmentResponse(BaseModel):
    success: bool = Field(default=True)
    project_id: str
    filename: str
    course_code: str
    course_name: str
    assignment_name: str
    submission_date: str
    calendar_iso_date: str
    extraction_method: str

class ManualTaskInput(BaseModel):
    project_id: str = Field(default="project-1", description="Active sidebar workspace/profile identifier")
    project: str = Field(..., description="Course code details")
    title: str = Field(..., description="Assignment task description header")
    deadline_iso: str = Field(..., description="Target timeline limit index (YYYY-MM-DD)")
    priority: str = Field(default="Normal")

# ==============================================================================
# ROUTER COMPARISON ENDPOINT
# ==============================================================================
@router.post("/upload", response_model=ExtractedAssignmentResponse)
async def upload_and_extract_assignment(
    file: UploadFile = File(...),
    project_id: str = Form(default="project-1")
):
    active_project_id = normalize_project_id(project_id)
    if not file.filename.lower().endswith(('.pdf', '.txt')):
        raise HTTPException(status_code=400, detail="Invalid format. Supply a standard .pdf or .txt brief.")

    file_path = os.path.join(UPLOAD_DIR, f"temp_{int(time.time())}_{file.filename}")
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        extracted_text = FileTextExtractor.extract_text(file_path)
        if not extracted_text.strip():
            raise HTTPException(status_code=400, detail="Document layout parsing yielded empty parameters.")
        if not validate_assignment_template(extracted_text):
            raise HTTPException(
                status_code=422,
                detail="Upload rejected: This document does not match the official template structure."
            )
        # Remove fixed template header before extraction
        extracted_text = remove_template_headers(extracted_text)
        nlp_pipeline = load_local_bert_model()
        clean_window = " ".join(extracted_text.split())
        all_words = clean_window.split()
        
        # ----------------------------------------------------------------------
        # RUN PIPELINE 1: PURE NER BERT BASELINE ENGINE
        # ----------------------------------------------------------------------
        pure_bert_extracted = {"PROJECT_NAME": [], "COURSE_NAME": [], "TASK_TYPE": [], "DEADLINE": []}
        chunk_size, overlap = 350, 40
        i = 0
        
        while i < len(all_words):
            words_chunk = all_words[i:i + chunk_size]
            i += (chunk_size - overlap)
            if not words_chunk: break
            
            chunk_text = " ".join(words_chunk)
            entities = nlp_pipeline(chunk_text)
            
            for ent in entities:
                label = ent.get("entity_group")
                text_val = ent.get("word", "").strip()
                confidence = ent.get("score", 0.0)
                
                if label in pure_bert_extracted and confidence >= 0.4:
                    if text_val not in pure_bert_extracted[label] and len(text_val) > 1:
                        pure_bert_extracted[label].append(text_val)

        # Build Pure BERT Results
        pure_project = " ".join(pure_bert_extracted["PROJECT_NAME"]).strip().upper()
        pure_course = " ".join(pure_bert_extracted["COURSE_NAME"]).strip().title()
        pure_task = " ".join(pure_bert_extracted["TASK_TYPE"]).strip().title()
        pure_deadline_raw = " ".join(pure_bert_extracted["DEADLINE"]).strip()
        pure_date = normalize_extracted_date(pure_bert_extracted["DEADLINE"])

        # Clean individual token string formatting variants
        pure_project_resolved = re.search(r'\b([A-Za-z]{2,4})\s*(\d{3,4})\b', pure_project)
        pure_code_final = f"{pure_project_resolved.group(1)} {pure_project_resolved.group(2)}" if pure_project_resolved else (pure_project if pure_project else "Unable to detect")
        pure_name_final = pure_course if (pure_course and "COURSE" not in pure_course.upper()) else "Unable to detect"
        pure_title_final = re.sub(r'\(\s*\d+%\s*\)', '', pure_task).strip() if pure_task else "Unable to detect"
        pure_date_final = pure_date if pure_date != "NOT_FOUND" else "NO_DATE_EXTRACTED"

        # ----------------------------------------------------------------------
        # RUN PIPELINE 2: THE 5-STAGE HYBRID PIPELINE
        # ----------------------------------------------------------------------
        # Remove literal quotes, comma noise, and normalize spaces for flawless structural lookup
        flat_normalized_text = re.sub(r'\s+', ' ', extracted_text.replace('"', '').replace("'", "").replace(",", " "))
        flat_normalized_upper = flat_normalized_text.upper()

        method_logs = {"course_code": "DEFAULT_FALLBACK", "course_name": "DEFAULT_FALLBACK", "assignment_name": "DEFAULT_FALLBACK"}
        hybrid_code, hybrid_name, hybrid_title = "Unable to detect", "Unable to detect", "Unable to detect"

        # ─── STAGE A: NATIVE TABLE MATRIX INTERCEPT (WITH LINE BREAK SANITIZATION) ───
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    for table_data in page.extract_tables():
                        for row in table_data:
                            if not row or len(row) < 2: continue
                            
                            # Clean vertical line spacing artifacts injected within native cells
                            left_cell = " ".join(str(row[0]).replace("\n", " ").split()).strip().upper()
                            right_cell = " ".join(str(row[1]).replace("\n", " ").split()).strip()
                            
                            if "COURSE CODE" in left_cell or "COURSE_CODE" in left_cell:
                                if right_cell and right_cell.lower() != "none" and len(right_cell) > 1:
                                    # Cross-verify if it matches target code format (e.g. AIT303)
                                    if re.search(r'\b[A-Z]{2,4}\s*\d{3,4}\b', right_cell.upper()): 
                                        hybrid_code = right_cell.upper()
                                    else: 
                                        hybrid_name = right_cell
                                    method_logs["course_code"] = "NATIVE_TABLE_MATRIX"
                                    
                            elif "COURSE NAME" in left_cell or "COURSE_NAME" in left_cell:
                                if right_cell and right_cell.lower() != "none" and len(right_cell) > 1:
                                    if re.search(r'\b[A-Z]{2,4}\s*\d{3,4}\b', right_cell.upper()): 
                                        hybrid_code = right_cell.upper()
                                    else: 
                                        hybrid_name = right_cell
                                    method_logs["course_name"] = "NATIVE_TABLE_MATRIX"
                                    
                            elif "ASSESSMENT TITLE" in left_cell or "ASSIGNMENT NAME" in left_cell or "ASSESSMENT_TITLE" in left_cell:
                                if right_cell and right_cell.lower() != "none" and len(right_cell) > 1:
                                    hybrid_title = right_cell
                                    method_logs["assignment_name"] = "NATIVE_TABLE_MATRIX"
        except Exception as table_err:
            print(f"⚠️ Table grid processing error: {str(table_err)}")

        # ─── STAGE B: ADAPTIVE FLAT-REGEX LOOKUPS (FIX FOR MULTI-LINE TABLE TEXT) ───
        if hybrid_code == "Unable to detect" or method_logs["course_code"] == "DEFAULT_FALLBACK":
            # Target standard bounding fields cleanly using lookahead markers
            regex_code = re.search(r'COURSE\s+CODE\s+([A-Z]{2,4}\s*\d{3,4})', flat_normalized_upper)
            if regex_code:
                hybrid_code = regex_code.group(1).strip()
                method_logs["course_code"] = "REGEX_FLAT_MATRIX_LOOKUP"
            elif pure_project_resolved:
                hybrid_code = f"{pure_project_resolved.group(1)} {pure_project_resolved.group(2)}"
                method_logs["course_code"] = "BERT_NER_EXTRACTION"
            else:
                course_code_match = re.search(r'\b(?!XMUM|OAA|PAGE|NOTE)([A-Z]{2,4})\s*(\d{3,4})\b', flat_normalized_upper)
                if course_code_match:
                    hybrid_code = f"{course_code_match.group(1)} {course_code_match.group(2)}".strip()
                    method_logs["course_code"] = "REGEX_LINE_RESTRICTED_LOOKUP"

        if hybrid_name == "Unable to detect" or method_logs["course_name"] == "DEFAULT_FALLBACK":
            # Pull strings dynamically running between Course Name header and Lecturer assignments
            regex_name = re.search(r'COURSE\s+NAME\s+(.*?)(?=\bLECTURER\b|\bACADEMIC\b|\bASSESSMENT\b|$)', flat_normalized_text, re.IGNORECASE)
            if regex_name and len(regex_name.group(1).strip()) > 2:
                hybrid_name = regex_name.group(1).strip()
                method_logs["course_name"] = "REGEX_FLAT_MATRIX_LOOKUP"
            elif pure_course and len(pure_course) > 3 and "COURSE" not in pure_course.upper():
                hybrid_name = pure_course
                method_logs["course_name"] = "BERT_NER"

        if hybrid_title == "Unable to detect" or method_logs["assignment_name"] == "DEFAULT_FALLBACK":
            # Unpack assignment metadata headers safely
            regex_title = re.search(r'ASSESSMENT\s+TITLE\s+(.*?)(?=\bA\b\.\s+INTRODUCTION|\bINTRODUCTION\b|\bLECTURER\b|\bACADEMIC\b|$)', flat_normalized_text, re.IGNORECASE)
            if regex_title and len(regex_title.group(1).strip()) > 2:
                hybrid_title = regex_title.group(1).strip()
                method_logs["assignment_name"] = "REGEX_FLAT_MATRIX_LOOKUP"
            elif pure_task and len(pure_task.strip()) > 1:
                hybrid_title = pure_task.strip()
                method_logs["assignment_name"] = "BERT_NER"

        # Sanitization processing for Hybrid variables
        hybrid_code = " ".join(hybrid_code.replace('\n', ' ').split()).upper().strip()
        hybrid_name = " ".join(hybrid_name.replace('\n', ' ').split()).strip()
        hybrid_title = " ".join(hybrid_title.replace('\n', ' ').split()).strip()

        if hybrid_name not in ("Unable to detect", "None"):
            hybrid_name = " ".join(hybrid_name.replace("*", "").strip(" -:").split()).title()

        if hybrid_title not in ("Unable to detect", "None"):
            hybrid_title = re.sub(r'\(\s*\d+%\s*\)', '', hybrid_title).strip()
            hybrid_title = " ".join(hybrid_title.replace("*", "").strip(" -:").split()).title()

        # Hybrid Deadline Resolution Channel
        hybrid_date = "NO_DATE_EXTRACTED"
        if pure_bert_extracted["DEADLINE"] and "EFFECTIVE" not in pure_deadline_raw.upper():
            bert_attempt = normalize_extracted_date(pure_bert_extracted["DEADLINE"])
            if bert_attempt != "NOT_FOUND":
                hybrid_date = bert_attempt
  
        if hybrid_date == "NO_DATE_EXTRACTED":
            deadline_anchors = re.finditer(r'(?<!EFFECTIVE\s)(?<!EFFECTIVE\sDATE\s)(?:DEADLINE|DUE\s*DATE|SUBMISSION|SUBMIT)', flat_normalized_upper)
            for anchor in deadline_anchors:
                context_chunk = flat_normalized_upper[max(0, anchor.start() - 30):min(len(flat_normalized_upper), anchor.end() + 120)]
                regex_attempt = normalize_extracted_date(context_chunk)
                if regex_attempt != "NOT_FOUND":
                    hybrid_date = regex_attempt
                    break

        iso_calendar_date = convert_to_calendar_iso(hybrid_date)
        method_used = "BERT_NER_MODEL" if method_logs["assignment_name"] == "BERT_NER" else "HYBRID_HEURISTICS"

        # ==============================================================================
        # 🖨️ SIDE-BY-SIDE BENCHMARK BACKEND TERMINAL DISPLAY
        # ==============================================================================
        print("\n📊 =====================================================================")
        print(f"📡 COMPARISON LOG REPORT FOR DEPLOYED BRIEF: {file.filename}")
        print(f"🧭 ACTIVE WORKSPACE PROJECT_ID: {active_project_id}")
        print("=========================================================================")
        print("🤖 [1] PURE NER BERT RESULT")
        print(f"  -> PROJECT_NAME : {pure_code_final}")
        print(f"  -> COURSE_NAME  : {pure_name_final}")
        print(f"  -> TASK_TYPE    : {pure_title_final}")
        print(f"  -> DEADLINE     : {pure_date_final}")
        print("-" * 73)
        print("⚡ [2] FULL HYBRID EXTRACTION PIPELINE RESULT")
        print(f"  -> PROJECT_NAME : {hybrid_code}")
        print(f"  -> COURSE_NAME  : {hybrid_name}")
        print(f"  -> TASK_TYPE    : {hybrid_title}")
        print(f"  -> DEADLINE     : {hybrid_date}")
        print("=========================================================================\n")

        # Persistence layer utilizes the balanced parameters from full hybrid extraction
        db_payload = {
            "project_id": active_project_id,
            "project": hybrid_code if hybrid_code != "Unable to detect" else "GENERAL",
            "title": hybrid_title if hybrid_title != "Unable to detect" else "Assessment Brief Tracker Task",
            "deadline_iso": iso_calendar_date if iso_calendar_date != "" else "2026-07-15",
            "priority": "Normal"
        }
        db_manager.insert_assignment_direct(project_id=active_project_id, payload=db_payload)

        return {
            "success": True,
            "project_id": active_project_id,
            "filename": file.filename,
            "course_code": hybrid_code,
            "course_name": hybrid_name,
            "assignment_name": hybrid_title,
            "submission_date": hybrid_date,
            "calendar_iso_date": iso_calendar_date,
            "extraction_method": method_used
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Assignment evaluation crash: {str(e)}")
    finally:
        if os.path.exists(file_path): os.remove(file_path)

# ==============================================================================
# MANUALLY EXTRACTED ENTRY STREAM BRIDGE ROUTE
# ==============================================================================
@router.post("/save-manual")
async def save_chat_extracted_task(payload: ManualTaskInput):
    try:
        active_project_id = normalize_project_id(payload.project_id)
        db_payload = {
            "project_id": active_project_id,
            "project": payload.project.strip().upper(),
            "title": payload.title.strip(),
            "deadline_iso": payload.deadline_iso.strip(),
            "priority": payload.priority.strip()
        }
        # Injects direct pointer bypass straight into your optimization engine db
        db_manager.insert_assignment_direct(project_id=active_project_id, payload=db_payload)
        return {
            "success": True,
            "project_id": active_project_id,
            "message": "Manual stream assignment logged."
        }
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Failed to persist manual task: {str(err)}")