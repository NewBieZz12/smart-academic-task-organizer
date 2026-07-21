import os
from pypdf import PdfReader

class FileTextExtractor:
    @staticmethod
    def extract_text(file_path):
        """
        Determines the file extension and extracts all raw text content.
        Supported formats: .txt, .pdf
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Target file not found at: {file_path}")
            
        extension = os.path.splitext(file_path)[1].lower()
        
        if extension == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
                
        elif extension == '.pdf':
            reader = PdfReader(file_path)
            full_text = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text.append(text)
            return "\n".join(full_text)
            
        else:
            raise ValueError(f"Unsupported file format: {extension}. Please upload a .txt or .pdf file.")