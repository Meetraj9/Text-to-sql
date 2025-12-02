"""
Database configuration using Pydantic Settings.
Loads configuration from environment variables or .env file.
"""

from typing import Dict, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from utils.common.config_loader import load_config


class DatabaseSettings(BaseSettings):
    """Database connection settings."""
    
    db_type: str = "postgresql"  # postgresql, databricks, mysql, sqlite, etc.
    host: str = "localhost"
    port: int = 5432
    name: str = ""
    user: str = ""
    password: str = ""
    # Additional fields for specific databases
    token: str = ""  # For Databricks token-based auth
    db_schema: str = Field(default="", validation_alias="SCHEMA")  # Optional schema name (renamed to avoid shadowing BaseSettings.schema)
    driver: str = ""  # Optional SQLAlchemy driver (e.g., 'psycopg2', 'pymysql')
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="DB_",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True  # Allow both field name and alias
    )


def get_db_settings() -> DatabaseSettings:
    """Get database settings instance."""
    return DatabaseSettings()


class LLMSettings(BaseSettings):
    """LLM configuration settings."""
    
    api_key: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="LLM_",
        case_sensitive=False,
        extra="ignore"
    )


def get_llm_settings() -> LLMSettings:
    """Get LLM configuration settings instance."""
    return LLMSettings()


# Cache for workflow settings
_workflow_settings_cache: Optional[Dict] = None


def get_workflow_settings() -> Dict:
    """
    Get workflow settings from workflow_config.json.
    
    Returns:
        Dictionary of workflow settings
    """
    global _workflow_settings_cache
    if _workflow_settings_cache is None:
        from pathlib import Path
        config_file = Path(__file__).parent.parent.parent / "workflow_config.json"
        if not config_file.exists():
            raise FileNotFoundError(f"Workflow config file not found: {config_file}")
        
        import json
        with open(config_file, 'r', encoding='utf-8') as f:
            _workflow_settings_cache = json.load(f)
    return _workflow_settings_cache

