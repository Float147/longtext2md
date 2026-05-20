"""
全局配置 —— 所有值从 .env 读取，零硬编码。

两个 LLM 配置档位：
  - economy：纠错、摘要、润色（便宜/快速）
  - premium：最终结构化（高质量）
"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(os.path.normpath(_env_path))


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_float(key: str, default: float) -> float:
    val = os.getenv(key)
    return float(val) if val else default


def _env_int(key: str, default: int) -> int:
    val = os.getenv(key)
    return int(val) if val else default


@dataclass
class LLMProfile:
    """LLM 供应商配置档 —— 所有值从 .env 读取。"""
    provider: str
    api_key: str
    base_url: str
    model: str
    temperature: float
    max_tokens: int


@dataclass
class Config:
    # ---- 经济档位（纠错/摘要/润色）----
    economy: LLMProfile = field(default_factory=lambda: LLMProfile(
        provider="deepseek",
        api_key=_env("DEEPSEEK_API_KEY"),
        base_url=_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=_env("ECONOMY_MODEL", "deepseek-chat"),
        temperature=_env_float("ECONOMY_TEMPERATURE", 0.1),
        max_tokens=_env_int("ECONOMY_MAX_TOKENS", 4096),
    ))

    # ---- 高端档位（结构化）----
    premium: LLMProfile = field(default_factory=lambda: LLMProfile(
        provider="deepseek",
        api_key=_env("DEEPSEEK_API_KEY"),
        base_url=_env("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        model=_env("PREMIUM_MODEL", "deepseek-chat"),
        temperature=_env_float("PREMIUM_TEMPERATURE", 0.3),
        max_tokens=_env_int("PREMIUM_MAX_TOKENS", 16000),
    ))

    # ---- 向量嵌入 + 重排序 (SiliconFlow) ----
    siliconflow_api_key: str = field(default_factory=lambda: _env("SILICONFLOW_API_KEY"))
    siliconflow_base_url: str = field(default_factory=lambda: _env("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"))
    embedding_model: str = field(default_factory=lambda: _env("EMBEDDING_MODEL", "BAAI/bge-m3"))
    reranker_model: str = field(default_factory=lambda: _env("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"))
    # ---- 流水线参数 ----
    max_chunk_chars: int = field(default_factory=lambda: _env_int("MAX_CHUNK_CHARS", 2000))
    max_parallel_tasks: int = field(default_factory=lambda: _env_int("MAX_PARALLEL_TASKS", 3))
    max_llm_concurrency: int = field(default_factory=lambda: _env_int("MAX_LLM_CONCURRENCY", 50))
    llm_retry_max: int = field(default_factory=lambda: _env_int("LLM_RETRY_MAX", 3))
    llm_retry_base_delay: float = field(default_factory=lambda: _env_float("LLM_RETRY_BASE_DELAY", 1.0))
    output_base_dir: str = field(default_factory=lambda: _env("OUTPUT_BASE_DIR", "output"))
    streamlit_port: int = field(default_factory=lambda: _env_int("STREAMLIT_PORT", 8501))


config = Config()
