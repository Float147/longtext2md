# longtext2md Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local GUI tool that converts course transcripts (up to 60k chars) + optional code/courseware into structured Markdown notes with multi-task concurrency, checkpoint recovery, and optional mindmap generation.

**Architecture:** Three-layer design: (1) `src/utils/` + `src/llm/` for foundational services, (2) `src/pipeline/` for the 9-step DAG processing pipeline with per-stage checkpoint outputs, (3) `src/task/` + `gui/` for the multi-task concurrency layer with Streamlit UI. All LLM calls through DeepSeek API.

**Tech Stack:** Python 3.11+, Streamlit, OpenAI SDK (DeepSeek-compatible), ChromaDB, tiktoken, python-docx, asyncio

---

## File Structure Map

| File | Responsibility |
|---|---|
| `src/utils/config.py` | Env vars, model names, default paths, concurrency limits |
| `src/utils/token_counter.py` | tiktoken wrapper, count tokens for a string |
| `src/utils/text_utils.py` | Noise regex patterns, chunk merge/split helpers |
| `src/utils/toc_generator.py` | Parse `##/###/####` from markdown, output TOC markdown |
| `src/utils/mindmap.py` | Parse heading tree, output Mermaid `mindmap` syntax |
| `src/llm/client.py` | DeepSeek API wrapper with retry logic (3 retries, exponential backoff) |
| `src/chunking/boundary_detector.py` | Multi-signal recursive boundary detection, output chunk list |
| `src/rag/glossary.py` | Extract technical terms from code/courseware via regex |
| `src/rag/parsers/code_parser.py` | Parse code files into function/class slices |
| `src/rag/parsers/markdown_parser.py` | Parse Markdown courseware into paragraph slices |
| `src/rag/parsers/docx_parser.py` | Parse Word courseware into paragraph slices |
| `src/rag/indexer.py` | Embed slices into ChromaDB |
| `src/rag/retriever.py` | Query ChromaDB, return compressed code fingerprints |
| `src/pipeline/stage0_preprocess.py` | Orchestrate 0.0-0.4: clean, glossary, correct, summarize, chunk |
| `src/pipeline/stage1_polish.py` | Assemble 4-layer context, parallel polish all chunks via asyncio |
| `src/pipeline/stage2_structure.py` | Single Pro call: add headings + inject code blocks |
| `src/pipeline/orchestrator.py` | DAG execution engine: run stages in order, handle checkpoints |
| `src/task/task_store.py` | Task metadata CRUD (JSON file per task) |
| `src/task/task_manager.py` | Task state machine: create/pause/resume/cancel, dispatch |
| `src/task/concurrency_limiter.py` | Semaphore-based LLM request limiter + task slot limiter |
| `gui/app.py` | Streamlit UI: task list + detail view + new task dialog |

---

### Task 1: Project Skeleton & Config

**Files:**
- Create: `requirements.txt`
- Create: `src/__init__.py`
- Create: `src/utils/__init__.py`
- Create: `src/utils/config.py`

- [ ] **Step 1: Write requirements.txt**

```
streamlit>=1.28.0
openai>=1.12.0
chromadb>=0.4.22
tiktoken>=0.5.0
python-docx>=1.0.0
jieba>=0.42.1
aiohttp>=3.9.0
pydantic>=2.5.0
```

- [ ] **Step 2: Create package init files**

```bash
New-Item -ItemType File -Path src/__init__.py -Force
New-Item -ItemType File -Path src/utils/__init__.py -Force
```

- [ ] **Step 3: Write config.py**

```python
import os
from dataclasses import dataclass, field

@dataclass
class Config:
    deepseek_api_key: str = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", ""))
    deepseek_base_url: str = "https://api.deepseek.com"
    polish_model: str = "deepseek-chat"
    structure_model: str = "deepseek-reasoner"
    embedding_model: str = "text-embedding-3-small"
    max_chunk_chars: int = 2000
    max_parallel_tasks: int = 3
    max_llm_concurrency: int = 50
    llm_retry_max: int = 3
    llm_retry_base_delay: float = 1.0
    output_base_dir: str = "output"

config = Config()
```

- [ ] **Step 4: Commit**


### Task 2: Token Counter & Text Utilities

**Files:**
- Create: `src/utils/token_counter.py`
- Create: `src/utils/text_utils.py`
- Create: `tests/test_token_counter.py`
- Create: `tests/test_text_utils.py`

- [ ] **Step 1: Write failing test for token_counter**

```python
# tests/test_token_counter.py
from src.utils.token_counter import count_tokens

def test_count_tokens_english():
    assert 0 < count_tokens("Hello, world!") < 10

def test_count_tokens_chinese():
    assert count_tokens("你好世界") > 0

def test_count_tokens_empty():
    assert count_tokens("") == 0
```

- [ ] **Step 2: Write token_counter.py**

```python
import tiktoken
_encoder = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_encoder.encode(text))
```

- [ ] **Step 3: Write text_utils.py with noise patterns**

```python
import re

FILLER_PATTERNS = [
    (re.compile(r"\b(那个|就是说|然后呢|对吧|是不是|这个嘛)\b"), ""),
    (re.compile(r"(嗯|啊|哦|呃){3,}"), ""),
]

def clean_noise(text: str) -> str:
    for pattern, replacement in FILLER_PATTERNS:
        text = pattern.sub(replacement, text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
```

- [ ] **Step 4: Write tests for text_utils**

```python
# tests/test_text_utils.py
from src.utils.text_utils import clean_noise

def test_clean_removes_filler_words():
    result = clean_noise("那个就是说这个东西对吧")
    assert "那个" not in result
    assert "就是说" not in result

def test_clean_collapses_blank_lines():
    result = clean_noise("line1\n\n\n\nline2")
    assert result.count("\n\n") == 1

def test_clean_preserves_meaningful_text():
    result = clean_noise("我们来讲Spring Boot的自动配置原理")
    assert "Spring Boot" in result
```

- [ ] **Step 5: Run tests, commit**


### Task 3: LLM Client

**Files:**
- Create: `src/llm/__init__.py`
- Create: `src/llm/client.py`

- [ ] **Step 1: Write llm/client.py with retry logic**

```python
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
```

- [ ] **Step 2: Commit**


### Task 4: Noise Cleaning Stage (0.0)

**Files:**
- Create: `src/pipeline/__init__.py`
- Create: `src/pipeline/stage0_preprocess.py`
- Create: `tests/test_stage0_preprocess.py`

- [ ] **Step 1: Write stage0_preprocess.py with clean_noise_stage**

```python
from src.utils.text_utils import clean_noise

def clean_noise_stage(text: str) -> str:
    return clean_noise(text)
```

- [ ] **Step 2: Write tests**

```python
# tests/test_stage0_preprocess.py
from src.pipeline.stage0_preprocess import clean_noise_stage

def test_clean_noise_removes_repeated_fillers():
    result = clean_noise_stage("那个那个就是说嗯嗯Spring Boot配置")
    assert "Spring Boot" in result
    assert result.count("那个") <= 1

def test_clean_noise_preserves_code_terms():
    result = clean_noise_stage("然后写一个 @RestController 注解")
    assert "@RestController" in result

def test_clean_noise_handles_empty():
    assert clean_noise_stage("") == ""
```

- [ ] **Step 3: Run tests, commit**

### Task 5: Glossary Extraction (0.1)

**Files:**
- Create: `src/rag/__init__.py`
- Create: `src/rag/glossary.py`
- Create: `tests/test_glossary.py`

- [ ] **Step 1: Write glossary.py**

```python
import re

def extract_terms_from_code(code: str, file_ext: str = "") -> list[str]:
    terms = set()
    terms.update(re.findall(r"(?:class|interface|enum)\s+(\w+)", code))
    terms.update(re.findall(r"(?:public|private|protected)\s+\w+\s+(\w+)\s*\(", code))
    terms.update(re.findall(r"@(\w+)", code))
    terms.update(re.findall(r"class\s+(\w+)", code))
    terms.update(re.findall(r"def\s+(\w+)", code))
    return sorted(terms)

def extract_terms_from_markdown(md: str) -> list[str]:
    terms = set()
    for match in re.finditer(r"```\w*\n(.*?)```", md, re.DOTALL):
        terms.update(extract_terms_from_code(match.group(1)))
    terms.update(re.findall(r"`([A-Z]\w+(?:\.\w+)*)`", md))
    return sorted(terms)
```

- [ ] **Step 2: Write test and commit**


### Task 6: Full-Text Error Correction (0.2)

**Files:**
- Modify: `src/pipeline/stage0_preprocess.py`

- [ ] **Step 1: Add correct_errors_stage**

```python
# Add to stage0_preprocess.py
import asyncio
from src.llm.client import chat
from src.utils.config import config

CORRECT_PROMPT = "你是中文技术文本纠错助手。只修正技术术语的错误音译。不改非技术文字。不改结构。直接输出修正后文本。"

async def correct_errors_stage(text: str, glossary: list[str] | None = None) -> str:
    chunk_size = 10000
    if len(text) <= chunk_size:
        user_msg = f"术语表: {', '.join(glossary)}\n\n{text}" if glossary else text
        return await chat(model=config.polish_model, system_prompt=CORRECT_PROMPT, user_message=user_msg, temperature=0.1)
    lines = text.split("\n")
    chunks, current = [], ""
    for line in lines:
        if len(current) + len(line) > chunk_size and current:
            chunks.append(current); current = line
        else:
            current += "\n" + line if current else line
    if current: chunks.append(current)
    results = []
    for chunk in chunks:
        user_msg = f"术语表: {', '.join(glossary)}\n\n{chunk}" if glossary else chunk
        results.append(await chat(model=config.polish_model, system_prompt=CORRECT_PROMPT, user_message=user_msg, temperature=0.1))
    return "\n".join(results)

def correct_errors_stage_sync(text: str, glossary: list[str] | None = None) -> str:
    return asyncio.run(correct_errors_stage(text, glossary))
```

- [ ] **Step 2: Commit**

### Task 7: Course Summary (0.3)

**Files:**
- Modify: `src/pipeline/stage0_preprocess.py`

- [ ] **Step 1: Add generate_summary**

```python
import json

SUMMARY_PROMPT = '你是课程内容分析助手。输出JSON: {"course_title":"...","overview":"...","tech_stack":[...],"chapters_summary":[...]}'

async def generate_summary(text: str) -> dict:
    if len(text) <= 8000:
        sample = text
    else:
        sample = text[:3000]
        for i in range(10000, len(text)-3000, 10000):
            sample += "\n...\n" + text[i:i+500]
        sample += "\n...\n" + text[-3000:]
    result = await chat(model=config.polish_model, system_prompt=SUMMARY_PROMPT, user_message=sample, temperature=0.3)
    result = result.strip()
    if result.startswith("```"): result = result.split("\n",1)[1].rsplit("\n",1)[0]
    return json.loads(result)

def generate_summary_sync(text: str) -> dict:
    return asyncio.run(generate_summary(text))
```

- [ ] **Step 2: Commit**

### Task 8: Boundary Detection (0.4)

**Files:**
- Create: `src/chunking/__init__.py`
- Create: `src/chunking/boundary_detector.py`
- Create: `tests/test_boundary_detector.py`

- [ ] **Step 1: Write boundary_detector.py**

```python
import re

SECTION_MARKERS = [r"接下来我们讲", r"下面来看", r"最后一个", r"我们继续", r"第[\d一二三四五六七八九十]+节", r"总结一下", r"回顾一下"]
CODE_SWITCH = [r"我们写一下", r"来看代码", r"运行一下", r"新建一个", r"创建一个类"]
ENUMERATION = [r"首先.*其次.*最后", r"第一步.*第二步", r"先.*再.*最后"]

def detect_boundaries(text: str, max_chars: int = 2000) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    paragraphs = text.split("\n")
    scores = []
    for i, para in enumerate(paragraphs):
        score = 0
        ctx = "\n".join(paragraphs[max(0,i-1):min(len(paragraphs),i+2)])
        for m in SECTION_MARKERS:
            if re.search(m, ctx): score += 5
        for m in CODE_SWITCH:
            if re.search(m, ctx): score += 3
        for m in ENUMERATION:
            if re.search(m, ctx): score += 2
        if para.strip() == "": score += 1
        scores.append(score)
    return _recursive_cut(paragraphs, scores, max_chars)

def _recursive_cut(paragraphs, scores, max_chars):
    text = "\n".join(paragraphs)
    if len(text) <= max_chars:
        return [text] if text.strip() else []
    n = len(paragraphs)
    lo, hi = int(n*0.2), int(n*0.8)
    best_idx, best_score = lo, -1
    for i in range(lo, hi):
        if scores[i] > best_score:
            best_score = scores[i]; best_idx = i
    if best_score <= 1:
        running = 0
        for i, para in enumerate(paragraphs):
            running += len(para)
            if running >= max_chars:
                best_idx = i; break
    return _recursive_cut(paragraphs[:best_idx], scores[:best_idx], max_chars) + _recursive_cut(paragraphs[best_idx:], scores[best_idx:], max_chars)
```

- [ ] **Step 2: Write tests, run, commit**

### Task 9: Code & Courseware Parsers

**Files:**
- Create: `src/rag/parsers/__init__.py`
- Create: `src/rag/parsers/code_parser.py`
- Create: `src/rag/parsers/markdown_parser.py`
- Create: `src/rag/parsers/docx_parser.py`

- [ ] **Step 1: Write code_parser.py**

```python
import os, re

def parse_code_file(filepath: str) -> list[dict]:
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    ext = os.path.splitext(filepath)[1]
    slices = []
    for match in re.finditer(r"(?:^|\n)((?:public|private|protected|static|async|def|class|function)\s+[^\n]*(?:\{[^}]*\}|[^\n]*;?))", content, re.DOTALL):
        block = match.group(1).strip()
        if len(block) > 10:
            slices.append({"file": filepath, "type": "code", "content": block, "metadata": {"language": ext.lstrip(".")}})
    if not slices:
        slices.append({"file": filepath, "type": "code", "content": content[:2000], "metadata": {"language": ext.lstrip(".")}})
    return slices

def create_code_fingerprint(slice_content: str, filename: str, annotations: str = "") -> str:
    lines = slice_content.split("\n")
    keywords = ["class ", "def ", "function ", "public ", "@", "import ", "from ", "const ", "interface "]
    key_lines = [l.strip() for l in lines if any(kw in l.strip() for kw in keywords)]
    fp = f"代码: {filename}\n" + "\n".join(key_lines[:5])
    if annotations:
        fp += f"\n// {annotations}"
    return fp
```

- [ ] **Step 2: Write markdown_parser.py**

```python
import re

def parse_markdown_file(filepath: str) -> list[dict]:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    slices = []
    for section in re.split(r"\n(?=#{1,4}\s)", content):
        section = section.strip()
        if not section: continue
        title_match = re.match(r"#{1,4}\s+(.+)", section)
        slices.append({"file": filepath, "type": "courseware", "content": section, "metadata": {"title": title_match.group(1) if title_match else filepath}})
    return slices
```

- [ ] **Step 3: Write docx_parser.py**

```python
from docx import Document

def parse_docx_file(filepath: str) -> list[dict]:
    doc = Document(filepath)
    return [{"file": filepath, "type": "courseware", "content": p.text.strip(), "metadata": {"title": p.text.strip()[:50]}} for p in doc.paragraphs if p.text.strip()]
```

- [ ] **Step 4: Commit**

### Task 10: RAG Indexer & Retriever

**Files:**
- Create: `src/rag/indexer.py`
- Create: `src/rag/retriever.py`

- [ ] **Step 1: Write indexer.py**

```python
import chromadb
from chromadb.utils import embedding_functions
import os

_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.getenv("OPENAI_API_KEY", ""),
    model_name="text-embedding-3-small",
)

def build_index(slices: list[dict], collection_name: str, persist_dir: str = "./chromadb"):
    client = chromadb.PersistentClient(path=persist_dir)
    try: client.delete_collection(collection_name)
    except: pass
    collection = client.create_collection(name=collection_name, embedding_function=_ef)
    if not slices: return collection
    collection.add(
        ids=[f"s_{i}" for i in range(len(slices))],
        documents=[s["content"] for s in slices],
        metadatas=[s["metadata"] for s in slices],
    )
    return collection
```

- [ ] **Step 2: Write retriever.py**

```python
from src.rag.parsers.code_parser import create_code_fingerprint

def retrieve_relevant(collection, query: str, k: int = 3) -> str:
    if collection is None or collection.count() == 0:
        return ""
    results = collection.query(query_texts=[query], n_results=k)
    fps = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i] if results.get("metadatas") else {}
        fn = meta.get("file", "unknown")
        if meta.get("type") == "code":
            fps.append(create_code_fingerprint(doc, fn))
        else:
            fps.append(f"课件: {meta.get('title','')}\n{doc[:100]}")
    return "\n---\n".join(fps)
```

- [ ] **Step 3: Commit**

### Task 11: Parallel Polish (Stage 1)

**Files:**
- Create: `prompts/polish_chunk.md`
- Create: `src/pipeline/stage1_polish.py`

- [ ] **Step 1: Write prompt template**

```markdown
# prompts/polish_chunk.md
## 课程概览
{course_overview}

## 你的位置
第 {chunk_index} 块 / 共 {total_chunks} 块

## 前文回顾
{prev_chunk_last_80}

## 后文预告
{next_chunk_first_60}

## 参考资料
{rag_fingerprints}

## 需要润色的文本
{current_chunk}

## 任务
将上面的文本润色为流畅的中文书面语：
- 去除口语化填充词
- 整理为清晰的段落，不要加任何 Markdown 标题
- 不要插入代码块
- 不要遗漏任何知识点
- 不要做摘要压缩，只做语言精炼
- 确保与前文后文的过渡自然
```

- [ ] **Step 2: Write stage1_polish.py**

```python
import asyncio
from pathlib import Path
from src.llm.client import chat
from src.utils.config import config

POLISH_SYSTEM = "你是中文课程笔记润色助手。去除口语化填充词，整理为清晰段落，不加标题不插代码，不遗漏知识点，不做摘要压缩。直接输出润色后文本。"

def _load_template() -> str:
    prompt_path = Path(__file__).parent.parent.parent / "prompts" / "polish_chunk.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()

async def polish_chunks(chunks: list[str], summary: dict, rag_fingerprints_map: dict[int, str] | None = None, max_concurrency: int = 30) -> list[str]:
    template = _load_template()
    total = len(chunks)
    semaphore = asyncio.Semaphore(max_concurrency)
    async def polish_one(idx: int, chunk: str) -> str:
        prev_end = chunks[idx-1][-80:] if idx > 0 else "（这是第一块）"
        next_start = chunks[idx+1][:60] if idx < total-1 else "（这是最后一块）"
        rags = rag_fingerprints_map.get(idx, "") if rag_fingerprints_map else ""
        user_msg = template.format(
            course_overview=summary.get("overview", summary.get("course_title", "")),
            chunk_index=idx+1, total_chunks=total,
            prev_chunk_last_80=prev_end, next_chunk_first_60=next_start,
            rag_fingerprints=rags, current_chunk=chunk,
        )
        async with semaphore:
            return await chat(model=config.polish_model, system_prompt=POLISH_SYSTEM, user_message=user_msg, temperature=0.3)
    tasks = [polish_one(i, c) for i, c in enumerate(chunks)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [chunks[i] if isinstance(r, Exception) else r for i, r in enumerate(results)]
```

- [ ] **Step 3: Commit**

### Task 12: Global Structure + Code Injection (Stage 2)

**Files:**
- Create: `prompts/structure_and_inject.md`
- Create: `src/pipeline/stage2_structure.py`

- [ ] **Step 1: Write prompt template**

```markdown
# prompts/structure_and_inject.md
## 任务
对以下润色后的课程文本进行处理：
1. 添加层级标题（## / ### / ####，最多四级）
2. 在老师讨论代码的位置插入参考代码块（带语言标注）
3. 保留"先讲思路 -> 再写代码 -> 再解释"的叙事节奏
4. 如果老师分步写代码，笔记也分步展示

## 参考代码
{code_files}

## 课程文本
{polished_text}

直接输出完整的 Markdown 笔记。
```

- [ ] **Step 2: Write stage2_structure.py**

```python
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
            code_text += f"\n### {fn}\n```{ext}\n{content}\n```\n"
    else:
        code_text = "（无参考代码）"
    user_msg = template.format(code_files=code_text, polished_text=polished_text)
    return chat_sync(model=config.structure_model, system_prompt="你是课程笔记整理助手。直接输出Markdown笔记。", user_message=user_msg, temperature=0.3, max_tokens=16000)
```

- [ ] **Step 3: Commit**

### Task 13: TOC Generator & Mindmap

**Files:**
- Create: `src/utils/toc_generator.py`
- Create: `src/utils/mindmap.py`
- Create: `tests/test_toc_generator.py`
- Create: `tests/test_mindmap.py`

- [ ] **Step 1: Write toc_generator.py**

```python
import re

def generate_toc(markdown: str) -> str:
    lines = []
    for match in re.finditer(r"^(#{2,4})\s+(.+)$", markdown, re.MULTILINE):
        level = len(match.group(1)) - 2
        title = match.group(2).strip()
        anchor = title.lower().replace(" ", "-")
        anchor = re.sub(r"[^a-z0-9\u4e00-\u9fff-]", "", anchor)
        lines.append(f"{'  '*level}- [{title}](#{anchor})")
    return "\n".join(lines)

def insert_toc(markdown: str) -> str:
    toc = generate_toc(markdown)
    if not toc:
        return markdown
    toc_block = f"## 目录\n\n{toc}\n\n---\n\n"
    first_heading = re.search(r"^#\s+.+$", markdown, re.MULTILINE)
    if first_heading:
        pos = first_heading.end()
        return markdown[:pos] + "\n\n" + toc_block + markdown[pos:].lstrip("\n")
    return toc_block + markdown
```

- [ ] **Step 2: Write mindmap.py**

```python
import re

def generate_mindmap(markdown: str, root_title: str = "课程笔记") -> str:
    headings = []
    for match in re.finditer(r"^(#{2,4})\s+(.+)$", markdown, re.MULTILINE):
        level = len(match.group(1)) - 1
        headings.append((level, match.group(2).strip()))
    if not headings:
        return ""
    lines = ["```mermaid", "mindmap", f"  root(({root_title}))"]
    for level, title in headings:
        lines.append(f"{'    ' + '  '*(level-1)}{title}")
    lines.append("```")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 3: Write tests and commit**

### Task 14: Pipeline Orchestrator

**Files:**
- Create: `src/pipeline/orchestrator.py`

- [ ] **Step 1: Write orchestrator.py**

```python
import json, os, time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class StageResult:
    stage_name: str
    status: str = "pending"
    output_file: str = ""
    error: str | None = None
    duration_s: float = 0.0

@dataclass
class PipelineState:
    task_id: str
    output_dir: str
    stages: dict[str, StageResult] = field(default_factory=dict)
    current_stage: str = "0.0"
    summary: dict | None = None
    chunks: list[str] | None = None

class Orchestrator:
    def __init__(self, state: PipelineState, progress_callback: Callable | None = None):
        self.state = state
        self.progress_callback = progress_callback
        Path(state.output_dir).mkdir(parents=True, exist_ok=True)

    def _save(self, filename: str, content):
        filepath = os.path.join(self.state.output_dir, filename)
        if isinstance(content, (dict, list)):
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=2)
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

    def run_stage(self, stage_name: str, fn: Callable, *args, **kwargs):
        self.state.current_stage = stage_name
        self.state.stages[stage_name] = StageResult(stage_name=stage_name, status="running")
        if self.progress_callback:
            self.progress_callback(self.state)
        try:
            t0 = time.time()
            result = fn(*args, **kwargs)
            dt = time.time() - t0
            out_file = f"{stage_name.replace('.','_')}_output"
            if stage_name == "0.0":
                out_file = "00_cleaned.txt"
            elif stage_name == "0.2":
                out_file = "02_corrected.txt"
            elif stage_name == "0.3":
                out_file = "03_summary.json"
                self.state.summary = result if isinstance(result, dict) else None
            elif stage_name == "0.4":
                out_file = "04_chunks.json"
                self.state.chunks = result
            elif stage_name == "1":
                out_file = "05_polished.txt"
                result = "\n\n".join(result) if isinstance(result, list) else result
            elif stage_name == "2":
                out_file = "06_structured.md"
            self._save(out_file, result)
            self.state.stages[stage_name] = StageResult(stage_name=stage_name, status="completed", output_file=out_file, duration_s=dt)
            return result
        except Exception as e:
            self.state.stages[stage_name] = StageResult(stage_name=stage_name, status="failed", error=str(e))
            raise
        finally:
            if self.progress_callback:
                self.progress_callback(self.state)
```

- [ ] **Step 2: Commit**

### Task 15: Task Store & Manager

**Files:**
- Create: `src/task/__init__.py`
- Create: `src/task/task_store.py`
- Create: `src/task/concurrency_limiter.py`
- Create: `src/task/task_manager.py`

- [ ] **Step 1: Write task_store.py**

```python
import json, os
from pathlib import Path
from datetime import datetime

STORE_DIR = "tasks"

def _path(task_id: str) -> str:
    Path(STORE_DIR).mkdir(exist_ok=True)
    return os.path.join(STORE_DIR, f"{task_id}.json")

def create_task(task_id: str, name: str, inputs: dict) -> dict:
    task = {"id": task_id, "name": name, "status": "pending", "inputs": inputs, "output_dir": f"output/{task_id}", "created_at": datetime.now().isoformat(), "mindmap_enabled": inputs.get("mindmap_enabled", True)}
    _save(task)
    return task

def get_task(task_id: str) -> dict | None:
    p = _path(task_id)
    return json.load(open(p, "r", encoding="utf-8")) if os.path.exists(p) else None

def update_task(task_id: str, updates: dict):
    t = get_task(task_id)
    if t:
        t.update(updates)
        _save(t)

def list_tasks(status: str | None = None) -> list[dict]:
    Path(STORE_DIR).mkdir(exist_ok=True)
    tasks = []
    for fn in os.listdir(STORE_DIR):
        if fn.endswith(".json"):
            t = json.load(open(os.path.join(STORE_DIR, fn), "r", encoding="utf-8"))
            if status is None or t.get("status") == status:
                tasks.append(t)
    return sorted(tasks, key=lambda t: t.get("created_at", ""))

def delete_task(task_id: str):
    p = _path(task_id)
    if os.path.exists(p):
        os.remove(p)

def _save(task: dict):
    json.dump(task, open(_path(task["id"]), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
```

- [ ] **Step 2: Write concurrency_limiter.py**

```python
import asyncio
from src.utils.config import config

class TaskSlotLimiter:
    def __init__(self, max_slots: int | None = None):
        self._sem = asyncio.Semaphore(max_slots or config.max_parallel_tasks)
    async def acquire(self):
        await self._sem.acquire()
    def release(self):
        self._sem.release()
    @property
    def available(self) -> int:
        return self._sem._value

task_slot_limiter = TaskSlotLimiter()
```

- [ ] **Step 3: Write task_manager.py**

```python
import asyncio, os, threading
from datetime import datetime
from src.task.task_store import create_task, get_task, update_task, list_tasks, delete_task
from src.task.concurrency_limiter import task_slot_limiter

async def run_task(task_id: str, progress_callback=None):
    task = get_task(task_id)
    if not task:
        raise ValueError(f"Task {task_id} not found")
    update_task(task_id, {"status": "running"})
    await task_slot_limiter.acquire()
    try:
        from src.pipeline.orchestrator import Orchestrator, PipelineState
        state = PipelineState(task_id=task_id, output_dir=task["output_dir"])
        orch = Orchestrator(state, progress_callback)
        # Load transcript
        text = task["inputs"].get("transcript_text", "")
        if not text and task["inputs"].get("transcript_file"):
            with open(task["inputs"]["transcript_file"], "r", encoding="utf-8") as f:
                text = f.read()
        # Stage 0.0
        from src.pipeline.stage0_preprocess import clean_noise_stage
        text = orch.run_stage("0.0", clean_noise_stage, text)
        # Stage 0.2
        from src.pipeline.stage0_preprocess import correct_errors_stage_sync
        text = orch.run_stage("0.2", correct_errors_stage_sync, text)
        # Stage 0.3
        from src.pipeline.stage0_preprocess import generate_summary_sync
        summary = orch.run_stage("0.3", generate_summary_sync, text)
        # Stage 0.4
        from src.chunking.boundary_detector import detect_boundaries
        chunks = orch.run_stage("0.4", detect_boundaries, text)
        # Stage 1
        from src.pipeline.stage1_polish import polish_chunks
        polished = orch.run_stage("1", lambda: asyncio.run(polish_chunks(chunks, summary)))
        # Stage 2
        from src.pipeline.stage2_structure import structure_and_inject
        code_files = _load_code_files(task["inputs"])
        structured = orch.run_stage("2", structure_and_inject, polished, code_files)
        # Post-processing
        from src.utils.toc_generator import insert_toc
        final = insert_toc(structured)
        if task.get("mindmap_enabled", True):
            from src.utils.mindmap import generate_mindmap
            mm = generate_mindmap(final, summary.get("course_title", "课程笔记"))
            if mm:
                final = final + "\n\n" + mm
        orch._save("07_final.md", final)
        update_task(task_id, {"status": "completed", "completed_at": datetime.now().isoformat()})
    except Exception as e:
        update_task(task_id, {"status": "failed", "error": str(e)})
        raise
    finally:
        task_slot_limiter.release()

def _load_code_files(inputs: dict) -> dict[str, str] | None:
    code_dir = inputs.get("code_dir")
    if not code_dir or not os.path.isdir(code_dir):
        return None
    files = {}
    for root, _, fns in os.walk(code_dir):
        for fn in fns:
            if fn.endswith((".py",".java",".js",".ts",".go",".rs",".kt",".swift",".xml",".yaml",".yml",".properties")):
                try:
                    with open(os.path.join(root, fn), "r", encoding="utf-8", errors="ignore") as f:
                        files[fn] = f.read()
                except: pass
    return files if files else None
```

- [ ] **Step 4: Commit**

### Task 16: Streamlit GUI

**Files:**
- Create: `gui/__init__.py`
- Create: `gui/app.py`

- [ ] **Step 1: Write app.py**

```python
import streamlit as st
import asyncio, threading, os
from datetime import datetime
from src.task.task_store import create_task, get_task, list_tasks, update_task, delete_task
from src.task.task_manager import run_task

st.set_page_config(page_title="longtext2md", layout="wide")
st.title("longtext2md - 逐字稿转Markdown笔记")

if "show_detail" not in st.session_state:
    st.session_state.show_detail = None

# Sidebar: New Task
with st.sidebar:
    st.header("+ 新建任务")
    task_name = st.text_input("任务名称 (可选)", placeholder="自动提取")
    transcript_file = st.file_uploader("逐字稿", type=["txt", "md"])
    transcript_text = st.text_area("或粘贴逐字稿", height=150)
    code_dir = st.text_input("代码目录 (可选)")
    mindmap_enabled = st.checkbox("生成思维导图", value=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("创建并开始", use_container_width=True):
            text = transcript_text
            if transcript_file and not text:
                text = transcript_file.getvalue().decode("utf-8")
            if text:
                tid = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                name = task_name or f"任务 {tid[-6:]}"
                create_task(tid, name, {"transcript_text": text, "code_dir": code_dir, "mindmap_enabled": mindmap_enabled})
                threading.Thread(target=lambda: asyncio.run(run_task(tid)), daemon=True).start()
                st.rerun()
            else:
                st.error("请提供逐字稿")

# Main: Task List
st.subheader("任务列表")
tasks = list_tasks()
for task in tasks:
    cols = st.columns([3, 2, 1, 1, 1])
    icon = {"pending": "⚪", "running": "🔵", "completed": "🟢", "failed": "🔴"}.get(task["status"], "⚪")
    cols[0].write(f"{icon} **{task['name']}**")
    cols[1].write(f"{task['status']}")
    if cols[2].button("详情", key=f"d_{task['id']}"):
        st.session_state.show_detail = task["id"]; st.rerun()
    if task["status"] == "completed":
        out = f"output/{task['id']}/07_final.md"
        if os.path.exists(out):
            with open(out, "r", encoding="utf-8") as f:
                cols[3].download_button("下载", f.read(), file_name=f"{task['name']}.md")
    if cols[4].button("删除", key=f"del_{task['id']}"):
        delete_task(task["id"]); st.rerun()

# Detail view
if st.session_state.show_detail:
    task = get_task(st.session_state.show_detail)
    if task:
        st.divider()
        st.subheader(f"{task['name']} - 管道详情")
        st.write(f"逐字稿 | 代码: {task['inputs'].get('code_dir', '无')}")
        for sid, sname in [("0.0","噪音清洗"),("0.2","错别字纠正"),("0.3","全局摘要"),("0.4","边界检测"),("1","并行润色"),("2","结构化")]:
            st.write(f"⚪ {sid} {sname}")
        if st.button("返回"):
            st.session_state.show_detail = None; st.rerun()

st.divider()
st.caption("并行上限: 3 | DeepSeek API")
```

- [ ] **Step 2: Commit**

### Task 17: Integration Test & Final Wiring

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration smoke test**

```python
# tests/test_integration.py
from src.utils.text_utils import clean_noise
from src.chunking.boundary_detector import detect_boundaries
from src.utils.toc_generator import generate_toc, insert_toc
from src.utils.mindmap import generate_mindmap

def test_full_text_pipeline_no_llm():
    text = "那个就是说我们来讲Spring Boot的自动配置。\n\n\n首先创建配置类加上@Configuration注解。\n\n接下来讲条件装配@ConditionalOnClass是核心。\n\n我们写一下代码。\npublic class MyConfig {\n    @Bean\n    public DataSource dataSource() { return new HikariDataSource(); }\n}\n运行一下看看效果。"
    cleaned = clean_noise(text)
    assert "Spring Boot" in cleaned
    assert cleaned.count("\n\n\n") == 0
    chunks = detect_boundaries(cleaned, max_chars=300)
    assert len(chunks) >= 2
    for c in chunks:
        assert len(c) <= 300

def test_toc_and_mindmap():
    md = "# Spring Boot\n## 自动配置\n### @ConditionalOnClass\n条件装配核心注解。\n## 数据库集成\n### MyBatis-Plus配置"
    toc = generate_toc(md)
    assert "自动配置" in toc
    assert "MyBatis-Plus配置" in toc
    mm = generate_mindmap(md, "Spring Boot")
    assert "mindmap" in mm
    assert "自动配置" in mm
    full = insert_toc(md)
    assert "## 目录" in full
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/test_integration.py -v`
Expected: 2 PASS

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete longtext2md implementation - all 17 tasks defined"
```
