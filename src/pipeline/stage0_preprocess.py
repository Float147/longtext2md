from src.utils.text_utils import clean_noise

def clean_noise_stage(text: str) -> str:
    return clean_noise(text)

import asyncio
import json
from src.llm.client import chat
from src.utils.config import config

CORRECT_PROMPT = "You are a Chinese technical text proofreader. Only fix pinyin-to-English mistranscriptions of technical terms. Do not change non-technical text. Do not convert Chinese to English. Output the corrected text directly."

async def correct_errors_stage(text: str, glossary: list[str] | None = None) -> str:
    chunk_size = 10000
    if len(text) <= chunk_size:
        user_msg = f"Glossary: {', '.join(glossary)}\n\n{text}" if glossary else text
        return await chat(model=config.polish_model, system_prompt=CORRECT_PROMPT, user_message=user_msg, temperature=0.1)
    lines = text.split("\n")
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) > chunk_size and current:
            chunks.append(current)
            current = line
        else:
            current += "\n" + line if current else line
    if current:
        chunks.append(current)
    results = []
    for chunk in chunks:
        user_msg = f"Glossary: {', '.join(glossary)}\n\n{chunk}" if glossary else chunk
        results.append(await chat(model=config.polish_model, system_prompt=CORRECT_PROMPT, user_message=user_msg, temperature=0.1))
    return "\n".join(results)

def correct_errors_stage_sync(text: str, glossary: list[str] | None = None) -> str:
    return asyncio.run(correct_errors_stage(text, glossary))

SUMMARY_PROMPT = 'You are a course content analyzer. Output JSON: {"course_title":"...","overview":"...","tech_stack":[...],"chapters_summary":[...]}'

async def generate_summary(text: str) -> dict:
    if len(text) <= 8000:
        sample = text
    else:
        sample = text[:3000]
        for i in range(10000, len(text) - 3000, 10000):
            sample += "\n...\n" + text[i:i+500]
        sample += "\n...\n" + text[-3000:]
    result = await chat(model=config.polish_model, system_prompt=SUMMARY_PROMPT, user_message=sample, temperature=0.3)
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1].rsplit("\n", 1)[0]
    return json.loads(result)

def generate_summary_sync(text: str) -> dict:
    return asyncio.run(generate_summary(text))
