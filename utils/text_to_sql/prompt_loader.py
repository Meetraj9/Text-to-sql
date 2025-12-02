"""
Utility for loading prompt templates from YAML files.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def get_prompts_dir() -> Path:
    """Get the prompts directory path."""
    return Path(__file__).parent.parent.parent / "prompts"


def load_prompt(filename: str) -> str:
    """
    Load a prompt template from the prompts directory.
    
    Args:
        filename: Name of the prompt YAML file (e.g., "information_extraction_prompt.yaml")
        
    Returns:
        Prompt template content as string
    """
    # Validate file extension first
    if not (filename.endswith('.yaml') or filename.endswith('.yml')):
        raise ValueError(f"Prompt file must be a YAML file (.yaml or .yml): {filename}")
    
    prompt_path = get_prompts_dir() / filename
    
    # Check if file exists
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    
    # Load YAML file
    with open(prompt_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        
    if not isinstance(data, dict):
        raise ValueError(f"Invalid YAML format in {filename}: expected dictionary")
    
    if 'prompt' not in data:
        raise ValueError(f"Missing 'prompt' key in {filename}")
    
    return data['prompt']


def load_prompt_metadata(filename: str) -> Optional[Dict[str, Any]]:
    """
    Load prompt metadata from a YAML file.
    
    Args:
        filename: Name of the prompt file (e.g., "information_extraction_prompt.yaml")
        
    Returns:
        Dictionary with metadata, or None if not available
    """
    prompt_path = get_prompts_dir() / filename
    
    if not prompt_path.exists():
        return None
    
    if filename.endswith('.yaml') or filename.endswith('.yml'):
        with open(prompt_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if isinstance(data, dict) and 'metadata' in data:
                return data['metadata']
    
    return None

