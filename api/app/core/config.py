from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@database:5432/prospect"
    insee_api_key: str = ""
    inpi_username: str = ""
    inpi_password: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
