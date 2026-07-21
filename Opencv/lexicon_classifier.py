import re

NAME_MARKERS = {
    "binti", "bin", "a/l", "a/p", "mohd", "mohamad", "muhamad", "muhammad",
    "dr", "prof", "assoc", "assistant", "kumar", "sevamalai", "ganapathy",
    "subashini", "yoong", "kooi", "kuan", "hassan", "ahmad", "nazmi", "safian",
    "nahar", "lutfun", "akma"
}

COURSE_DICTIONARY = {
    "technology", "application", "internet", "of", "things", "project",
    "elective", "academic", "software", "engineering", "architecture", "design",
    "patterns", "information", "security", "cloud", "computing", "introduction",
    "mobile", "system", "fundamental", "research", "programming", "community", "service",
    "advanced", "data", "structures", "algorithms", "database", "network", "web", "devops"
}

def classify_line_hybrid(text_line: str) -> str:
    """
    Evaluates whether a text token string matches a Course Title sequence
    or an Instructor's Name footprint using cross-lexicon weight distribution.
    """
    # Clean tokenization using regex to handle arbitrary punctuation safely
    words = [w.lower() for w in re.findall(r'\b\w+\b', text_line)]
    if not words:
        return "EMPTY"
        
    title_score = 0
    lecturer_score = 0
   
    # Smart comma check: only penalize if it looks like an academic qualification
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
           
        # Neutral distribution for unknown technical terms
        if not is_matched:
            title_score += 1
            lecturer_score += 1

    # --- STRUCTURAL FALLBACK TIEBREAKER ---
    if title_score == lecturer_score:
        has_teacher_hints = any(w in NAME_MARKERS for w in words)
        return "LECTURER" if has_teacher_hints else "COURSE_TITLE"
        
    return "COURSE_TITLE" if title_score > lecturer_score else "LECTURER"