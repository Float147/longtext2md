from pathlib import Path

_PROMPT_DIR = Path(__file__).parent.parent.parent / "prompts"

def load_prompt(filename: str) -> str:
    """Load a prompt file from prompts/ directory."""
    with open(_PROMPT_DIR / filename, "r", encoding="utf-8") as f:
        return f.read()
