import os
import importlib.util

class DocumentParser:
    def __init__(self):
        self.ocr = None

    def _init_ocr(self):
        if self.ocr is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self.ocr = RapidOCR()
            except ImportError:
                pass

    def parse_file(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return ""

        ext = os.path.splitext(file_path)[1].lower()

        try:
            if ext in ['.txt', '.md', '.py', '.json', '.csv', '.log']:
                return self._parse_txt(file_path)
            elif ext == '.pdf':
                return self._parse_pdf(file_path)
            elif ext in ['.docx', '.doc']:
                return self._parse_docx(file_path)
            elif ext in ['.png', '.jpg', '.jpeg', '.bmp', '.webp']:
                return self._parse_image(file_path)
            else:
                return f"Формат {ext} пока не поддерживается."
        except Exception as e:
            return f"Ошибка при чтении файла: {e}"

    def _parse_txt(self, file_path):
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def _parse_pdf(self, file_path):
        if importlib.util.find_spec("pypdf") is None:
            return "Библиотека pypdf не установлена."

        from pypdf import PdfReader
        text = ""
        with open(file_path, 'rb') as f:
            reader = PdfReader(f)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"

        if not text.strip():
            return "В этом PDF нет текстового слоя."
        return text.strip()

    def _parse_docx(self, file_path):
        if importlib.util.find_spec("docx") is None:
            return "Библиотека python-docx не установлена."

        import docx
        doc = docx.Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs]).strip()

    def _parse_image(self, file_path):
        self._init_ocr()
        if self.ocr is None:
            return "Модуль OCR не загружен."

        result, _ = self.ocr(file_path)
        if result:
            return "\n".join([line[1] for line in result]).strip()
        return "Текст на изображении не найден."