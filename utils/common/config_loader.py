"""
Utility for loading configuration from JSON files.
"""

import json
from pathlib import Path
from typing import Dict


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def load_config(config_path: str = None) -> Dict:
    """
    Load configuration from JSON file.
    
    Args:
        config_path: Path to config file (relative to project root). 
                     Defaults to 'data/config.json'
        
    Returns:
        Configuration dictionary
    """
    if config_path is None:
        config_path = 'data/config.json'
    
    config_file = get_project_root() / config_path
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        return json.load(f)

