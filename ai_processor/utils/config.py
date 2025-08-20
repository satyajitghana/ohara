"""Configuration management for AI processor."""
import json
import os
from pathlib import Path
from typing import Dict, Any


def load_config(config_path: Path = Path("config.json")) -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Config file not found: {config_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON in config file: {config_path}")


def get_api_config(config_path: Path = Path("config.json")) -> Dict[str, Any]:
    """Get API configuration."""
    config = load_config(config_path)
    ai_config = config.get("ai_processor", {})
    api_config = ai_config.get("api", {})
    
    return {
        "gemini_api_key": config.get("gemini_api_key"),
        "max_retries": api_config.get("max_retries", 3),
        "timeout": api_config.get("timeout", 30),
        "model": api_config.get("model", "gemini-2.5-flash")
    }


def get_processing_config(config_path: Path = Path("config.json")) -> Dict[str, Any]:
    """Get processing configuration."""
    config = load_config(config_path)
    ai_config = config.get("ai_processor", {})
    processing_config = ai_config.get("processing", {})
    
    return {
        "num_processes": processing_config.get("num_processes", 50),
        "skip_existing": processing_config.get("skip_existing", True),
        "enable_ocr": processing_config.get("enable_ocr", True)
    }


def suppress_grpc_logging():
    """Suppress verbose gRPC logging."""
    os.environ["GRPC_VERBOSITY"] = "ERROR"
    os.environ["GLOG_minloglevel"] = "2"


def get_directories_config(config_path: Path = Path("config.json")) -> Dict[str, str]:
    """Get directory configuration."""
    config = load_config(config_path)
    ai_config = config.get("ai_processor", {})
    directories_config = ai_config.get("directories", {})
    
    return {
        "scraped_data": directories_config.get("scraped_data", "scraped_data"),
        "ai_output": directories_config.get("ai_output", "ai_processed"),
        "logs": directories_config.get("logs", "logs")
    }
