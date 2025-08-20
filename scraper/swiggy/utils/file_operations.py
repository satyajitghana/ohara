"""File operations utilities."""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Union


def ensure_directories_exist(directories: Dict[str, str]) -> None:
    """Create directories if they don't exist."""
    for dir_path in directories.values():
        Path(dir_path).mkdir(parents=True, exist_ok=True)


def save_json(data: Any, filepath: Union[str, Path], indent: int = 2) -> None:
    """Save data to JSON file."""
    filepath = Path(filepath)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def load_json(filepath: Union[str, Path]) -> Any:
    """Load data from JSON file."""
    filepath = Path(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_timestamped_filename(base_name: str, extension: str = "json") -> str:
    """Generate a timestamped filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{timestamp}.{extension}"


def save_error_response(content: str, category_name: str, page_no: int, 
                       error_dir: Union[str, Path], extension: str = "html") -> Path:
    """Save error response to file."""
    error_dir = Path(error_dir)
    error_filename = get_timestamped_filename(
        f"error_{category_name}_page_{page_no}", extension
    )
    error_filepath = error_dir / error_filename
    
    with open(error_filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return error_filepath


def clean_image_id(image_id: str) -> str:
    """
    Clean the image ID to be used as a filename.
    e.g., NI_CATALOG/IMAGES/CIW/2025/4/10/xyz.png -> xyz.png
    e.g., 5b0f010e1c9b2ebce6a965512a896ba6 -> 5b0f010e1c9b2ebce6a965512a896ba6.png
    """
    filename = Path(image_id).name
    if not Path(filename).suffix:
        filename += ".png"
    return filename
