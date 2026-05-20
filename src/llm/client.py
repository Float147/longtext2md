import asyncio
from openai import AsyncOpenAI
from src.utils.config import config

_client: AsyncOpenAI | None = None

def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=config.deepseek_api_key, base_url=config.deepseek_base_url)
    return _client

async def chat(model: str, system_prompt: str, user_message: str, temperature: float = 0.3, max_tokens: int = 4096) -> str:
    client = _get_client()
    last_error = None
    for attempt in range(config.llm_retry_max):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
                temperature=temperature, max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            last_error = e
            if attempt < config.llm_retry_max - 1:
                await asyncio.sleep(config.llm_retry_base_delay * (2 ** attempt))
    raise RuntimeError(f"LLM call failed after {config.llm_retry_max} retries: {last_error}")

def chat_sync(model: str, system_prompt: str, user_message: str, temperature: float = 0.3, max_tokens: int = 4096) -> str:
    return asyncio.run(chat(model, system_prompt, user_message, temperature, max_tokens))
