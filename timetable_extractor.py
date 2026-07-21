import os
import easyocr

class TimetableTextExtractor:
    # Initialize the Reader object once when the class loads to save memory
    _reader = None

    @classmethod
    def _get_reader(cls):
        """Ensures the EasyOCR reader is initialized only once (Singleton pattern)."""
        if cls._reader is None:
            print("🧠 Loading EasyOCR engine models into memory...")
            # Set gpu=True if your university server or Mac has an Apple Silicon / CUDA GPU setup
            cls._reader = easyocr.Reader(['en'], gpu=False)
        return cls._reader

    @staticmethod
    def extract_text(file_path: str) -> list:
        """
        Processes timetable screenshots (.png, .jpg, .jpeg) and extracts raw 
        structural coordinate maps including bounding boxes, text strings, and confidences.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Target image file not found at: {file_path}")
            
        extension = os.path.splitext(file_path)[1].lower()
        valid_extensions = ['.png', '.jpg', '.jpeg']
        
        if extension not in valid_extensions:
            raise ValueError(f"Unsupported image format: {extension}. Expects .png, .jpg, or .jpeg.")

        try:
            reader = TimetableTextExtractor._get_reader()
            
            print(f"👁️ Scanning image bounding boxes for text blocks...")
            results = reader.readtext(file_path)
            
            # Filter out empty strings but keep the raw structural bounding array shape intact
            clean_results = [item for item in results if item[1].strip()]
            
            print(f"✅ OCR Spatial Mapping complete. Extracted {len(clean_results)} structural coordinate nodes.")
            
            # 🎯 CRITICAL FIX: Returns the raw list layout array instead of collapsing to a single string line
            return clean_results

        except Exception as e:
            print(f"❌ OCR Extraction engine failed: {str(e)}")
            raise RuntimeError(f"Failed to parse image file: {str(e)}")