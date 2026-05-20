# longtext2md 项目结构完全手册

> 网课视频逐字稿 → 高质量 Markdown 笔记 自动生成系统
> 
> 两阶段流水线：预处理(正则+LLM纠错) → 并行润色 → 标题生成 → 代码注入
> 版本：v2 (2026-05-20)

---

## 目录结构总览

```
longtext2md/
├── .env                          # 所有 API Key 和模型配置
├── requirements.txt              # Python 依赖
├── AGENTS.md                     # 架构设计文档（权威参考）
├── PROJECT_STRUCTURE.md          # 本文件：项目结构手册
├── filler_words.txt              # 屏蔽词列表（一行一词，支持 # 注释）
│
├── src/                          # === 核心源码 ===
│   ├── utils/                    # 基础工具层（零依赖其他模块）
│   │   ├── config.py             # 全局配置（从 .env 读取）
│   │   ├── text_utils.py         # 纯正则噪音清洗（屏蔽词外部化）
│   │   ├── token_counter.py      # tiktoken 封装，精确计算 token 数
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
│   │   ├── retriever.py          # 两阶段检索：粗排→reranker精排 + 全量切片检索
│   │   ├── reranker.py           # SiliconFlow bge-reranker API 封装
│   │   └── parsers/              # 文件解析器
│   │       ├── code_parser.py    # 代码文件解析+分块+指纹压缩
│   │       ├── markdown_parser.py# Markdown 课件解析
│   │       └── docx_parser.py    # Word 课件解析
│   │
│   ├── pipeline/                 # 流水线核心（阶段0/1/2）
│   │   ├── orchestrator.py       # DAG 执行引擎：按序跑阶段，落盘checkpoint
│   │   ├── stage0_preprocess.py  # 阶段0：噪音清洗 + LLM纠错 + 全局摘要
│   │   ├── stage1_polish.py      # 阶段1：全并行上下文润色
│   │   └── stage2_structure.py   # 阶段2a(标题) + 阶段2b(代码注入)
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
│   ├── correct_errors_system.md  # 0.2 纠错：机械术语替换（正反例约束）
│   ├── global_summary_system.md  # 0.3 全局摘要：输出课程概要 JSON
│   ├── polish_chunk_system.md    # 阶段1 润色：防压缩、保护知识点
│   ├── polish_chunk_user.md      # 阶段1 润色：四层上下文用户模板
│   ├── structure_headers_system.md  # 阶段2a 标题：段落标记法 JSON 输出
│   ├── inject_code_system.md     # 阶段2b 代码注入：铁律防编造
│   ├── structure_and_inject_system.md  # [旧] 结构化系统提示词（v1 遗留）
│   └── structure_and_inject_user.md    # [旧] 结构化用户模板（v1 遗留）
│
├── tests/                        # === 测试 ===
│   ├── test_text_utils.py        # 噪音清洗测试
│   ├── test_token_counter.py     # token计数测试
│   ├── test_boundary_detector.py # 边界检测测试
│   ├── test_stage0_preprocess.py # 阶段0测试
│   ├── test_integration.py       # 无LLM集成冒烟测试
│   └── 测试文本.txt              # 测试用文本
│
├── output/                       # 流水线产物（按任务ID分目录）
├── tasks/                        # 任务状态存储（JSON文件）
├── log/                          # 运行日志
└── kb/                           # 持久化知识库（ChromaDB）
```

---

## 数据流全景（v2）

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
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│           src/pipeline/orchestrator.py                   │
│  按序执行各阶段，每阶段完自动落盘 checkpoint               │
│                                                        │
│  阶段 0.0 ──→ 00_cleaned.txt      纯正则清洗             │
│  阶段 0.2 ──→ 02_corrected.txt    LLM纠错（Flash）       │
│  阶段 0.3 ──→ 03_summary.json     课程全局摘要（Flash）   │
│  阶段 0.4 ──→ 04_chunks.json      递归边界检测            │
│  阶段 1   ──→ 05_polished.txt     全并行润色（Flash×N）   │
│  阶段 2a  ──→ 06a_structured.md   标题生成（Pro）         │
│  阶段 2b  ──→ 07_final.md         代码注入（Pro）         │
└──────────────────────────────────────────────────────────┘

各阶段详解：

阶段0.0: text_utils.clean_noise()                     — 纯正则（filler_words.txt）
阶段0.2: LLM纠错(Flash) × ~8块                         — 8K字分块+200字重叠+术语词典
阶段0.3: LLM摘要(Flash) × 1                           — 采样头尾+每隔10K
阶段0.4: chunking/boundary_detector.py                 — 纯程序多信号递归

阶段1:   LLM润色(Flash) × N块（并行）                   — 四层上下文+代码指纹
阶段2a:  LLM标题(Pro thinking) × 1                     — 段落标记法，只输出JSON计划
阶段2b:  LLM代码注入(Pro thinking) × 1                  — RAG检索top-15代码切片
```

---

## v2 变更记录（相对于 v1）

### 提示词工程全面强化

所有 LLM 调用点都经过重新设计，采用"铁律 + 正反例"模式：

| 调用点 | 核心约束策略 |
|--------|------------|
| 0.2 纠错 | 身份锁定"机械替换工具"，3组正反例，否则越界润色 |
| 阶段1 润色 | 核心原则前置（"违反即失败"），字数预期，2组"渐进讲解反例" |
| 阶段2a 标题 | 段落标记法，LLM只出JSON（~2K tokens），程序做插入 |
| 阶段2b 代码注入 | 7条铁律，编造/篡改反例，分步展示正例 |

### 0.2 纠错：正则 → LLM

- **旧方案**：`PINYIN_CORRECTIONS` 硬编码映射表，无法覆盖语音转写的随机变体
- **新方案**：DeepSeek-V4-Flash 分块纠错，8K字/块 + 200字重叠，利用编程上下文推断正确术语
- **参考信息**：术语词典优先；无课件时用 `suspicious_scanner` 自动检测高频可疑词

### 阶段2：单次调用 → 两步拆分

- **旧方案**：一次 LLM 调用同时加标题+插代码，全部代码文件无差别拼接
- **新方案**：
  - 2a 标题：段落标记法（`[§N]`），LLM 只输出 JSON 标题计划，程序插入。输出从 35K → 2K tokens
  - 2b 代码注入：RAG 检索 top-15 相关代码切片（非完整文件），仅喂相关代码

### 废弃模块

- `src/utils/toc_generator.py` — 目录生成（项目不需要）
- `src/utils/mindmap.py` — 思维导图（功能太简单）
- `src/utils/text_utils.py` 中的 `PINYIN_CORRECTIONS` 字典和 `correct_terms_regex` 函数

### 新增

- `filler_words.txt` — 屏蔽词外部化配置，一行一词，`text_utils.py` 运行时加载
- `prompts/structure_headers_system.md` — 阶段2a 标题生成提示词
- `prompts/inject_code_system.md` — 阶段2b 代码注入提示词
- `src/rag/retriever.py::retrieve_code_slices()` — 全量代码切片检索（供2b使用）
- `src/rag/reranker.py` — SiliconFlow bge-reranker 精排

---

## 关键设计决策

### 1. 为什么 0.2 从正则改回 LLM？

硬编码 `PINYIN_CORRECTIONS` 只能匹配预先列出的音译变体。语音转写本质是概率采样——同一个"SpringBoot"每次可能转写成"斯普瑞布特""斯普润布特""思普瑞不特"等不同变体。LLM 通过编程上下文推断正确术语，无需穷举。

关键在于提示词约束：正例+反例锁死"只做术语替换，不改结构、不去口语"，消除 LLM 的"编辑冲动"。

### 2. 为什么阶段2拆为两步？

标题（宏观结构）和代码注入（微观定位）是不同性质的认知任务。捆在一次调用中互相干扰。拆分后：
- 2a（标题）：LLM 只需理解叙事弧线，输出 JSON 计划，不碰正文
- 2b（代码注入）：RAG 过滤只喂相关代码切片（~3K tokens），而非全量文件（~80K tokens）

### 3. 段落标记法为什么比行号好？

- 行号法：LLM 需精确计数，偏移1行就插错位置
- 标记法：`[§N]` 是程序写入的，解析时绝对精确，JSON 解析失败可回退到无标题原文

### 4. 为什么代码注入用切片而非完整文件？

RAG 索引中的切片是函数/类级别的。一个文件可能有 10 个函数，但正文只讨论了其中 2 个。喂完整文件 = 多喂 80% 的噪声。切片让 LLM 注意力集中在被讨论的代码上。

### 5. 为什么嵌入用 SiliconFlow？

- 无需额外申请 OpenAI API Key
- `BAAI/bge-m3` 中文嵌入质量优秀，8192 token 上下文
- 同平台提供重排序 `bge-reranker-v2-m3`