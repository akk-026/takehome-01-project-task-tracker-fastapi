from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Northstar Project Tracker"
    database_url: str = "sqlite:///./northstar.db"
    model_config = SettingsConfigDict(env_file=".env", env_prefix="NORTHSTAR_")


settings = Settings()
