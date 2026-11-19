from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    database_url: str = "sqlite:///./database/finops.db"
    finops_admin_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = Field(default="gemini-3.5-flash-lite", max_length=80, pattern=r"^[a-zA-Z0-9.-]+$")
    notification_mode: str = Field(default="simulated", pattern=r"^(simulated|smtp)$")
    public_demo: bool = False
    cors_origin: str = ""
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: str = ""

    @field_validator("cors_origin")
    @classmethod
    def validate_cors_origin(cls, value: str) -> str:
        if not value:
            return value
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or "*" in parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port is not None
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("CORS_ORIGIN deve ser uma origem HTTPS, sem caminho ou credenciais.")
        return f"https://{parsed.hostname}"
