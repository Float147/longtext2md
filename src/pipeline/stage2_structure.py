"""
阶段 2：全局结构化 + 代码注入。

拆分为两个独立的 LLM 调用：
  2a. structure_headers — 段落标记法添加层级标题，LLM 只输出 JSON 计划
  2b. inject_code — RAG 过滤相关代码切片后，LLM 在叙事位置插入代码块

提示词从 prompts/structure_headers_system.md / inject_code_system.md 加载。
"""
import json
import re
from src.llm.client import chat
from src.utils.config import config
from src.utils.prompt_loader import load_prompt


# ---- 段落标记法参数 ----
_MIN_PARA_CHARS = 100  # 短于此的相邻段落会被合并


# ============================================================
# 2a：标题生成
# ============================================================


def _mark_paragraphs(text: str) -> tuple[str, int]:
    """将文本按双换行分段，合并短段落，插入 [§N] 标记。
    返回 (带标记的文本, 段落数)。"""
    raw_paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    # 合并短段落
    merged = []
    buf = ""
    for p in raw_paras:
        if buf and len(buf) < _MIN_PARA_CHARS:
            buf += "\n\n" + p
        elif len(p) < _MIN_PARA_CHARS and merged:
            # 短段落与上一个合并（如果有上一个）
            if merged:
                merged[-1] = merged[-1] + "\n\n" + p
            else:
                buf = p
        else:
            if buf:
                merged.append(buf)
                buf = ""
            merged.append(p)
    if buf:
        merged.append(buf)

    # 插入标记
    lines = []
    for i, para in enumerate(merged, 1):
        lines.append(f"[§{i}]\n{para}")
    return "\n\n".join(lines), len(merged)


def _insert_headers(marked_text: str, headers: list[dict]) -> str:
    """根据 LLM 返回的 headers JSON，在标记位置插入 Markdown 标题。"""
    def _safe_marker_num(h):
        try:
            return int(h[chr(34)+chr(109)+chr(97)+chr(114)+chr(107)+chr(101)+chr(114)+chr(34)].lstrip(chr(34)+chr(167)+chr(34)))
        except (ValueError, KeyError):
            return 0
    sorted_headers = sorted(headers, key=_safe_marker_num, reverse=True)


    result = marked_text
    for h in sorted_headers:
        level = max(2, min(4, h.get("level", 2)))
        prefix = "#" * level
        marker = h["marker"]
        title = h["text"]
        # 在 [§N] 前插入标题
        result = result.replace(f"[{marker}]", f"{prefix} {title}\n\n[{marker}]")

    # 移除所有残留的 [§N] 标记
    result = re.sub(r"\[§\d+\]\s*", "", result)
    # 清理多余空行
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def _compress_marked(marked_text: str) -> str:
    sect = chr(167)
    segments = re.split(r"\[" + sect + r"\d+\]", marked_text)
    compressed = []
    for i, seg in enumerate(segments[1:], 1):
        seg = seg.strip()
        if len(seg) <= 120:
            preview = seg
        else:
            preview = seg[:80] + "(...)" + seg[-20:]
        compressed.append("[" + sect + str(i) + "] " + preview)
    return "\n\n".join(compressed)


async def structure_headers(polished_text: str) -> str:
    """
    阶段 2a：为润色后的文本添加层级标题。

    采用段落标记法：程序给段落加 [§N] 标记 → LLM 只输出 JSON 标题计划 →
    程序按计划插入 ##/###/####。LLM 不输出正文，避免 token 浪费和正文篡改风险。
    """
    system_prompt = load_prompt("structure_headers_system.md")
    marked_text, para_count = _mark_paragraphs(polished_text)

    compressed = _compress_marked(marked_text)
    user_msg = f"以下是课程文本的段落头尾预览（共 {para_count} 个段落，每段仅显示头尾，完整正文已省略）。\n请根据头尾信息判断每个段落是否需要添加标题，输出标题计划 JSON。\n\n{compressed}"

    result = await chat(profile=config.premium, system_prompt=system_prompt, user_message=user_msg)

    # 解析 LLM 返回的 JSON
    result = result.strip()
    if result.startswith("```"):
        lines = result.split("\n")
        result = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    try:
        plan = json.loads(result)
        headers = plan.get("headers", [])
    except json.JSONDecodeError:
        # JSON 解析失败时回退：不加标题，返回原文
        return polished_text

    if not headers:
        return polished_text

    return _insert_headers(marked_text, headers)


# ============================================================
# 2b：代码注入
# ============================================================


def _retrieve_code_slices_for_injection(
    rag_collection, structured_text: str
) -> str:
    """对结构化文本检索相关代码切片，返回格式化的代码参考文本。
    切片而非完整文件，避免噪声。"""
    if rag_collection is None or rag_collection.count() == 0:
        return "（无参考代码）"

    # 对全文检索 top-15 最相关切片
    from src.rag.retriever import retrieve_code_slices
    slices = retrieve_code_slices(rag_collection, structured_text, top_k=15)

    if not slices:
        return "（无参考代码）"

    # 格式化：文件名 + 语言类型 + 代码内容
    parts = []
    for meta, content in slices:
        fn = meta.get("file", "unknown")
        ext = fn.rsplit(".", 1)[-1] if "." in fn else ""
        parts.append(f"### {fn}\n```{ext}\n{content}\n```")

    return "\n\n".join(parts)


async def inject_code(structured_text: str, rag_collection=None) -> str:
    """
    阶段 2b：在结构化笔记中精确插入代码块。

    使用 RAG 检索全文最相关的 top-15 代码切片（非完整文件），
    喂给 LLM 进行代码注入。LLM 输出完整 Markdown 笔记。
    无 RAG 索引时跳过，返回原文。
    """
    code_slices = _retrieve_code_slices_for_injection(rag_collection, structured_text)
    if code_slices == "（无参考代码）":
        return structured_text

    system_prompt = load_prompt("inject_code_system.md")

    # 将代码切片和笔记文本填入 user prompt
    # inject_code_system.md 既是 system prompt 也含 user 模板占位符
    # 这里用简单的字符串拼接

    # 构造 user message
    user_msg = f"## 参考代码（只有以下代码可以插入，禁止编造）\n\n{code_slices}\n\n## 需要处理的笔记\n\n{structured_text}\n\n## 输出\n直接输出插入代码后的完整 Markdown 笔记。不要加额外文字或解释。"

    result = await chat(profile=config.premium, system_prompt=system_prompt, user_message=user_msg)
    return result.strip()


# ---- 兼容旧接口 ----

async def structure_and_inject(
    polished_text: str, code_files: dict[str, str] | None = None
) -> str:
    """
    [已废弃] 旧版单次调用：标题 + 代码注入。
    保留以兼容旧调用方，实际内部拆分为两步。
    """
    result = await structure_headers(polished_text)
    # 无 RAG collection 时无法做代码注入，直接返回
    return result