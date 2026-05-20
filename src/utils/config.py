import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

# 自动加载项目根目录下的 .env 文件
_env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(os.path.normpath(_env_path))

@dataclass
class Config:
    deepseek_api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    deepseek_base_url: str = "https://api.deepseek.com"
    polish_model: str = "deepseek-chat"
    structure_model: str = "deepseek-reasoner"
    embedding_model: str = "text-embedding-3-small"
    max_chunk_chars: int = 2000
    max_parallel_tasks: int = 3
    max_llm_concurrency: int = 50
    llm_retry_max: int = 3
    llm_retry_base_delay: float = 1.0
    output_base_dir: str = "output"

config = Config()