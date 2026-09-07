from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "postgresql://postgres:postgres@database:5432/prospect"
    insee_api_key: str = ""
    inpi_username: str = ""
    inpi_password: str = ""
    searxng_url: str = "http://searxng:8080"
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2"
    use_llm: bool = True
    # Allowed CORS origins — add your frontend URL when running locally outside Docker
    cors_origins: list[str] = ["http://localhost", "http://localhost:5173"]


settings = Settings()