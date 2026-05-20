"""
LLM 调用封装 —— 所有模型调用的统一入口。

使用 config.economy / config.premium 两个配置档位选择模型。
DeepSeek API 兼容 OpenAI SDK，直接用标准客户端。
"""
import asyncio
from openai import AsyncOpenAI
from src.utils.config import config, LLMProfile

# 客户端缓存（每个 profile 一个实例）
_clients: dict[str, AsyncOpenAI] = {}


def _get_client(profile: LLMProfile) -> AsyncOpenAI:
    """获取或创建指定 profile 对应的 AsyncOpenAI 客户端。"""
    key = f"{profile.provider}:{profile.base_url}"
    if key not in _clients:
        _clients[key] = AsyncOpenAI(api_key=profile.api_key, base_url=profile.base_url)
    return _clients[key]


async def chat(
    profile: LLMProfile,
    system_prompt: str,
    user_message: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """
    单轮 LLM 调用。

    DeepSeek v4 系列模型（flash + pro）均支持：
    - system 角色消息
    - temperature 和 max_tokens 参数
    - pro 模型会返回 reasoning_content，单轮调用直接忽略
    """
    client = _get_client(profile)
    temp = temperature if temperature is not None else profile.temperature
    mt = max_tokens if max_tokens is not None else profile.max_tokens

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    last_error = None
    for attempt in range(config.llm_retry_max):
        try:
            response = await client.chat.completions.create(
                model=profile.model,
                messages=messages,
                temperature=temp,
                max_tokens=mt,
            )
            content = response.choices[0].message.content
            return content if content else ""
        except Exception as e:
            last_error = e
            if attempt < config.llm_retry_max - 1:
                await asyncio.sleep(config.llm_retry_base_delay * (2 ** attempt))

    raise RuntimeError(
        f"LLM 调用失败（已重试 {config.llm_retry_max} 次）: {last_error}"
    )


def chat_sync(
    profile: LLMProfile,
    system_prompt: str,
    user_message: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """同步版 chat，内部用 asyncio.run 包装。"""
    return asyncio.run(chat(profile, system_prompt, user_message, temperature, max_tokens))