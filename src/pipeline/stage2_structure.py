"""
阶段 2：全局结构化 + 代码注入。

使用 premium 模型一次性处理全文：添加层级标题 + 在叙事流中插入代码块。
提示词从 prompts/structure_and_inject_*.md 加载。
"""
from pathlib import Path
from src.llm.client import chat
from src.utils.config import config
from src.utils.prompt_loader import load_prompt



async def structure_and_inject(polished_text: str, code_files: dict[str, str] | None = None) -> str:
    """
    全局结构化 + 代码注入。

    参数：
        polished_text: 阶段 1 输出的润色后全文
        code_files: 文件名 -> 代码内容映射，用于注入代码块
    """
    system_prompt = load_prompt("structure_and_inject_system.md")
    user_template = load_prompt("structure_and_inject_user.md")

    code_text = ""
    if code_files:
        for fn, content in code_files.items():
            ext = fn.rsplit(".", 1)[-1] if "." in fn else ""
            code_text += f"\n### {fn}\n```{ext}\n{content}\n```\n"
    else:
        code_text = "（无参考代码）"

    user_msg = user_template.format(code_files=code_text, polished_text=polished_text)
    return await chat(profile=config.premium, system_prompt=system_prompt, user_message=user_msg)