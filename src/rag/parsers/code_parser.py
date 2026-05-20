"""
代码文件解析器 + 指纹提取器。

按 AGENTS.md 1.3：RAG 检索结果在喂给润色 LLM 前做程序侧压缩，
只保留类名、关键注解、方法签名，去掉方法体，控制在 80-150 tokens。
"""
import os
import re
from typing import List


def parse_code_file(filepath: str) -> List[dict]:
    """解析代码文件为 RAG 索引切片。"""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    ext = os.path.splitext(filepath)[1]
    fn = os.path.basename(filepath)
    return [{
        "file": fn,
        "type": "code",
        "content": content,
        "metadata": {"language": ext.lstrip("."), "filepath": filepath},
    }]


def create_code_fingerprint(slice_content: str, filename: str, annotations: str = "") -> str:
    """
    将完整代码压缩为紧凑"指纹"，供阶段 1 润色上下文使用。

    保留：类名、注解、方法签名、接口声明
    丢弃：方法体、注释、import
    目标：80-150 tokens（完整代码 500-800 tokens）
    """
    lines = slice_content.split("\n")
    key_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 保留注解
        if stripped.startswith("@"):
            key_lines.append(stripped.rstrip("("))
            continue

        # 保留类/接口/枚举/record 声明
        if re.search(
            r"^\s*(?:public\s+)?(?:abstract\s+)?(?:class|interface|enum|record)\s+\w+",
            stripped,
        ):
            key_lines.append(stripped)
            continue

        # 保留方法签名（含返回类型，不含方法体）
        method_match = re.match(
            r"^\s*(?:public|private|protected)?\s*(?:static\s+)?"
            r"(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\([^)]*\)",
            stripped,
        )
        if method_match:
            sig = stripped[:120]
            key_lines.append(sig + (" ..." if len(stripped) > 120 else ""))
            continue

        # 保留 Python 函数/类定义
        if re.match(r"^\s*(?:async\s+)?def\s+\w+|^\s*class\s+\w+", stripped):
            key_lines.append(stripped[:120])
            continue

        # 保留接口/类型声明（Go、TypeScript）
        if re.match(r"^\s*(?:type|interface)\s+\w+", stripped):
            key_lines.append(stripped)
            continue

    # 防膨胀：最多保留 15 行
    if len(key_lines) > 15:
        key_lines = key_lines[:15]
        key_lines.append("...（已截断）")

    fp = f"代码: {filename}\n" + "\n".join(key_lines)

    if annotations:
        fp += f"\n// {annotations}"

    return fp