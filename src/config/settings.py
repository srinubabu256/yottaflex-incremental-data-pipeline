"""
Application configuration and settings management.
"""

import os
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict

# Base directory is the project root (2 levels up from src/config)
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class PipelineSettings(BaseModel):
    """Configuration settings for the pipeline."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    database_path: Path = Field(
        default_factory=lambda: BASE_DIR / os.getenv("DB_FILE", "yottaflex.db")
    )
    db_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("DB_TIMEOUT_SECONDS", "30.0"))
    )
    batch_size: int = Field(
        default_factory=lambda: int(os.getenv("BATCH_SIZE", "5000"))
    )
    log_level: str = Field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )
    default_currency: str = Field(
        default_factory=lambda: os.getenv("DEFAULT_CURRENCY", "INR")
    )

    # Directories
    reference_data_dir: Path = Field(
        default_factory=lambda: BASE_DIR / "data" / "reference"
    )
    quarantine_dir: Path = Field(
        default_factory=lambda: BASE_DIR / "data" / "quarantine"
    )
    output_dir: Path = Field(
        default_factory=lambda: BASE_DIR / "outputs"
    )
    schema_sql_path: Path = Field(
        default_factory=lambda: BASE_DIR / "database" / "schema.sql"
    )


# Global default settings instance
settings = PipelineSettings()


def get_settings() -> PipelineSettings:
    """Returns the current settings instance."""
    return settings
