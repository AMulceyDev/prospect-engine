from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql://postgres:postgres@database:5432/prospect"
    insee_api_key: str = ""
    inpi_username: str = ""
    inpi_password: str = ""


settings = Settings()