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
# 2b：代码 + 课件注入（按 ## 标题切分，并行处理）
# ============================================================

import asyncio
import re

_MAX_SECTION_CHARS = 8000  # 单节超过此值按 ### 再切


def _split_by_headers(text: str) -> list[str]:
    """按 ## 标题将结构化文本切为独立节。
    
    每节以 ## 开头（保留标题在节内）。
    如果单节超过 _MAX_SECTION_CHARS，递降到 ### 再切。
    返回：节列表，每节以标题开头。
    """
    if not text.strip():
        return []

    # 按 ## (非 ###) 切分 —— 负向前瞻确保第三个字符不是 #
    pattern = r"^(?=## (?!#)[^\n]*)"
    parts = re.split(pattern, text, flags=re.MULTILINE)
    parts = [p.strip() for p in parts if p.strip()]

    result = []
    for part in parts:
        if len(part) <= _MAX_SECTION_CHARS:
            result.append(part)
        else:
            # 递降：按 ### 再切
            sub_pattern = r"^(?=### (?!#)[^\n]*)"
            sub_parts = re.split(sub_pattern, part, flags=re.MULTILINE)
            sub_parts = [p.strip() for p in sub_parts if p.strip()]
            for sp in sub_parts:
                if len(sp) > _MAX_SECTION_CHARS:
                    # 仍过大：按段落硬切
                    paras = sp.split("\n\n")
                    current = paras[0] if paras else ""
                    for para in paras[1:]:
                        if len(current) + len(para) < _MAX_SECTION_CHARS:
                            current += "\n\n" + para
                        else:
                            if current.strip():
                                result.append(current.strip())
                            current = para
                    if current.strip():
                        result.append(current.strip())
                else:
                    result.append(sp)

    return result


def _format_slices_for_prompt(slices: list) -> str:
    """格式化检索切片为 LLM 可读的参考文本。
    
    代码切片 → 代码块（带语言标注）
    课件切片 → 截取前 500 字作为引用参考
    """
    if not slices:
        return "（无参考资料）"

    parts = []
    for meta, content in slices:
        fn = meta.get("file", "unknown")
        slice_type = meta.get("type", "code")
        ext = fn.rsplit(".", 1)[-1] if "." in fn else ""

        if slice_type == "code":
            # 代码文件：完整代码块
            parts.append(f"### [代码] {fn}\n```{ext}\n{content}\n```")
        else:
            # 课件：截取前 500 字作为引用参考
            title = meta.get("title", fn)
            preview = content[:500] + ("..." if len(content) > 500 else "")
            parts.append(f"### [课件] {title}\n> {preview}")

    return "\n\n".join(parts)



def _verify_headers_preserved(original: str, merged: str) -> bool:
    """校验合并后的文本是否保留了原文的所有标题及顺序。
    
    检查 original 中的每一个 ## / ### / #### 标题：
    - 数量不能减少
    - 文本必须一致
    - 相对顺序不能变
    """
    orig_h = re.findall(r"^(#{2,4} [^\n]+)", original, re.MULTILINE)
    merged_h = re.findall(r"^(#{2,4} [^\n]+)", merged, re.MULTILINE)
    if len(merged_h) < len(orig_h):
        return False
    # 顺序匹配：每个原文标题必须在合并结果中按序出现
    idx = 0
    for oh in orig_h:
        found = False
        while idx < len(merged_h):
            if merged_h[idx].strip() == oh.strip():
                found = True
                idx += 1
                break
            idx += 1
        if not found:
            return False
    return True


async def inject_assets(structured_text: str, rag_collection=None) -> str:
    """
    阶段 2b：在结构化笔记中注入代码块和课件补充内容。

    流程：
    1. 按 ## 标题切分为独立节（每节 2000-8000 字）
    2. 对每节独立做 RAG 检索 → 取 top-8 相关代码 + 课件切片
    3. 每节独立并行调用 LLM 做注入
    4. 合并结果

    关键约束（通过 prompt 保证）：
    - 原文一字不改，标题层级不动
    - 代码渐进展示（先写框架→解释→补全细节）
    - 只在参考材料里有的内容才能插入
    - 课件内容以引用块形式插入
    """
    if not structured_text.strip():
        return structured_text

    # 无 RAG 时直接返回原文
    if rag_collection is None or rag_collection.count() == 0:
        return structured_text

    sections = _split_by_headers(structured_text)
    if not sections:
        return structured_text

    system_prompt = load_prompt("inject_assets_system.md")

    async def process_one(idx: int, section: str) -> str:
        # 检索本节相关的代码 + 课件切片
        from src.rag.retriever import retrieve_slices_for_injection
        slices = await asyncio.to_thread(
            retrieve_slices_for_injection, rag_collection, section, top_k=8
        )

        if not slices:
            return section

        refs = _format_slices_for_prompt(slices)

        # 上下文：前文尾 + 后文头 + 位置标签
        position = f"第 {idx + 1} 块 / 共 {len(sections)} 块"
        prev_tail = sections[idx - 1][-80:] if idx > 0 else "（这是开头）"
        next_head = sections[idx + 1][:80] if idx < len(sections) - 1 else "（这是结尾）"

        user_msg = (
            f"【位置】{position}\n\n"
            f"【前文结尾】\n{prev_tail}\n\n"
            f"【后文开头】\n{next_head}\n\n"
            f"--- 参考资料（只有以下资料可以插入，禁止编造） ---\n\n{refs}\n\n"
            f"--- 以下是你需要处理的笔记，仅输出处理结果，不要加任何说明 ---\n\n{section}"
        )

        result = await chat(
            profile=config.premium,
            system_prompt=system_prompt,
            user_message=user_msg,
        )
        return result.strip()

    # 全并行处理
    processed = await asyncio.gather(*[
        process_one(i, s) for i, s in enumerate(sections)
    ])

    merged = "\n\n".join(processed)

    # 安全校验：确保标题顺序和数量未被破坏
    if not _verify_headers_preserved(structured_text, merged):
        from src.utils.logger import get_pipeline_logger
        _log = get_pipeline_logger()
        _log.warning("Header preservation check failed in inject_assets, falling back to original")
        return structured_text

    return merged


# ---- 兼容旧接口 ----

def _retrieve_code_slices_for_injection(rag_collection, structured_text):
    """[兼容旧接口] 返回格式化代码参考文本（仅代码类型）。"""
    if rag_collection is None or rag_collection.count() == 0:
        return "（无参考代码）"
    from src.rag.retriever import retrieve_slices_for_injection
    slices = retrieve_slices_for_injection(rag_collection, structured_text, top_k=15)
    code_only = [(m, c) for m, c in slices if m.get("type") == "code"]
    if not code_only:
        return "（无参考代码）"
    parts = []
    for meta, content in code_only:
        fn = meta.get("file", "unknown")
        ext = fn.rsplit(".", 1)[-1] if "." in fn else ""
        parts.append(f"### {fn}\n```{ext}\n{content}\n```")
    return "\n\n".join(parts)


async def inject_code(structured_text: str, rag_collection=None) -> str:
    """[兼容旧接口] 内部委托给 inject_assets。"""
    return await inject_assets(structured_text, rag_collection)


# ---- 兼容旧接口 ----

async def structure_and_inject(
    polished_text: str, code_files: dict[str, str] | None = None
) -> str:
    """
    [已废弃] 旧版单次调用：标题 + 代码注入。
    保留以兼容旧调用方，实际内部拆分为两步。
    """
    result = await structure_headers(polished_text)
    return result