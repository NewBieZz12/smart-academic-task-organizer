#assignment_summarizer.py
import os
import shutil
import re
import time
import json
import traceback
import requests
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel, Field
from typing import List


try:
   import pypdf
except ImportError:
   pypdf = None


router = APIRouter(prefix="/api/assignment", tags=["Assignment Summarizer Engine"])


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploaded_assignments")
OLLAMA_API_URL = "http://localhost:11434/api/generate"


# ==============================================================================
# STRICT CORE SCHEMAS (Only containing your target output array)
# ==============================================================================
class SummarizedAssignmentResponse(BaseModel):
   success: bool = Field(default=True)
   filename: str
   core_tasks: List[str] = Field(default_factory=list, description="Strictly extracted task milestones in UPPERCASE")




# ==============================================================================
# STRIPPED-DOWN TEXT EXTRACTOR
# ==============================================================================
class IntegratedFileTextExtractor:
   @staticmethod
   def extract_text(file_path: str) -> str:
       ext = os.path.splitext(file_path)[1].lower()
       if ext == '.txt':
           with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
               return f.read()
       elif ext == '.pdf':
           if pypdf is None:
               raise ImportError("The 'pypdf' package is missing. Run: pip install pypdf")
           text_content = []
           with open(file_path, 'rb') as f:
               reader = pypdf.PdfReader(f)
               for page in reader.pages:
                   page_text = page.extract_text()
                   if page_text:
                       text_content.append(page_text)
           return "\n".join(text_content)
       return ""




# ==============================================================================
# CORE ROUTER ENDPOINT (Strict Boundary Slicing & Targeted LLM Summarization)
# ==============================================================================
@router.post("/summarize", response_model=SummarizedAssignmentResponse)
async def upload_and_summarize_assignment(file: UploadFile = File(...)):
   """
   Slices the assignment text strictly between 'Evaluation Breakdown' and 'MARKING RUBRICS/APPENDIX',
   falling back to the absolute end of the file if no terminal rubric anchor is matched.
   """
   if not file.filename.lower().endswith(('.pdf', '.txt')):
       raise HTTPException(status_code=400, detail="Invalid format. Please supply a standard .pdf or .txt brief.")


   file_path = ""
   try:
       # 1. Save file to disk securely
       os.makedirs(UPLOAD_DIR, exist_ok=True)
       file_path = os.path.join(UPLOAD_DIR, f"sum_{int(time.time())}_{file.filename}")
     
       with open(file_path, "wb") as buffer:
           shutil.copyfileobj(file.file, buffer)


       # 2. Extract full raw text
       raw_text = IntegratedFileTextExtractor.extract_text(file_path)
       if not raw_text.strip():
           raise HTTPException(status_code=400, detail="Document layout parsing yielded empty parameters.")


       # Normalize spaces to make regex anchoring matching ultra-stable
       normalized_text = re.sub(r'\s+', ' ', raw_text)
       lower_text = normalized_text.lower()


       # 3. ─── STAGE 1: ANCHOR START SLICING ───
       start_pattern = re.compile(r'(evaluation|assessment)\s+breakdown.*?\btotal\/?\s*(\d{2,3})', re.DOTALL)
       start_match = start_pattern.search(lower_text)


       if start_match:
           start_idx = start_match.end()
           print(f"⚓ [BOUND START] Found 'Evaluation Breakdown' total score anchor.")
       else:
           secondary_pattern = re.compile(r'\btotal\s*[\/\\\|\:]\s*(\d{2,3})\b')
           secondary_match = secondary_pattern.search(lower_text)
           if secondary_match:
               start_idx = secondary_match.end()
               print(f"⚓ [BOUND START] Found fallback 'TOTAL/XX' anchor.")
           else:
               start_idx = 0
               print("⚠️ [BOUND START] Warning: Primary evaluation anchors not found. Starting from index 0.")


       # 4. ─── STAGE 2: ANCHOR STOP SLICING ───
       remaining_text = normalized_text[start_idx:]
       stop_pattern = re.compile(r'(MARKING\s+RUBRICS?|APPENDIX|RUBRICS|RUBRIC)')
       stop_match = stop_pattern.search(remaining_text)


       if stop_match:
           end_idx = start_idx + stop_match.start()
           print(f"🛑 [BOUND STOP] Slicing text right before strict anchor: '{stop_match.group(1)}'.")
       else:
           end_idx = len(normalized_text)
           print("ℹ️ [BOUND STOP] No strict rubric/appendix anchors discovered. Capturing remaining text to the absolute end of file.")


       # Extract the isolated operational target window text string
       targeted_zone_text = normalized_text[start_idx:end_idx].strip()


       if not targeted_zone_text:
           raise HTTPException(
               status_code=400,
               detail="The segmented text zone between your evaluation anchors and rubrics turned out to be empty."
           )


       # 5. Send only the sliced zone text to your local LLM engine
       system_instruction = (
           "You are a strict task extraction assistant. Read the assignment segment provided and extract.\n"
           "Rules:\n"
           "1. Extract up to 10 actionable, specific milestone items.\n"
           "2. Summarize comprehensive tasks comprehensively across the text. If tasks use a numerical order "
           "or sequential list indexing (e.g., 1., 2., Step A), maintain and align the extracted tasks to match "
           "that exact structural sequence.\n"
           "3. Fallback: If the text does not contain any numerical order or explicit list structures, synthesize "
           "and summarize the text into clear milestone tasks defining exactly what needs to be done and what the "
           "overall assignment scope is about.\n"
           "4. Do NOT extract any grading scales, course details, deadlines, or rules.\n"
           "5. Return a clean JSON array assigned to the key 'core_tasks' containing string elements. Do not return objects inside the array."
       )


       print(f"🧠 Extracting core tasks using local Qwen2.5:3b model for: {file.filename}")
       try:
           ollama_response = requests.post(
               OLLAMA_API_URL,
               json={
                   "model": "qwen2.5:3b",
                   "prompt": f"{system_instruction}\n\nTarget Sliced Text Context:\n{targeted_zone_text}",
                   "stream": False,
                   "format": "json"
               },
               timeout=30.0
           )
           ollama_response.raise_for_status()
        
           raw_response_text = ollama_response.json().get("response", "{}")
           model_data = json.loads(raw_response_text)
        
       except Exception as ollama_err:
           print(f"❌ Ollama task parsing crash: {ollama_err}")
           raise HTTPException(
               status_code=503,
               detail="Local LLM service failed. Verify 'ollama run qwen2.5:3b' is up and healthy."
           )


       # ==============================================================================
       # 🛠️ FIXED STEP 6: ROBUST COMPONENT EXTRACTION & STRIP PARSING
       # ==============================================================================
       raw_core_tasks = model_data.get("core_tasks", [])
       validated_string_tasks = []


       for task in raw_core_tasks:
           if isinstance(task, dict):
               # Pull the main descriptive values safely from the object keys Qwen generated
               task_str = task.get("description") or task.get("task") or task.get("text") or str(task)
           else:
               task_str = str(task)
          
           # Ensure it is converted to UPPERCASE as expected by your scheme rules
           validated_string_tasks.append(task_str.strip().upper())


       output_data = {
           "success": True,
           "filename": file.filename,
           "core_tasks": validated_string_tasks
       }


       # ==============================================================================
       # 📝 QWEN JSON SUMMARY & SOURCE TEXT TERMINAL ENGINE LOG
       # ==============================================================================
       print("\n" + "="*80)
       print(f"📡 [QWEN PROCESSING MATRIX REPORT] FILE: {file.filename}")
       print("="*80)
       print("📖 [SOURCE TEXT - SLICED ZONE EXTRACT]:")
       print(f"\"{targeted_zone_text}\"")
       print("-" * 80)
       print("🤖 [RAW QWEN GENERATED JSON DATA]:")
       print(json.dumps(model_data, indent=4, ensure_ascii=False))
       print("-" * 80)
       print("📦 [FINAL SANITIZED BACKEND API OUTPUT]:")
       print(json.dumps(output_data, indent=4, ensure_ascii=False))
       print("="*80 + "\n")


       return output_data


   except HTTPException as http_ex:
       raise http_ex
   except Exception as e:
       traceback.print_exc()
       raise HTTPException(status_code=500, detail=f"Assignment parser system exception: {str(e)}")


   finally:
       # Housekeeping: instantly remove temporary cached file allocations
       if file_path and os.path.exists(file_path):
           os.remove(file_path)

