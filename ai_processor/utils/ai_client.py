"""AI client utilities for Gemini API."""
import os
from google import genai
from google.genai import types
from pathlib import Path
from typing import List, Dict, Any
import logging


def setup_gemini_client(api_key: str) -> genai.Client:
    """Setup Gemini client with API key."""
    os.environ["GEMINI_API_KEY"] = api_key
    return genai.Client()


def get_mime_type(image_path: Path) -> str:
    """Returns the MIME type based on the image file extension."""
    suffix = image_path.suffix.lower()
    if suffix in [".jpg", ".jpeg"]:
        return "image/jpeg"
    elif suffix == ".png":
        return "image/png"
    elif suffix == ".webp":
        return "image/webp"
    elif suffix in [".bmp"]:
        return "image/bmp"
    elif suffix in [".gif"]:
        return "image/gif"
    else:
        return "application/octet-stream"


def prepare_image_parts(image_paths: List[Path]) -> List[types.Part]:
    """Prepare image parts for Gemini API."""
    image_parts = []
    
    for image_path in image_paths:
        try:
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            mime_type = get_mime_type(image_path)
            image_parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
        except IOError as e:
            logging.warning(f"Could not read image {image_path}, skipping. Error: {e}")
    
    return image_parts


def send_to_gemini(client: genai.Client, prompt_parts: List, response_schema: Any, model: str = "gemini-2.5-flash"):
    """Send request to Gemini API and get structured response."""
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt_parts,
            config={
                "response_mime_type": "application/json",
                "response_schema": response_schema,
            }
        )
        return response
    except Exception as e:
        logging.error(f"Failed to get response from Gemini: {e}")
        raise
