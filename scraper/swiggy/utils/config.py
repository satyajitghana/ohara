"""Configuration management utilities."""
import json
import os
from pathlib import Path
from typing import Dict, Any


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json."""
    config_path = Path(__file__).parent.parent.parent.parent / "config.json"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found at {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_swiggy_config() -> Dict[str, Any]:
    """Get Swiggy-specific configuration."""
    config = load_config()
    return config.get('swiggy', {})


def get_api_config() -> Dict[str, Any]:
    """Get API configuration."""
    swiggy_config = get_swiggy_config()
    return swiggy_config.get('api', {})


def get_directories_config() -> Dict[str, str]:
    """Get directories configuration."""
    swiggy_config = get_swiggy_config()
    return swiggy_config.get('directories', {})


def get_categories_to_process() -> list:
    """Get list of categories to process."""
    swiggy_config = get_swiggy_config()
    return swiggy_config.get('categories_to_process', [])


def get_default_params() -> Dict[str, str]:
    """Get default API parameters."""
    swiggy_config = get_swiggy_config()
    return swiggy_config.get('default_params', {})
