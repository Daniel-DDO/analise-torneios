from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    JAVA_BACKEND_URL: str = "http://localhost:8080"
    DATABASE_URL: str = "sqlite:///./analise.db"
    N_SIMULACOES_MONTE_CARLO: int = 10_000

    class Config:
        env_file = ".env"


settings = Settings()
