import cv2
import numpy as np
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ==============================================================================
# DISCRETE TIME ROW LOCKING
# ==============================================================================
def map_pixel_to_hour_discrete(card_top, card_bot, y_lines, time_anchors):
    """
    Finds the start and end hours by checking entry boundary containment 
    across the actual detected horizontal structural grid lines.
    """
    # Fallback absolute hour matrix baseline array map
    hour_map = [8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]
    
    start_hour = 8
    end_hour = 9

    # 1-by-1 top boundary containment match with an offset cushion
    for idx in range(len(y_lines) - 1):
        if y_lines[idx] <= (card_top + 15) < y_lines[idx+1]:
            start_hour = hour_map[min(idx, len(hour_map)-1)]
            break

    # 1-by-1 bottom boundary containment match
    for idx in range(len(y_lines) - 1):
        if y_lines[idx] < (card_bot - 15) <= y_lines[idx+1]:
            end_hour = hour_map[min(idx + 1, len(hour_map)-1)]
            break

    if end_hour <= start_hour:
        end_hour = start_hour + 1

    return f"{start_hour:02d}:00", f"{end_hour:02d}:00"


# ==============================================================================
# MAIN PARSER ARCHITECTURE
# ==============================================================================
def parse_opencv_blocks_to_slots(ocr_results: list, file_path: str) -> list:
    if not ocr_results or isinstance(ocr_results, str):
        return []

    img_raw = cv2.imread(file_path)
    if img_raw is None:
        return []

    orig_h, orig_w = img_raw.shape[:2]
    STANDARD_W, STANDARD_H = 1920, 1080

    # ── 1. TIMETABLE GRID ISOLATION ──────────────────────────────────────────
    gray_raw = cv2.cvtColor(img_raw, cv2.COLOR_BGR2GRAY)
    blurred  = cv2.GaussianBlur(gray_raw, (5, 5), 0)
    _, thresh_raw = cv2.threshold(blurred, 220, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh_raw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    crop_x1, crop_y1, crop_x2, crop_y2 = 0, 0, orig_w, orig_h
    if contours:
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)
        if w > orig_w * 0.5 and h > orig_h * 0.5:
            crop_x1, crop_y1 = x, y
            crop_x2, crop_y2 = x + w, y + h

    grid_width  = crop_x2 - crop_x1
    grid_height = crop_y2 - crop_y1

    img_cropped = img_raw[crop_y1:crop_y2, crop_x1:crop_x2]
    img = cv2.resize(img_cropped, (STANDARD_W, STANDARD_H), interpolation=cv2.INTER_CUBIC)

    # ── 2. ISOLATE EXACT PHYSICAL GRID LANES ─────────────────────────────────
    gray   = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 19, 3)

    TUNING_FACTOR = 20
    h_kernel_size = STANDARD_W // TUNING_FACTOR
    v_kernel_size = STANDARD_H // TUNING_FACTOR

    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_size, 1))
    detect_horizontal = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
    h_contours, _ = cv2.findContours(detect_horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    raw_y_lines = sorted([cv2.boundingRect(c)[1] for c in h_contours])

    vertical_kernel   = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_size))
    detect_vertical   = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, vertical_kernel, iterations=2)
    v_contours, _ = cv2.findContours(detect_vertical, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    raw_x_lines = sorted([cv2.boundingRect(c)[0] for c in v_contours])

    # De-duplicate horizontal line paths (within 15px range limit)
    actual_y_lines = []
    for y_val in raw_y_lines:
        if not actual_y_lines or (y_val - actual_y_lines[-1] > 15):
            actual_y_lines.append(y_val)

    # De-duplicate vertical line paths (within 20px range limit)
    actual_x_lines = []
    for x_val in raw_x_lines:
        if not actual_x_lines or (x_val - actual_x_lines[-1] > 20):
            actual_x_lines.append(x_val)

    # ── 3. ANCHOR NORMALIZATION (Locate Dynamic Origin Border Corner) ───────
    origin_x2 = actual_x_lines[1] if len(actual_x_lines) > 1 else 180
    for item in ocr_results:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            box, text = item[0], item[1]
        elif isinstance(item, dict):
            box, text = item.get("box"), item.get("text", "")
        else:
            continue

        text_clean = text.strip().lower()
        if "time" in text_clean or "hari" in text_clean:
            try:
                box_str = str(box).replace("np.int32", "").replace("np.float64", "")
                coords  = eval(box_str) if isinstance(box_str, str) else box
                t_x2    = int((coords[2][0] - crop_x1) * (STANDARD_W / grid_width))
                matching_x = [x for x in actual_x_lines if x >= t_x2]
                if matching_x:
                    origin_x2 = matching_x[0]
                break
            except Exception:
                pass

    active_columns = [x for x in actual_x_lines if x >= origin_x2]
    if len(active_columns) < 2:
        active_columns = [180, 430, 680, 930, 1180, 1430, 1680, 1920]

    if len(actual_y_lines) < 3:
        actual_y_lines = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1080]

    # ── 4. PROCESS OCR TOKENS ────────────────────────────────────────────────
    all_content_tokens = []
    for item in ocr_results:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            box, text = item[0], item[1]
        elif isinstance(item, dict):
            box, text = item.get("box"), item.get("text", "")
        else:
            continue

        text_clean = text.strip()
        if not text_clean:
            continue  

        try:
            box_str = str(box).replace("np.int32", "").replace("np.float64", "")
            coords  = eval(box_str) if isinstance(box_str, str) else box
            cx = int(((coords[0][0] + coords[2][0]) / 2 - crop_x1) * (STANDARD_W / grid_width))
            cy = int(((coords[0][1] + coords[2][1]) / 2 - crop_y1) * (STANDARD_H / grid_height))
        except Exception:
            continue

        all_content_tokens.append({"cx": cx, "cy": cy, "text": text_clean})

    # ── 5. COLOR BLOCK CONTINGENCY DETECTION ──────────────────────────────────
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    lower_blue = np.array([90, 30, 40])
    upper_blue = np.array([135, 255, 255])
    mask_blue  = cv2.inRange(hsv, lower_blue, upper_blue)

    lower_red1 = np.array([0, 40, 40])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([165, 40, 40])
    upper_red2 = np.array([180, 255, 255])
    mask_red   = cv2.bitwise_or(cv2.inRange(hsv, lower_red1, upper_red1), cv2.inRange(hsv, lower_red2, upper_red2))

    color_mask    = cv2.bitwise_or(mask_blue, mask_red)
    card_contours, _ = cv2.findContours(color_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    days_labels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    extracted_course_blocks = []

    # ── 6. 1-BY-1 BOUNDING BOX CONTAINMENT ENGINE ────────────────────────────
    for cnt in card_contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w < 35 or h < 35:
            continue

        card_tokens = [t for t in all_content_tokens if x <= t["cx"] <= (x + w) and y <= t["cy"] <= (y + h)]
        if not card_tokens:
            continue

        # Passes dictionary tokens upstream as a raw string list to your mapping/NER framework
        # Metadata filtering, course naming, and week logic are handled outside this block
        raw_text_payload = [t["text"] for t in card_tokens]

        # ─── 1-BY-1 COLUMN CHECK (Stops Day Skipping) ───
        center_x = x + (w / 2.0)
        day_name = "Monday"
        
        for col_idx in range(len(active_columns) - 1):
            col_left = active_columns[col_idx]
            col_right = active_columns[col_idx + 1]
            if col_left <= center_x < col_right:
                day_name = days_labels[min(col_idx, len(days_labels) - 1)]
                break
        else:
            if center_x >= active_columns[-1]:
                day_name = days_labels[min(len(active_columns) - 1, 6)]

        # ─── 1-BY-1 ROW EDGE LOCKING (Stops 1-Hour Missing Gaps) ───
        # Note: 'time_anchors' parameter left empty as calculations use actual structural grid lanes
        start_time, end_time = map_pixel_to_hour_discrete(y, y + h, actual_y_lines, [])

        extracted_course_blocks.append({
            "class_day": day_name,
            "start_time": start_time,
            "end_time": end_time,
            "raw_tokens": raw_text_payload  # Sent over to your secondary parsing engine
        })

    day_priority = {day: idx for idx, day in enumerate(days_labels)}
    extracted_course_blocks.sort(key=lambda item: (day_priority.get(item["class_day"], 99), item["start_time"]))

    return extracted_course_blocks

