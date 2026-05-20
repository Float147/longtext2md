"""
术语词典抽取 —— 从代码文件和课件中自动提取技术术语。

按 AGENTS.md 0.1 设计：扫描代码/课件，程序化提取类名、方法名、注解等，
去噪合并去重，生成约 200-500 词的术语表供阶段 0.2 纠错使用。
"""
import os
import re
from typing import List, Set

# ---- 代码术语提取 ----

_CODE_TERM_PATTERNS = [
    # Java/C#/Kotlin：类/接口/枚举名
    r"(?:class|interface|enum|record)\s+(\w+)",
    # 方法签名（可见性 + 返回类型 + 方法名）
    r"(?:public|private|protected)\s+(?:static\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\(",
    # 注解
    r"@(\w+)",
    # Python：类/函数定义
    r"class\s+(\w+)",
    r"def\s+(\w+)",
    # Go：类型/结构体/接口
    r"type\s+(\w+)\s+(?:struct|interface)",
    # TypeScript：接口/类型/枚举
    r"(?:interface|type|enum)\s+(\w+)",
    # Rust：结构体/枚举/trait/impl
    r"(?:struct|enum|trait|impl)\s+(\w+)",
    # 配置文件键（properties/yaml）
    r"^\s*([a-zA-Z][\w.]*)\s*[:=]",
]

# 常见噪声词，不收入术语表
_NOISE_TERMS = {
    "main", "test", "demo", "example", "sample", "tmp", "temp",
    "set", "get", "is", "has", "do", "run", "init", "start", "stop",
    "String", "int", "void", "boolean", "long", "double", "float",
    "public", "private", "protected", "static", "final", "abstract",
    "if", "for", "while", "return", "new", "try", "catch", "throw",
    "import", "package", "from", "this", "super", "class", "interface",
    "def", "self", "True", "False", "None", "pass", "fn", "let", "const",
    "var", "function", "export", "default", "require", "module",
}


def extract_terms_from_code(code: str, file_ext: str = "") -> List[str]:
    """从源代码中提取技术术语。"""
    terms: Set[str] = set()
    for pattern in _CODE_TERM_PATTERNS:
        for match in re.finditer(pattern, code, re.MULTILINE):
            term = match.group(1)
            if term not in _NOISE_TERMS and len(term) >= 2:
                terms.add(term)
    return sorted(terms)


def extract_terms_from_markdown(md: str) -> List[str]:
    """从 Markdown 课件中提取术语（代码块 + 行内代码）。"""
    terms: Set[str] = set()
    # 代码块
    for match in re.finditer(r"```\w*\n(.*?)```", md, re.DOTALL):
        terms.update(extract_terms_from_code(match.group(1)))
    # 行内代码（驼峰命名）
    terms.update(re.findall(r"`([A-Z]\w+(?:\.\w+)*)`", md))
    # 加粗技术词
    terms.update(re.findall(r"\*\*([A-Z]\w+(?:-\w+)*)\*\*", md))
    return sorted(terms)


def extract_terms_from_docx(paragraphs: List[str]) -> List[str]:
    """从 docx 段落中提取术语（驼峰标识符 + 全大写常量）。"""
    terms: Set[str] = set()
    text = "\n".join(paragraphs)
    terms.update(re.findall(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", text))
    terms.update(re.findall(r"\b([A-Z][A-Z_]{2,})\b", text))
    return sorted(t for t in terms if t not in _NOISE_TERMS)


# ---- 文件系统扫描 ----

_CODE_EXTS = {
    ".py", ".java", ".js", ".ts", ".go", ".rs", ".kt", ".swift",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".scala",
    ".xml", ".yaml", ".yml", ".properties", ".json", ".sql",
    ".toml", ".cfg", ".conf", ".gradle", ".proto",
}

_COURSEWARE_EXTS = {".md", ".txt", ".docx", ".pptx", ".pdf"}


def build_glossary(
    code_dir: str | None = None,
    courseware_dir: str | None = None,
) -> List[str]:
    """
    从代码 + 课件目录构建统一的术语词典。
    返回去重排序后的术语列表，上限 500 词。
    """
    terms: Set[str] = set()

    # 扫描代码目录
    if code_dir and os.path.isdir(code_dir):
        for root, _, files in os.walk(code_dir):
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext in _CODE_EXTS:
                    try:
                        with open(os.path.join(root, fn), "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        terms.update(extract_terms_from_code(content, ext))
                    except Exception:
                        pass

    # 扫描课件目录
    if courseware_dir and os.path.isdir(courseware_dir):
        for root, _, files in os.walk(courseware_dir):
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                filepath = os.path.join(root, fn)
                try:
                    if ext in (".md", ".txt"):
                        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        terms.update(extract_terms_from_markdown(content))
                    elif ext == ".docx":
                        from src.rag.parsers.docx_parser import parse_docx_file
                        slices = parse_docx_file(filepath)
                        paras = [s["content"] for s in slices]
                        terms.update(extract_terms_from_docx(paras))
                except Exception:
                    pass

    # 排序并限制数量，避免提示词膨胀
    return sorted(terms)[:500]