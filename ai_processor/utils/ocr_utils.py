"""OCR utilities for extracting text from images."""
import pytesseract
from PIL import Image
from pathlib import Path
from typing import List
import logging


def extract_text_from_image(image_path: Path) -> str:
    """Extracts text from an image using OCR."""
    try:
        image = Image.open(image_path)
        # Use OCR to extract text with optimized config
        text = pytesseract.image_to_string(image, config='--psm 6')
        return text.strip()
    except Exception as e:
        logging.warning(f"Failed to extract text from {image_path}: {e}")
        return ""


def extract_all_ocr_text(image_paths: List[Path]) -> str:
    """Extracts text from all images and combines them."""
    all_text = []
    for image_path in image_paths:
        text = extract_text_from_image(image_path)
        if text:
            all_text.append(f"=== Text from {image_path.name} ===\n{text}\n")
    
    return "\n".join(all_text)


def is_ocr_available() -> bool:
    """Check if OCR is available (tesseract installed)."""
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def validate_ocr_requirements():
    """Validate that OCR requirements are available, raise error if not."""
    if not is_ocr_available():
        raise RuntimeError(
            "pytesseract/tesseract is not available but OCR is enabled in config. "
            "Please install tesseract-ocr and pytesseract, or disable OCR in config.json"
        )
