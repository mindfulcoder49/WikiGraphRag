from pathlib import Path

from pydantic_settings import BaseSettings

# Walk up from config.py → app/ → src/ → backend/ → project root
_ENV_FILE = Path(__file__).parent.parent.parent.parent / ".env"
#log env file path for debugging
print(f"Loading environment variables from: {_ENV_FILE}")
#log the variables being loaded for debugging hide nothing
print(f"Environment variables being loaded: {open(_ENV_FILE).read() if _ENV_FILE.is_file() else 'No .env file found'}")

class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-5-mini"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "pleasechange"

    wikipedia_user_agent: str = "WikiGraphRAG-MVP/0.1 (contact: you@example.com)"

    default_max_pages: int = 15
    default_max_depth: int = 1

    # LLM limits
    llm_max_concurrent: int = 3
    llm_max_tokens: int = 16000

    # Wikipedia rate limit (seconds between requests)
    wiki_rate_limit: float = 0.35

    # Max chunks sent to LLM per page extraction
    max_chunks_per_extraction: int = 10

    model_config = {"env_file": str(_ENV_FILE), "extra": "ignore"}


settings = Settings()
print(f"[config] NEO4J_URI:      {settings.neo4j_uri}")
print(f"[config] NEO4J_USER:     {settings.neo4j_user}")
print(f"[config] NEO4J_PASSWORD: {settings.neo4j_password}")
print(f"[config] OPENAI_MODEL:   {settings.openai_model}")
