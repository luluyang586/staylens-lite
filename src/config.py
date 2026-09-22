"""Environment configuration. No implicit model choice or paid calls."""
import os
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def default_database_path() -> Path:
    configured = os.getenv("DUCKDB_PATH")
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else ROOT / path
    full = ROOT / "data/staylens.duckdb"
    return full if full.exists() else ROOT / "data/staylens_demo.duckdb"


class Settings:
    db_path = default_database_path()
    prompt_version = "v2"
    llm_provider = os.getenv("LLM_PROVIDER", "openai").lower()
    llm_model = os.getenv("LLM_MODEL", "")
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    base_url = os.getenv("LLM_BASE_URL") or None
    review_candidates = 20
    final_recommendations = 5
    @property
    def has_llm(self):
        supported = self.llm_provider in {"openai", "anthropic", "openai_compatible"}
        endpoint_ok = self.llm_provider != "openai_compatible" or bool(self.base_url)
        return bool(self.api_key and self.llm_model and supported and endpoint_ok)
settings = Settings()
