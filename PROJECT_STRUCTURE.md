# longtext2md 项目结构完全手册

> 网课视频逐字稿 → 高质量 Markdown 笔记 自动生成系统
> 
> 两阶段流水线：预处理(正则+LLM) → 并行润色 → 全局结构化+代码注入

---

## 目录结构总览

```
longtext2md/
├── .env                          # 所有 API Key 和模型配置
├── requirements.txt              # Python 依赖
├── AGENTS.md                     # 架构设计文档（权威参考）
│
├── src/                          # === 核心源码 ===
│   ├── utils/                    # 基础工具层（零依赖其他模块）
│   │   ├── config.py             # 全局配置（从 .env 读取）
│   │   ├── text_utils.py         # 正则噪音清洗 + 拼音术语纠错字典
│   │   ├── token_counter.py      # tiktoken 封装，精确计算 token 数
│   │   ├── toc_generator.py      # 解析 ##/### 生成可跳转目录
│   │   ├── mindmap.py            # 解析标题树生成 Mermaid mindmap
│   │   ├── prompt_loader.py      # 从 prompts/ 目录加载提示词文件
│   │   ├── suspicious_scanner.py # 扫描高频疑似乱码词（无课件兜底）
│   │   └── logger.py             # 流水线和任务的日志系统
│   │
│   ├── llm/                      # LLM 调用层
│   │   └── client.py             # DeepSeek API 封装（async+sync，3次重试）
│   │
│   ├── chunking/                 # 文本切分层
│   │   └── boundary_detector.py  # 多信号递归话题边界检测
│   │
│   ├── rag/                      # RAG 检索增强层
│   │   ├── glossary.py           # 从代码/课件提取技术术语词典
│   │   ├── indexer.py            # ChromaDB 向量索引构建（SiliconFlow嵌入）
│   │   ├── retriever.py          # 两阶段检索：粗排→reranker精排
│   │   ├── reranker.py           # SiliconFlow bge-reranker API 封装
│   │   └── parsers/              # 文件解析器
│   │       ├── code_parser.py    # 代码文件解析+分块+指纹压缩
│   │       ├── markdown_parser.py# Markdown 课件解析
│   │       └── docx_parser.py    # Word 课件解析
│   │
│   ├── pipeline/                 # 流水线核心（阶段0/1/2）
│   │   ├── orchestrator.py       # DAG 执行引擎：按序跑阶段，落盘checkpoint
│   │   ├── stage0_preprocess.py  # 阶段0：噪音清洗 + 正则纠错 + 全局摘要
│   │   ├── stage1_polish.py      # 阶段1：全并行上下文润色
│   │   └── stage2_structure.py   # 阶段2：全局结构化 + 代码注入
│   │
│   ├── task/                     # 任务管理层（GUI后端）
│   │   ├── task_store.py         # 任务元数据 CRUD（JSON文件）
│   │   ├── task_manager.py       # 任务状态机 + 完整流水线入口
│   │   └── concurrency_limiter.py# Semaphore 并发槽位限制
│   │
│   └── kb/                       # 知识库管理层
│       └── kb_manager.py         # 命名知识库的创建/复用/删除
│
├── gui/                          # === Streamlit 前端 ===
│   └── app.py                    # Web界面：上传文件、管理任务、预览笔记
│
├── prompts/                      # === LLM 提示词模板 ===
│   ├── correct_errors_system.md  # 纠错提示词（当前已改用正则，保留备用）
│   ├── global_summary_system.md  # 全局摘要提示词
│   ├── polish_chunk_system.md    # 润色系统提示词
│   ├── polish_chunk_user.md      # 润色用户提示词模板（含四层上下文占位符）
│   ├── structure_and_inject_system.md  # 结构化系统提示词
│   └── structure_and_inject_user.md    # 结构化用户提示词模板
│
├── tests/                        # === 测试 ===
│   ├── test_text_utils.py        # 噪音清洗测试
│   ├── test_token_counter.py     # token计数测试
│   ├── test_boundary_detector.py # 边界检测测试
│   ├── test_stage0_preprocess.py # 阶段0测试
│   ├── test_toc_generator.py     # 目录生成测试
│   ├── test_mindmap.py           # 思维导图测试
│   ├── test_integration.py       # 无LLM集成冒烟测试
│   └── 测试文本.txt              # 测试用文本
│
├── output/                       # 流水线产物（按任务ID分目录）
├── tasks/                        # 任务状态存储（JSON文件）
├── log/                          # 运行日志
└── kb/                           # 持久化知识库（ChromaDB）
```

---

## 文件详解

### 第一层：基础设施（src/utils/ + src/llm/）

这些文件是项目地基，不依赖任何其他模块，被所有上层代码使用。

#### `.env` — 所有配置的源头
```
DEEPSEEK_API_KEY      # 纠错/润色/结构化 LLM
SILICONFLOW_API_KEY   # 嵌入向量 + 重排序
ECONOMY_MODEL         # 纠错/润色用的便宜模型 (deepseek-v4-flash)
PREMIUM_MODEL         # 结构化用的高端模型 (deepseek-v4-pro)
EMBEDDING_MODEL       # 向量嵌入模型 (BAAI/bge-m3)
RERANKER_MODEL        # 重排序模型 (BAAI/bge-reranker-v2-m3)
MAX_CHUNK_CHARS       # 每块最大字符数 (2000)
ECONOMY_MAX_TOKENS    # 经济档最大输出token (16384)
```

#### `src/utils/config.py` — 全局配置单例
**作用**：从 `.env` 读取所有配置，生成 `config` 全局对象。  
**核心产出**：`config.economy`（LLMProfile）、`config.premium`（LLMProfile）。  
**被引用**：几乎所有文件。

```python
from src.utils.config import config
# config.economy.model → "deepseek-v4-flash"
# config.siliconflow_api_key → "sk-..."
```

#### `src/utils/text_utils.py` — 文本处理工具箱
**两个核心功能**：
1. `clean_noise(text)` — 正则噪音清洗（阶段0.0）：去除填充词、折叠空行、去除行首尾叹词
2. `PINYIN_CORRECTIONS` + `correct_terms_regex(text)` — 拼音术语纠错字典（阶段0.2）：纯字符串替换，零LLM成本

```python
# 示例："斯普瑞布特" → "SpringBoot"
# 150+ 条映射规则覆盖 Java/Python/通用技术术语
```

#### `src/utils/token_counter.py` — Token 计算
**作用**：用 tiktoken 的 `cl100k_base` 编码器精确计算文本 token 数。  
**使用场景**：控制每块输入不超过模型上下文窗口。

#### `src/llm/client.py` — LLM 调用统一入口
**作用**：封装 DeepSeek API 调用，所有 LLM 请求的唯一出口。  
**功能**：
- 根据 `LLMProfile` 自动选择模型和参数
- 内置 3 次指数退避重试
- 同时提供 `chat()` (async) 和 `chat_sync()` (sync)

```python
from src.llm.client import chat
result = await chat(profile=config.economy, system_prompt="...", user_message="...")
```

#### `src/utils/prompt_loader.py` — 提示词加载
**作用**：从 `prompts/` 目录读取 `.md` 提示词文件。一行代码的事，但统一了路径管理。

#### `src/utils/suspicious_scanner.py` — 可疑词扫描
**作用**：当没有课件/代码时（无法构建术语词典），纯程序化扫描逐字稿中的高频疑似乱码片段。  
**举例**：发现"斯普瑞布特"出现 47 次 → 告诉纠错 LLM "这极可能是 SpringBoot"。  
**当前状态**：纠错已改用正则方案，此模块暂时未使用。

#### `src/utils/toc_generator.py` — 目录生成器
**作用**：解析 Markdown 中的 `##`/`###`/`####` 标题，生成可跳转的目录。  
**两个函数**：`generate_toc(md)` 生成目录文本，`insert_toc(md)` 将目录插入到正文开头。

#### `src/utils/mindmap.py` — 思维导图生成
**作用**：解析标题树，输出 Mermaid `mindmap` 格式。

#### `src/utils/logger.py` — 日志系统
**作用**：创建两个日志文件：`log/pipeline_YYYYMMDD.log` 和 `log/task_YYYYMMDD.log`。

---

### 第二层：文本切分（src/chunking/）

#### `src/chunking/boundary_detector.py` — 话题边界检测
**作用**：在语义边界上递归切分文本，每块控制在 ≤2000 字。  
**算法**：
1. 多信号融合打分（章节标记词 5 分、代码切换 3 分、列举结构 2 分、空行 1 分）
2. 在得分最高处切分，递归到所有块 ≤2000 字
3. 最坏情况：无信号时中点强切

**输入**：清洗后的全文  
**输出**：`list[str]` — N 个话题块

---

### 第三层：RAG 检索增强（src/rag/）

#### `src/rag/glossary.py` — 术语词典抽取
**作用**：从代码目录扫描类名、函数名、注解等，构建技术术语词表。  
**当前用途**：术语词典传给正则纠错模块做辅助匹配。

#### `src/rag/parsers/code_parser.py` — 代码解析器
**两个核心功能**：
1. `parse_code_file(path)` — 将代码文件解析为 RAG 切片。超大文件自动按函数/类边界分块（每块 ≤4000 字符）
2. `create_code_fingerprint(code, filename)` — 将完整代码压缩为"指纹"（类名+注解+方法签名，80-150 tokens）

> 指纹压缩是 AGENTS.md 1.3 的核心设计：RAG 检索结果在喂给润色 LLM 前做程序侧压缩，控制每块输入在 2400 tokens 以内。

#### `src/rag/parsers/markdown_parser.py` — Markdown 课件解析
**作用**：将 Markdown 课件按段落切分为 RAG 切片。

#### `src/rag/parsers/docx_parser.py` — Word 课件解析
**作用**：将 `.docx` 课件按段落切分为 RAG 切片。

#### `src/rag/indexer.py` — 向量索引构建
**作用**：将切片列表嵌入为向量并存入 ChromaDB。  
**关键细节**：
- 使用 SiliconFlow 的 `BAAI/bge-m3` 做嵌入（OpenAI 兼容接口，只需改 `api_base`）
- 每次构建先删旧集合再新建（全量重建策略）

#### `src/rag/retriever.py` — 两阶段检索器
**作用**：
1. **粗排**：ChromaDB 向量检索取 `k*3` 条候选
2. **精排**：调用 SiliconFlow `bge-reranker-v2-m3` 重排序
3. **压缩**：代码结果转指纹，课件结果截前 100 字

**输入**：ChromaDB collection + 查询文本  
**输出**：压缩后的参考文本（≤200 tokens）

#### `src/rag/reranker.py` — 重排序客户端
**作用**：封装 SiliconFlow 的 rerank API。同时提供 `rerank()` (async) 和 `rerank_sync()` (sync)。

---

### 第四层：流水线核心（src/pipeline/）

#### `src/pipeline/orchestrator.py` — DAG 执行引擎
**作用**：按序执行各阶段，每个阶段完成后自动落盘 checkpoint。  
**核心方法**：`run_stage(name, fn, *args)` — 执行一个阶段，计时，保存产物，更新状态。  
**产物命名**：
```
0.0 → 00_cleaned.txt      0.2 → 02_corrected.txt
0.3 → 03_summary.json     0.4 → 04_chunks.json
1   → 05_polished.txt     2   → 06_structured.md
后处理 → 07_final.md
```

#### `src/pipeline/stage0_preprocess.py` — 阶段0：预处理
**三个功能**：
1. `clean_noise_stage(text)` — 0.0 噪音清洗（纯正则，零LLM）
2. `correct_errors_stage(text, glossary)` — 0.2 错别字纠正（纯正则替换，零LLM）
3. `generate_summary(text)` — 0.3 课程全局摘要（采样+LLM）

> **为什么纠错不用 LLM？** 经过大量实验发现：chat 模型天然倾向于"整理输出"而非"机械替换"，会严重压缩内容（95%+丢失）。正则方案零内容损失、零成本、零延迟。

#### `src/pipeline/stage1_polish.py` — 阶段1：全并行上下文润色
**作用**：将 N 个话题块同时发给 LLM 润色，每个块拿到四层上下文：
1. 全局摘要（这门课在讲什么）
2. 位置标签（第 X 块 / 共 N 块）
3. 前块结尾 80 字 + 后块开头 60 字
4. RAG 检索到的代码指纹

**并行策略**：`asyncio.gather` + `Semaphore(30)` 控制并发。  
**输入**：N 个话题块 + 全局摘要 + RAG 指纹  
**输出**：N 段润色后文本

#### `src/pipeline/stage2_structure.py` — 阶段2：全局结构化 + 代码注入
**作用**：将润色后的全文 + 全部代码文件，一次性交给大窗口 LLM。  
**任务**：
1. 添加层级标题（## / ### / ####）
2. 在老师讲到代码的位置精确插入代码块
3. 保留"思路→代码→解释"的叙事节奏

**模型**：`deepseek-v4-pro` (thinking 模式)，1M 上下文窗口。

---

### 第五层：任务管理 + GUI（src/task/ + gui/）

#### `src/task/task_store.py` — 任务持久化
**作用**：任务的 JSON 文件 CRUD。每个任务一个 `tasks/{id}.json`。  
**字段**：id, name, status(pending/running/completed/failed), inputs, output_dir, error

#### `src/task/task_manager.py` — 完整流水线入口
**作用**：`run_task(task_id)` 是端到端执行的唯一入口。  
**执行流程**：
```
1. 加载逐字稿
2. 构建术语词典 (0.1)
3. 构建/复用 RAG 索引 (0.5)
4. 加载代码文件
5. 阶段0.0: 噪音清洗
6. 阶段0.2: 正则纠错
7. 阶段0.3: 全局摘要
8. 阶段0.4: 边界检测
9. 阶段1:   并行润色（含RAG指纹）
10. 阶段2:  结构化+代码注入
11. 后处理: TOC + 思维导图
12. 落盘 07_final.md
```

#### `src/task/concurrency_limiter.py` — 并发控制
**作用**：`TaskSlotLimiter` — 基于 `asyncio.Semaphore` 限制同时运行的任务数（默认 3）。

#### `src/kb/kb_manager.py` — 知识库管理
**作用**：命名知识库的 CRUD。创建知识库时会扫描代码/课件目录，构建 ChromaDB 索引并持久化。支持跨任务复用（避免重复嵌入）。

#### `gui/app.py` — Streamlit Web 界面
**功能**：
- 侧边栏：上传逐字稿（文件拖拽或粘贴）+ 参考资料（代码/课件自动分类）+ 文件夹选择
- 主区域：任务列表（状态图标、详情按钮、下载按钮、删除按钮）
- 任务详情：各阶段状态、最终笔记预览
- 知识库管理：创建、列表、删除

---

### 第六层：提示词模板（prompts/）

| 文件 | 对应阶段 | 用途 |
|------|---------|------|
| `correct_errors_system.md` | 0.2 | 纠错提示词（当前暂未使用，纠错已改用正则） |
| `global_summary_system.md` | 0.3 | 让 LLM 从采样文本生成课程概要 JSON |
| `polish_chunk_system.md` | 1 | 润色系统提示词：口语→书面语 |
| `polish_chunk_user.md` | 1 | 润色用户提示词模板（含 `{course_overview}` 等占位符） |
| `structure_and_inject_system.md` | 2 | 结构化系统提示词 |
| `structure_and_inject_user.md` | 2 | 结构化用户提示词模板（含 `{code_files}` 和 `{polished_text}` 占位符） |

---

## 数据流全景

```
┌──────────────────────────────────────────────────────────┐
│                    gui/app.py (Streamlit)                │
│  用户上传逐字稿 + 代码/课件 → 创建任务 → 启动流水线        │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│              src/task/task_manager.py                    │
│  run_task(): 编排全流程，每步调用 orchestrator            │
│                                                        │
│  ① 构建术语词典 (glossary.py)                            │
│  ② 构建 RAG 索引 (indexer.py → ChromaDB)                 │
│  ③ 加载代码文件（供阶段2代码注入用）                       │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│           src/pipeline/orchestrator.py                   │
│  按序执行各阶段，每阶段完自动落盘 checkpoint               │
│                                                        │
│  阶段 0.0 ──→ 00_cleaned.txt                            │
│  阶段 0.2 ──→ 02_corrected.txt                          │
│  阶段 0.3 ──→ 03_summary.json                           │
│  阶段 0.4 ──→ 04_chunks.json                            │
│  阶段 1   ──→ 05_polished.txt (28块并行LLM调用)          │
│  阶段 2   ──→ 06_structured.md (单次大窗口LLM)           │
│  后处理   ──→ 07_final.md (TOC + Mindmap)                │
└──────────────────────────────────────────────────────────┘

阶段0.0: text_utils.clean_noise()           ─ 纯正则
阶段0.2: text_utils.correct_terms_regex()   ─ 纯正则字典
阶段0.3: llm/client.chat()                  ─ LLM调用 (Flash)
阶段0.4: chunking/boundary_detector.py       ─ 纯程序
阶段1:   llm/client.chat() × 28             ─ 并行LLM (Flash)
阶段2:   llm/client.chat() × 1              ─ 单次LLM (Pro)
```

---

## 关键设计决策与经验教训

### 1. 为什么纠错不用 LLM？
经过 5 轮迭代验证：chat 模型（包括 deepseek-v4-flash）天然倾向于"整理输出"而非"机械替换"。无论怎么约束 prompt，模型都会做摘要压缩，导致 95%+ 内容丢失。最终采用纯正则字典方案（`PINYIN_CORRECTIONS`），零成本、零损失。

### 2. 为什么嵌入不用 OpenAI 而用 SiliconFlow？
- 不需要额外申请 OpenAI API Key
- `BAAI/bge-m3` 中文嵌入质量优秀，且支持 8192 token 上下文
- SiliconFlow 提供兼容 OpenAI 的接口，零代码改动
- 同时提供重排序模型 `bge-reranker-v2-m3`，实现两阶段检索

### 3. 为什么代码要"指纹化"？
RAG 检索到的完整代码可达 500-800 tokens。在润色阶段（每块仅 2000 字），如果让 LLM 同时看完整代码+四层上下文+原文，注意力分散，润色质量下降。指纹化压缩到 80-150 tokens，保证 LLM 专注润色任务。

### 4. 为什么阶段2只用一次 LLM 调用？
代码注入需要理解"老师在哪个叙事位置写了哪段代码"，这是全局理解任务。分块做会导致：① 同一段代码被多次插入 ② 叙事节奏被打乱。只有一次性看到全文的 LLM 才能做出正确决策。
