from pathlib import Path
from src.llm.client import chat_sync
from src.utils.config import config

def structure_and_inject(polished_text: str, code_files: dict[str, str] | None = None) -> str:
    prompt_path = Path(__file__).parent.parent.parent / "prompts" / "structure_and_inject.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        template = f.read()
    code_text = ""
    if code_files:
        for fn, content in code_files.items():
            ext = fn.rsplit(".", 1)[-1] if "." in fn else ""
            code_text += f"
### {fn}
```{ext}
{content}
```
"
    else:
        code_text = "(No reference code)"
    user_msg = template.format(code_files=code_text, polished_text=polished_text)
    return chat_sync(model=config.structure_model, system_prompt="You are a course note organizer. Output Markdown notes directly.", user_message=user_msg, temperature=0.3, max_tokens=16000)
