import io
import logging
from abc import ABC, abstractmethod
from typing import Tuple, Optional
from PIL import Image

try:
    import pytesseract
    from pytesseract import Output
    HAS_PYTESSERACT = True
    for p in [r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]:
        import os
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break
except ImportError:
    HAS_PYTESSERACT = False

from app.config import settings

logger = logging.getLogger(__name__)


class OCRResult:
    def __init__(self, text: str, confidence: float, rotation_deg: int = 0):
        self.text = text
        self.confidence = confidence  # 0.0 to 1.0
        self.rotation_deg = rotation_deg


class BaseOCRProvider(ABC):
    @abstractmethod
    def ocr_image(self, image_bytes: bytes) -> OCRResult:
        """Run OCR on image bytes and return structured result."""
        pass


class TesseractOCRProvider(BaseOCRProvider):
    def ocr_image(self, image_bytes: bytes) -> OCRResult:
        if not HAS_PYTESSERACT:
            logger.warning("pytesseract library not available.")
            return OCRResult(text="", confidence=0.0)

        try:
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Try OSD for rotation detection
            rotation_deg = 0
            try:
                osd = pytesseract.image_to_osd(image, output_type=Output.DICT)
                rotation_deg = osd.get("rotate", 0)
                if rotation_deg in (90, 180, 270):
                    image = image.rotate(-rotation_deg, expand=True)
            except Exception:
                # OSD might fail if page has very little text or tesseract OSD data is missing
                rotation_deg = 0

            # Extract data with confidence
            data = pytesseract.image_to_data(image, output_type=Output.DICT)
            n_boxes = len(data.get("text", []))
            confidences = []
            words = []

            for i in range(n_boxes):
                text_word = data["text"][i].strip()
                conf_val = float(data["conf"][i])
                if text_word:
                    words.append(text_word)
                    if conf_val >= 0:
                        confidences.append(conf_val / 100.0)

            full_text = " ".join(words)
            if not full_text:
                full_text = pytesseract.image_to_string(image).strip()

            avg_conf = (sum(confidences) / len(confidences)) if confidences else 0.5
            return OCRResult(text=full_text, confidence=round(avg_conf, 3), rotation_deg=rotation_deg)

        except Exception as e:
            logger.warning(f"Tesseract OCR failed or tesseract binary not found in PATH: {str(e)}")
            # Graceful degraded result with low confidence
            return OCRResult(text="", confidence=0.1, rotation_deg=0)


class OpenAIVisionOCRProvider(BaseOCRProvider):
    def ocr_image(self, image_bytes: bytes) -> OCRResult:
        raise NotImplementedError(
            "OpenAI Vision OCR not implemented. Set OCR_PROVIDER=tesseract."
        )


class AzureDIProvider(BaseOCRProvider):
    def ocr_image(self, image_bytes: bytes) -> OCRResult:
        raise NotImplementedError(
            "Azure DI OCR not implemented. Set OCR_PROVIDER=tesseract."
        )


def get_ocr_provider() -> BaseOCRProvider:
    provider = settings.ocr_provider.lower()
    if provider == "openai":
        return OpenAIVisionOCRProvider()
    elif provider == "azure":
        return AzureDIProvider()
    return TesseractOCRProvider()
