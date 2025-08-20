"""File operations utilities for AI processor."""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional


def load_json(filepath: Path) -> Dict[str, Any]:
    """Load JSON data from file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise ValueError(f"Failed to load JSON from {filepath}: {e}")


def save_json(data: Dict[str, Any], filepath: Path) -> None:
    """Save JSON data to file."""
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        raise ValueError(f"Failed to save JSON to {filepath}: {e}")


def find_all_brand_directories(base_path: Path) -> List[Path]:
    """Find all brand directories in the scraped data."""
    if not base_path.exists():
        return []
    
    return [p for p in base_path.iterdir() if p.is_dir()]


def find_all_variation_paths(base_path: Path) -> List[Path]:
    """Find all variation paths that have images."""
    variation_paths = []
    
    for brand_dir in find_all_brand_directories(base_path):
        for variation_dir in brand_dir.iterdir():
            if (variation_dir.is_dir() and 
                variation_dir.name not in ["brand_info.json", "products_list.json"] and
                (variation_dir / "images").exists() and 
                any((variation_dir / "images").iterdir())):
                variation_paths.append(variation_dir)
    
    return variation_paths


def get_variation_data(variation_path: Path) -> Dict[str, Any]:
    """Get variation data from the data.json file."""
    data_path = variation_path / "data.json"
    if not data_path.exists():
        return {}
    
    return load_json(data_path)


def get_brand_info(brand_path: Path) -> Dict[str, Any]:
    """Get brand information from brand_info.json."""
    brand_info_path = brand_path / "brand_info.json"
    if not brand_info_path.exists():
        return {}
    
    return load_json(brand_info_path)


def get_products_list(brand_path: Path) -> Dict[str, Any]:
    """Get products list from products_list.json."""
    products_list_path = brand_path / "products_list.json"
    if not products_list_path.exists():
        return {"product_ids": [], "products_info": {}}
    
    return load_json(products_list_path)


def has_ai_output(variation_path: Path) -> bool:
    """Check if variation already has AI processing output."""
    return (variation_path / "parsed_ai.json").exists()


def get_image_paths(variation_path: Path) -> List[Path]:
    """Get all image paths for a variation."""
    images_dir = variation_path / "images"
    if not images_dir.exists():
        return []
    
    # Common image extensions
    extensions = ['*.png', '*.jpg', '*.jpeg', '*.webp', '*.bmp', '*.gif']
    image_paths = []
    
    for ext in extensions:
        image_paths.extend(images_dir.glob(ext))
    
    return sorted(image_paths)


def create_ai_output_path(variation_path: Path, filename: str = "parsed_ai.json") -> Path:
    """Create the path for AI output file."""
    return variation_path / filename
