from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    google_api_key: str | None = None

    # Tiered Google Gemini Model Architecture
    # Fast structured parsing & keyword extraction
    orchestrator_model: str = "gemini-3.8-flash"

    # Deep rules reasoning & grounded adjudication
    rules_judge_model: str = "gemini-3.8-flash"

    # Multimodal image & diagram understanding
    vision_model: str = "gemini-3.8-flash"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


# Create a global instance to be used across the app
settings = Settings()
